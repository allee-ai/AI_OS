from fastapi import APIRouter, HTTPException
from typing import List
from models.chat_models import ChatMessage, SendMessageRequest, SendMessageResponse, AgentStatus
from services.agent_service import get_agent_service
from datetime import datetime

router = APIRouter(prefix="/api/chat", tags=["chat"])

@router.get("/history", response_model=List[ChatMessage])
async def get_chat_history(limit: int = 50):
    """Get recent chat history"""
    try:
        agent_service = get_agent_service()
        history = await agent_service.get_chat_history(limit)
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving chat history: {str(e)}")

@router.post("/message", response_model=SendMessageResponse) 
async def send_message(request: SendMessageRequest):
    """Send message and get response via HTTP"""
    try:
        agent_service = get_agent_service()
        response_message = await agent_service.send_message(request.content, request.session_id)
        agent_status_data = await agent_service.get_agent_status()
        
        return SendMessageResponse(
            message=response_message,
            agent_status=agent_status_data.get("status", "ready")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

@router.get("/agent/status", response_model=AgentStatus)
async def get_agent_status():
    """Get agent availability"""
    try:
        agent_service = get_agent_service()
        status_data = await agent_service.get_agent_status()
        
        return AgentStatus(
            status=status_data.get("status", "ready"),
            name=status_data.get("name", "Alex"),
            last_interaction=status_data.get("last_interaction")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving agent status: {str(e)}")

@router.post("/clear")
async def clear_chat_history():
    """Clear chat history"""
    try:
        agent_service = get_agent_service()
        agent_service.message_history.clear()
        return {"message": "Chat history cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing history: {str(e)}")