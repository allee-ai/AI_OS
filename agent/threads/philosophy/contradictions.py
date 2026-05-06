"""
philosophy.contradictions — belief surfacing + disagreement detection.
=====================================================================

Lives in philosophy because beliefs/stances/principles already live in
`philosophy_profile_facts`. This module just adds *analysis*:

  - top_beliefs(n): high-weight facts the system actually leans on.
  - find_contradictions(): same `key`, different `l1_value`, across
    profiles. The classic "the system says X under one frame and ¬X
    under another" signal.
  - emit_contradiction_meta_thoughts(): for each detected pair, drop
    a kind="contradiction" meta-thought with both values + profiles
    so the active agent can resolve it later.

Pure SQL. No LLM. Idempotent — same contradiction won't re-emit on
the same heartbeat because the meta-thought key is deterministic.
"""

from __future__ import annotations

import hashlib
from contextlib import closing
from typing import List, Dict, Any, Optional, Tuple

from data.db import get_connection


# ─────────────────────────────────────────────────────────────────────
# Belief surfacing
# ─────────────────────────────────────────────────────────────────────

def top_beliefs(min_weight: float = 0.6, limit: int = 25) -> List[Dict[str, Any]]:
    """Return the philosophy facts the system most heavily relies on."""
    try:
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                """
                SELECT profile_id, key, l1_value, weight, updated_at
                FROM philosophy_profile_facts
                WHERE weight >= ?
                ORDER BY weight DESC, updated_at DESC
                LIMIT ?
                """,
                (float(min_weight), int(limit)),
            ).fetchall()
            return [
                {
                    "profile_id": r["profile_id"],
                    "key": r["key"],
                    "value": r["l1_value"],
                    "weight": float(r["weight"] or 0.0),
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────
# Contradiction detection
# ─────────────────────────────────────────────────────────────────────

def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def find_contradictions(min_weight: float = 0.4) -> List[Dict[str, Any]]:
    """Return pairs of facts with same `key` but different `l1_value`.

    Strategy: SQL self-join on `key`, exclude self, require both rows
    weight >= min_weight, require different normalized l1_value. Group
    by canonical (key, value_a, value_b) so a single conflict surfaces
    once.
    """
    try:
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                """
                SELECT a.key             AS key,
                       a.profile_id      AS profile_a,
                       a.l1_value        AS value_a,
                       a.weight          AS weight_a,
                       b.profile_id      AS profile_b,
                       b.l1_value        AS value_b,
                       b.weight          AS weight_b
                FROM philosophy_profile_facts a
                JOIN philosophy_profile_facts b
                  ON a.key = b.key
                 AND a.profile_id < b.profile_id
                WHERE a.weight >= ?
                  AND b.weight >= ?
                  AND COALESCE(LOWER(TRIM(a.l1_value)),'') !=
                      COALESCE(LOWER(TRIM(b.l1_value)),'')
                  AND COALESCE(a.l1_value,'') != ''
                  AND COALESCE(b.l1_value,'') != ''
                """,
                (float(min_weight), float(min_weight)),
            ).fetchall()
    except Exception:
        return []

    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({
            "key": r["key"],
            "profile_a": r["profile_a"],
            "value_a": r["value_a"],
            "weight_a": float(r["weight_a"] or 0.0),
            "profile_b": r["profile_b"],
            "value_b": r["value_b"],
            "weight_b": float(r["weight_b"] or 0.0),
            "tension": round((float(r["weight_a"] or 0.0) + float(r["weight_b"] or 0.0)) / 2.0, 3),
        })
    out.sort(key=lambda d: d["tension"], reverse=True)
    return out


def _contradiction_signature(c: Dict[str, Any]) -> str:
    """Deterministic key so the same conflict doesn't re-emit each tick."""
    parts = [
        c["key"],
        c["profile_a"], _norm(c["value_a"]),
        c["profile_b"], _norm(c["value_b"]),
    ]
    return hashlib.blake2b("|".join(parts).encode("utf-8", "ignore"), digest_size=8).hexdigest()


def emit_contradiction_meta_thoughts(limit: int = 5) -> int:
    """For top-tension contradictions, drop one meta-thought each.

    Idempotent within a session: signatures are checked against recent
    meta_thoughts of kind='contradiction'.
    """
    contras = find_contradictions()
    if not contras:
        return 0
    contras = contras[: int(limit)]

    try:
        from agent.threads.reflex.schema import add_meta_thought
    except Exception:
        return 0

    # Pull recent contradiction meta-thoughts to dedupe.
    recent_sigs: set = set()
    try:
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                """
                SELECT content FROM reflex_meta_thoughts
                WHERE kind = 'contradiction'
                  AND created_at >= datetime('now','-7 days')
                LIMIT 200
                """
            ).fetchall()
            for r in rows:
                content = r["content"] or ""
                # We embed the signature as suffix "[sig:xxxx]"
                if "[sig:" in content:
                    try:
                        sig = content.split("[sig:")[1].split("]")[0].strip()
                        if sig:
                            recent_sigs.add(sig)
                    except Exception:
                        pass
    except Exception:
        pass

    written = 0
    for c in contras:
        sig = _contradiction_signature(c)
        if sig in recent_sigs:
            continue
        content = (
            f"contradiction on '{c['key']}': "
            f"{c['profile_a']}={_short(c['value_a'])} vs "
            f"{c['profile_b']}={_short(c['value_b'])} "
            f"(tension={c['tension']}) [sig:{sig}]"
        )[:500]
        try:
            add_meta_thought(
                kind="contradiction",
                content=content,
                source="system",
                confidence=1.0,
                weight=min(0.85, 0.4 + c["tension"] * 0.5),
            )
            written += 1
        except Exception:
            continue
    return written


def _short(v: Optional[str], n: int = 80) -> str:
    s = (v or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


# ─────────────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────────────

def contradictions_summary() -> Dict[str, Any]:
    contras = find_contradictions()
    beliefs = top_beliefs(min_weight=0.7, limit=10)
    return {
        "n_strong_beliefs": len(beliefs),
        "n_contradictions": len(contras),
        "top_tension": contras[0]["tension"] if contras else 0.0,
        "top_keys": [c["key"] for c in contras[:5]],
    }


__all__ = [
    "top_beliefs",
    "find_contradictions",
    "emit_contradiction_meta_thoughts",
    "contradictions_summary",
]
