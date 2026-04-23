"""
agent/subconscious/trace_bus.py — in-memory trace of subconscious events.

The subconscious orchestrator does a lot of interesting work on every
`get_state(query)` call: scoring every thread and module, choosing
context levels, calling adapters, budgeting tokens.  None of that is
visible from outside — you only see the resulting STATE string.

This module gives the orchestrator (and anyone else who wants) a tiny
helper to publish an event.  A ring buffer keeps the last N events in
memory, keyed by a monotonic sequence number.  An SSE endpoint (see
`agent/subconscious/api.py`) reads from the buffer and streams events
to any connected client, so the phone / dashboard / debugger can watch
the system think in real time.

Design notes:
  • Lock-guarded deque.  No asyncio, no external deps, no Redis.
  • Publishing is best-effort and never raises.
  • A monotonic sequence lets subscribers resume after a dropped
    connection without losing anything that's still in the buffer.
  • Default buffer is 2000 events (~a few minutes of live orchestration).

Goal #26.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Dict, Iterable, List, Optional

# How many events to keep in memory at once.  Raise if the UI needs a
# longer replay window; lower if memory becomes a concern.
_MAX_EVENTS = 2000

# All state lives in module-level singletons.  Safe because the server
# is a single process; if AI_OS ever runs multi-process the bus would
# need to move to redis/sqlite.
_LOCK = threading.Lock()
_BUFFER: "deque[Dict[str, Any]]" = deque(maxlen=_MAX_EVENTS)
_NEXT_SEQ = 1

# Counter of all events ever published — useful for the /stats endpoint.
_TOTAL_PUBLISHED = 0


def publish(event_type: str, **fields: Any) -> Optional[int]:
    """Publish one event to the trace bus.

    Returns the sequence number assigned, or None on any failure.
    Never raises — the orchestrator must stay fast even if tracing
    breaks.

    Args:
        event_type:  Short tag like 'score', 'threshold', 'adapter_call',
                     'adapter_result', 'budget', 'state_built'.
        **fields:    Arbitrary JSON-safe data.  Non-serialisable values
                     are coerced to str at SSE render time.
    """
    global _NEXT_SEQ, _TOTAL_PUBLISHED
    try:
        ev = {
            "seq": 0,  # filled in under lock
            "ts": time.time(),
            "type": event_type,
            **fields,
        }
        with _LOCK:
            ev["seq"] = _NEXT_SEQ
            _NEXT_SEQ += 1
            _TOTAL_PUBLISHED += 1
            _BUFFER.append(ev)
        return ev["seq"]
    except Exception:
        return None


def events_since(last_seq: int = 0, limit: int = 500) -> List[Dict[str, Any]]:
    """Return events with seq > last_seq, oldest first, up to `limit`."""
    with _LOCK:
        # deque → list copy is fine for a 2000-item buffer.
        snap = list(_BUFFER)
    out: List[Dict[str, Any]] = []
    for ev in snap:
        if ev["seq"] > last_seq:
            out.append(ev)
            if len(out) >= limit:
                break
    return out


def latest_seq() -> int:
    """Highest sequence number currently in the buffer (or 0 if empty)."""
    with _LOCK:
        if not _BUFFER:
            return 0
        return _BUFFER[-1]["seq"]


def stats() -> Dict[str, int]:
    with _LOCK:
        return {
            "buffer_size": len(_BUFFER),
            "max_events": _MAX_EVENTS,
            "total_published": _TOTAL_PUBLISHED,
            "next_seq": _NEXT_SEQ,
        }


def clear() -> None:
    """Drop everything.  Debug / test use only."""
    global _NEXT_SEQ, _TOTAL_PUBLISHED
    with _LOCK:
        _BUFFER.clear()
        _NEXT_SEQ = 1
        _TOTAL_PUBLISHED = 0


__all__ = [
    "publish",
    "events_since",
    "latest_seq",
    "stats",
    "clear",
]
