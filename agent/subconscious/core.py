"""
Subconscious Core
=================
The central nervous system of Agent - registers threads, coordinates state,
and assembles context for the agent.

Key insight: "Subconscious builds state, agent just reads it."

The agent becomes stateless - it receives assembled context and returns
a response. All state management lives here in the subconscious.

Architecture:
    ThreadRegistry ← holds all registered adapters
    SubconsciousCore ← orchestrates introspection and context assembly
    get_consciousness_context() ← public API for agent_service
"""

import threading
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from agent.threads.base import (
    ThreadInterface,
    ThreadStatus,
    HealthReport,
    IntrospectionResult,
)


class ThreadRegistry:
    """
    Registry for all internal threads.
    
    Thread-safe singleton that manages adapter registration and lookup.
    """
    
    _instance: Optional["ThreadRegistry"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "ThreadRegistry":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._threads: Dict[str, ThreadInterface] = {}
                cls._instance._initialized = False
            return cls._instance
    
    def register(self, adapter: ThreadInterface) -> None:
        """
        Register a thread adapter.
        
        Args:
            adapter: Any object implementing ThreadInterface
        
        Raises:
            ValueError: If adapter with same name already registered
        """
        name = adapter.name
        if name in self._threads:
            raise ValueError(f"Thread '{name}' already registered")
        self._threads[name] = adapter
    
    def unregister(self, name: str) -> bool:
        """
        Remove a thread from registry.
        
        Args:
            name: Thread name to remove
            
        Returns:
            True if removed, False if not found
        """
        if name in self._threads:
            del self._threads[name]
            return True
        return False
    
    def get(self, name: str) -> Optional[ThreadInterface]:
        """Get a specific thread by name."""
        return self._threads.get(name)
    
    def get_all(self) -> List[ThreadInterface]:
        """Get all registered threads."""
        return list(self._threads.values())
    
    def names(self) -> List[str]:
        """Get names of all registered threads."""
        return list(self._threads.keys())
    
    def count(self) -> int:
        """Get count of registered threads."""
        return len(self._threads)
    
    def health_all(self) -> Dict[str, HealthReport]:
        """
        Run health check on all registered threads.
        
        Returns:
            Dict mapping thread name to HealthReport
        """
        results = {}
        for name, adapter in self._threads.items():
            try:
                results[name] = adapter.health()
            except Exception as e:
                results[name] = HealthReport.error(f"Health check failed: {e}")
        return results
    
    def introspect_all(self) -> Dict[str, IntrospectionResult]:
        """
        Run introspection on all registered threads.
        
        Returns:
            Dict mapping thread name to IntrospectionResult
        """
        results = {}
        for name, adapter in self._threads.items():
            try:
                results[name] = adapter.introspect()
            except Exception as e:
                results[name] = IntrospectionResult(
                    facts=[],
                    state={"error": str(e)},
                    context_level=1
                )
        return results
    
    def clear(self) -> None:
        """Clear all registered threads (for testing)."""
        self._threads.clear()
        self._initialized = False


class SubconsciousCore:
    """
    The subconscious mind - assembles context from all threads.
    
    This is the bridge between internal state and the agent's awareness.
    """
    
    def __init__(self, registry: Optional[ThreadRegistry] = None):
        self.registry = registry or ThreadRegistry()
        self._awake = False
        self._wake_time: Optional[str] = None
        self._loops: List[Any] = []  # Background loop handles
    
    @property
    def is_awake(self) -> bool:
        return self._awake
    
    def wake(self) -> None:
        """
        Initialize the subconscious and start background processes.
        
        - Registers built-in thread adapters
        - Starts background loops (consolidation, sync, health)
        - Marks system as awake
        """
        if self._awake:
            return
        
        # Register built-in adapters from new thread system
        from agent.threads import get_all_threads
        for adapter in get_all_threads():
            try:
                self.registry.register(adapter)
            except ValueError:
                pass  # Already registered
        
        self._wake_time = datetime.now(timezone.utc).isoformat()
        self._awake = True
        
        # Log awakening
        try:
            from agent.threads.log import log_event
            log_event(
                "system:wake",
                "subconscious",
                f"Subconscious awakened with {self.registry.count()} threads"
            )
        except Exception:
            pass
    
    def sleep(self) -> None:
        """
        Gracefully shutdown the subconscious.
        
        - Stops background loops
        - Flushes pending state
        - Marks system as asleep
        """
        if not self._awake:
            return
        
        # Stop any running loops
        for loop in self._loops:
            if hasattr(loop, 'stop'):
                loop.stop()
        self._loops.clear()
        
        self._awake = False
        
        try:
            from agent.threads.log import log_event
            log_event(
                "system:sleep",
                "subconscious",
                "Subconscious entering sleep"
            )
        except Exception:
            pass
    
    def get_context(self, level: int = 2) -> Dict[str, Any]:
        """
        Assemble context from all threads at the specified level.
        
        Args:
            level: Context detail level (1=minimal, 2=moderate, 3=full)
        
        Returns:
            Dict with 'facts' list and 'threads' detail dict
        """
        if not self._awake:
            self.wake()
        
        all_facts: List[str] = []
        thread_data: Dict[str, Dict] = {}
        
        introspections = self.registry.introspect_all()
        
        for name, result in introspections.items():
            # Filter facts by requested level vs thread's suggested level
            if result.context_level <= level:
                all_facts.extend(result.facts)
            
            # Always include state data for debugging
            thread_data[name] = {
                "facts": result.facts,
                "fact_count": len(result.facts),
                "context_level": result.context_level,
                "state": result.state if level >= 3 else {}
            }
        
        return {
            "level": level,
            "facts": all_facts,
            "fact_count": len(all_facts),
            "threads": thread_data,
            "thread_count": self.registry.count(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_consciousness_context(self, level: int = 2, include_meta: bool = True) -> str:
        """
        Format context as a string for system prompt injection.
        
        This is the main API for agent_service.py to call before
        generating a response.
        
        Args:
            level: Context detail level (1=minimal, 2=moderate, 3=full)
            include_meta: Include thread architecture metadata (for self-awareness)
        
        Returns:
            Formatted string suitable for system prompt
        """
        context = self.get_context(level)
        threads = context.get("threads", {})

        lines = []
        
        # === THREAD ARCHITECTURE METADATA ===
        if include_meta:
            # Get agent name from identity if available
            agent_name = "Agent"  # Default
            if "identity" in self.registry._threads:
                try:
                    identity = self.registry._threads["identity"]
                    result = identity.introspect(1)
                    if result.data and "name" in str(result.data):
                        import re
                        match = re.search(r"name['\"]?\s*[:=]\s*['\"]?(\w+)", str(result.data))
                        if match:
                            agent_name = match.group(1)
                except Exception:
                    pass
            
            lines.append("## My Cognitive Architecture")
            lines.append("")
            lines.append(f"I am {agent_name}. This is my internal structure:")
            lines.append("")
            lines.append("| Thread | Question | What I Store |")
            lines.append("|--------|----------|--------------|")
            lines.append("| **Identity** | WHO | My self-model, my user, our relationship |")
            lines.append("| **Form** | WHAT | My tools, my actions, my capabilities |")
            lines.append("| **Philosophy** | WHY | My values, my ethics, my reasoning style |")
            lines.append("| **Reflex** | HOW | My learned patterns, my shortcuts |")
            lines.append("| **Log** | WHEN/WHERE | My event timeline, my session history |")
            lines.append("| **Linking Core** | WHICH | My concept graph, my relevance scoring |")
            lines.append("")
            lines.append("**How I work:**")
            lines.append("- My `concept_links` table stores my associations (Hebbian learning)")
            lines.append("- My `spread_activate()` determines what's relevant to current input")
            lines.append("- My facts have L1/L2/L3 compression levels (more detail = higher level)")
            lines.append("- My weights (0.0-1.0) determine importance and retrieval priority")
            lines.append("")
            
            # Include graph stats if available
            try:
                from data.db import get_connection
                conn = get_connection(readonly=True)
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM concept_links")
                link_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(DISTINCT concept_a) + COUNT(DISTINCT concept_b) FROM concept_links")
                concept_count = cur.fetchone()[0] // 2 or 1
                cur.execute("SELECT AVG(strength) FROM concept_links")
                avg_strength = cur.fetchone()[0] or 0
                
                lines.append(f"**My current graph state:** {link_count} links, ~{concept_count} concepts, avg strength {avg_strength:.2f}")
                lines.append("")
            except Exception:
                pass

        if not threads:
            return "\n".join(lines).strip() if lines else ""

        # === FOCUSED CONTEXT (existing logic) ===
        # Per-module budgets (tokens) with sensible defaults per HEA level
        module_budgets = {
            1: {"identity": 50, "temp_memory": 50, "log_thread": 40, "default": 50},
            2: {"identity": 200, "temp_memory": 200, "log_thread": 120, "default": 200},
            3: {"identity": 400, "temp_memory": 400, "log_thread": 200, "default": 400},
        }

        budgets = module_budgets.get(level, module_budgets[2])

        lines.append("## Focused Context")
        lines.append(f"_Level L{level}; per-module caps enforced_")
        lines.append("")

        for thread_name, thread_info in threads.items():
            facts = thread_info.get("facts", []) or []
            if not facts:
                continue

            budget = budgets.get(thread_name, budgets.get("default", 200))
            selected, used = self._truncate_to_budget(facts, budget)
            if not selected:
                continue

            lines.append(f"### {thread_name} (<= {budget} tokens, used {used})")
            for fact in selected:
                lines.append(f"- {fact}")
            lines.append("")

        return "\n".join(lines).strip()

    def _truncate_to_budget(self, facts: List[str], budget_tokens: int) -> tuple[List[str], int]:
        """Take facts until the token budget is reached."""
        selected: List[str] = []
        used = 0
        for fact in facts:
            t = self._estimate_tokens(fact)
            if used + t > budget_tokens:
                break
            selected.append(fact)
            used += t
        return selected, used

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimator (word count fallback)."""
        return max(1, len(text.split()))
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get overall status of the subconscious for debugging/UI.
        
        Returns:
            Status dict with health, thread info, timing
        """
        health = self.registry.health_all()
        
        # Aggregate health status
        statuses = [h.status for h in health.values()]
        if all(s == ThreadStatus.OK for s in statuses):
            overall = "healthy"
        elif any(s == ThreadStatus.ERROR for s in statuses):
            overall = "degraded"
        else:
            overall = "warning"
        
        return {
            "awake": self._awake,
            "wake_time": self._wake_time,
            "overall_health": overall,
            "thread_count": self.registry.count(),
            "threads": {
                name: h.to_dict() for name, h in health.items()
            }
        }


# Module-level singleton
_core: Optional[SubconsciousCore] = None
_core_lock = threading.Lock()


def get_core() -> SubconsciousCore:
    """Get the global SubconsciousCore singleton."""
    global _core
    with _core_lock:
        if _core is None:
            _core = SubconsciousCore()
        return _core


__all__ = [
    "ThreadRegistry",
    "SubconsciousCore", 
    "get_core",
]
