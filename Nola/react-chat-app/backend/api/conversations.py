"""
Conversations API

List, load, and manage saved conversations.
Auto-generates conversation names using a small LLM after first turn.

Now uses SQLite database (via chatschema) instead of JSON files.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import asyncio
import os

# Import database functions
from .chatschema import (
    save_conversation,
    add_turn,
    get_conversation,
    list_conversations as db_list_conversations,
    rename_conversation as db_rename_conversation,
    archive_conversation as db_archive_conversation,
    delete_conversation as db_delete_conversation,
    increment_conversation_weight,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

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
    weight: Optional[float] = None


class ConversationDetail(BaseModel):
    session_id: str
    name: str
    started: str
    turns: List[dict]
    state_snapshot: Optional[dict] = None
    weight: Optional[float] = None


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
        convo = get_conversation(session_id)
        if not convo:
            return
        
        # Only name if no name yet and has at least one turn
        if convo.get("name") and not convo["name"].startswith("Chat "):
            return  # Already has a real name
        
        turns = convo.get("turns", [])
        if not turns:
            return
        
        first_turn = turns[0]
        name = await generate_conversation_name(
            first_turn.get("user", ""),
            first_turn.get("assistant", "")
        )
        
        # Update in database
        db_rename_conversation(session_id, name)
        print(f"📝 Named conversation {session_id}: {name}")
        
    except Exception as e:
        print(f"Auto-naming failed for {session_id}: {e}")


@router.get("", response_model=List[ConversationSummary])
async def list_conversations_endpoint(limit: int = 50, archived: bool = False):
    """List all saved conversations, newest first. Filter by archived status."""
    conversations = db_list_conversations(limit=limit, archived=archived)
    
    return [
        ConversationSummary(
            session_id=c["session_id"],
            name=c["name"],
            started=c["started"] or "",
            turn_count=c["turn_count"],
            last_message=c.get("last_message"),
            preview=c.get("preview"),
            archived=c["archived"],
            weight=c.get("weight"),
        )
        for c in conversations
    ]


@router.get("/{session_id}", response_model=ConversationDetail)
async def get_conversation_endpoint(session_id: str):
    """Get full conversation by session ID."""
    convo = get_conversation(session_id)
    
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Increment weight when user views conversation (shows it's important)
    increment_conversation_weight(session_id, 0.02)
    
    return ConversationDetail(
        session_id=convo["session_id"],
        name=convo["name"],
        started=convo["started"] or "",
        turns=convo["turns"],
        state_snapshot=convo.get("state_snapshot"),
        weight=convo.get("weight"),
    )


@router.post("/{session_id}/rename")
async def rename_conversation(session_id: str, request: RenameRequest):
    """Manually rename a conversation."""
    success = db_rename_conversation(session_id, request.name)
    
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"success": True, "name": request.name}


@router.delete("/{session_id}")
async def delete_conversation(session_id: str):
    """Delete a conversation."""
    success = db_delete_conversation(session_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"success": True, "deleted": session_id}


@router.post("/{session_id}/archive")
async def archive_conversation(session_id: str):
    """Archive a conversation (hide from main list)."""
    success = db_archive_conversation(session_id, archived=True)
    
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"success": True, "archived": True}


@router.post("/{session_id}/unarchive")
async def unarchive_conversation(session_id: str):
    """Unarchive a conversation (restore to main list)."""
    success = db_archive_conversation(session_id, archived=False)
    
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"success": True, "archived": False}


@router.post("/new")
async def create_new_conversation():
    """Create a new conversation session (clears current and starts fresh)."""
    session_id = f"react_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Pre-create in database
    save_conversation(session_id=session_id, started=datetime.now())
    
    return {"session_id": session_id}
