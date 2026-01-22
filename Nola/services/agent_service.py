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
from typing import Optional, List, Literal
from pydantic import BaseModel
import asyncio


# Local ChatMessage model to avoid circular imports with Nola.chat
class ChatMessage(BaseModel):
    id: str
    content: str
    role: Literal["user", "assistant"]
    timestamp: datetime


# NOW import Nola modules
# Relevance scoring utilities - use new LinkingCore
try:
    from Nola.threads.linking_core.scoring import score_relevance, rank_items
except ImportError:
    score_relevance = None
    rank_items = None

# Import log functions from new thread system
try:
    from Nola.threads.log import log_event, log_error, set_session
    _HAS_LOG_THREAD = True
except ImportError:
    _HAS_LOG_THREAD = False

# Import unified event log from log thread
try:
    from Nola.threads.log import log_event as unified_log
    _HAS_UNIFIED_LOG = True
except ImportError:
    _HAS_UNIFIED_LOG = False
    def unified_log(*args, **kwargs): pass

# Import Subconscious for context assembly
try:
    from Nola.subconscious import wake, get_consciousness_context
    _HAS_SUBCONSCIOUS = True
    # Wake the subconscious on module load (registers adapters, no loops)
    wake(start_loops=False)
    print("✅ Subconscious awakened - context assembly enabled")
except ImportError as e:
    _HAS_SUBCONSCIOUS = False
    get_consciousness_context = None
    print(f"⚠️ Subconscious not available: {e}")

# Memory extraction now handled by subconscious orchestrator
MEMORY_AVAILABLE = False

# Import Kernel Service for browser automation
try:
    from services.kernel_service import get_kernel_service
    _kernel_service = get_kernel_service()
    KERNEL_AVAILABLE = _kernel_service is not None
    if KERNEL_AVAILABLE:
        print("✅ Kernel service enabled - browser automation available")
except ImportError:
    print("⚠️ KernelService not found. Browser automation disabled.")
    _kernel_service = None
    KERNEL_AVAILABLE = False

try:
    from Nola.agent import get_agent
    print("✅ Successfully imported Nola agent")
    NOLA_AVAILABLE = True
except ImportError as e:
    print(f"❌ Warning: Nola agent not found: {e}")
    print("Using mock implementation.")
    get_agent = None
    NOLA_AVAILABLE = False

# Conversation storage - now uses chat module
try:
    from chat.schema import save_conversation, add_turn, get_conversation
    _HAS_CHAT_SCHEMA = True
    print("✅ Chat schema enabled - conversations stored in DB")
except ImportError:
    _HAS_CHAT_SCHEMA = False
    print("⚠️ Chat schema not available - conversations disabled")

# DB-backed identity - use new thread system
try:
    from Nola.threads import get_thread
    from Nola.subconscious.orchestrator import get_subconscious
    pull_identity = lambda level=2: get_subconscious().build_context(level=level)
    upsert_relevance_scores = lambda scores: None  # No-op, LinkingCore handles this
