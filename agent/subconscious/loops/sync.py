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
    
    def _sync(self) -> None:
        """Sync state across threads."""
        try:
            from agent.subconscious.core import get_core
            
            core = get_core()
            
            for adapter in core.registry.get_all():
                if hasattr(adapter, 'sync'):
                    adapter.sync()
            
            from agent.threads.log import log_event
            log_event(
                "system:sync",
                "sync_loop",
                f"Synced {core.registry.count()} threads"
            )
        except Exception:
            pass  # Best effort
