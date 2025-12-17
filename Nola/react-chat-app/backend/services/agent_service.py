"""
Nola Agent Service - React Chat as Stimuli Channel

This module connects the React frontend to Nola's hierarchical state system.
The UI never sees context levels - it just sends messages and receives responses.
All HEA (Hierarchical Experiential Attention) logic runs here.
"""

import sys
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from models.chat_models import ChatMessage

# Add Nola to Python path (repo-relative)
nola_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "Nola")
sys.path.insert(0, nola_path)

# Also need Nola's parent for relative imports within Nola
nola_parent = os.path.dirname(nola_path)
if nola_parent not in sys.path:
    sys.path.insert(0, nola_parent)

try:
    from agent import get_agent
    print(f"✅ Successfully imported Nola agent from {nola_path}")
    NOLA_AVAILABLE = True
except ImportError as e:
    print(f"❌ Warning: Nola agent not found at {nola_path}: {e}")
    print("Using mock implementation.")
    get_agent = None
    NOLA_AVAILABLE = False

# Conversation storage path (Stimuli channel)
CONVERSATIONS_PATH = Path(nola_path) / "Stimuli" / "conversations"


class AgentService:
    """
    Service layer connecting React UI to Nola.
    
    Responsibilities:
    - Route messages through Nola's generate()
    - Manage context levels via stimuli_type
    - Store conversations in Stimuli/conversations/
    - Hide all HEA complexity from the frontend
    """
    
    def __init__(self):
        self.agent = get_agent() if get_agent else None
        self.context_manager = ContextManager()
        self.message_history: List[ChatMessage] = []
        self.session_id = f"react_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Ensure conversations directory exists
        CONVERSATIONS_PATH.mkdir(parents=True, exist_ok=True)
        
        if self.agent:
            print(f"🧠 Nola agent initialized: {self.agent.name}")
            print(f"📁 Conversations will be stored in: {CONVERSATIONS_PATH}")
        
    async def send_message(self, user_message: str, session_id: Optional[str] = None) -> ChatMessage:
        """Send message to Nola and manage context automatically"""
        
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
                # Determine stimuli type based on message analysis
                stimuli_type = await self.context_manager.classify_stimuli(user_message)
                
                # Build conversation context from recent history
                convo_context = self._build_conversation_context()
                
                # Generate response through Nola's HEA system
                response_text = self.agent.generate(
                    user_input=user_message,
                    convo=convo_context,
                    stimuli_type=stimuli_type
                )
                
                # Log interaction for context tracking and persistence
                await self.context_manager.log_interaction(
                    user_message, 
                    response_text,
                    stimuli_type
                )
                
                # Persist to Stimuli/conversations/
                await self._save_conversation_turn(user_message, response_text, stimuli_type)
                
            else:
                # Mock response when Nola not available
                response_text = f"[Nola offline] Echo: {user_message}"
                
        except Exception as e:
            print(f"Error generating response: {e}")
            import traceback
            traceback.print_exc()
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
    
    def _build_conversation_context(self, max_turns: int = 5) -> str:
        """Build conversation context string from recent history"""
        if len(self.message_history) < 2:
            return ""
        
        recent = self.message_history[-(max_turns * 2):]  # Last N turns (user + assistant)
        context_parts = []
        
        for msg in recent[:-1]:  # Exclude the current message
            role = "User" if msg.role == "user" else "Nola"
            context_parts.append(f"{role}: {msg.content}")
        
        return "\n".join(context_parts)
    
    async def _save_conversation_turn(self, user_msg: str, assistant_msg: str, stimuli_type: str):
        """Persist conversation to Stimuli/conversations/ for Nola's memory"""
        try:
            convo_file = CONVERSATIONS_PATH / f"{self.session_id}.json"
            
            # Load existing or create new
            if convo_file.exists():
                with open(convo_file) as f:
                    convo_data = json.load(f)
            else:
                convo_data = {
                    "session_id": self.session_id,
                    "channel": "react-chat",
                    "started": datetime.now().isoformat(),
                    "turns": []
                }
            
            # Add turn
            convo_data["turns"].append({
                "timestamp": datetime.now().isoformat(),
                "user": user_msg,
                "assistant": assistant_msg,
                "stimuli_type": stimuli_type,
                "context_level": self.context_manager.current_level
            })
            convo_data["last_updated"] = datetime.now().isoformat()
            
            # Save
            with open(convo_file, "w") as f:
                json.dump(convo_data, f, indent=2)
                
        except Exception as e:
            print(f"Warning: Could not save conversation: {e}")
        
    async def get_chat_history(self, limit: int = 50) -> List[ChatMessage]:
        """Get recent chat history"""
        return self.message_history[-limit:] if self.message_history else []
        
    async def get_agent_status(self) -> dict:
        """Get Nola's current status"""
        if self.agent:
            try:
                status = self.agent.introspect()
                return {
                    "status": "ready",
                    "name": self.agent.name,
                    "context_level": self.context_manager.current_level,
                    "session_id": self.session_id,
                    "turns": len(self.message_history) // 2,
                    "last_interaction": datetime.now(),
                    "sections": status.get("sections", [])
                }
            except Exception as e:
                print(f"Introspect error: {e}")
                
        return {
            "status": "offline", 
            "name": "Nola",
            "context_level": 1,
            "last_interaction": None
        }
    
    async def clear_history(self):
        """Clear conversation history and start fresh session"""
        self.message_history = []
        self.context_manager.reset()
        self.session_id = f"react_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


