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
    rename_conversation as db_rename_conversation,
    archive_conversation as db_archive_conversation,
    delete_conversation as db_delete_conversation,
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


class ConversationDetail(BaseModel):
    session_id: str
    name: str
    started: str
    turns: List[dict]
    state_snapshot: Optional[dict] = None
    weight: Optional[float] = None


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
    from Nola.services.agent_service import get_agent_service
    return get_agent_service()


@chat_router.get("/history", response_model=List[ChatMessage])
async def get_chat_history(limit: int = 50):
    """Get recent chat history"""
    try:
        agent_service = _get_agent_service()
        history = await agent_service.get_chat_history(limit)
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving chat history: {str(e)}")


@chat_router.post("/message", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    """Send message and get response via HTTP"""
    try:
        if request.model_id:
            os.environ["NOLA_MODEL_NAME"] = request.model_id
        
        agent_service = _get_agent_service()
        response_message = await agent_service.send_message(request.content, request.session_id)
        agent_status_data = await agent_service.get_agent_status()
        
        return SendMessageResponse(
            message=response_message,
            agent_status=agent_status_data.get("status", "ready")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


@chat_router.get("/agent-status", response_model=AgentStatus)
async def get_agent_status():
    """Get agent availability"""
    try:
        agent_service = _get_agent_service()
        status_data = await agent_service.get_agent_status()
        
        return AgentStatus(
            status=status_data.get("status", "ready"),
            name=status_data.get("name", "Nola"),
            last_interaction=status_data.get("last_interaction")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving agent status: {str(e)}")


@chat_router.post("/clear")
async def clear_chat_history():
    """Clear chat history"""
    try:
        agent_service = _get_agent_service()
        agent_service.message_history.clear()
        return {"message": "Chat history cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing history: {str(e)}")


@chat_router.post("/start-session", response_model=SendMessageResponse)
async def start_session():
    """Start a new session with Nola's proactive intro"""
    try:
        agent_service = _get_agent_service()
        await agent_service.clear_history()
        intro_message = await agent_service.get_proactive_intro()
        
        return SendMessageResponse(
            message=intro_message,
            agent_status="ready"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting session: {str(e)}")


# =============================================================================
# Conversation Endpoints
# =============================================================================

NAMING_MODEL = os.getenv("NOLA_NAMING_MODEL", "llama3.2:1b")


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
async def list_conversations_endpoint(limit: int = 50, archived: bool = False):
    """List all saved conversations, newest first."""
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


@convos_router.get("/{session_id}", response_model=ConversationDetail)
async def get_conversation_endpoint(session_id: str):
    """Get full conversation by session ID."""
    convo = get_conversation(session_id)
    
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    increment_conversation_weight(session_id, 0.02)
    
    return ConversationDetail(
        session_id=convo["session_id"],
        name=convo["name"],
        started=convo["started"] or "",
        turns=convo["turns"],
        state_snapshot=convo.get("state_snapshot"),
        weight=convo.get("weight"),
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


@convos_router.post("/new")
async def create_new_conversation():
    """Create a new conversation session."""
    session_id = f"react_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    save_conversation(session_id=session_id)
    return {"session_id": session_id}


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
            "content": "You are Nola, a helpful AI assistant. Be concise, supportive, and clarifying."
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
    
    def __init__(self):
        from typing import Dict
        from fastapi import WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        
    async def connect(self, websocket, client_id: str):
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
            
            from Nola.services.agent_service import get_agent_service
            agent_service = get_agent_service()
            response_message = await agent_service.send_message(content)
            
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
