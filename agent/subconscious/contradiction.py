"""
Contradiction Detection
=======================

Periodic scan of `reflex_meta_thoughts` for self-contradictions.  When
the agent's past thoughts disagree about the same concepts, emit a new
`source='system'` `<unknown>` asking which is true.

Design:
    - Pulls last `window_days` of meta_thoughts (all sources).
    - Extracts concepts via `linking_core` (silently skipped if unavailable).
    - Pair-wise: candidates share ≥2 concepts, have opposing kinds, and
      were asserted ≥1 day apart.
    - Dedupes via content hash stored in the emitted unknown's content.
    - Capped at `max_emit` per run.

Gated by AIOS_CONTRADICTION_SCAN=1.  Never raises.  Typically invoked
by ConsolidationLoop or manually.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple


OPPOSING_KINDS: Set[Tuple[str, str]] = {
    ("rejected", "expected"),
    ("rejected", "compression"),
    ("expected", "rejected"),
    ("compression", "rejected"),
}


def _extract_concepts(text: str) -> Set[str]:
    if not text:
        return set()
    try:
        from agent.threads.linking_core.schema import extract_concepts_from_text
        cs = extract_concepts_from_text(text) or []
        return {c for c in cs if c and len(c) > 2}
    except Exception:
        return set()


def _pair_hash(a_id: int, b_id: int) -> str:
    key = f"{min(a_id, b_id)}:{max(a_id, b_id)}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:8]


def _already_emitted(pair_hash: str) -> bool:
    """Best-effort check: did we already surface this contradiction?"""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            row = conn.execute(
                """
                SELECT 1 FROM reflex_meta_thoughts
                WHERE source='system' AND kind='unknown'
                  AND content LIKE ?
                LIMIT 1
                """,
                (f"%#cx{pair_hash}%",),
            ).fetchone()
            return row is not None
    except Exception:
        return False


def find_contradictions(
    window_days: int = 30,
    fetch_limit: int = 200,
    max_emit: int = 3,
) -> List[Dict[str, Any]]:
    """Scan, emit, return list of emitted unknowns (dicts with id + text).

    Returns []; never raises.
    """
    if os.getenv("AIOS_CONTRADICTION_SCAN", "0") != "1":
        return []
    try:
        from data.db import get_connection
        from contextlib import closing
        from agent.threads.reflex.schema import add_meta_thought
    except Exception:
        return []

    # Pull window
    rows: List[Dict[str, Any]] = []
    try:
        with closing(get_connection(readonly=True)) as conn:
            q = f"""
                SELECT id, kind, content, source, first_asserted_at
                FROM reflex_meta_thoughts
                WHERE first_asserted_at >= datetime('now', '-{int(window_days)} days')
                  AND kind IN ('rejected','expected','compression')
                ORDER BY id DESC
                LIMIT ?
            """
            for r in conn.execute(q, (int(fetch_limit),)).fetchall():
                rows.append({
                    "id": r[0], "kind": r[1], "content": r[2] or "",
                    "source": r[3] or "", "date": r[4] or "",
                })
    except Exception:
        return []

    # Extract concepts once per row (cache)
    concepts_cache: Dict[int, Set[str]] = {}
    for r in rows:
        concepts_cache[r["id"]] = _extract_concepts(r["content"])

    emitted: List[Dict[str, Any]] = []
    seen_pairs: Set[str] = set()

    for i in range(len(rows)):
        if len(emitted) >= max_emit:
            break
        a = rows[i]
        a_concepts = concepts_cache.get(a["id"], set())
        if len(a_concepts) < 2:
            continue
        for j in range(i + 1, len(rows)):
            b = rows[j]
            # Opposing kinds
            if (a["kind"], b["kind"]) not in OPPOSING_KINDS:
                continue
            b_concepts = concepts_cache.get(b["id"], set())
            overlap = a_concepts & b_concepts
            if len(overlap) < 2:
                continue
            # Different days
            if a["date"][:10] == b["date"][:10]:
                continue
            ph = _pair_hash(a["id"], b["id"])
            if ph in seen_pairs or _already_emitted(ph):
                continue
            # Compose unknown
            a_date = (a["date"] or "")[:10] or "?"
            b_date = (b["date"] or "")[:10] or "?"
            content = (
                f"I said '{a['content'][:100]}' on {a_date}, "
                f"then '{b['content'][:100]}' on {b_date} — which is true? #cx{ph}"
            )
            try:
                new_id = add_meta_thought(
                    kind="unknown",
                    content=content[:500],
                    source="system",
                    weight=0.9,
                    confidence=0.5,
                )
                if new_id:
                    emitted.append({"id": new_id, "content": content, "pair": ph})
                    seen_pairs.add(ph)
                    if len(emitted) >= max_emit:
                        break
            except Exception:
                continue

    return emitted


__all__ = ["find_contradictions"]
