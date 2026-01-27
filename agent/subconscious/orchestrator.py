"""
Subconscious Orchestrator
=========================

The orchestrator that builds STATE from all threads.

Core equation: state_t+1 = f(state_t, assess)

Two-step flow in subconscious:
    1. score(query) → thread scores
    2. build_state(scores, query) → STATE block

Then agent.generate(STATE, query) IS the assess step.
The LLM receives state + assess block and produces output.

Usage:
    from agent.subconscious.orchestrator import get_subconscious
    
    sub = get_subconscious()
    scores = sub.score("who are you")
    state = sub.build_state(scores, "who are you")
    # Then: agent.generate(user_input, state) - this IS assess

Architecture:
    - score() uses LinkingCore to score all threads for relevance
    - build_state() orders threads by score, calls introspect with threshold
    - agent.generate() IS assess - LLM evaluates query against state
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
import json


# Thread list (linking_core excluded - it scores, doesn't contribute facts)
THREADS = ["identity", "log", "form", "philosophy", "reflex"]

# Score thresholds for context levels
# Score determines: (1) block order, (2) L1/L2/L3 level, (3) fact weight threshold
SCORE_THRESHOLDS = {
    "L1": 3.5,   # 0 - 3.5: L1 (lean), only high-weight facts
    "L2": 7.0,   # 3.5 - 7: L2 (medium)
    "L3": 10.0,  # 7 - 10: L3 (full)
}


class Subconscious:
    """
    The orchestrator that builds STATE from all threads.
    
    Core equation: state_t+1 = f(state_t, assess)
    
    Key insight: 
    - STATE is assembled from threads, ordered by relevance
    - Each thread filters its facts by the score threshold
    - Facts use dot notation for addressability
    - The same STATE structure works for conversation, consolidation, reading, etc.
    """
    
    def __init__(self):
        self._last_context_time: Optional[str] = None
        self._last_query: Optional[str] = None
        self._adapters: Dict[str, Any] = {}
        self._linking_core = None
    
    def _get_adapter(self, thread_name: str):
        """Lazy-load thread adapters. Each import is fully isolated."""
        if thread_name not in self._adapters:
            # Each adapter import in its own try/catch - one failure doesn't affect others
            if thread_name == "identity":
                try:
                    from agent.threads.identity.adapter import IdentityThreadAdapter
                    self._adapters[thread_name] = IdentityThreadAdapter()
                except Exception as e:
                    print(f"⚠️ Failed to load identity adapter: {e}")
                    self._adapters[thread_name] = None
            elif thread_name == "philosophy":
                try:
                    from agent.threads.philosophy.adapter import PhilosophyThreadAdapter
                    self._adapters[thread_name] = PhilosophyThreadAdapter()
                except Exception as e:
                    print(f"⚠️ Failed to load philosophy adapter: {e}")
                    self._adapters[thread_name] = None
            elif thread_name == "log":
                try:
                    from agent.threads.log.adapter import LogThreadAdapter
                    self._adapters[thread_name] = LogThreadAdapter()
                except Exception as e:
                    print(f"⚠️ Failed to load log adapter: {e}")
                    self._adapters[thread_name] = None
            elif thread_name == "form":
                try:
                    from agent.threads.form.adapter import FormThreadAdapter
                    self._adapters[thread_name] = FormThreadAdapter()
                except Exception as e:
                    print(f"⚠️ Failed to load form adapter: {e}")
                    self._adapters[thread_name] = None
            elif thread_name == "reflex":
                try:
                    from agent.threads.reflex.adapter import ReflexThreadAdapter
                    self._adapters[thread_name] = ReflexThreadAdapter()
                except Exception as e:
                    print(f"⚠️ Failed to load reflex adapter: {e}")
                    self._adapters[thread_name] = None
            elif thread_name == "linking_core":
                try:
                    from agent.threads.linking_core.adapter import LinkingCoreThreadAdapter
                    self._adapters[thread_name] = LinkingCoreThreadAdapter()
                except Exception as e:
                    print(f"⚠️ Failed to load linking_core adapter: {e}")
                    self._adapters[thread_name] = None
            else:
                self._adapters[thread_name] = None
        return self._adapters.get(thread_name)
    
    def _get_linking_core(self):
        """Get the LinkingCore adapter for scoring."""
        if self._linking_core is None:
            try:
                from agent.threads.linking_core.adapter import LinkingCoreThreadAdapter
                self._linking_core = LinkingCoreThreadAdapter()
            except Exception as e:
                print(f"⚠️ Failed to load linking_core: {e}")
        return self._linking_core
    
    def score(self, query: str = "") -> Dict[str, float]:
        """
        Score all threads for relevance to query.
        
        Step 1 of the flow: score(query) → scores
        
        Args:
            query: The input to score against (user message, file chunk, etc.)
        
        Returns:
            Dict mapping thread_name → relevance_score (0-10)
            
            Example:
                {"identity": 9.0, "log": 5.0, "form": 4.0, ...}
        """
        linking_core = self._get_linking_core()
        if linking_core and query:
            scores = linking_core.score_threads(query)
        else:
            # Default scores if linking_core unavailable or no query
            scores = {t: 5.0 for t in THREADS}
        
        # Ensure all threads have a score (default 5.0)
        for thread in THREADS:
            if thread not in scores:
                scores[thread] = 5.0
        
        return scores
    
    def build_state(self, scores: Dict[str, float], query: str = "") -> str:
        """
        Build STATE block from thread scores.
        
        Step 2 of the flow: build_state(scores) → STATE
        
        Args:
            scores: Thread relevance scores from score()
            query: Optional query for thread introspection filtering
        
        Returns:
            Formatted STATE block string:
            
            == STATE ==
            
            identity - 8.2
            identity.agent.name.value: Nola
            identity.agent.name.weight: 10.0
            
            log - 5.5
            log.events.0.message: discussed architecture
            
            == END STATE ==
        """
        # Order by score (highest first)
        ordered_threads: List[Tuple[str, float]] = sorted(
            scores.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        # Build state blocks
        lines = ["== STATE ==", ""]
        
        for thread_name, score in ordered_threads:
            if thread_name == "linking_core":
                continue  # linking_core scores, doesn't contribute facts
                
            adapter = self._get_adapter(thread_name)
            if not adapter:
                continue
            
            # Determine level from score
            if score < SCORE_THRESHOLDS["L1"]:
                level = 1
            elif score < SCORE_THRESHOLDS["L2"]:
                level = 2
            else:
                level = 3
            
            # Use score as threshold
            threshold = score
            
            try:
                # Call introspect with threshold
                result = adapter.introspect(
                    context_level=level, 
                    query=query,
                    threshold=threshold
                )
                result_dict = result.to_dict()
                facts = result_dict.get("facts", [])
                
                if facts:
                    # Thread header with score
                    lines.append(f"{thread_name} - {score:.1f}")
                    
                    # Facts (already formatted with dot notation by adapter)
                    for fact in facts:
                        lines.append(fact)
                    
                    lines.append("")  # Blank line between threads
                    
            except TypeError:
                # Adapter doesn't support threshold yet - fall back to old signature
                try:
                    result = adapter.introspect(context_level=level, query=query)
                    result_dict = result.to_dict()
                    facts = result_dict.get("facts", [])
                    
                    if facts:
                        lines.append(f"{thread_name} - {score:.1f}")
                        for fact in facts:
                            lines.append(fact)
                        lines.append("")
                except Exception as e:
                    print(f"⚠️ {thread_name} introspect failed: {e}")
                    
            except Exception as e:
                print(f"⚠️ {thread_name} introspect failed: {e}")
        
        lines.append("== END STATE ==")
        
        # Track timing
        self._last_context_time = datetime.now(timezone.utc).isoformat()
        self._last_query = query
        
        return "\n".join(lines)
    
    def get_state(self, query: str = "") -> str:
        """
        Convenience method: score + build_state in one call.
        
        For when you just need the STATE block without intermediate access.
        
        Args:
            query: The input to build state for
        
        Returns:
            Formatted STATE block string
        """
        scores = self.score(query)
        return self.build_state(scores, query)
    
    def build_context(
        self,
        level: int = 2,
        query: str = "",
        threads: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Build STATE + CONTEXT blocks by calling each thread's introspect().
        
        Args:
            level: Context level (1=minimal, 2=standard, 3=full)
            query: User's message - passed to threads for relevance filtering
            threads: Which threads to query (default: all)
        
        Returns:
            {
                "state": {thread: {health, state, ...}},
                "context": [{"key": ..., "value": ..., "source": ...}, ...],
                "meta": {"level": N, "total_facts": N, ...}
            }
        """
        level = max(1, min(3, level))
        threads = threads or THREADS
        
        state = {}
        all_facts = []
        all_concepts = set()
        
        # Call each thread's introspect
        for thread_name in threads:
            adapter = self._get_adapter(thread_name)
            if not adapter:
                state[thread_name] = {"health": {"status": "error", "message": "Adapter not found"}}
                continue
            
            try:
                result = adapter.introspect(context_level=level, query=query)
                result_dict = result.to_dict()
                
                # Add to state
                state[thread_name] = {
                    "health": result_dict.get("health", {}),
                    "state": result_dict.get("state", {}),
                    "fact_count": result_dict.get("fact_count", 0),
                }
                
                # Collect facts with source
                for fact in result_dict.get("facts", []):
                    all_facts.append({
                        "fact": fact,
                        "source": thread_name,
                    })
                
                # Collect relevant concepts
                for concept in result_dict.get("relevant_concepts", []):
                    all_concepts.add(concept)
                    
            except Exception as e:
                state[thread_name] = {
                    "health": {"status": "error", "message": str(e)[:100]},
                    "state": {},
                    "fact_count": 0,
                }
        
        # Track timing
        self._last_context_time = datetime.now(timezone.utc).isoformat()
        self._last_query = query
        
        return {
            "state": state,
            "context": all_facts,
            "relevant_concepts": list(all_concepts),
            "meta": {
                "level": level,
                "total_facts": len(all_facts),
                "threads_queried": threads,
                "timestamp": self._last_context_time,
                "query": query[:100] if query else None,
            }
        }
    
    def get_all_health(self) -> Dict[str, Dict]:
        """Get health status from all threads. Each thread is fully isolated."""
        health = {}
        for thread_name in THREADS:
            # Completely isolated - adapter load + health check in one try block
            try:
                adapter = self._get_adapter(thread_name)
                if adapter is not None:
                    try:
                        report = adapter.health()
                        health[thread_name] = report.to_dict()
                    except Exception as e:
                        health[thread_name] = {"status": "error", "message": f"health() failed: {str(e)[:80]}"}
                else:
                    health[thread_name] = {"status": "error", "message": "Adapter failed to load"}
            except Exception as e:
                # Catch-all for any unexpected error
                health[thread_name] = {"status": "error", "message": f"Unexpected: {str(e)[:80]}"}
        return health
    
    def record_interaction(
        self,
        user_message: str,
        agent_response: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """Record an interaction to the log thread."""
        try:
            from agent.threads.log.schema import log_event
            log_event(
                event_type="convo",
                data=json.dumps({
                    "user": user_message[:500],
                    "agent": agent_response[:500],
                }),
                metadata=metadata,
                source="agent",
            )
        except Exception as e:
            print(f"⚠️ Failed to record interaction: {e}")
    
    def get_identity_facts(self, level: int = 2) -> List[str]:
        """Get identity facts as simple strings (backwards compatibility)."""
        ctx = self.build_context(level=level, threads=["identity"])
        return [item["fact"] for item in ctx.get("context", [])]
    
    def get_context_string(self, level: int = 2, query: str = "") -> str:
        """Get context as a formatted string for system prompt."""
        ctx = self.build_context(level=level, query=query)
        
        lines = []
        for item in ctx.get("context", []):
            fact = item.get("fact", "")
            source = item.get("source", "")
            lines.append(f"[{source}] {fact}")
        
        return "\n".join(lines)


# Singleton instance
_SUBCONSCIOUS: Optional[Subconscious] = None


def get_subconscious() -> Subconscious:
    """Get the singleton Subconscious instance."""
    global _SUBCONSCIOUS
    if _SUBCONSCIOUS is None:
        _SUBCONSCIOUS = Subconscious()
    return _SUBCONSCIOUS


def build_state(query: str = "") -> str:
    """
    Convenience function: score(query) + build_state(scores, query).
    
    This is the primary state assembly function for the architecture.
    Agent.generate(state, query) IS the assess step.
    
    Flow:
        scores = score(query)
        state = build_state(scores, query)
        response = agent.generate(state, query)  ← this IS assess
    
    Args:
        query: The assess block content (user message, file chunk, etc.)
    
    Returns:
        Formatted STATE block string with dot notation facts.
    """
    return get_subconscious().get_state(query)


def build_context(level: int = 2, query: str = "", threads: Optional[List[str]] = None) -> Dict[str, Any]:
    """Convenience function to build context (legacy)."""
    return get_subconscious().build_context(level, query, threads)


def record_interaction(user_msg: str, agent_resp: str, meta: Optional[Dict] = None) -> None:
    """Convenience function to record interaction."""
    get_subconscious().record_interaction(user_msg, agent_resp, meta)
