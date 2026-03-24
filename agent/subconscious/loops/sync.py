"""
Sync Loop
=========
Periodically syncs state across threads.
"""

from .base import BackgroundLoop, LoopConfig


class SyncLoop(BackgroundLoop):
    """
    Periodically syncs state across threads.
    
    Ensures all threads have consistent view of state,
    persists pending changes, and reconciles conflicts.
    """
    
    def __init__(self, interval: float = 600.0):  # 10 minutes
        config = LoopConfig(
            interval_seconds=interval,
            name="sync",
            enabled=True
        )
        super().__init__(config, self._sync)
    
    def _sync(self) -> str:
        """Sync state across threads. Returns summary."""
        try:
            from agent.subconscious.core import get_core
            
            core = get_core()
            synced = 0
            
            for adapter in core.registry.get_all():
                if hasattr(adapter, 'sync'):
                    adapter.sync()
                    synced += 1
            
            result = f"Synced {synced}/{core.registry.count()} threads"
            
            from agent.threads.log import log_event
            log_event(
                "system:sync",
                "sync_loop",
                result
            )
            return result
        except Exception as e:
            return f"Sync error: {e}"
