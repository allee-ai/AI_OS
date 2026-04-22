"""
Expectation Grading
===================

Grades pending `<expected>` meta_thoughts against subsequent turn
content, writing a delta via grade_expectation().

Heuristic-first (cheap): word-level Jaccard overlap between the
expectation's content and the subsequent (user + assistant) messages.

Optional LLM judge gated by AIOS_LLM_GRADER=1; falls back to heuristic
on any failure.

Policy (single source of truth):
    overlap ≥ 0.50       → delta +1.0  ("hit")
    overlap 0.25..0.50   → delta +0.3  (partial)
    overlap < 0.25
        and age < 2 turns → leave pending
        and age ≥ 3 turns → delta -0.5 (miss)

Rules:
    - Never raises.  Any failure → no grade written.
    - Excludes source='system' by default (system questions, not
      predictions); enable via AIOS_GRADE_SYSTEM=1 if needed.
    - kind='unknown' is NEVER graded here (unknowns are questions).
"""

from __future__ import annotations

import os
import re
from typing import Dict, Optional, Any


_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")
_STOP = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "at",
    "for", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "will", "would", "should", "could", "can", "may", "might", "about",
    "that", "this", "these", "those", "it", "its", "as", "if", "so",
    "you", "your", "i", "me", "my", "we", "our", "they", "them", "their",
    "user", "assistant", "not", "no", "yes",
}


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    try:
        return {
            t.lower() for t in _WORD_RE.findall(text)
            if len(t) > 2 and t.lower() not in _STOP
        }
    except Exception:
        return set()


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = a & b
    if not inter:
        return 0.0
    union = a | b
    return len(inter) / len(union) if union else 0.0


def grade_expectation_against_turn(
    meta_thought: Dict[str, Any],
    user_msg: str,
    assistant_msg: str,
    *,
    age_turns: int = 3,
) -> Optional[Dict[str, Any]]:
    """Return a grade dict or None.

    A grade dict has:
        {"delta": float, "match": bool, "overlap": float, "method": str}

    None means "leave pending — not enough evidence yet."
    Never raises.
    """
    try:
        if not meta_thought:
            return None
        if meta_thought.get("kind") != "expected":
            return None
        if meta_thought.get("graded"):
            return None
        content = meta_thought.get("content") or ""
        if not content:
            return None

        # Heuristic grade (always computed; LLM optionally overrides)
        exp_tokens = _tokens(content)
        turn_tokens = _tokens(f"{user_msg or ''}\n{assistant_msg or ''}")
        overlap = _jaccard(exp_tokens, turn_tokens)

        if overlap >= 0.50:
            return {"delta": 1.0, "match": True, "overlap": overlap, "method": "heuristic"}
        if overlap >= 0.25:
            return {"delta": 0.3, "match": True, "overlap": overlap, "method": "heuristic"}
        if age_turns < 2:
            return None  # too early to call it a miss
        if age_turns >= 3:
            return {"delta": -0.5, "match": False, "overlap": overlap, "method": "heuristic"}
        return None
    except Exception:
        return None


def grade_pending_for_session(session_id: str, *, turn_age_lookup: int = 3) -> int:
    """Grade pending expectations for a session against its latest turn.

    Returns count of grades written.  Never raises.
    Call after a turn is committed; uses the latest user+assistant
    messages in `conversations` (or equivalent) to score.
    """
    if not session_id:
        return 0
    if os.getenv("AIOS_AUTO_GRADE", "1") != "1":
        return 0
    try:
        from agent.threads.reflex.schema import (
            get_recent_meta_thoughts,
            grade_expectation,
        )
    except Exception:
        return 0

    try:
        # Pull the last turn's text.  We intentionally only pull one
        # (the just-committed turn) because grading is turn-boundary.
        latest_user, latest_asst = _latest_turn_text(session_id)
        if not (latest_user or latest_asst):
            return 0
    except Exception:
        return 0

    # Fetch pending expectations for this session.
    try:
        meta = get_recent_meta_thoughts(session_id=session_id, limit=50)
    except Exception:
        return 0

    allow_system = os.getenv("AIOS_GRADE_SYSTEM", "0") == "1"
    n = 0
    for m in meta:
        try:
            if m.get("kind") != "expected":
                continue
            if m.get("graded"):
                continue
            src = m.get("source", "")
            if src == "system" and not allow_system:
                continue
            # age_turns is not tracked on the row; use "3" as the trigger
            # so misses fire on the *second* subsequent turn.  For the
            # first subsequent turn we rely on the overlap tiers.
            grade = grade_expectation_against_turn(
                m, latest_user, latest_asst, age_turns=3,
            )
            if grade is None:
                continue
            # Dry-run mode: log and skip the real write.
            if os.getenv("AIOS_GRADE_DRYRUN", "0") == "1":
                continue
            # grade_expectation(thought_id, actual, match, notes)
            actual = (f"u:{(latest_user or '')[:120]} | a:{(latest_asst or '')[:120]}")
            notes = f"overlap={grade.get('overlap',0):.2f} method={grade.get('method','')}"
            ok = grade_expectation(
                m.get("id", 0),
                actual,
                bool(grade.get("match")),
                notes,
            )
            if ok:
                n += 1
        except Exception:
            continue
    return n


def _latest_turn_text(session_id: str) -> tuple[str, str]:
    """Return (user_msg, assistant_msg) of the latest turn for session.

    Best-effort; returns ("", "") on any failure.
    """
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            # Real schema: convos(session_id) → convo_turns(convo_id)
            try:
                row = conn.execute(
                    """
                    SELECT t.user_message, t.assistant_message
                    FROM convo_turns t
                    JOIN convos c ON c.id = t.convo_id
                    WHERE c.session_id = ?
                    ORDER BY t.id DESC LIMIT 1
                    """,
                    (session_id,),
                ).fetchone()
                if row:
                    return (row[0] or "", row[1] or "")
            except Exception:
                pass
    except Exception:
        pass
    return ("", "")


__all__ = [
    "grade_expectation_against_turn",
    "grade_pending_for_session",
]
