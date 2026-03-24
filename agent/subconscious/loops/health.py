"""
Health Loop
===========
Periodically checks health of all threads.
"""

from typing import Dict, Any

from .base import BackgroundLoop, LoopConfig


class HealthLoop(BackgroundLoop):
    """
    Periodically checks health of all threads.
    
    Logs anomalies and can trigger alerts for degraded threads.
    """
    
    def __init__(self, interval: float = 60.0):  # 1 minute
        config = LoopConfig(
            interval_seconds=interval,
            name="health",
            enabled=True
        )
        super().__init__(config, self._check_health)
        self._last_status: Dict[str, str] = {}
    
    def _check_health(self) -> str:
        """Check health of all registered threads. Returns summary."""
        try:
            from agent.subconscious.core import get_core
            from agent.threads.base import ThreadStatus
            
            core = get_core()
            health_reports = core.registry.health_all()
            
            lines = []
            for name, report in health_reports.items():
                current_status = report.status.value
                previous_status = self._last_status.get(name, "unknown")
                
                if current_status != previous_status:
                    from agent.threads.log import log_event
                    
                    level = "WARN" if report.status in (ThreadStatus.ERROR, ThreadStatus.DEGRADED) else "INFO"
                    log_event(
                        "system:health",
                        "health_loop",
                        f"Thread '{name}' status: {previous_status} → {current_status}",
                        level=level
                    )
                    lines.append(f"{name}: {previous_status} → {current_status}")
                else:
                    lines.append(f"{name}: {current_status}")
                
                self._last_status[name] = current_status
            
            return "\n".join(lines) if lines else "No threads registered"
                
        except Exception as e:
            return f"Health check error: {e}"