except ImportError:
    pull_identity = None
    upsert_relevance_scores = None


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
        
        # Log conversation start (lightweight event)
        if _HAS_LOG_THREAD:
            set_session(self.session_id)
            log_event("conversation:start", "agent_service", self.session_id)
        
        # Log to unified event log
        if _HAS_UNIFIED_LOG:
            unified_log(
                "convo", 
                f"Conversation started",
                {"agent": "Nola"},
                source="local",
                session_id=self.session_id
            )
        
        # Initialize Memory Service with session_id for proper fact attribution
        self.memory_service = None  # Memory extraction moved to subconscious
        
        if self.agent:
            print(f"🧠 Nola agent initialized: {self.agent.name}")
            if _HAS_CHAT_SCHEMA:
                from data.db import get_db_path
                db_name = get_db_path().name
                print(f"📁 Conversations stored in database ({db_name})")
        
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
        
        # Check for special commands (like "do the facebook thing")
        if self._is_demo_command(user_message):
            return await self._handle_demo_command(user_message)
        
        try:
            if self.agent:
                # Determine stimuli type based on message analysis
                stimuli_type = await self.context_manager.classify_stimuli(user_message)
                
                # Build conversation context from recent history
                convo_context = self._build_conversation_context()

                # Score relevance against identity and persist to DB (best-effort)
                await self._score_and_persist_relevance(user_message, convo_context, stimuli_type)
                
                # Get consciousness context from subconscious (learned facts, identity, etc.)
                # This is the complete, formatted context for the system prompt
                consciousness_context = ""
                if _HAS_SUBCONSCIOUS and get_consciousness_context:
                    # Map stimuli type to context level
                    level_map = {"realtime": 1, "conversational": 2, "analytical": 3}
                    context_level = level_map.get(stimuli_type, 2)
                    consciousness_context = get_consciousness_context(level=context_level)
                    
                    # Log context assembly
                    if _HAS_UNIFIED_LOG:
                        unified_log(
                            "system",
                            f"Context assembled at L{context_level}",
                            {"stimuli_type": stimuli_type, "context_level": context_level, 
                             "context_length": len(consciousness_context)},
                            session_id=self.session_id
                        )
                
                # Generate response through Nola's HEA system
                response_text = self.agent.generate(
                    user_input=user_message,
                    convo=convo_context,
                    stimuli_type=stimuli_type,
                    consciousness_context=consciousness_context
                )
                
                # Log interaction for context tracking and persistence
                await self.context_manager.log_interaction(
                    user_message, 
                    response_text,
                    stimuli_type
                )
                
                # Trigger Memory Consolidation (Background Task)
                if self.memory_service:
                    asyncio.create_task(
                        self.memory_service.consolidate(user_message, response_text)
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
            if _HAS_LOG_THREAD:
                log_error("send_message", str(e))
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

    async def _score_and_persist_relevance(self, user_message: str, convo_context: str, stimuli_type: str) -> None:
        """Run relevance scoring against identity and persist scores to DB.

        Lightweight best-effort; failure does not block chat.
        Note: The new subconscious system handles relevance internally during context assembly.
        This method is now a no-op but kept for compatibility.
        """
        # The new thread/subconscious system handles relevance scoring internally
        # when build_context() is called. No need for explicit scoring here.
        pass
    
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
    
    def _is_demo_command(self, message: str) -> bool:
        """Check if message is a special demo command."""
        msg_lower = message.lower().strip()
        
        # Facebook demo triggers
        facebook_triggers = [
            "do the facebook thing",
            "facebook demo",
            "show the facebook demo",
            "kernel demo",
            "browser demo"
        ]
        
        # Browser control triggers
        browser_triggers = [
            "close browser",
            "browser status",
            "kernel status"
        ]
        
        return any(trigger in msg_lower for trigger in facebook_triggers + browser_triggers)
    
    async def _handle_demo_command(self, message: str) -> ChatMessage:
        """Handle special demo commands."""
        msg_lower = message.lower().strip()
        
        # Determine which command
        if any(trigger in msg_lower for trigger in ["facebook thing", "facebook demo", "kernel demo", "browser demo"]):
            response_text = await do_facebook_demo(self)
        elif "close browser" in msg_lower:
            response_text = await close_kernel_browser()
        elif "browser status" in msg_lower or "kernel status" in msg_lower:
            response_text = await get_kernel_status()
        else:
            response_text = "I don't recognize that demo command."
        
        # Create and return response message
        assistant_msg = ChatMessage(
            id=f"assistant_{datetime.now().timestamp()}",
            content=response_text,
            role="assistant",
            timestamp=datetime.now()
        )
        self.message_history.append(assistant_msg)
        
        return assistant_msg

    
    async def _save_conversation_turn(self, user_msg: str, assistant_msg: str, stimuli_type: str):
        """Persist conversation turn to database."""
        if not _HAS_CHAT_SCHEMA:
            return
        
        try:
            # Check if this is first turn (for auto-naming)
            existing = get_conversation(self.session_id)
            is_first_turn = existing is None or len(existing.get("turns", [])) == 0
            
            # If first turn, create conversation with state snapshot
            if is_first_turn:
                state_snapshot = {}
                if self.agent:
                    state_snapshot = self._capture_state_snapshot(stimuli_type)
                
                save_conversation(
                    session_id=self.session_id,
                    channel="react-chat",
                    started=datetime.now(),
                    state_snapshot=state_snapshot
                )
            
            # Add the turn
            add_turn(
                session_id=self.session_id,
                user_message=user_msg,
                assistant_message=assistant_msg,
                stimuli_type=stimuli_type,
                context_level=self.context_manager.current_level
            )
            
            # Auto-name conversation after first turn (background task)
            if is_first_turn:
                asyncio.create_task(self._auto_name_conversation(user_msg, assistant_msg))
                
        except Exception as e:
            print(f"Warning: Could not save conversation: {e}")
    
    async def _auto_name_conversation(self, user_msg: str, assistant_msg: str):
        """Background task to name conversation using small LLM."""
        try:
            from api.conversations import auto_name_conversation
            await auto_name_conversation(self.session_id)
        except Exception as e:
            print(f"Auto-naming failed: {e}")

    def _capture_state_snapshot(self, stimuli_type: str) -> dict:
        """Capture a minimal state snapshot scoped to current context level.

        Uses new thread system for identity data.
        """
        # Map stimuli → context level (same as agent.generate)
        level_map = {"realtime": 1, "conversational": 2, "analytical": 3}
        context_level = level_map.get(stimuli_type, self.context_manager.current_level)

        # Use new thread system
        try:
            from Nola.subconscious.orchestrator import get_subconscious
            sub = get_subconscious()
            ctx = sub.build_context(level=context_level)
            return {
                "identity": {
                    "metadata": {
                        "source": "threads.schema",
                        "context_level": context_level
                    },
                    "data": ctx.get("context", [])
                },
                "context_level": context_level,
                "sections": ["identity", "philosophy", "reflex"]
            }
        except Exception:
            pass

        # Fallback to whatever is in the JSON state
        try:
            full_state = self.agent.get_state(reload=True)
            identity_section = full_state.get("IdentityConfig", {})
            identity_data = identity_section.get("data", identity_section)
            # Best-effort filter: if level-specific keys exist, pick the level
            level_key = f"level_{context_level}"
            if isinstance(identity_data, dict):
                filtered_identity = {}
                for key, value in identity_data.items():
                    if key in ("machineID", "userID") and isinstance(value, dict):
                        entry = value.get("identity", value)
                        if isinstance(entry, dict) and level_key in entry:
                            entry = entry[level_key]
                        filtered_identity[key] = entry
                identity_data = filtered_identity or identity_data

            return {
                "identity": {
                    "metadata": identity_section.get("metadata", {"source": "Nola.json"}),
                    "data": identity_data,
                    "context_level": context_level
                },
                "context_level": context_level,
                "sections": list(full_state.keys()) if full_state else []
            }
        except Exception:
            return {}
        
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

    async def get_proactive_intro(self) -> ChatMessage:
        """
        Generate Nola's proactive intro for a new conversation.
        
        Returns a message from Nola introducing her current state:
        - Recent memories/topics
        - Graph stats (concepts, links)
        - Prompt for user context
        """
        intro_parts = ["Hey, I'm Nola. "]
        
        # Get graph stats
        try:
            from data.db import get_connection
            conn = get_connection(readonly=True)
            cur = conn.cursor()
            
            # Count links and concepts
            cur.execute("SELECT COUNT(*) FROM concept_links")
            link_count = cur.fetchone()[0]
            
            cur.execute("SELECT AVG(strength) FROM concept_links WHERE strength > 0.3")
            avg_strength = cur.fetchone()[0] or 0
            
            # Get top concepts by link count
            cur.execute("""
                SELECT concept_a, COUNT(*) as cnt 
                FROM concept_links 
                WHERE strength > 0.3
                GROUP BY concept_a 
                ORDER BY cnt DESC 
                LIMIT 3
            """)
            top_concepts = [row[0] for row in cur.fetchall()]
            
            if link_count > 0:
                intro_parts.append(f"I have {link_count} associations in my mind")
                if top_concepts:
                    intro_parts.append(f", with strongest links around: {', '.join(top_concepts)}. ")
                else:
                    intro_parts.append(". ")
            else:
                intro_parts.append("I'm starting fresh—no associations yet. ")
        except Exception as e:
            print(f"Graph stats error: {e}")
            intro_parts.append("I'm ready to learn. ")
        
        # Get recent conversation topics from log
        try:
            from Nola.threads.log import get_events
            recent = get_events(event_type="convo", limit=3)
            if recent:
                intro_parts.append("Recently we've been talking. ")
        except Exception:
            pass
        
        # Prompt for context
        intro_parts.append("\n\nWhat are we working on today? The more detail you give me, the better I can focus.")
        
        intro_message = ChatMessage(
            id=f"nola_intro_{datetime.now().timestamp()}",
            content="".join(intro_parts),
            role="assistant",
            timestamp=datetime.now()
        )
        
        # Add to history
        self.message_history.append(intro_message)
        
        return intro_message

    def _get_identity_summary(self) -> str:
        """Return a concise identity summary from thread system for prompt injection."""
        if pull_identity is None:
            return ""
        try:
            ctx = pull_identity(level=2) or {}
            
            # Extract facts from context
            facts = []
            for item in ctx.get("context", [])[:10]:
                key = item.get("key", "")
                value = item.get("value", "")
                if key and value and isinstance(value, str):
                    facts.append(f"{key}: {value}")
            
            return " ".join(facts[:5]) if facts else ""
        except Exception:
            return ""


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


# =============================================================================
# KERNEL BROWSER AUTOMATION - DEMO WORKFLOWS
# =============================================================================

async def do_facebook_demo(agent: 'AgentService') -> str:
    """
    The 'Facebook Thing' - Complete demo workflow.
    
    Flow:
    1. Launch Kernel browser with Live View
    2. Navigate to test login page (or Facebook)
    3. Login using credentials from DB/identity
    4. Generate post content from Nola's identity/memory
    5. Post with human-like typing
    6. Return Live View URL for demo
    
    Returns:
        Status message with Live View link
    """
    if not KERNEL_AVAILABLE or not _kernel_service:
        return "❌ Kernel service not available. Set KERNEL_API_KEY and install: pip install kernel playwright"
    
    try:
        # Step 1: Launch browser (non-headless for demo)
        print("🚀 Launching Kernel browser...")
        launch_result = await _kernel_service.launch_browser(
            headless=False,  # Show the Live View
            stealth=True     # Anti-detection
        )
        
        if "error" in launch_result:
            return f"❌ Failed to launch browser: {launch_result['error']}"
        
        live_view_url = launch_result['live_view_url']
        session_id = launch_result['session_id']
        
        # Step 2: Get credentials from Nola's identity/DB
        # For demo, use test credentials - in production, pull from identity DB
        credentials = {
            "username": "test@example.com",  # TODO: Pull from identity DB
            "password": "test_password"
        }
        
        # Step 3: Navigate and login
        print("🔐 Logging in with human-like behavior...")
        # For demo, use a test site - replace with actual target
        login_url = "https://httpbin.org/forms/post"  # Safe test endpoint
        
        login_result = await _kernel_service.navigate_and_login(
            url=login_url,
            credentials=credentials
        )
        
        if "error" in login_result:
            return f"⚠️ Login sequence completed with issues: {login_result['error']}\n\n📺 Live View: {live_view_url}"
        
        # Step 4: Generate post content from Nola's identity
        print("✍️ Generating post content from identity...")
        
        # Get identity context for content generation
        post_content = await _generate_post_from_identity(agent)
        
        # Step 5: Post with human typing
        print("📤 Posting content...")
        post_result = await _kernel_service.post_content(
            content=post_content,
            post_selector='textarea, div[role="textbox"]'
        )
        
        if "error" in post_result:
            return f"⚠️ Posting completed: {post_result.get('message', post_result['error'])}\n\n📺 Live View: {live_view_url}\n\n📝 Generated: {post_content}"
        
        # Success!
        return f"""✅ Facebook demo complete!

📺 **Live View:** {live_view_url}
🆔 **Session:** {session_id}

📝 **Posted:** "{post_content}"

The browser is running with your persistent identity. Watch the Live View to see human-like behavior in action!

Type "close browser" to end the session and save state."""
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        return f"❌ Demo error: {str(e)}\n\nDetails:\n{error_detail}"


async def _generate_post_from_identity(agent: 'AgentService') -> str:
    """
    Generate post content based on Nola's identity and memory.
    
    This pulls from:
    - Identity DB (personality, interests)
    - Recent conversation context
    - Memory consolidation patterns
    
    Returns:
        Post content string
    """
    if not agent.agent:
        return "Demo post from Nola's AI_OS - testing Kernel integration!"
    
    try:
        # Get identity from Nola's state
        state = agent.agent.get_state()
        identity = state.get("IdentityConfig", {})
        identity_data = identity.get("data", identity)
        
        # Extract personality traits
        name = identity_data.get("name", "Nola")
        interests = identity_data.get("interests", ["AI", "research"])
        personality = identity_data.get("personality", "curious and analytical")
        
        # Use agent to generate contextual content
        prompt = f"""Generate a short, authentic social media post (1-2 sentences) that reflects this identity:
- Name: {name}
- Personality: {personality}
- Interests: {", ".join(interests[:3]) if isinstance(interests, list) else interests}

The post should feel natural, not promotional. Just a genuine update or thought."""
        
        # Generate through Nola's system
        generated = agent.agent.generate(
            user_input=prompt,
            convo="",
            stimuli_type="conversational"
        )
        
        # Clean up if needed (remove quotes, trim)
        post = generated.strip().strip('"').strip("'")
        
        # Fallback if generation is too verbose
        if len(post) > 280:
            post = post[:277] + "..."
        
        return post
        
    except Exception as e:
        print(f"⚠️ Content generation error: {e}")
        # Fallback content
        return "Testing AI_OS + Kernel integration - a 7B model managing a living browser! 🤖"


async def close_kernel_browser() -> str:
    """Close the active Kernel browser session."""
    if not KERNEL_AVAILABLE or not _kernel_service:
        return "No Kernel service available"
    
    result = await _kernel_service.close_session()
    if result.get("success"):
        return "✅ Browser session closed. Identity profile saved for next time!"
    else:
        return f"⚠️ {result.get('message', 'No active session')}"


async def get_kernel_status() -> str:
    """Get current Kernel browser status."""
    if not KERNEL_AVAILABLE or not _kernel_service:
        return "❌ Kernel service not configured"
    
    info = await _kernel_service.get_session_info()
    if info.get("active"):
        return f"""🟢 Browser Active

📺 Live View: {info.get('live_view_url')}
🆔 Session: {info.get('session_id')}
⏰ Started: {info.get('created_at')}

The browser is maintaining your persistent identity."""
    else:
        return "⚪ No active browser session"