from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

class ChatMessage(BaseModel):
    id: str
    content: str
    role: Literal["user", "assistant"] 
    timestamp: datetime

class SendMessageRequest(BaseModel):
    content: str
    session_id: Optional[str] = None

class SendMessageResponse(BaseModel):
    message: ChatMessage
    agent_status: str

class WebSocketMessage(BaseModel):
    type: Literal["chat_message", "typing_start", "typing_stop", "agent_response"]
    content: Optional[str] = None
    session_id: Optional[str] = None
    message_id: Optional[str] = None

class AgentStatus(BaseModel):
    status: Literal["ready", "thinking", "offline"]
    name: str
    last_interaction: Optional[datetime] = None