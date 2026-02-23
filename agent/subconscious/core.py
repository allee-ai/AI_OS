"""
Subconscious Core
=================
Thread registry and wake/sleep lifecycle.

Key insight: "Subconscious builds state, agent just reads it."

The agent becomes stateless - it receives assembled context and returns
a response. All state management lives here in the subconscious.

Architecture:
    ThreadRegistry ← holds all registered adapters
    SubconsciousCore ← manages lifecycle (wake/sleep) and health
    Orchestrator   ← builds STATE blocks (see orchestrator.py)
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
        
        Marks system as asleep. Loop/trigger shutdown is handled
        by the module-level sleep() in __init__.py.
        """
        if not self._awake:
            return
        
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
