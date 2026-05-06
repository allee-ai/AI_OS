"""
scheduler.py — Single-flight, idle-aware loop coordinator
=========================================================

Sits between BackgroundLoop._execute_task and the actual task call.
Provides four guarantees:

1. **Single-flight**: at most ONE loop's task runs at a time across the
   whole process. Eliminates overlapping LLM/embedding work.

2. **Idle-aware**: when the user has interacted (chat / API / CLI) in the
   last AIOS_USER_IDLE_MIN minutes, expensive cloud loops are deferred.
   "Cheap" loops (health, sync) still run.

3. **Rate-gated**: consults `agent.services.rate_gate` before allowing
   cloud-backed loops through. Purely-local loops (health, embedding-only
   tasks) bypass this check.

4. **Average-time tracked**: BackgroundLoop already records durations.
   Scheduler exposes `summary()` aggregating across all loops for STATE.

Usage from BackgroundLoop._execute_task:
    if not scheduler.acquire_for(self.config.name): return  # skipped
    try: ...
    finally: scheduler.release()
"""

from __future__ import annotations

import os
import threading
import time
from typing import Dict, Optional, Tuple

# ── Config ─────────────────────────────────────────────────

_SINGLE_FLIGHT = os.getenv("AIOS_LOOP_SINGLE_FLIGHT", "1") == "1"
_USER_IDLE_MIN = float(os.getenv("AIOS_USER_IDLE_MIN", "5"))     # minutes
_DEFER_WHEN_ACTIVE = os.getenv("AIOS_DEFER_WHEN_ACTIVE", "1") == "1"

# Loops tagged as "cheap" never wait for idle / rate gate.
CHEAP_LOOPS = frozenset({"health", "sync"})

# Loops mapped to their primary provider for rate-gate lookup. Default is
# whatever the env is set to. Empty string skips the gate check.
_LOOP_PROVIDER_HINT: Dict[str, str] = {
    # Local-only loops — no cloud provider gate
    "health": "",
    "sync": "",
    # Heavy / planner loops use whatever PLANNER role resolves to
    # (resolved lazily at acquire time)
}


# ── State ──────────────────────────────────────────────────

_lock = threading.RLock()
_global_flight_lock = threading.Lock()      # actual single-flight gate
_current_loop: Optional[str] = None
_acquired_at: float = 0.0
_skip_counts: Dict[str, int] = {}           # loop_name → skip count
_skip_reasons: Dict[str, str] = {}          # loop_name → last skip reason
_run_counts: Dict[str, int] = {}


def _last_user_activity_seconds() -> Optional[float]:
    """
    Seconds since the most recent user interaction. None if unknown.
    Reads `unified_events` for source IN ('user', 'chat', 'cli', 'api')
    in the last 30 minutes.
    """
    try:
        from contextlib import closing
        from data.db import get_connection
        with closing(get_connection(readonly=True)) as conn:
            row = conn.execute(
                "SELECT MAX(timestamp) FROM unified_events "
                "WHERE source IN ('user', 'chat', 'cli', 'api') "
                "AND timestamp >= datetime('now', '-30 minutes')"
            ).fetchone()
        if not row or not row[0]:
            return None
        from datetime import datetime, timezone
        # SQLite isoformat (no tz) — parse as UTC
        ts_str = row[0].replace("Z", "+00:00")
        if "+" not in ts_str and "T" in ts_str:
            ts_str += "+00:00"
        try:
            ts = datetime.fromisoformat(ts_str)
        except Exception:
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds())
    except Exception:
        return None


def _user_active() -> bool:
    """True if the user has interacted within AIOS_USER_IDLE_MIN minutes."""
    age = _last_user_activity_seconds()
    if age is None:
        return False
    return age < _USER_IDLE_MIN * 60.0


def _provider_for_loop(loop_name: str) -> str:
    """Best-effort mapping of a loop name to a provider for rate-gate lookup."""
    hint = _LOOP_PROVIDER_HINT.get(loop_name)
    if hint is not None:
        return hint
    # Fallback: use env default provider
    return os.getenv("AIOS_MODEL_PROVIDER", "ollama").lower()


# ── Public API ─────────────────────────────────────────────

def acquire_for(loop_name: str, timeout: float = 0.5) -> Tuple[bool, str]:
    """
    Try to acquire the global single-flight slot for this loop.

    Returns (acquired, reason):
      - (True, "ok")             — caller MUST run its task and call release()
      - (False, "busy:{name}")   — another loop is running
      - (False, "user_active")   — user is interacting; defer
      - (False, "rate_gate:...") — provider cooling down
      - (False, "disabled")      — single-flight is off (caller proceeds normally)

    Cheap loops (health, sync) bypass user-active and rate gates.
    """
    global _current_loop, _acquired_at

    if not _SINGLE_FLIGHT:
        # Single-flight is disabled — caller may proceed but we don't track.
        return True, "disabled"

    is_cheap = loop_name in CHEAP_LOOPS

    # Idle check
    if _DEFER_WHEN_ACTIVE and not is_cheap and _user_active():
        with _lock:
            _skip_counts[loop_name] = _skip_counts.get(loop_name, 0) + 1
            _skip_reasons[loop_name] = "user_active"
        return False, "user_active"

    # Rate gate
    if not is_cheap:
        try:
            from agent.services import rate_gate as _rg
            provider = _provider_for_loop(loop_name)
            if provider:
                skip, reason = _rg.should_skip(provider)
                if skip:
                    with _lock:
                        _skip_counts[loop_name] = _skip_counts.get(loop_name, 0) + 1
                        _skip_reasons[loop_name] = f"rate_gate:{reason}"
                    return False, f"rate_gate:{reason}"
        except Exception:
            pass

    # Single-flight lock
    got = _global_flight_lock.acquire(timeout=timeout)
    if not got:
        with _lock:
            _skip_counts[loop_name] = _skip_counts.get(loop_name, 0) + 1
            _skip_reasons[loop_name] = f"busy:{_current_loop or 'unknown'}"
        return False, f"busy:{_current_loop or 'unknown'}"

    with _lock:
        _current_loop = loop_name
        _acquired_at = time.time()
        _run_counts[loop_name] = _run_counts.get(loop_name, 0) + 1
    return True, "ok"


def release() -> None:
    """Release the single-flight slot. Safe to call multiple times."""
    global _current_loop, _acquired_at
    with _lock:
        _current_loop = None
        _acquired_at = 0.0
    try:
        _global_flight_lock.release()
    except RuntimeError:
        pass  # not held — fine


def summary() -> Dict[str, object]:
    """Snapshot for STATE / dashboards."""
    with _lock:
        cur_age = (time.time() - _acquired_at) if _acquired_at else None
        return {
            "single_flight": _SINGLE_FLIGHT,
            "defer_when_active": _DEFER_WHEN_ACTIVE,
            "user_idle_min": _USER_IDLE_MIN,
            "current_loop": _current_loop,
            "current_age": round(cur_age, 1) if cur_age else None,
            "user_active": _user_active(),
            "user_idle_seconds": _last_user_activity_seconds(),
            "run_counts": dict(_run_counts),
            "skip_counts": dict(_skip_counts),
            "skip_reasons_last": dict(_skip_reasons),
        }
