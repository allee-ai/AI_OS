"""
sequences — n-gram mining over event_type series.
=================================================

Pure SQL + Python. Scans the recent unified_events tail, builds bigrams
and trigrams of event_type, ranks by frequency, surfaces the top
patterns as a reflex compression meta-thought so STATE shows the
agent's habits.

Run from coma every Nth tick. Cheap.

Design rule: do not invent new tokens. The vocabulary is whatever
event_type values already exist. The compression is the signal.
"""

from __future__ import annotations

from collections import Counter
from contextlib import closing
from typing import Dict, Any, List, Tuple

from data.db import get_connection


def mine_sequences(
    window_hours: int = 168,
    max_events: int = 5000,
    top_k: int = 8,
    min_count: int = 3,
) -> Dict[str, Any]:
    """Return top n-gram patterns over the recent event window."""
    out: Dict[str, Any] = {
        "bigrams": [],
        "trigrams": [],
        "n_events": 0,
    }
    try:
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                f"""
                SELECT event_type, session_id
                FROM unified_events
                WHERE timestamp >= datetime('now','-{int(window_hours)} hours')
                ORDER BY id ASC
                LIMIT {int(max_events)}
                """
            ).fetchall()
    except Exception:
        return out

    if not rows:
        return out

    out["n_events"] = len(rows)

    # Group by session_id so n-grams stay within a coherent arc.
    by_session: Dict[str, List[str]] = {}
    for r in rows:
        sid = r["session_id"] or "_no_session"
        et = r["event_type"] or "_unknown"
        by_session.setdefault(sid, []).append(et)

    bigrams: Counter = Counter()
    trigrams: Counter = Counter()
    for series in by_session.values():
        if len(series) >= 2:
            for i in range(len(series) - 1):
                bigrams[(series[i], series[i + 1])] += 1
        if len(series) >= 3:
            for i in range(len(series) - 2):
                trigrams[(series[i], series[i + 1], series[i + 2])] += 1

    out["bigrams"] = [
        {"pattern": " -> ".join(p), "count": c}
        for p, c in bigrams.most_common(top_k)
        if c >= min_count
    ]
    out["trigrams"] = [
        {"pattern": " -> ".join(p), "count": c}
        for p, c in trigrams.most_common(top_k)
        if c >= min_count
    ]
    return out


def write_sequence_compression(result: Dict[str, Any]) -> bool:
    """Surface the top patterns as a reflex compression meta-thought."""
    try:
        from agent.threads.reflex.schema import add_meta_thought
        bits: List[str] = []
        if result.get("bigrams"):
            bits.append(
                "bigrams " + ", ".join(
                    f"{b['pattern']}({b['count']})"
                    for b in result["bigrams"][:4]
                )
            )
        if result.get("trigrams"):
            bits.append(
                "trigrams " + ", ".join(
                    f"{t['pattern']}({t['count']})"
                    for t in result["trigrams"][:3]
                )
            )
        if not bits:
            return False
        content = (
            f"sequence patterns 7d ({result.get('n_events', 0)} events): "
            + " | ".join(bits)
        )[:500]
        add_meta_thought(
            kind="compression",
            content=content,
            source="system",
            confidence=1.0,
            weight=0.55,
        )
        return True
    except Exception:
        return False


__all__ = ["mine_sequences", "write_sequence_compression"]
