import sys
import os
from datetime import datetime
from typing import Optional, List
from models.chat_models import ChatMessage

# Add demo-integration to Python path
demo_path = os.path.join(os.path.dirname(__file__), "..", "..", "demo-integration")
sys.path.insert(0, demo_path)

try:
    from agent import get_agent
    print(f"✅ Successfully imported Demo agent from {demo_path}")
except ImportError as e:
    print(f"❌ Warning: Demo agent not found at {demo_path}: {e}")
    print("Using mock implementation.")
    get_agent = None

class AgentService:
    def __init__(self):
        self.agent = get_agent() if get_agent else None
        self.context_manager = ContextManager()
        self.message_history: List[ChatMessage] = []
        
    async def send_message(self, user_message: str, session_id: Optional[str] = None) -> ChatMessage:
        """Send message to agent and manage context automatically"""
        
        # Add user message to history
        user_msg = ChatMessage(
            id=f"user_{datetime.now().timestamp()}",
            content=user_message,
            role="user",
            timestamp=datetime.now()
        )
        self.message_history.append(user_msg)
        
        try:
            if self.agent:
                # Context management happens behind the scenes
                await self.context_manager.adjust_context(user_message, self.agent)
                
                # Try primary model first, fallback to available models
                try:
                    response_text = self.agent.generate(user_message, model='gpt-oss:20b-cloud')
                except Exception as e:
                    print(f"Primary model failed, trying fallback: {e}")
                    try:
                        response_text = self.agent.generate(user_message, model='llama3.2:3b')
                    except Exception as e2:
                        print(f"Fallback model failed, trying mistral: {e2}")
                        response_text = self.agent.generate(user_message, model='mistral:7b')
                
                # Log interaction for future context decisions
                await self.context_manager.log_interaction(user_message, response_text)
            else:
                # Mock response when Demo backend not available
                response_text = f"Echo: {user_message}"
                
        except Exception as e:
            print(f"Error generating response: {e}")
            response_text = "Sorry, I encountered an error processing your message."
        
        # Create assistant response
        assistant_msg = ChatMessage(
            id=f"assistant_{datetime.now().timestamp()}",
            content=response_text,
            role="assistant", 
            timestamp=datetime.now()
        )
        self.message_history.append(assistant_msg)
        
        return assistant_msg
        
    async def get_chat_history(self, limit: int = 50) -> List[ChatMessage]:
        """Get recent chat history"""
        return self.message_history[-limit:] if self.message_history else []
        
    async def get_agent_status(self) -> dict:
        """Get simplified agent status"""
        if self.agent:
            try:
                status = self.agent.introspect()
                return {
                    "status": "ready",
                    "name": "Alex",
                    "last_interaction": datetime.now()
                }
            except:
                pass
                
        return {
            "status": "ready", 
            "name": "Alex",
            "last_interaction": None
        }

class ContextManager:
    """Hides all context escalation logic from the React UI"""
    
    def __init__(self):
        self.conversation_history: List[str] = []
        
    async def adjust_context(self, user_message: str, agent):
        """Apply the sophisticated context logic from Demo backend"""
        if not agent or not hasattr(agent, 'set_context_depth'):
            return
            
        try:
            # Keywords from Demo backend logic
            work_keywords = ["project", "deadline", "manager", "team", "work", "job", "meeting"]
            personal_keywords = ["therapy", "jordan", "anxiety", "climbing", "personal", "feel", "emotion"]
            
            user_lower = user_message.lower()
            work_relevant = any(kw in user_lower for kw in work_keywords)
            personal_relevant = any(kw in user_lower for kw in personal_keywords)
            
            if work_relevant:
                if any(word in user_lower for word in ["manager", "team member", "who", "people"]):
                    agent.set_context_depth('work', 3)
                else:
                    agent.set_context_depth('work', 2)
            else:
                # De-escalate if not mentioned for 2+ turns
                if len(self.conversation_history) >= 2:
                    recent_messages = self.conversation_history[-2:]
                    if not any('work' in msg.lower() for msg in recent_messages):
                        agent.set_context_depth('work', 1)
                        
            if personal_relevant:
                if any(word in user_lower for word in ["jordan", "therapy", "climbing", "anxiety"]):
                    agent.set_context_depth('personal', 3)
                else:
                    agent.set_context_depth('personal', 2)
            else:
                # De-escalate personal context
                if len(self.conversation_history) >= 2:
                    recent_messages = self.conversation_history[-2:]
                    if not any('personal' in msg.lower() or any(kw in msg.lower() for kw in personal_keywords) for msg in recent_messages):
                        agent.set_context_depth('personal', 1)
                        
        except Exception as e:
            print(f"Context adjustment error: {e}")
            
    async def log_interaction(self, user_message: str, response: str):
        """Log interaction for context management"""
        self.conversation_history.append(user_message)
        # Keep only last 10 interactions for efficiency
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]

# Global agent instance
_agent_service = None

def get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service