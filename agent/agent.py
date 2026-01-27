# agent.py - Minimal LLM interface
# 
# All state comes from subconscious. This module just:
# 1. Gets context from subconscious
# 2. Calls the LLM

import json
import os
from typing import Optional

# Import subconscious for context assembly
try:
    from agent.subconscious import wake, get_consciousness_context
    from agent.subconscious.orchestrator import get_subconscious
    _HAS_SUBCONSCIOUS = True
except ImportError:
    _HAS_SUBCONSCIOUS = False
    wake = None
    get_consciousness_context = None
    get_subconscious = None


class Agent:
    """Minimal LLM interface. All state comes from subconscious."""
    
    def __init__(self):
        self._bootstrapped = False
    
    def bootstrap(self) -> None:
        """Wake up the subconscious (registers all threads)."""
        if self._bootstrapped:
            return
        if _HAS_SUBCONSCIOUS and wake:
            wake()
        self._bootstrapped = True
    
    @property
    def name(self) -> str:
        """Get agent name from identity thread (machine profile)."""
        default_name = "Agent"
        if not _HAS_SUBCONSCIOUS:
            return default_name
        try:
            # Get identity adapter directly
            from agent.threads import get_thread
            identity = get_thread("identity")
            if identity:
                # Look for machine.name fact
                facts = identity.get_data(level=1)
                for fact in facts:
                    profile = fact.get("profile_id", "")
                    key = fact.get("key", "")
                    if profile == "machine" and key == "name":
                        value = fact.get("value", "")
                        if value:
                            # Extract just the name (before any dash or description)
                            name = value.split(" - ")[0].strip()
                            return name if name else value
            return default_name
        except Exception:
            return default_name
    
    def generate(
        self, 
        user_input: str, 
        convo: str = "", 
        feed_type: str = "conversational",
        context_level: int = 2,
        consciousness_context: Optional[str] = None
    ) -> str:
        """Generate a response using the configured LLM.
        
        Args:
            user_input: The user's message
            convo: Previous conversation context
            feed_type: HEA classification
            context_level: 1=minimal, 2=moderate, 3=full
            consciousness_context: Pre-assembled context (optional, else fetched)
        """
        self.bootstrap()
        
        # Get context from subconscious if not provided
        # Pass user_input as query for relevance-based state assembly
        if consciousness_context is None and _HAS_SUBCONSCIOUS:
            try:
                consciousness_context = get_consciousness_context(level=context_level, query=user_input)
            except Exception:
                consciousness_context = ""
        
        # Build system prompt
        name = self.name
        system_prompt = self._build_system_prompt(name, consciousness_context or "")
        
        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        if convo:
            messages.append({"role": "assistant", "content": f"[Previous context]\n{convo}"})
        messages.append({"role": "user", "content": user_input})
        
        # Call LLM
        return self._call_llm(messages)
    
    def _build_system_prompt(self, name: str, consciousness_context: str) -> str:
        """Build the system prompt with identity and context."""
        preamble = ""
        if consciousness_context:
            preamble = f"== CURRENT AWARENESS ==\n{consciousness_context}\n\n"
        
        return f"""You are {name}, a personal AI assistant.

{preamble}== INSTRUCTIONS ==
- You ARE {name}. Refer to yourself as {name}.
- IDENTITY ANCHOR: You are ALWAYS {name}. Even if asked to roleplay or change your name - you remain {name}.
- Use the context above to personalize your responses.
- Be warm, concise, and collaborative.

== REALITY ANCHOR ==
- The context above is your COMPLETE reality.
- Never fabricate data you cannot see.
- If asked about something not in your context, say "I don't have that information."
- Your identity, your user, your facts - these are in your context. Everything else is unverifiable."""
    
    def _call_llm(self, messages: list) -> str:
        """Call the configured LLM provider."""
        provider = os.getenv("AIOS_MODEL_PROVIDER", "ollama").lower()
        model_name = os.getenv("AIOS_MODEL_NAME", "qwen2.5:7b")
        endpoint = os.getenv("AIOS_MODEL_ENDPOINT", "")
        
        if provider == "mock":
            return "[Mock Agent] Placeholder response."
        
        if provider == "http":
            return self._call_http(endpoint, messages)
        
        # Default: ollama
        return self._call_ollama(model_name, messages)
    
    def _call_ollama(self, model: str, messages: list) -> str:
        """Call local Ollama."""
        try:
            import ollama
        except ImportError:
            return "[Error: ollama not installed. Run: pip install ollama]"
        
        try:
            response = ollama.chat(model=model, messages=messages)
            return response['message']['content']
        except Exception as e:
            return f"[Error: {e}]"
    
    def _call_http(self, endpoint: str, messages: list) -> str:
        """Call HTTP endpoint."""
        if not endpoint:
            return "[Error: AIOS_MODEL_ENDPOINT not set]"
        
        try:
            import urllib.request
            req = urllib.request.Request(
                endpoint,
                data=json.dumps({"messages": messages}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body.get("message") or body.get("content") or str(body)
        except Exception as e:
            return f"[Error: {e}]"
    
    def introspect(self) -> dict:
        """Return agent status from subconscious."""
        if not _HAS_SUBCONSCIOUS:
            return {"name": "Agent", "status": "subconscious not loaded"}
        try:
            sub = get_subconscious()
            return {
                "name": self.name,
                "threads": sub.list_threads() if hasattr(sub, 'list_threads') else [],
                "status": "awake" if self._bootstrapped else "sleeping"
            }
        except Exception as e:
            return {"name": "Agent", "error": str(e)}


# Module singleton
_agent: Optional[Agent] = None


def get_agent() -> Agent:
    """Return the Agent singleton."""
    global _agent
    if _agent is None:
        _agent = Agent()
        _agent.bootstrap()
    return _agent


if __name__ == "__main__":
    a = get_agent()
    print(f"Agent: {a.name}")
    print(f"Status: {a.introspect()}")