class ContextManager:
    """
    Hierarchical Experiential Attention (HEA) Controller
    
    Maps user messages to appropriate context levels using stimuli classification.
    This is the "attention head" that decides how much context Nola needs.
    
    Stimuli Types → Context Levels:
    - "realtime" → L1 (~10 tokens) - Quick responses, greetings
    - "conversational" → L2 (~50 tokens) - Default, moderate context
    - "analytical" → L3 (~200 tokens) - Deep analysis, reflection
    """
    
    def __init__(self):
        self.conversation_history: List[dict] = []
        self.current_level = 2  # Default to L2
        self.turns_at_level = 0
        
    def reset(self):
        """Reset context state for new session"""
        self.conversation_history = []
        self.current_level = 2
        self.turns_at_level = 0
        
    async def classify_stimuli(self, user_message: str) -> str:
        """
        Classify message into stimuli type for Nola's context system.
        
        Returns: "realtime", "conversational", or "analytical"
        """
        msg_lower = user_message.lower().strip()
        
        # L1 triggers: Casual, quick, greetings
        l1_exact = ["hi", "hello", "hey", "thanks", "bye", "ok", "sure", "yes", "no", "yep", "nope"]
        l1_patterns = ["good morning", "good night", "what time", "tell me a joke"]
        
        if msg_lower in l1_exact or any(p in msg_lower for p in l1_patterns):
            return self._transition_level(1, "realtime")
        
        # L3 triggers: Analytical, reflective, deep
        l3_triggers = [
            "analyze", "explain why", "help me understand", "reflect on",
            "what have i", "pattern", "history", "tell me about my",
            "why do i always", "what's my", "summarize my"
        ]
        
        if any(t in msg_lower for t in l3_triggers):
            return self._transition_level(3, "analytical")
        
        # L2: Default for substantive conversation
        # Also escalate to L2 if emotional content detected
        emotional_triggers = ["stressed", "anxious", "worried", "frustrated", "happy", "excited"]
        if any(t in msg_lower for t in emotional_triggers):
            return self._transition_level(2, "conversational")
        
        # Check for de-escalation opportunity
        # If we've been at L3 for 3+ turns without analytical queries, drop to L2
        if self.current_level == 3 and self.turns_at_level >= 3:
            return self._transition_level(2, "conversational")
        
        # Stay at current level for normal messages
        return self._current_stimuli_type()
    
    def _transition_level(self, new_level: int, stimuli_type: str) -> str:
        """Handle level transition with logging"""
        if new_level != self.current_level:
            direction = "⬆️" if new_level > self.current_level else "⬇️"
            print(f"🧠 {direction} Context: L{self.current_level} → L{new_level} ({stimuli_type})")
            self.current_level = new_level
            self.turns_at_level = 0
        else:
            self.turns_at_level += 1
        return stimuli_type
    
    def _current_stimuli_type(self) -> str:
        """Map current level to stimuli type"""
        return {1: "realtime", 2: "conversational", 3: "analytical"}.get(self.current_level, "conversational")
        
    async def log_interaction(self, user_message: str, response: str, stimuli_type: str):
        """Log interaction for context tracking"""
        self.conversation_history.append({
            "timestamp": datetime.now().isoformat(),
            "user": user_message,
            "response": response,
            "stimuli_type": stimuli_type,
            "level": self.current_level
        })
        
        # Keep only last 10 interactions for efficiency
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]


# Global agent service instance (singleton)
_agent_service = None

def get_agent_service() -> AgentService:
    """Get or create the global AgentService instance"""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service