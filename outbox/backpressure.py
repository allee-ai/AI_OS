"""
backpressure — shared "should this loop pause?" primitive.

The principle: loops that emit observations / questions / proposals
to the operator should NOT keep emitting when prior outputs are still
unresolved. Otherwise we get a stack of identical thoughts (because
state hasn't moved) and the inbox becomes noise.

Each loop that adopts this checks ``should_pause(...)`` at the start
of ``tick_once()``. If it returns a reason string, the tick logs
``paused=<reason>`` and exits early instead of burning a cloud call.

Currently we count unresolved rows in two places:

  1. ``notifications`` rows where ``read=0 AND dismissed=0`` of a given
     ``type`` (e.g. 'aios_thought' for the reflector).
  2. ``outbox`` cards where ``status='pending'`` of a given ``motor``
     (e.g. 'copilot_request' for the executor — though executor wants
     to keep eating those, so it doesn't pause on its own queue).

Thresholds default to 3. Override via per-loop env (e.g.
``AIOS_REFLECT_PAUSE_AT=2`` or ``AIOS_REFLECT_PAUSE_AT=0`` to disable).

This module is dependency-free other than ``data.db`` so any loop can
import it without dragging the subconscious in.
"""

from __future__ import annotations

import os
from contextlib import closing
from typing import Optional

from data.db import get_connection


def unread_notifications_count(type_filter: Optional[str] = None) -> int:
    """How many notifications are still unread AND undismissed?

    If ``type_filter`` is given, only count rows of that ``type``.
    """
    sql = ("SELECT COUNT(*) AS n FROM notifications "
           "WHERE read = 0 AND dismissed = 0")
    params: tuple = ()
    if type_filter:
        sql += " AND type = ?"
        params = (type_filter,)
    try:
        with closing(get_connection(readonly=True)) as conn:
            row = conn.execute(sql, params).fetchone()
            return int(row["n"]) if row else 0
    except Exception:
        # If the table doesn't exist or DB hiccups, don't pause loops
        # for that — pretend zero so the loop runs and the real error
        # surfaces in its own try/except.
        return 0


def pending_outbox_count(motor: Optional[str] = None) -> int:
    """How many outbox cards are still in 'pending' status?"""
    sql = "SELECT COUNT(*) AS n FROM outbox WHERE status = 'pending'"
    params: tuple = ()
    if motor:
        sql += " AND motor = ?"
        params = (motor,)
    try:
        with closing(get_connection(readonly=True)) as conn:
            row = conn.execute(sql, params).fetchone()
            return int(row["n"]) if row else 0
    except Exception:
        return 0


def should_pause(
    *,
    notif_type: Optional[str] = None,
    pending_motor: Optional[str] = None,
    threshold: int = 3,
) -> Optional[str]:
    """Return a non-empty reason string if the loop should pause,
    else None.

    Example for the reflector:

        reason = should_pause(notif_type='aios_thought', threshold=3)
        if reason:
            return {"paused": reason, ...}

    Counts both unread notifications of ``notif_type`` and pending
    outbox cards of ``pending_motor`` (whichever are provided) and
    pauses if EITHER exceeds ``threshold``. Pass threshold=0 to
    disable pausing entirely.
    """
    if threshold <= 0:
        return None

    if notif_type is not None:
        n = unread_notifications_count(notif_type)
        if n >= threshold:
            return f"{n} unresolved {notif_type} (>= {threshold})"

    if pending_motor is not None:
        n = pending_outbox_count(pending_motor)
        if n >= threshold:
            return f"{n} pending {pending_motor} cards (>= {threshold})"

    return None
