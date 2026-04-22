"""
Chat API - Real-time chat + conversation management
---------------------------------------------------
Combined endpoints for chat interaction and conversation CRUD.

Endpoints:
  Chat:
    GET  /api/chat/history          - Get recent messages
    POST /api/chat/message          - Send message (HTTP)
    GET  /api/chat/agent-status     - Get agent status
    POST /api/chat/clear            - Clear current history
    POST /api/chat/start-session    - Start new session with intro
  
  Conversations:
    GET    /api/conversations             - List conversations
    POST   /api/conversations/new         - Create new conversation
    GET    /api/conversations/{id}        - Get full conversation
    POST   /api/conversations/{id}/rename - Rename conversation
    DELETE /api/conversations/{id}        - Delete conversation
    POST   /api/conversations/{id}/archive   - Archive
    POST   /api/conversations/{id}/unarchive - Unarchive
  
  Ratings:
    POST /api/ratings/rate  - Rate message (thumbs up/down)
    GET  /api/ratings/stats - Get rating statistics
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import asyncio
import json
import os
import sys

# Ensure project root on path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import schema functions
from .schema import (
    save_conversation,
    add_turn,
    get_conversation,
    list_conversations as db_list_conversations,
    search_conversations as db_search_conversations,
    rename_conversation as db_rename_conversation,
    archive_conversation as db_archive_conversation,
    delete_conversation as db_delete_conversation,
    delete_conversations_by_source as db_delete_by_source,
    increment_conversation_weight,
)


# =============================================================================
# Routers
# =============================================================================

router = APIRouter()
chat_router = APIRouter(prefix="/api/chat", tags=["chat"])
convos_router = APIRouter(prefix="/api/conversations", tags=["conversations"])
ratings_router = APIRouter(prefix="/api/ratings", tags=["ratings"])


# =============================================================================
# Pydantic Models
# =============================================================================

# Chat models
class ChatMessage(BaseModel):
    id: Optional[str] = None
    role: str
    content: str
    timestamp: Optional[datetime] = None


class SendMessageRequest(BaseModel):
    content: str
    session_id: Optional[str] = None
    model_id: Optional[str] = None


class SendMessageResponse(BaseModel):
    message: ChatMessage
    agent_status: str
    session_id: Optional[str] = None


class StartSessionResponse(BaseModel):
    messages: List[ChatMessage]
    agent_status: str
    session_id: Optional[str] = None


class AgentStatus(BaseModel):
    status: str
    name: str
    last_interaction: Optional[datetime] = None


# Conversation models
class ConversationSummary(BaseModel):
    session_id: str
    name: str
    started: str
    turn_count: int
    last_message: Optional[str] = None
    preview: Optional[str] = None
    archived: bool = False
    weight: Optional[float] = None
    source: str = "aios"
    summary: Optional[str] = None


class ConversationDetail(BaseModel):
    session_id: str
    name: str
    started: str
    turns: List[dict]
    total_turns: Optional[int] = None
    state_snapshot: Optional[dict] = None
    weight: Optional[float] = None
    summary: Optional[str] = None


class RenameRequest(BaseModel):
    name: str


# Rating models
class RatingRequest(BaseModel):
    message_id: str
    conversation_id: str
    rating: str  # "up" or "down"
    user_message: str
    assistant_message: str
    system_prompt: Optional[str] = None
    reason: Optional[str] = None


class RatingResponse(BaseModel):
    success: bool
    message: str
    finetune_saved: bool = False


# =============================================================================
# Chat Endpoints
# =============================================================================

def _get_agent_service():
    """Lazy import agent service."""
    from agent.services.agent_service import get_agent_service
    return get_agent_service()


@chat_router.get("/history", response_model=List[ChatMessage])
async def get_chat_history(limit: int = 50):
    """Get recent chat history from database for current session"""
    try:
        agent_service = _get_agent_service()
        session_id = agent_service.session_id
        
        # Load from database
        convo = get_conversation(session_id)
        if not convo or not convo.get('turns'):
            return []
        
        messages = []
        for turn in convo['turns'][-limit:]:
            if turn.get('user'):
                messages.append(ChatMessage(
                    id=f"user_{turn['timestamp']}",
                    role='user',
                    content=turn['user'],
                    timestamp=turn['timestamp']
                ))
            if turn.get('assistant'):
                messages.append(ChatMessage(
                    id=f"assistant_{turn['timestamp']}",
                    role='assistant',
                    content=turn['assistant'],
                    timestamp=turn['timestamp']
                ))
        
        return messages
    except Exception as e:
        print(f"Error retrieving chat history: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving chat history")


@chat_router.post("/message", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    """Send message and get response via HTTP"""
    try:
        if request.model_id:
            os.environ["AIOS_MODEL_NAME"] = request.model_id
        
        agent_service = _get_agent_service()
        response_message = await agent_service.send_message(request.content, request.session_id)
        agent_status_data = await agent_service.get_agent_status()

        # agent_service returns its own ChatMessage model class; coerce to this module's model.
        if isinstance(response_message, ChatMessage):
            message_obj = response_message
        elif hasattr(response_message, "model_dump"):
            message_obj = ChatMessage(**response_message.model_dump())
        elif isinstance(response_message, dict):
            message_obj = ChatMessage(**response_message)
        else:
            message_obj = ChatMessage(
                id=getattr(response_message, "id", f"assistant_{datetime.now().timestamp()}"),
                role=getattr(response_message, "role", "assistant"),
                content=getattr(response_message, "content", str(response_message)),
                timestamp=getattr(response_message, "timestamp", datetime.now()),
            )
        
        return SendMessageResponse(
            message=message_obj,
            agent_status=agent_status_data.get("status", "ready")
        )
    except Exception as e:
        print(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail="Error processing message")


@chat_router.get("/agent-status", response_model=AgentStatus)
async def get_agent_status():
    """Get agent availability"""
    try:
        agent_service = _get_agent_service()
        status_data = await agent_service.get_agent_status()
        
        return AgentStatus(
            status=status_data.get("status", "ready"),
            name=status_data.get("name", "Agent"),
            last_interaction=status_data.get("last_interaction")
        )
    except Exception as e:
        print(f"Error retrieving agent status: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving agent status")


@chat_router.post("/clear")
async def clear_chat_history():
    """Clear chat history"""
    try:
        agent_service = _get_agent_service()
        agent_service.message_history.clear()
        return {"message": "Chat history cleared"}
    except Exception as e:
        print(f"Error clearing history: {e}")
        raise HTTPException(status_code=500, detail="Error clearing history")


@chat_router.post("/start-session")
async def start_session():
    """Start a new chat session"""
    try:
        agent_service = _get_agent_service()
        new_session_id = await agent_service.clear_history()
        
        return {"session_id": new_session_id, "status": "ok"}
    except Exception as e:
        print(f"Error starting session: {e}")
        raise HTTPException(status_code=500, detail="Error starting session")


@chat_router.post("/set-session/{session_id}")
async def set_session(session_id: str):
    """Set the current session ID (when loading an existing conversation)"""
    try:
        agent_service = _get_agent_service()
        agent_service.set_session(session_id)
        return {"session_id": session_id, "status": "ok"}
    except Exception as e:
        print(f"Error setting session: {e}")
        raise HTTPException(status_code=500, detail="Error setting session")


# =============================================================================
# Conversation Endpoints
# =============================================================================

NAMING_MODEL = os.getenv("AIOS_NAMING_MODEL", "llama3.2:1b")


def _generate_name_sync(first_user_msg: str, first_assistant_msg: str) -> str:
    """Synchronously generate a conversation name using the configured LLM provider."""
    prompt_text = f"""Generate a short title (3-6 words) for this conversation. Reply with ONLY the title, nothing else.

