"""
Log Thread Adapter
==================

Provides temporal awareness and history to Agent.

This thread answers: "What has happened? When? How long have we been talking?"

Log events use RECENCY-based levels, not depth-based:
- L1 = Last 10 events (quick context)
- L2 = Last 100 events (conversational history)  
- L3 = Last 1000 events (full timeline)

Weight represents temporal importance for concept mapping.

Modules:
- events: System events (start, stop, errors)
- sessions: Conversation session metadata
- temporal: Time-based patterns and facts
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

try:
    from agent.threads.base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from agent.threads.log.schema import pull_log_events
except ImportError:
    from ..base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from .schema import pull_log_events

# Recency limits per context level
LOG_LIMITS = {1: 10, 2: 100, 3: 1000}

# Event type relevance scores for sparse activation (0-10 scale)
# Used with score_thread_relevance() for three-tier gating
EVENT_TYPE_RELEVANCE = {
    "agent_turn": 9,  # Highest: deliberate coder/agent turn boundaries
    "turn_outcome": 9,# Highest: did the prior turn's work survive?
    "convo": 8,       # High: Conversation events (direct interaction)
    "memory": 7,      # High: Memory/reflection events (cognitive)
    "tool_call": 7,   # High: explicit tool invocations
    "code_change": 7, # High: files written by the coder/agent
    "user_action": 6, # Medium-High: User actions (significant)
    "file": 4,        # Medium: File operations (context dependent)
    "system": 2,      # Low: System events (background)
    "activation": 1   # Low: Activation patterns (technical)
}


class LogThreadAdapter(BaseThreadAdapter):
    """
    Thread adapter for temporal awareness — events, sessions, history.
    
    Log uses recency-based levels:
    - L1 = 10 most recent (quick glance)
    - L2 = 100 most recent (conversation context)
    - L3 = 1000 most recent (full history)
    """
    
    _name = "log"
    _description = "Temporal awareness and history"
    
    def __init__(self):
        super().__init__()
        self._session_start: Optional[datetime] = None
        self._message_count: int = 0
        self._session_id: Optional[str] = None

    def _ensure_session(self) -> None:
        """Auto-start a session if one isn't active."""
        if self._session_start is None:
            self.start_session()
    
    def get_data(self, level: int = 2, limit: int = None) -> List[Dict]:
        """
        Get log data by recency level.
        
        Level determines how far back to look:
        - L1 = 10 events
        - L2 = 100 events
        - L3 = 1000 events
        """
        recency_limit = limit or LOG_LIMITS.get(level, 100)
        all_data = []
        
        for module in ["events", "sessions"]:
            rows = pull_log_events(module_name=module, limit=recency_limit)
            for row in rows:
                all_data.append({**row, "module": module})
        
        # Sort by timestamp descending
        all_data.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return all_data[:recency_limit]
    
    def start_session(self) -> str:
        """Start a new conversation session."""
        self._session_start = datetime.now(timezone.utc)
        self._message_count = 0
        session_id = self._session_start.strftime("%Y%m%d_%H%M%S")
        self._session_id = session_id
        
        self.push(
            module="sessions",
            key=f"session_{session_id}",
            metadata={"type": "session", "description": "Conversation session"},
            data={
                "start_time": self._session_start.isoformat(),
                "status": "active",
            },
            level=1,
            weight=0.5
        )
        
        return session_id
    
    def log_event(
        self,
        event_type: str,
        source: str,
        message: str,
        weight: float = 0.3
    ) -> None:
        """Log a system event with weight."""
        timestamp = datetime.now(timezone.utc)
        
        self.push(
            module="events",
            key=f"evt_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}",
            metadata={"type": event_type, "source": source},
            data={"message": message, "timestamp": timestamp.isoformat()},
            level=1,
            weight=weight
        )
    
    def record_message(self) -> None:
        """Record that a message was exchanged."""
        self._message_count += 1
    
    def get_session_duration(self) -> Optional[float]:
        """Get current session duration in seconds."""
        if self._session_start:
            delta = datetime.now(timezone.utc) - self._session_start
            return delta.total_seconds()
        return None
    
    def get_recent_events(self, limit: int = 10) -> List[Dict]:
        """Get recent events from the unified log.

        Returns events shaped for downstream consumers:
            - event_type (str)
            - source (str)
            - timestamp (str)
            - data (dict with 'message' / 'timestamp' keys)
            - metadata (dict)
            - weight (float)
        """
        try:
            from .schema import get_events
        except ImportError:
            from agent.threads.log.schema import get_events
        rows = get_events(limit=limit)
        shaped: List[Dict] = []
        for r in rows:
            raw_data = r.get("data")
            if isinstance(raw_data, dict):
                data = raw_data
            elif isinstance(raw_data, str) and raw_data:
                # unified_events stores a plain string in data;
                # present it as the event's 'message' so the existing
                # _get_raw_facts formatter works.
                data = {"message": raw_data, "timestamp": r.get("timestamp", "")}
            else:
                data = {"message": "", "timestamp": r.get("timestamp", "")}
            meta = r.get("metadata") or {}
            if isinstance(meta, str):
                import json as _json
                try:
                    meta = _json.loads(meta) or {}
                except Exception:
                    meta = {}
            if not isinstance(meta, dict):
                meta = {}
            meta.setdefault("type", r.get("event_type", "system"))
            meta.setdefault("source", r.get("source", ""))
            shaped.append({
                "event_type": r.get("event_type", ""),
                "source": r.get("source", ""),
                "timestamp": r.get("timestamp", ""),
                "data": data,
                "metadata": meta,
                "weight": 0.5,
            })
        return shaped
    
    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """Get recent sessions."""
        return pull_log_events(module_name="sessions", limit=limit)
    
    def health(self) -> HealthReport:
        """Check log thread health by counting recent events."""
        try:
            from .schema import get_events
            events = get_events(limit=10)
            total = len(events)
            
            if total > 0:
                return HealthReport.ok(f"{total} log entries", row_count=total)
            else:
                return HealthReport.ok("Ready", row_count=0)
        except Exception as e:
            return HealthReport.error(f"Log health check failed: {e}")

    def _get_raw_facts(self, min_weight: float = 0.0, limit: int = 50) -> List[Dict]:
        """Get raw facts with l1/l2/l3 value tiers for _budget_fill.

        Returns dicts with: path, l1_value, l2_value, l3_value, weight.
        """
        self._ensure_session()
        raw: List[Dict] = []

        # Session metadata — always high weight (temporal context)
        duration = self.get_session_duration()
        if duration:
            if duration < 60:
                dur_str = f"{int(duration)}s"
            elif duration < 3600:
                dur_str = f"{int(duration / 60)}m"
            else:
                dur_str = f"{duration / 3600:.1f}h"
            raw.append({
                "path": "log.session.duration",
                "l1_value": dur_str,
                "l2_value": f"Session active for {dur_str}",
                "l3_value": (
                    f"Current session started at "
                    f"{self._session_start.isoformat()}, active for {dur_str}"
                ),
                "weight": 0.9,
            })

        if self._message_count > 0:
            raw.append({
                "path": "log.session.messages",
                "l1_value": str(self._message_count),
                "l2_value": f"{self._message_count} messages exchanged",
                "l3_value": (
                    f"{self._message_count} messages exchanged in current session"
                ),
                "weight": 0.8,
            })

        # Events — convert to l1/l2/l3 dicts. Age-decay weights so an event
        # from 11 days ago doesn't compete with one from 11 minutes ago.
        # Half-life = 24h: a day-old event has its weight halved.
        import math as _math
        from datetime import datetime as _dt, timezone as _tz
        _now = _dt.now(_tz.utc)
        _HALF_LIFE_HOURS = 24.0

        events = self.get_recent_events(limit)
        for i, evt in enumerate(events):
            meta = evt.get("metadata", {})
            event_type = meta.get("type", "system")
            event_type_clean = (
                event_type.split(":")[0] if ":" in event_type else event_type
            )
            source = meta.get("source", "")
            data = evt.get("data", {})
            msg = data.get("message", "")
            timestamp = data.get("timestamp", "") or evt.get("timestamp", "")
            stored_weight = evt.get("weight", 0.3)

            if not msg or stored_weight < min_weight:
                continue

            # Blend stored weight with event-type relevance
            type_relevance = EVENT_TYPE_RELEVANCE.get(event_type_clean, 3) / 10.0
            weight = max(stored_weight, type_relevance)

            # Age decay
            age_hours: Optional[float] = None
            if timestamp:
                try:
                    ts_str = str(timestamp).replace("Z", "+00:00")
                    if "+" not in ts_str and "T" in ts_str:
                        ts_str += "+00:00"
                    ts = _dt.fromisoformat(ts_str)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=_tz.utc)
                    age_hours = max(0.0, (_now - ts).total_seconds() / 3600.0)
                except Exception:
                    age_hours = None
            if age_hours is not None:
                decay = _math.exp(-age_hours / _HALF_LIFE_HOURS)
                weight = weight * decay
                if weight < min_weight:
                    continue

            raw.append({
                "path": f"log.events.{i}",
                "l1_value": f"{msg[:40]} [{event_type_clean}]",
                "l2_value": f"{msg[:80]} [{event_type_clean}]",
                "l3_value": (
                    f"{msg} [{event_type_clean}] source={source} at={timestamp}"
                ),
                "weight": weight,
            })

        # Task queue — pending and recently-finished cloud-LLM jobs
        # queued by Copilot (or any surface) for AIOS to do the thinking.
        # High weight so they show up in lean STATE too.
        try:
            from agent.threads.log.schema import (
                list_pending_tasks, list_recent_tasks
            )
            for t in list_pending_tasks(limit=5):
                preview = (t.get("kind", "") + ": " + str(t.get("requested_by", "")))
                raw.append({
                    "path": f"log.tasks.pending.#{t['id']}",
                    "l1_value": f"#{t['id']} {t['kind']}",
                    "l2_value": f"#{t['id']} {t['kind']} (role={t['role']}, by={t['requested_by']})",
                    "l3_value": (
                        f"#{t['id']} kind={t['kind']} role={t['role']} "
                        f"by={t['requested_by']} biz={t.get('business_id') or '-'} "
                        f"queued={t.get('created_at')} attempts={t.get('attempts',0)}"
                    ),
                    "weight": 0.85,
                })
            for t in list_recent_tasks(limit=5):
                status = t.get("status", "?")
                tag = "[ok]" if status == "done" else f"[{status}]"
                # Age-decay finished tasks (4h half-life — they're stale fast).
                # Failures decay slower (24h) so they stay visible.
                w_base = 0.7 if status == "done" else 0.85
                fin = t.get("finished_at") or t.get("created_at")
                if fin:
                    try:
                        ts_str = str(fin).replace("Z", "+00:00")
                        if "+" not in ts_str and "T" in ts_str:
                            ts_str += "+00:00"
                        ts = _dt.fromisoformat(ts_str)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=_tz.utc)
                        age_h = max(0.0, (_now - ts).total_seconds() / 3600.0)
                        hl = 4.0 if status == "done" else 24.0
                        w_base *= _math.exp(-age_h / hl)
                    except Exception:
                        pass
                raw.append({
                    "path": f"log.tasks.recent.#{t['id']}",
                    "l1_value": f"#{t['id']} {t['kind']} {tag}",
                    "l2_value": f"#{t['id']} {t['kind']} {tag} -> {t.get('preview','')[:60]}",
                    "l3_value": (
                        f"#{t['id']} kind={t['kind']} status={status} "
                        f"model={t.get('model_used') or '-'} "
                        f"dur_ms={t.get('duration_ms') or 0} "
                        f"finished={t.get('finished_at')} :: {t.get('preview','')[:200]}"
                    ),
                    "weight": w_base,
                })
        except Exception:
            pass

        return raw[:limit]
    
    def get_section_metadata(self) -> List[str]:
        """Permanent log metadata for STATE section header."""
        try:
            lines = []
            if hasattr(self, '_session_id') and self._session_id:
                lines.append(f"  session: {self._session_id}")
            if hasattr(self, '_session_start') and self._session_start:
                elapsed = (datetime.now(timezone.utc) - self._session_start).total_seconds()
                if elapsed < 3600:
                    lines.append(f"  duration: {int(elapsed // 60)}m")
                else:
                    lines.append(f"  duration: {elapsed / 3600:.1f}h")
            if hasattr(self, '_message_count'):
                lines.append(f"  messages: {self._message_count}")
            try:
                from agent.threads.log.schema import get_log_stats
                stats = get_log_stats()
                lines.append(f"  total_events: {stats.get('total_events', 0)}")
            except Exception:
                pass
            # current_intent — the summary string from the most recent
            # agent_turn event (set by scripts/turn_start.py "<summary>").
            # Surfaces "what is this turn trying to do?" at the top of
            # [log], independent of the longer recent_agent_turns trail
            # below. If a coder/agent forgets to pass a summary, this is
            # missing — that absence itself is signal.
            try:
                from data.db import get_connection
                conn = get_connection(readonly=True)
                row = conn.execute("""
                    SELECT data, timestamp FROM unified_events
                    WHERE event_type = 'agent_turn'
                    ORDER BY id DESC LIMIT 1
                """).fetchone()
                if row and row["data"]:
                    txt = str(row["data"]).strip()
                    if txt.startswith("VS Code coding turn: "):
                        txt = txt[len("VS Code coding turn: "):]
                    txt = txt[:160]
                    ts = str(row["timestamp"] or "").split(".")[0]
                    # Compute age so the reader knows if this is now or stale.
                    age_str = ""
                    try:
                        dt = datetime.fromisoformat(
                            ts.replace(" ", "T").replace("Z", "+00:00")
                        )
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        age_s = (datetime.now(timezone.utc) - dt).total_seconds()
                        if age_s < 60:
                            age_str = f" ({int(age_s)}s ago)"
                        elif age_s < 3600:
                            age_str = f" ({int(age_s // 60)}m ago)"
                        else:
                            age_str = f" ({age_s / 3600:.1f}h ago)"
                    except Exception:
                        pass
                    lines.append(f"  current_intent: {txt}{age_str}")
            except Exception:
                pass
            # Idle time since last event (answers "is the world still moving?")
            try:
                from data.db import get_connection
                conn = get_connection(readonly=True)
                row = conn.execute(
                    "SELECT timestamp FROM unified_events ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if row and row["timestamp"]:
                    last_ts = str(row["timestamp"]).replace("T", " ").split(".")[0]
                    try:
                        # Robust parse — handle 'YYYY-MM-DD HH:MM:SS' or ISO
                        dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        idle = (datetime.now(timezone.utc) - dt).total_seconds()
                        if idle < 60:
                            idle_str = f"{int(idle)}s"
                        elif idle < 3600:
                            idle_str = f"{int(idle // 60)}m"
                        else:
                            idle_str = f"{idle / 3600:.1f}h"
                        lines.append(f"  idle_since_last_event: {idle_str}")
                    except Exception:
                        pass
            except Exception:
                pass
            # Event type distribution last hour (triage signal)
            try:
                from data.db import get_connection
                conn = get_connection(readonly=True)
                rows = conn.execute("""
                    SELECT event_type, COUNT(*) as cnt
                    FROM unified_events
                    WHERE timestamp >= datetime('now', '-1 hour')
                    GROUP BY event_type
                    ORDER BY cnt DESC
                    LIMIT 5
                """).fetchall()
                if rows:
                    parts = [f"{r['event_type']}={r['cnt']}" for r in rows]
                    lines.append(f"  last_hour: {', '.join(parts)}")
            except Exception:
                pass
            # Recent agent turns — "where was I" trail for the coding
            # agent (VS Code / future-me).  Answers: what did my prior
            # selves work on, before this turn?
            try:
                from data.db import get_connection
                import json as _json
                conn = get_connection(readonly=True)
                rows = conn.execute("""
                    SELECT data, metadata_json, timestamp
                    FROM unified_events
                    WHERE event_type = 'agent_turn'
                    ORDER BY id DESC
                    LIMIT 5
                """).fetchall()
                if rows:
                    lines.append("  recent_agent_turns:")
                    for r in rows:
                        txt = (r["data"] or "").strip()
                        if txt.startswith("VS Code coding turn: "):
                            txt = txt[len("VS Code coding turn: "):]
                        txt = txt[:80]
                        fcount = ""
                        if r["metadata_json"]:
                            try:
                                md = _json.loads(r["metadata_json"]) or {}
                                # New rows carry the exact count; old rows
                                # only have a capped list.  Prefer the count.
                                n = md.get("files_touched_count")
                                if n is None:
                                    files = md.get("files_touched") or []
                                    n = len(files) if files else 0
                                if n:
                                    fcount = f" ({n} files)"
                                # Grade tag (written by turn_start's
                                # _grade_prior_turn on the NEXT turn).
                                g = md.get("graded_status")
                                if g:
                                    fcount += f" [{g}]"
                            except Exception:
                                pass
                        ts = str(r["timestamp"] or "").split(".")[0]
                        lines.append(f"    - {ts}  {txt}{fcount}")
            except Exception:
                pass
            # [consequences] — working-tree state surfaced inside STATE so
            # the reader (agent or coder) sees *right now* whether the
            # system is in a clean, dirty, or stop-and-commit state.
            try:
                import subprocess as _sp
                import time as _t
                import os as _os
                proj_root = _os.path.abspath(
                    _os.path.join(_os.path.dirname(__file__), "..", "..", "..")
                )
                SOFT, HARD, STALE_H = 10, 25, 4.0  # match scripts/turn_start.py
                uncommitted: List[str] = []
                r = _sp.run(
                    ["git", "status", "--porcelain"],
                    cwd=proj_root, capture_output=True, text=True, timeout=2,
                )
                if r.returncode == 0:
                    for ln in r.stdout.splitlines():
                        p = ln[3:].strip()
                        if p:
                            uncommitted.append(p)
                last_commit_age_s: Optional[int] = None
                r = _sp.run(
                    ["git", "log", "-1", "--format=%ct", "HEAD"],
                    cwd=proj_root, capture_output=True, text=True, timeout=2,
                )
                if r.returncode == 0 and r.stdout.strip():
                    try:
                        last_commit_age_s = int(_t.time() - int(r.stdout.strip()))
                    except Exception:
                        last_commit_age_s = None
                if uncommitted or last_commit_age_s is not None:
                    lines.append("  consequences:")
                    lines.append(f"    uncommitted: {len(uncommitted)} file(s)")
                    if last_commit_age_s is not None:
                        if last_commit_age_s < 3600:
                            age_s = f"{last_commit_age_s // 60}m"
                        elif last_commit_age_s < 86400:
                            age_s = f"{last_commit_age_s / 3600:.1f}h"
                        else:
                            age_s = f"{last_commit_age_s / 86400:.1f}d"
                        lines.append(f"    last_commit: {age_s} ago")
                    n = len(uncommitted)
                    if n >= HARD:
                        lines.append(
                            f"    status: HARD_LIMIT  ({n} >= {HARD}) — commit before next change"
                        )
                    elif n >= SOFT:
                        lines.append(
                            f"    status: soft_limit  ({n} >= {SOFT}) — consider a checkpoint commit"
                        )
                    else:
                        lines.append("    status: ok")
            except Exception:
                pass
            # Unread pings — dashboard notes the user may have left for us.
            try:
                from data.db import get_connection
                from contextlib import closing as _closing
                with _closing(get_connection(readonly=True)) as _conn:
                    row = _conn.execute(
                        "SELECT COUNT(*) FROM notifications "
                        "WHERE read = 0 AND dismissed = 0"
                    ).fetchone()
                    unread = (row[0] if row else 0) or 0
                    recent_preview = ""
                    if unread:
                        pr = _conn.execute(
                            "SELECT substr(message, 1, 120) FROM notifications "
                            "WHERE read = 0 AND dismissed = 0 "
                            "ORDER BY id DESC LIMIT 1"
                        ).fetchone()
                        recent_preview = pr[0] if pr else ""
                if unread:
                    lines.append(f"  pings_unread: {unread}")
                    if recent_preview:
                        lines.append(f"  pings_latest: {recent_preview}")
            except Exception:
                pass
            # Last DB checkpoint to VM replica (log.checkpoint module)
            try:
                from agent.threads.log.checkpoint import get_last_checkpoint
                cp = get_last_checkpoint()
                if cp:
                    lines.append(
                        f"  last_checkpoint: {cp['age_human']} ago [{cp['status_label']}]"
                    )
            except Exception:
                pass
            # Task queue — pending/running cloud-LLM jobs queued by the
            # Copilot agent (or other surfaces) for AIOS to think on.
            # Surfacing here means the next turn-start sees what's in flight,
            # what just finished, and any rate-limit drag.
            try:
                from agent.threads.log.schema import task_counts
                counts = task_counts()
                if counts:
                    parts = [f"{k}={v}" for k, v in counts.items()]
                    lines.append(f"  tasks: {', '.join(parts)}")
            except Exception:
                pass
            # Loop scheduler — single-flight + idle awareness
            try:
                from agent.subconscious.loops import scheduler as _sched
                s = _sched.summary()
                if s.get("current_loop"):
                    lines.append(
                        f"  loop_running: {s['current_loop']} "
                        f"({s.get('current_age', 0)}s)"
                    )
                if s.get("user_active"):
                    lines.append(
                        f"  user_active: yes "
                        f"(idle={int(s.get('user_idle_seconds') or 0)}s)"
                    )
                skips = s.get("skip_counts") or {}
                if skips:
                    skip_parts = [
                        f"{n}={c}" for n, c in sorted(
                            skips.items(), key=lambda kv: -kv[1]
                        )[:3]
                    ]
                    lines.append(f"  loop_skips: {', '.join(skip_parts)}")
            except Exception:
                pass
            # Rate gate — provider cooldowns
            try:
                from agent.services import rate_gate as _rg
                rg = _rg.status()
                gc = rg.get("global_cooldown_remaining") or 0
                if gc and gc > 0:
                    lines.append(f"  global_cooldown: {int(gc)}s")
                providers = rg.get("providers") or {}
                cooling = [
                    (n, p) for n, p in providers.items()
                    if (p.get("cooldown_remaining") or 0) > 0
                ]
                if cooling:
                    parts = [
                        f"{n}={int(p['cooldown_remaining'])}s" for n, p in cooling
                    ]
                    lines.append(f"  cooling: {', '.join(parts)}")
                # Total 429s last hour-ish (running counter)
                total_429 = sum(
                    int(p.get("total_429s") or 0) for p in providers.values()
                )
                if total_429:
                    lines.append(f"  total_429s_session: {total_429}")
            except Exception:
                pass
            # Predictive reflex — last heartbeat's forward-model violations
            try:
                from agent.subconscious import predictions as _pred
                viols = _pred.last_violations()
                # Fresh process (e.g. turn_start.py CLI) has no cache —
                # do a cheap dry-run so STATE always reflects reality.
                if not viols:
                    try:
                        viols = _pred.check_all(emit_events=False)
                    except Exception:
                        viols = []
                if viols:
                    by_sev: Dict[str, int] = {}
                    for v in viols:
                        by_sev[v.severity] = by_sev.get(v.severity, 0) + 1
                    sev_str = ", ".join(
                        f"{s}={c}" for s, c in sorted(
                            by_sev.items(),
                            key=lambda kv: {"high": 0, "medium": 1, "low": 2}.get(kv[0], 9),
                        )
                    )
                    lines.append(f"  prediction_errors: {len(viols)} ({sev_str})")
                    # Surface top 3 in detail so the agent can act
                    for v in viols[:3]:
                        lines.append(
                            f"    - [{v.severity}] {v.prediction}: {v.detail[:120]}"
                        )
            except Exception:
                pass
            # Coma substrate — last heartbeat's programmatic touches.
            # Surfaces the system breathing without LLM calls.
            try:
                from agent.subconscious import coma as _coma
                cs = _coma.last_summary()
                if cs:
                    self_info = cs.get("self") or {}
                    bits = []
                    if self_info.get("uptime_h") is not None:
                        bits.append(f"uptime={self_info['uptime_h']}h")
                    if self_info.get("heartbeats"):
                        bits.append(f"hb={self_info['heartbeats']}")
                    if self_info.get("last_llm_age_h") is not None:
                        bits.append(f"last_llm={self_info['last_llm_age_h']}h")
                    if cs.get("events_touched"):
                        bits.append(f"touched={cs['events_touched']}")
                    if cs.get("edges_touched"):
                        bits.append(f"edges={cs['edges_touched']}")
                    if cs.get("graph_pruned"):
                        bits.append(f"pruned={cs['graph_pruned']}")
                    if cs.get("fts_added"):
                        bits.append(f"fts+={cs['fts_added']}")
                    if cs.get("slots_touched"):
                        bits.append(f"slots+={cs['slots_touched']}")
                    if cs.get("seq_predictions_added"):
                        bits.append(f"seq_pred+={cs['seq_predictions_added']}")
                    if cs.get("contradictions_emitted"):
                        bits.append(f"contra={cs['contradictions_emitted']}")
                    if cs.get("state_changed"):
                        bits.append(f"state_fp={cs.get('state_fp', '')}")
                    if bits:
                        lines.append("  coma: " + ", ".join(bits))
            except Exception:
                pass
            # Session topic — rolling compression from reflex_meta_thoughts
            # (no new table; we reuse the Phase 1 meta store)
            try:
                from agent.threads.reflex.schema import get_recent_meta_thoughts
                sess = getattr(self, "_session_id", None)
                if sess:
                    recent = get_recent_meta_thoughts(
                        session_id=sess,
                        kinds=["compression"],
                        limit=3,
                    )
                    if recent:
                        topic = recent[0].get("content", "")
                        if topic:
                            topic = topic[:120].replace("\n", " ").strip()
                            lines.append(f"  topic: {topic}")
            except Exception:
                pass
            return lines
        except Exception:
            return []

    def get_section_rules(self) -> List[str]:
        return [
            "  rules:",
            "  - Events shown are a sample. Do not fabricate events not listed here.",
            "  - To see more history, ask the user or use search tools.",
        ]

    def introspect(self, context_level: int = 2, query: str = None, threshold: float = 0.0) -> IntrospectionResult:
        """
        Log introspection with budget-aware fact packing.

        Uses _budget_fill to fit temporal facts within a per-level
        token budget.  Top facts get full detail; tail facts are
        downgraded to L1 so context stays compact.

        Args:
            context_level: HEA level (1=lean, 2=medium, 3=full)
            query: Optional query for relevance filtering
            threshold: Thread relevance score (0-10, inverted by orchestrator)
        """
        relevant_concepts: List[str] = []

        min_weight = threshold / 10.0
        raw = self._get_raw_facts(min_weight=min_weight)

        if query:
            raw, relevant_concepts = self._relevance_boost(raw, query)

        facts = self._budget_fill(raw, context_level, query=query)

        return IntrospectionResult(
            facts=facts,
            state=self.get_metadata(),
            context_level=context_level,
            health=self.health().to_dict(),
            relevant_concepts=relevant_concepts,
        )


__all__ = ["LogThreadAdapter"]
