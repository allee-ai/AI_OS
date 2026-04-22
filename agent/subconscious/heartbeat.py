"""
Heartbeat
=========

One tick every AIOS_HEARTBEAT_INTERVAL seconds (default 60).

Purpose:
    - Take a snapshot of system pressure (pending counts, idle time,
      ollama gate, meta-thought rate, loop status).
    - Run passive *faculties* (see faculties.py) that may nudge loops
      to fire early OR skip based on the snapshot.
    - Persist the snapshot to `heartbeat_ticks` so the dashboard and
      the STATE block can surface it.

The existing 12 background loops keep their own timers and their
pause controls.  The heartbeat is a *coordinator*, not a replacement.

Env flags:
    AIOS_HEARTBEAT              — 1 to start loop (default 1)
    AIOS_HEARTBEAT_INTERVAL     — seconds between ticks (default 60)
    AIOS_HEARTBEAT_IDLE_MIN     — min seconds since last user turn
                                  before heartbeat may fire "quiet"
                                  faculties (default 120)
    AIOS_HEARTBEAT_FACULTIES    — 1 to let faculties mutate loops
                                  (default 1; set 0 for pure observer)
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .loops.base import BackgroundLoop, LoopConfig


# ─────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────

def _ensure_table() -> None:
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS heartbeat_ticks (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts            TEXT NOT NULL DEFAULT (datetime('now')),
                    snapshot_json TEXT NOT NULL,
                    actions_json  TEXT NOT NULL DEFAULT '[]',
                    duration_ms   INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()
    except Exception as e:
        print(f"[Heartbeat] table init failed: {e}")


def _write_tick(snapshot: Dict[str, Any],
                actions: List[str],
                duration_ms: int) -> int:
    _ensure_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO heartbeat_ticks (snapshot_json, actions_json, duration_ms) "
                "VALUES (?, ?, ?)",
                (json.dumps(snapshot, default=str),
                 json.dumps(actions),
                 int(duration_ms))
            )
            conn.commit()
            return cur.lastrowid or 0
    except Exception:
        return 0


def get_recent_ticks(limit: int = 20) -> List[Dict[str, Any]]:
    """Public read used by the dashboard API."""
    _ensure_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                "SELECT id, ts, snapshot_json, actions_json, duration_ms "
                "FROM heartbeat_ticks ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            out = []
            for r in rows:
                try:
                    snap = json.loads(r[2] or "{}")
                except Exception:
                    snap = {}
                try:
                    acts = json.loads(r[3] or "[]")
                except Exception:
                    acts = []
                out.append({
                    "id": r[0], "ts": r[1],
                    "snapshot": snap, "actions": acts,
                    "duration_ms": r[4],
                })
            return out
    except Exception:
        return []


def get_latest_snapshot() -> Dict[str, Any]:
    """Latest snapshot dict, or {} if none."""
    ticks = get_recent_ticks(limit=1)
    if not ticks:
        return {}
    return ticks[0].get("snapshot") or {}


# ─────────────────────────────────────────────────────────────
# Snapshot builder — each probe is independent try/except → default
# ─────────────────────────────────────────────────────────────

def _count(sql: str, *args) -> int:
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            row = conn.execute(sql, args).fetchone()
            if not row:
                return 0
            return int(row[0] or 0)
    except Exception:
        return 0


def _last_turn_age_seconds() -> Optional[float]:
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            row = conn.execute(
                "SELECT MAX(created_at) FROM convo_turns"
            ).fetchone()
            if not row or not row[0]:
                return None
            ts = row[0]
            # created_at is 'YYYY-MM-DD HH:MM:SS' UTC in SQLite default.
            try:
                last = datetime.fromisoformat(ts.replace("Z", ""))
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
            except Exception:
                return None
            return max(0.0, (datetime.now(timezone.utc) - last).total_seconds())
    except Exception:
        return None


def _ollama_gate_busy() -> bool:
    """Best-effort: True if the Ollama semaphore has no free slot right now."""
    try:
        from .loops.base import _ollama_gate  # type: ignore
        # Semaphore has a private `_value` on CPython; we don't need to be
        # exact — just indicate pressure.
        val = getattr(_ollama_gate, "_value", None)
        if isinstance(val, int):
            return val <= 0
    except Exception:
        pass
    return False


def _loop_states() -> Dict[str, Any]:
    """Grab the current LoopManager's per-loop status."""
    out: Dict[str, Any] = {}
    try:
        from agent.subconscious import _loop_manager  # type: ignore
        if _loop_manager is None:
            return out
        for stats in _loop_manager.get_stats():
            out[stats.get("name", "?")] = {
                "status":        stats.get("status"),
                "is_busy":       stats.get("is_busy"),
                "last_run":      stats.get("last_run"),
                "run_count":     stats.get("run_count"),
                "error_count":   stats.get("error_count"),
                "last_duration": stats.get("last_duration"),
            }
    except Exception:
        pass
    return out