User: {first_user_msg[:200]}
Assistant: {first_assistant_msg[:200]}

Title:"""
    messages = [{"role": "user", "content": prompt_text}]

    # Role-specific override (AIOS_NAMING_PROVIDER/MODEL/ENDPOINT) with
    # fallback to the global model.  Keeps naming cheap by default.
    from agent.services.role_model import resolve_role
    cfg = resolve_role("NAMING")
    provider = cfg.provider

    try:
        if provider == "openai":
            import urllib.request, json as _json
            api_key = cfg.api_key or os.getenv("OPENAI_API_KEY", "")
            base_url = (cfg.endpoint or "").rstrip("/") or "https://api.openai.com/v1"
            model = cfg.model or os.getenv("AIOS_NAMING_MODEL", "gpt-4o-mini")
            payload = {"model": model, "messages": messages, "max_tokens": 30}
            req = urllib.request.Request(
                f"{base_url}/chat/completions",
                data=_json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = _json.loads(resp.read().decode("utf-8"))
                name = body.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        elif provider == "http":
            import urllib.request, json as _json
            endpoint = cfg.endpoint or os.getenv("AIOS_MODEL_ENDPOINT", "")
            req = urllib.request.Request(
                endpoint,
                data=_json.dumps({"messages": messages}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = _json.loads(resp.read().decode("utf-8"))
                name = (body.get("message") or body.get("content") or "").strip()
        else:
            # ollama (default)
            import ollama
            model = cfg.model or NAMING_MODEL
            response = ollama.generate(model=model, prompt=prompt_text)
            name = response.get('response', '').strip()

        name = name.strip('"\'')
        name = name[:50] if len(name) > 50 else name
        return name if name else "New Conversation"

    except Exception as e:
        print(f"Name generation failed: {e}")
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
        
        if convo.get("name") and not convo["name"].startswith("Chat "):
            return
        
        turns = convo.get("turns", [])
        if not turns:
            return
        
        first_turn = turns[0]
        name = await generate_conversation_name(
            first_turn.get("user", ""),
            first_turn.get("assistant", "")
        )
        
        db_rename_conversation(session_id, name)
        print(f"📝 Named conversation {session_id}: {name}")
        
    except Exception as e:
        print(f"Auto-naming failed for {session_id}: {e}")


@convos_router.get("", response_model=List[ConversationSummary])
async def list_conversations_endpoint(limit: int = 500, archived: bool = False, search: Optional[str] = None):
    """List all saved conversations, newest first. Optionally filter by search query."""
    if search:
        conversations = db_search_conversations(query=search, limit=limit, archived=archived)
    else:
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
            source=c.get("source", "aios"),
            summary=c.get("summary"),
        )
        for c in conversations
    ]


@convos_router.get("/{session_id}", response_model=ConversationDetail)
async def get_conversation_endpoint(session_id: str, limit: Optional[int] = None, offset: Optional[int] = None):
    """Get conversation by session ID, optionally paginated."""
    convo = get_conversation(session_id, limit=limit, offset=offset)
    
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    increment_conversation_weight(session_id, 0.02)
    
    return ConversationDetail(
        session_id=convo["session_id"],
        name=convo["name"],
        started=convo["started"] or "",
        turns=convo["turns"],
        total_turns=convo.get("total_turns"),
        state_snapshot=convo.get("state_snapshot"),
        weight=convo.get("weight"),
        summary=convo.get("summary"),
    )


@convos_router.post("/{session_id}/rename")
async def rename_conversation(session_id: str, request: RenameRequest):
    """Manually rename a conversation."""
    success = db_rename_conversation(session_id, request.name)
    
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"success": True, "name": request.name}


@convos_router.delete("/{session_id}")
async def delete_conversation(session_id: str):
    """Delete a conversation."""
    success = db_delete_conversation(session_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"success": True, "deleted": session_id}


@convos_router.delete("/source/{source}")
async def delete_by_source(source: str):
    """Delete all conversations from a specific source (chatgpt, claude, gemini, copilot)."""
    valid_sources = {"chatgpt", "claude", "gemini", "copilot", "aios"}
    if source not in valid_sources:
        raise HTTPException(status_code=400, detail=f"Invalid source: {source}. Valid: {', '.join(valid_sources)}")
    
    deleted = db_delete_by_source(source)
    return {"success": True, "source": source, "deleted_count": deleted}


@convos_router.post("/{session_id}/archive")
async def archive_conversation(session_id: str):
    """Archive a conversation."""
    success = db_archive_conversation(session_id, archived=True)
    
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"success": True, "archived": True}


@convos_router.post("/{session_id}/unarchive")
async def unarchive_conversation(session_id: str):
    """Unarchive a conversation."""
    success = db_archive_conversation(session_id, archived=False)
    
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"success": True, "archived": False}


@convos_router.post("/{session_id}/summarize")
async def summarize_conversation_endpoint(session_id: str):
    """Summarize a conversation using the LLM."""
    convo = get_conversation(session_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    from workspace.summarizer import summarize_conversation
    import asyncio
    loop = asyncio.get_event_loop()
    summary = await loop.run_in_executor(None, summarize_conversation, session_id)
    
    if not summary:
        raise HTTPException(status_code=500, detail="Summarization failed")
    
    return {"success": True, "session_id": session_id, "summary": summary}


@convos_router.get("/summary/prompt")
async def get_convo_summary_prompt_endpoint():
    """Get the current conversation summarizer prompt."""
    from workspace.summarizer import get_convo_summary_prompt
    return {"prompt": get_convo_summary_prompt()}


@convos_router.put("/summary/prompt")
async def set_convo_summary_prompt_endpoint(request: dict):
    """Update the conversation summarizer prompt."""
    from workspace.summarizer import set_convo_summary_prompt
    prompt = request.get("prompt", "")
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt required")
    success = set_convo_summary_prompt(prompt)
    return {"success": success}


@convos_router.post("/new")
async def create_new_conversation():
    """Create a new conversation session."""
    session_id = f"react_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    save_conversation(session_id=session_id)
    return {"session_id": session_id}


@convos_router.get("/{session_id}/export")
async def export_conversation(session_id: str):
    """Export a single conversation as JSON."""
    from fastapi.responses import JSONResponse
    
    convo = get_conversation(session_id)
    
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Format for export
    export_data = {
        "version": "1.0",
        "platform": "AI_OS",
        "exported_at": datetime.now().isoformat(),
        "conversation": {
            "session_id": convo["session_id"],
            "name": convo["name"],
            "started": convo["started"],
            "turns": convo["turns"],
            "turn_count": len(convo["turns"]),
            "state_snapshot": convo.get("state_snapshot")
        }
    }
    
    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f"attachment; filename=conversation_{session_id}.json"
        }
    )


@convos_router.get("/export/all")
async def export_all_conversations(archived: bool = False):
    """Export all conversations as a single JSON file."""
    from fastapi.responses import JSONResponse
    
    conversations = db_list_conversations(limit=1000, archived=archived)
    
    export_data = {
        "version": "1.0",
        "platform": "AI_OS",
        "exported_at": datetime.now().isoformat(),
        "conversations": []
    }
    
    for conv_summary in conversations:
        convo = get_conversation(conv_summary["session_id"])
        if convo:
            export_data["conversations"].append({
                "session_id": convo["session_id"],
                "name": convo["name"],
                "started": convo["started"],
                "turns": convo["turns"],
                "turn_count": len(convo["turns"]),
                "state_snapshot": convo.get("state_snapshot")
            })
    
    filename = f"ai_os_conversations_{'archived' if archived else 'active'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


# =============================================================================
# Rating Endpoints
# =============================================================================

FINETUNE_DIR = project_root / "finetune"
FINETUNE_DIR.mkdir(parents=True, exist_ok=True)
USER_APPROVED_FILE = FINETUNE_DIR / "user_approved.jsonl"
NEGATIVE_FEEDBACK_FILE = FINETUNE_DIR / "negative_feedback.jsonl"


def create_finetune_example(
    user_message: str,
    assistant_message: str,
    system_prompt: Optional[str] = None
) -> dict:
    """Create a fine-tuning example in the OpenAI/Ollama format."""
    messages = []
    
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    else:
        messages.append({
            "role": "system",
            "content": "You are an AI assistant, a helpful AI assistant. Be concise, supportive, and clarifying."
        })
    
    messages.append({"role": "user", "content": user_message})
    messages.append({"role": "assistant", "content": assistant_message})
    
    return {"messages": messages}


@ratings_router.post("/rate", response_model=RatingResponse)
async def rate_message(request: RatingRequest):
    """Rate a message thumbs up/down. Thumbs up saves as fine-tuning example."""
    if request.rating not in ["up", "down"]:
        raise HTTPException(status_code=400, detail="Rating must be 'up' or 'down'")
    
    finetune_saved = False
    
    if request.rating == "up":
        example = create_finetune_example(
            user_message=request.user_message,
            assistant_message=request.assistant_message,
            system_prompt=request.system_prompt
        )
        
        example["_meta"] = {
            "message_id": request.message_id,
            "conversation_id": request.conversation_id,
            "rated_at": datetime.utcnow().isoformat(),
            "source": "user_approved"
        }
        
        with open(USER_APPROVED_FILE, "a") as f:
            f.write(json.dumps(example) + "\n")
        
        finetune_saved = True
        message = "Response saved as training example"
    else:
        feedback = {
            "message_id": request.message_id,
            "conversation_id": request.conversation_id,
            "user_message": request.user_message,
            "assistant_message": request.assistant_message,
            "reason": request.reason or "",
            "rated_at": datetime.utcnow().isoformat()
        }
        
        with open(NEGATIVE_FEEDBACK_FILE, "a") as f:
            f.write(json.dumps(feedback) + "\n")
        
        # Mirror thumbs-down into the shared meta-thought bus so the
        # model reads it next turn as a weight=1.0 user correction.
        # Best-effort: a failure here must never break the rate endpoint.
        try:
            import os as _os
            if _os.getenv("AIOS_HUMAN_META", "1") == "1":
                from agent.threads.reflex.schema import add_meta_thought
                reason_txt = (request.reason or "").strip()
                if reason_txt:
                    content = reason_txt[:500]
                else:
                    # Even reason-less thumbs-down carries signal: the
                    # FACT of rejection at weight=1.0.
                    preview = (request.assistant_message or "")[:160].replace("\n", " ")
                    content = f"[user rejected assistant turn] {preview}"
                add_meta_thought(
                    kind="rejected",
                    content=content,
                    source="user_correction",
                    weight=1.0,
                    confidence=1.0,
                    session_id=request.conversation_id,
                )
        except Exception:
            pass
        
        message = "Feedback recorded - thank you!"
    
    return RatingResponse(
        success=True,
        message=message,
        finetune_saved=finetune_saved
    )


@ratings_router.get("/stats")
async def get_rating_stats():
    """Get statistics about rated messages."""
    approved_count = 0
    if USER_APPROVED_FILE.exists():
        with open(USER_APPROVED_FILE, "r") as f:
            for line in f:
                if line.strip():
                    approved_count += 1
    
    negative_count = 0
    if NEGATIVE_FEEDBACK_FILE.exists():
        with open(NEGATIVE_FEEDBACK_FILE, "r") as f:
            for line in f:
                if line.strip():
                    negative_count += 1
    
    return {
        "total_approved": approved_count,
        "total_negative": negative_count,
        "approved_file": str(USER_APPROVED_FILE),
        "negative_file": str(NEGATIVE_FEEDBACK_FILE)
    }


# =============================================================================
# WebSocket Manager
# =============================================================================

class WebSocketManager:
    """Manage WebSocket connections for real-time chat."""
    
    MAX_CONNECTIONS = 50

    def __init__(self):
        from typing import Dict
        from fastapi import WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        
    async def connect(self, websocket, client_id: str):
        if len(self.active_connections) >= self.MAX_CONNECTIONS:
            await websocket.close(code=1013, reason="Too many connections")
            return
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"WebSocket client {client_id} connected")
        
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            print(f"WebSocket client {client_id} disconnected")
            
    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(message))
            except:
                self.disconnect(client_id)
                
    async def broadcast(self, message: dict):
        for client_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, client_id)
            
    async def handle_message(self, websocket, client_id: str, data: dict):
        """Handle incoming WebSocket messages"""
        try:
            message_type = data.get("type")
            
            if message_type == "chat_message":
                await self.handle_chat_message(websocket, client_id, data)
            elif message_type == "typing_start":
                await self.handle_typing_status(client_id, True)
            elif message_type == "typing_stop":
                await self.handle_typing_status(client_id, False)
            elif message_type == "ping":
                await self.send_personal_message({"type": "pong"}, client_id)
                
        except Exception as e:
            print(f"Error handling WebSocket message: {e}")
            await self.send_personal_message({
                "type": "error",
                "content": "Error processing your message"
            }, client_id)
            
    async def handle_chat_message(self, websocket, client_id: str, data: dict):
        """Handle chat message with streaming response"""
        content = data.get("content", "")
        if not content.strip():
            return
            
        try:
            await self.send_personal_message({"type": "agent_typing_start"}, client_id)
            
            # Build a callback that pushes tool events over the WebSocket
            async def _tool_event(event: dict):
                await self.send_personal_message({
                    "type": f"tool_{event.get('status', 'info')}",
                    **event
                }, client_id)

            # Wrap async callback for sync agent.generate() call
            import asyncio
            loop = asyncio.get_event_loop()
            def on_tool_event(event: dict):
                asyncio.run_coroutine_threadsafe(_tool_event(event), loop)

            from agent.services.agent_service import get_agent_service
            agent_service = get_agent_service()
            response_message = await agent_service.send_message(
                content, on_tool_event=on_tool_event,
                provider_override=data.get("provider"),
                model_override=data.get("model"),
                endpoint_override=data.get("endpoint"),
            )
            
            await self.stream_response(client_id, response_message.content, response_message.id)
            await self.send_personal_message({"type": "agent_typing_stop"}, client_id)
            
        except Exception as e:
            print(f"Error in chat message handling: {e}")
            await self.send_personal_message({"type": "agent_typing_stop"}, client_id)
            await self.send_personal_message({
                "type": "error",
                "content": "Sorry, I encountered an error processing your message."
            }, client_id)
            
    async def stream_response(self, client_id: str, full_response: str, message_id: str):
        """Stream response word by word"""
        words = full_response.split()
        current_content = ""
        
        for i, word in enumerate(words):
            current_content += word + " "
            
            await self.send_personal_message({
                "type": "agent_response_chunk",
                "content": current_content.strip(),
                "message_id": message_id,
                "is_final": i == len(words) - 1
            }, client_id)
            
            await asyncio.sleep(0.05)
            
    async def handle_typing_status(self, client_id: str, is_typing: bool):
        """Handle typing status updates"""
        message = {
            "type": "user_typing" if is_typing else "user_typing_stop", 
            "client_id": client_id
        }
        for other_client_id in list(self.active_connections.keys()):
            if other_client_id != client_id:
                await self.send_personal_message(message, other_client_id)


# Global WebSocket manager instance
websocket_manager = WebSocketManager()


# =============================================================================
# Combine all routers
# =============================================================================

router.include_router(chat_router)
router.include_router(convos_router)
router.include_router(ratings_router)
