from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict
import json
import asyncio
from datetime import datetime
from models.chat_models import WebSocketMessage, ChatMessage
from services.agent_service import get_agent_service

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        
    async def connect(self, websocket: WebSocket, client_id: str):
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
                # Connection is broken, remove it
                self.disconnect(client_id)
                
    async def broadcast(self, message: dict):
        for client_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, client_id)
            
    async def handle_message(self, websocket: WebSocket, client_id: str, data: dict):
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
            
    async def handle_chat_message(self, websocket: WebSocket, client_id: str, data: dict):
        """Handle chat message with streaming response"""
        content = data.get("content", "")
        if not content.strip():
            return
            
        try:
            # Send typing indicator
            await self.send_personal_message({
                "type": "agent_typing_start"
            }, client_id)
            
            # Get agent response
            agent_service = get_agent_service()
            response_message = await agent_service.send_message(content)
            
            # Stream the response (simulate streaming for now)
            await self.stream_response(client_id, response_message.content, response_message.id)
            
            # Stop typing indicator
            await self.send_personal_message({
                "type": "agent_typing_stop"
            }, client_id)
            
        except Exception as e:
            print(f"Error in chat message handling: {e}")
            await self.send_personal_message({
                "type": "agent_typing_stop"
            }, client_id)
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
            
            # Small delay for streaming effect
            await asyncio.sleep(0.05)
            
    async def handle_typing_status(self, client_id: str, is_typing: bool):
        """Handle typing status updates"""
        message = {
            "type": "user_typing" if is_typing else "user_typing_stop", 
            "client_id": client_id
        }
        # Broadcast to other clients (if needed for multi-user support)
        for other_client_id, ws in self.active_connections.items():
            if other_client_id != client_id:
                await self.send_personal_message(message, other_client_id)

# Global WebSocket manager instance
websocket_manager = WebSocketManager()