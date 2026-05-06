"""
seq_predictions — predictions registered from observed event sequences.
=======================================================================

Closes the loop: habits become forward expectations.

Mining (in `agent.subconscious.sequences`) finds bigrams like
    code_change -> code_change   (count=245)
    turn_outcome -> agent_turn   (count=37)

For each high-confidence bigram (count >= K, ratio of A->B over A->* >= P),
this module registers a prediction: "if A just happened and >R minutes
pass without B, fire a prediction_error". The check runs each heartbeat
inside the existing predictions registry — no new pulse needed.

Pure SQL. No LLM. The system literally builds expectations from its
own past behavior, then notices when reality deviates.
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from contextlib import closing
from typing import List, Dict, Any, Tuple, Optional

from data.db import get_connection


_REGISTERED_NAMES: set = set()


def _make_check(head: str, tail: str, max_minutes: float):
    """Return a closure: if `head` happened in the last X min and no
    matching `tail` followed it, return a violation message."""

    def check() -> Optional[str]:
        try:
            with closing(get_connection(readonly=True)) as conn:
                # Most recent `head` event in the window
                row = conn.execute(
                    """
                    SELECT id, timestamp
                    FROM unified_events
                    WHERE event_type = ?
                      AND timestamp >= datetime('now', ?)
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (head, f"-{int(max_minutes)} minutes"),
                ).fetchone()
                if not row:
                    return None  # no recent head, nothing to predict
                head_id = int(row["id"])
                head_ts = row["timestamp"]
                # Did `tail` happen after that head_id?
                follow = conn.execute(
                    """
                    SELECT id FROM unified_events
                    WHERE event_type = ?
                      AND id > ?
                    LIMIT 1
                    """,
                    (tail, head_id),
                ).fetchone()
                if follow:
                    return None
                # Has enough time passed for the expectation to be wrong?
                age = conn.execute(
                    "SELECT (julianday('now') - julianday(?)) * 24.0 * 60.0 AS m",
                    (head_ts,),
                ).fetchone()
                age_min = float(age["m"] or 0.0)
                if age_min < max_minutes:
                    return None  # still within grace period
                return f"expected {tail} after {head} (last seen {age_min:.0f}m ago, no follow)"
        except Exception:
            return None

    return check


def mine_and_register(
    window_days: int = 14,
    max_events: int = 8000,
    min_count: int = 8,
    min_ratio: float = 0.5,
    grace_minutes: float = 30.0,
    max_predictions: int = 6,
) -> int:
    """Mine event_type bigrams and register the strongest as predictions.

    A bigram (A, B) becomes a prediction iff:
      - count(A,B) >= min_count
      - count(A,B) / sum(count(A,*)) >= min_ratio   (B is the *expected* successor)
      - A and B are not the same event type (avoid trivial self-loops)
      - we haven't already registered this name

    Returns number newly registered.
    """
    try:
        from agent.subconscious.predictions import (
            Prediction, register, list_predictions,
        )
    except Exception:
        return 0

    try:
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                f"""
                SELECT event_type, session_id
                FROM unified_events
                WHERE timestamp >= datetime('now','-{int(window_days)} days')
                ORDER BY id ASC
                LIMIT {int(max_events)}
                """
            ).fetchall()
    except Exception:
        return 0

    if not rows:
        return 0

    by_session: Dict[str, List[str]] = defaultdict(list)
    for r in rows:
        by_session[r["session_id"] or "_no_session"].append(r["event_type"] or "_unknown")

    head_counts: Counter = Counter()
    bigram_counts: Counter = Counter()
    for series in by_session.values():
        for i in range(len(series) - 1):
            a, b = series[i], series[i + 1]
            head_counts[a] += 1
            bigram_counts[(a, b)] += 1

    # Rank candidate predictions by (count * ratio).
    candidates: List[Tuple[float, str, str, int, float]] = []
    for (a, b), c in bigram_counts.items():
        if a == b:
            continue
        if c < min_count:
            continue
        ratio = c / max(1, head_counts[a])
        if ratio < min_ratio:
            continue
        candidates.append((c * ratio, a, b, c, ratio))
    candidates.sort(reverse=True)

    existing = {p.name for p in list_predictions()}
    new_count = 0
    for _, head, tail, count, ratio in candidates[: max_predictions]:
        name = f"seq.{head}__{tail}"
        if name in existing or name in _REGISTERED_NAMES:
            continue
        severity = "low" if ratio < 0.7 else ("medium" if ratio < 0.9 else "high")
        desc = (
            f"learned: {head} typically followed by {tail} "
            f"({count} obs, {ratio:.0%} of {head}s)"
        )
        register(Prediction(
            name=name,
            owner_thread="reflex",
            check=_make_check(head, tail, max_minutes=30.0),
            severity=severity,
            description=desc,
        ))
        _REGISTERED_NAMES.add(name)
        new_count += 1
    return new_count


def registered_seq_predictions() -> List[str]:
    return sorted(_REGISTERED_NAMES)


__all__ = ["mine_and_register", "registered_seq_predictions"]
