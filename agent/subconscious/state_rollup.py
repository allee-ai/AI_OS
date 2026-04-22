"""
Subconscious STATE rollup
=========================

One function — `build_subconscious_section(budget) -> str` — that
produces a compact `[subconscious]` block for STATE containing top
un-acted items across:

  - proposed_goals    (status='pending')
  - notifications     (read=0 and dismissed=0)
  - proposed_improvements (status='pending')
  - thought_log       (recent high-priority thoughts)

Gated by AIOS_SUBCONSCIOUS_SECTION=1.  Each DB call is independent:
if one fails, the rest still render.  Never raises.

Why separate from the mirror (meta_mirror.py):
    The mirror turns individual architecture writes into meta-thoughts
    the model sees as *cognitive* residue.  This rollup is an
    *operational* snapshot — "these are the open decisions waiting
    for you" — and preserves structure (goal, notify, improve, etc.)
    the meta flattening would lose.
"""

from __future__ import annotations

import os
from typing import List


_HEADER = "[subconscious] Operational queue (architecture voice)"


def _pending_goals(limit: int = 2) -> List[str]:
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                """
                SELECT goal, priority
                FROM proposed_goals
                WHERE status='pending'
                ORDER BY
                  CASE priority
                    WHEN 'urgent' THEN 0
                    WHEN 'high'   THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3 END,
                  id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
            return [f"[goal] {(r[0] or '')[:120]} ({r[1] or 'medium'})" for r in rows]
    except Exception:
        return []


def _pending_notifications(limit: int = 2) -> List[str]:
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                """
                SELECT message, priority
                FROM notifications
                WHERE read=0 AND dismissed=0
                ORDER BY
                  CASE priority
                    WHEN 'urgent' THEN 0
                    WHEN 'high'   THEN 1
                    WHEN 'warn'   THEN 2
                    WHEN 'warning' THEN 2
                    ELSE 3 END,
                  id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
            return [f"[notify] {(r[0] or '')[:120]} ({r[1] or 'normal'})" for r in rows]
    except Exception:
        return []


def _pending_improvements(limit: int = 1) -> List[str]:
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                """
                SELECT file_path, description
                FROM proposed_improvements
                WHERE status='pending'
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
            return [
                f"[improve] {(r[0] or '')[:60]}: {(r[1] or '')[:80]}"
                for r in rows
            ]
    except Exception:
        return []


def _recent_thoughts(limit: int = 2) -> List[str]:
    """Recent high-signal thoughts (alert/question) in last hour."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                """
                SELECT category, priority, thought
                FROM thought_log
                WHERE created_at >= datetime('now', '-1 hour')
                  AND category IN ('alert','question')
                  AND acted_on = 0
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
            return [
                f"[thought/{r[0]}] {(r[2] or '')[:120]} ({r[1] or 'low'})"
                for r in rows
            ]
    except Exception:
        return []


def _heartbeat_lines() -> List[str]:
    """Compact heartbeat summary — one or two lines describing the
    most recent tick, so the model knows what the background layer is
    currently seeing.  Silent on any failure.
    """
    if os.getenv("AIOS_HEARTBEAT_IN_STATE", "1") != "1":
        return []
    try:
        from agent.subconscious.heartbeat import get_latest_snapshot
        snap = get_latest_snapshot() or {}
        if not snap:
            return []
        c = snap.get("counts") or {}
        parts = [
            f"user_present={snap.get('user_present')}",
            f"meta/h={c.get('meta_thoughts_last_hour', 0)}",
            f"goals_pending={c.get('proposed_goals_pending', 0)}",
            f"tasks={c.get('tasks_pending', 0)}p/"
            f"{c.get('tasks_executing', 0)}x",
            f"unknowns={c.get('unknowns_open', 0)}",
        ]
        return [f"[heartbeat] {' '.join(parts)}"]
    except Exception:
        return []


def build_subconscious_section(budget: int = 400) -> str:
    """Assemble the [subconscious] STATE section.

    Returns '' if disabled or empty.  Caller splices into STATE as
    a pseudo-thread section.  Never raises.
    """
    if os.getenv("AIOS_SUBCONSCIOUS_SECTION", "0") != "1":
        return ""
    try:
        lines: List[str] = []
        # Order: heartbeat (pulse), goals (what you want),
        # notifications (what needs attention), improvements (what you
        # could do), thoughts (what i noticed).
        lines.extend(_heartbeat_lines())
        lines.extend(_pending_goals(2))
        lines.extend(_pending_notifications(2))
        lines.extend(_pending_improvements(1))
        lines.extend(_recent_thoughts(2))
        if not lines:
            return ""
        body = "\n  ".join(lines)
        out = f"{_HEADER}\n  {body}"
        # Budget clamp (char-approx of token budget).
        char_budget = max(120, int(budget) * 4)
        if len(out) > char_budget:
            out = out[: char_budget - 3] + "..."
        return out
    except Exception:
        return ""


__all__ = ["build_subconscious_section"]
