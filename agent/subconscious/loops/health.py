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

            # ── Predictive pulse ──────────────────────────────────────
            # Cheap forward-model checks: each registered prediction asks
            # "what should be true right now?" and emits prediction_error
            # events when it isn't. Runs every heartbeat. No LLM.
            try:
                from agent.subconscious import predictions as _pred
                violations = _pred.check_all(emit_events=True)
                if violations:
                    lines.append(
                        f"predictions: {len(violations)} violation(s) — "
                        + ", ".join(f"{v.prediction}({v.severity})" for v in violations[:3])
                    )
                else:
                    lines.append("predictions: ok")
            except Exception as _pe:
                lines.append(f"predictions: error: {_pe}")

            # ── Coma-mode programmatic substrate ──────────────────────
            # Every heartbeat: graph touch from new events, periodic
            # outcome tally, self-fact refresh, throttled decay. No LLM.
            # Lets STATE evolve when every loop is gated.
            try:
                from agent.subconscious import coma as _coma
                csum = _coma.run_once()
                bits = []
                if csum.get("events_touched"):
                    bits.append(
                        f"touched={csum['events_touched']}/edges={csum.get('edges_touched', 0)}"
                    )
                if csum.get("graph_pruned"):
                    bits.append(f"graph_pruned={csum['graph_pruned']}")
                if csum.get("facts_decayed"):
                    bits.append(f"facts_decayed={csum['facts_decayed']}")
                if csum.get("compression_written"):
                    bits.append("compression=yes")
                if csum.get("fts_added"):
                    bits.append(f"fts+={csum['fts_added']}")
                if csum.get("seq_mined"):
                    bits.append("seq=yes")
                if csum.get("slots_touched"):
                    bits.append(f"slots+={csum['slots_touched']}")
                if csum.get("seq_predictions_added"):
                    bits.append(f"seq_pred+={csum['seq_predictions_added']}")
                if csum.get("contradictions_emitted"):
                    bits.append(f"contra={csum['contradictions_emitted']}")
                if csum.get("state_changed"):
                    bits.append(f"state_fp={csum.get('state_fp', '')}")
                self_info = csum.get("self") or {}
                if self_info:
                    bits.append(
                        f"uptime={self_info.get('uptime_h', 0)}h "
                        f"hb={self_info.get('heartbeats', 0)}"
                    )
                lines.append(
                    "coma: " + (", ".join(bits) if bits else "idle")
                )
            except Exception as _ce:
                lines.append(f"coma: error: {_ce}")

            return "\n".join(lines) if lines else "No threads registered"

        except Exception as e:
            return f"Health check error: {e}"