def _meta_rate_last_hour() -> int:
    return _count(
        "SELECT COUNT(*) FROM reflex_meta_thoughts "
        "WHERE created_at >= datetime('now','-1 hour')"
    )


def _pending_unknowns() -> int:
    return _count(
        "SELECT COUNT(*) FROM reflex_meta_thoughts "
        "WHERE kind='unknown' AND (graded IS NULL OR graded=0)"
    )


def build_snapshot() -> Dict[str, Any]:
    """Read-only, best-effort pressure snapshot."""
    idle_min = float(os.getenv("AIOS_HEARTBEAT_IDLE_MIN", "120"))
    last_turn_age = _last_turn_age_seconds()
    user_present = (last_turn_age is not None and last_turn_age < idle_min)

    snap: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "user_present": user_present,
        "last_turn_age_seconds": last_turn_age,
        "ollama_busy": _ollama_gate_busy(),
        "counts": {
            "temp_memory_pending": _count(
                "SELECT COUNT(*) FROM temp_facts WHERE status='pending'"
            ),
            "temp_memory_pending_review": _count(
                "SELECT COUNT(*) FROM temp_facts WHERE status='pending_review'"
            ),
            "temp_memory_approved": _count(
                "SELECT COUNT(*) FROM temp_facts WHERE status='approved'"
            ),
            "proposed_goals_pending": _count(
                "SELECT COUNT(*) FROM proposed_goals WHERE status='pending'"
            ),
            "proposed_goals_approved": _count(
                "SELECT COUNT(*) FROM proposed_goals WHERE status='approved'"
            ),
            "proposed_improvements_pending": _count(
                "SELECT COUNT(*) FROM proposed_improvements WHERE status='pending'"
            ),
            "tasks_pending": _count(
                "SELECT COUNT(*) FROM tasks WHERE status='pending'"
            ),
            "tasks_executing": _count(
                "SELECT COUNT(*) FROM tasks WHERE status='executing'"
            ),
            "notifications_unread": _count(
                "SELECT COUNT(*) FROM notifications WHERE read=0 AND dismissed=0"
            ),
            "meta_thoughts_last_hour": _meta_rate_last_hour(),
            "unknowns_open": _pending_unknowns(),
        },
        "loops": _loop_states(),
    }
    return snap


# ─────────────────────────────────────────────────────────────
# Heartbeat loop
# ─────────────────────────────────────────────────────────────

class HeartbeatLoop(BackgroundLoop):
    """Single conductor: tick → snapshot → faculties → persist.

    Faculties are consulted only if AIOS_HEARTBEAT_FACULTIES=1
    (default on).  Turn it off to run heartbeat as a pure observer.
    """

    def __init__(self, interval: Optional[float] = None, enabled: bool = True):
        iv = float(interval if interval is not None
                   else os.getenv("AIOS_HEARTBEAT_INTERVAL", "60"))
        config = LoopConfig(
            interval_seconds=iv,
            name="heartbeat",
            enabled=enabled,
            max_errors=10,
            error_backoff=2.0,
            context_aware=False,
            initial_delay=20.0,  # fire ~20s after boot
        )
        super().__init__(config, self._tick)
        self._tick_count = 0

    @property
    def stats(self) -> Dict[str, Any]:
        base = super().stats
        base["tick_count"] = self._tick_count
        try:
            base["last_snapshot"] = get_latest_snapshot()
        except Exception:
            base["last_snapshot"] = {}
        return base

    def _tick(self) -> str:
        t0 = time.monotonic()
        snapshot = build_snapshot()
        actions: List[str] = []

        if os.getenv("AIOS_HEARTBEAT_FACULTIES", "1") == "1":
            try:
                from .faculties import run_faculties
                actions = run_faculties(snapshot)
            except Exception as e:
                actions = [f"faculty_error: {e}"]

        duration_ms = int((time.monotonic() - t0) * 1000)
        _write_tick(snapshot, actions, duration_ms)
        self._tick_count += 1

        # Compact summary for the stats panel
        c = snapshot.get("counts", {})
        summary = (
            f"user_present={snapshot.get('user_present')} "
            f"goals={c.get('proposed_goals_pending',0)}/"
            f"{c.get('proposed_goals_approved',0)} "
            f"tasks={c.get('tasks_pending',0)}/"
            f"{c.get('tasks_executing',0)} "
            f"meta/h={c.get('meta_thoughts_last_hour',0)} "
            f"unknowns={c.get('unknowns_open',0)} "
            f"actions={len(actions)}"
        )
        return summary


__all__ = [
    "HeartbeatLoop",
    "build_snapshot",
    "get_recent_ticks",
    "get_latest_snapshot",
]
