"""
Conversations API

List, load, and manage saved conversations.
Auto-generates conversation names using a small LLM after first turn.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
from datetime import datetime
import json
import asyncio
import os

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

# Path to conversations (same as agent_service)
CONVERSATIONS_PATH = Path(__file__).resolve().parents[4] / "Nola" / "Stimuli" / "conversations"

# Small model for naming - fast background task
NAMING_MODEL = os.getenv("NOLA_NAMING_MODEL", "llama3.2:1b")


class ConversationSummary(BaseModel):
    session_id: str
    name: str
    started: str
    turn_count: int
    last_message: Optional[str] = None
    preview: Optional[str] = None
    archived: bool = False


class ConversationDetail(BaseModel):
    session_id: str
    name: str
    started: str
    turns: List[dict]
    state_snapshot: Optional[dict] = None


class RenameRequest(BaseModel):
    name: str


def _generate_name_sync(first_user_msg: str, first_assistant_msg: str) -> str:
    """Synchronously generate a conversation name using LLM."""
    try:
        import ollama
        
        prompt = f"""Generate a short title (3-6 words) for this conversation. Reply with ONLY the title, nothing else.

User: {first_user_msg[:200]}
Assistant: {first_assistant_msg[:200]}

Title:"""
        
        response = ollama.generate(model=NAMING_MODEL, prompt=prompt)
        name = response.get('response', '').strip()
        
        # Clean up - remove quotes, limit length
        name = name.strip('"\'')
        name = name[:50] if len(name) > 50 else name
        
        return name if name else "New Conversation"
        
    except Exception as e:
        print(f"Name generation failed: {e}")
        # Fallback: use first few words of user message
        words = first_user_msg.split()[:4]
        return " ".join(words) + "..." if words else "New Conversation"


async def generate_conversation_name(first_user_msg: str, first_assistant_msg: str) -> str:
    """Generate a conversation name in background."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _generate_name_sync, first_user_msg, first_assistant_msg)


async def auto_name_conversation(session_id: str):
    """Background task to name a conversation after first turn."""
    try:
        convo_file = CONVERSATIONS_PATH / f"{session_id}.json"
        if not convo_file.exists():
            return
        
        with open(convo_file) as f:
            data = json.load(f)
        
        # Only name if no name yet and has at least one turn
        if data.get("name") or not data.get("turns"):
            return
        
        first_turn = data["turns"][0]
        name = await generate_conversation_name(
            first_turn.get("user", ""),
            first_turn.get("assistant", "")
        )
        
        # Update file with name
        data["name"] = name
        with open(convo_file, "w") as f:
            json.dump(data, f, indent=2)
        
        print(f"📝 Named conversation {session_id}: {name}")
        
    except Exception as e:
        print(f"Auto-naming failed for {session_id}: {e}")


def _get_conversation_preview(data: dict) -> str:
    """Get a preview of the conversation."""
    turns = data.get("turns", [])
    if not turns:
        return ""
    
    first_msg = turns[0].get("user", "")
    return first_msg[:100] + "..." if len(first_msg) > 100 else first_msg


def _get_conversation_name(data: dict, session_id: str) -> str:
    """Get conversation name, with fallback."""
    if data.get("name"):
        return data["name"]
    
    # Fallback: use timestamp from session_id
    try:
        # Format: react_20260109_123456
        parts = session_id.split("_")
        if len(parts) >= 2:
            date_str = parts[1]
            return f"Chat from {date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    except:
        pass
    
    return "Unnamed Conversation"


@router.get("", response_model=List[ConversationSummary])
async def list_conversations(limit: int = 50, archived: bool = False):
    """List all saved conversations, newest first. Filter by archived status."""
    conversations = []
    
    if not CONVERSATIONS_PATH.exists():
        return []
    
    # Get all conversation files
    files = list(CONVERSATIONS_PATH.glob("*.json"))
    
    # Sort by modification time, newest first
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    
    for file in files[:limit * 2]:  # Read more to account for filtering
        try:
            with open(file) as f:
                data = json.load(f)
            
            # Filter by archived status
            is_archived = data.get("archived", False)
            if is_archived != archived:
                continue
            
            session_id = data.get("session_id", file.stem)
            turns = data.get("turns", [])
            
            conversations.append(ConversationSummary(
                session_id=session_id,
                name=_get_conversation_name(data, session_id),
                started=data.get("started", ""),
                turn_count=len(turns),
                last_message=turns[-1].get("assistant", "")[:100] if turns else None,
                preview=_get_conversation_preview(data),
                archived=is_archived
            ))
            
            if len(conversations) >= limit:
                break
                
        except Exception as e:
            print(f"Error loading {file}: {e}")
            continue
    
    return conversations


@router.get("/{session_id}", response_model=ConversationDetail)
async def get_conversation(session_id: str):
    """Get full conversation by session ID."""
    convo_file = CONVERSATIONS_PATH / f"{session_id}.json"
    
    if not convo_file.exists():
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    with open(convo_file) as f:
        data = json.load(f)
    
    return ConversationDetail(
        session_id=session_id,
        name=_get_conversation_name(data, session_id),
        started=data.get("started", ""),
        turns=data.get("turns", []),
        state_snapshot=data.get("state_snapshot")
    )


@router.post("/{session_id}/rename")
async def rename_conversation(session_id: str, request: RenameRequest):
    """Manually rename a conversation."""
    convo_file = CONVERSATIONS_PATH / f"{session_id}.json"
    
    if not convo_file.exists():
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    with open(convo_file) as f:
        data = json.load(f)
    
    data["name"] = request.name
    
    with open(convo_file, "w") as f:
        json.dump(data, f, indent=2)
    
    return {"success": True, "name": request.name}


@router.delete("/{session_id}")
async def delete_conversation(session_id: str):
    """Delete a conversation."""
    convo_file = CONVERSATIONS_PATH / f"{session_id}.json"
    
    if not convo_file.exists():
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    convo_file.unlink()
    
    return {"success": True, "deleted": session_id}


@router.post("/{session_id}/archive")
async def archive_conversation(session_id: str):
    """Archive a conversation (hide from main list)."""
    convo_file = CONVERSATIONS_PATH / f"{session_id}.json"
    
    if not convo_file.exists():
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    with open(convo_file) as f:
        data = json.load(f)
    
    data["archived"] = True
    
    with open(convo_file, "w") as f:
        json.dump(data, f, indent=2)
    
    return {"success": True, "archived": True}


@router.post("/{session_id}/unarchive")
async def unarchive_conversation(session_id: str):
    """Unarchive a conversation (restore to main list)."""
    convo_file = CONVERSATIONS_PATH / f"{session_id}.json"
    
    if not convo_file.exists():
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    with open(convo_file) as f:
        data = json.load(f)
    
    data["archived"] = False
    
    with open(convo_file, "w") as f:
        json.dump(data, f, indent=2)
    
    return {"success": True, "archived": False}


@router.post("/new")
async def create_new_conversation():
    """Create a new conversation session (clears current and starts fresh)."""
    session_id = f"react_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    return {"session_id": session_id}
