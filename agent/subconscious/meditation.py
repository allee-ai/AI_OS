"""
meditation — continuous, sub-second substrate updates.
======================================================

The DB does half the thinking. This module is the trickle.

Every tick (default 2s):
  1. Pull events newer than our watermark
  2. Extract concepts from each
  3. Inject activation into a `concept_activation` table (max-merge)
  4. Spread activation through concept_links (one hop, weighted)
  5. Decay all activations toward zero
  6. Recompute a `salience` overlay on profile_facts +
     philosophy_profile_facts: salience = weight * (1 + α * sum(activation
     of concepts mentioned in fact value))
  7. Refresh `state_cache` — top-K most salient facts per profile

Result: at any instant, a surface can ask "what's on her mind?" and
get a sorted answer in one SELECT, no compute. STATE assembly becomes
a lookup, not a graph walk. Working memory in pure SQL.

Cost: a single tick is a few hundred row UPDATEs against indexed cols.
On WAL SQLite, well under 50 ms. Run at 0.5-2 Hz indefinitely with
negligible CPU.

No LLM. No embeddings. Just decay and diffusion.
"""

from __future__ import annotations

import json
import time
from contextlib import closing
from typing import List, Dict, Any, Optional, Iterable

from data.db import get_connection


# ─────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────

def _ensure_schema(conn) -> None:
    cur = conn.cursor()
    # Activation overlay on concepts. Continuous; decays toward 0.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS concept_activation (
            concept TEXT PRIMARY KEY,
            activation REAL NOT NULL DEFAULT 0,
            last_kicked TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_concept_activation ON concept_activation(activation DESC)"
    )

    # Pre-baked top-salience per profile_id, refreshed each tick.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS state_cache (
            profile_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            weight REAL,
            salience REAL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (profile_id, key)
        )
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_state_cache_salience ON state_cache(salience DESC)"
    )

    # Watermark + meta
    cur.execute("""
        CREATE TABLE IF NOT EXISTS meditation_meta (
            k TEXT PRIMARY KEY,
            v TEXT
        )
    """)


def _meta_get(conn, key: str, default: str = "") -> str:
    row = conn.execute(
        "SELECT v FROM meditation_meta WHERE k=?", (key,)
    ).fetchone()
    if not row:
        return default
    return row["v"] or default


def _meta_set(conn, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meditation_meta (k,v) VALUES (?,?) "
        "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
        (key, str(value)),
    )


# ─────────────────────────────────────────────────────────────────────
# Tick
# ─────────────────────────────────────────────────────────────────────

# Tunables. Conservative — change after measuring.
KICK = 1.0          # activation injected for each concept of a new event
SPREAD = 0.35       # fraction of activation that diffuses one hop
DECAY = 0.92        # multiplicative decay each tick
FLOOR = 0.02        # below this, drop the row
TOP_SALIENT = 200   # rows kept in state_cache
ALPHA = 0.6         # contribution of activation to salience


def tick(now: Optional[float] = None) -> Dict[str, Any]:
    """One meditation tick. Returns a small summary dict."""
    t0 = time.time()
    summary: Dict[str, Any] = {
        "events_seen": 0,
        "concepts_kicked": 0,
        "spread_edges": 0,
        "decayed_rows": 0,
        "salience_rows": 0,
        "elapsed_ms": 0,
    }
    try:
        with closing(get_connection()) as conn:
            _ensure_schema(conn)

            # 1) Pull new events since watermark
            last_id = int(_meta_get(conn, "last_event_id", "0") or 0)
            mx_row = conn.execute(
                "SELECT MAX(id) AS mx FROM unified_events"
            ).fetchone()
            mx = int(mx_row["mx"] or 0)
            new_concepts: Dict[str, float] = {}
            if mx > last_id:
                rows = conn.execute(
                    """
                    SELECT id, data, tags_json, thread_subject
                    FROM unified_events
                    WHERE id > ? AND id <= ?
                    ORDER BY id ASC
                    LIMIT 200
                    """,
                    (last_id, mx),
                ).fetchall()
                summary["events_seen"] = len(rows)
                # Extract concepts cheaply: tags + thread_subject + a
                # token pass over `data` via linking_core.
                try:
                    from agent.threads.linking_core.schema import (
                        extract_concepts_from_text,
                    )
                except Exception:
                    extract_concepts_from_text = lambda _t: []  # noqa: E731
                last_seen = last_id
                for r in rows:
                    last_seen = max(last_seen, int(r["id"]))
                    tags: List[str] = []
                    if r["tags_json"]:
                        try:
                            decoded = json.loads(r["tags_json"])
                            if isinstance(decoded, list):
                                tags = [str(t).strip() for t in decoded if t]
                        except Exception:
                            pass
                    if r["thread_subject"]:
                        tags.append(str(r["thread_subject"]).strip())
                    try:
                        tags.extend(extract_concepts_from_text(r["data"] or ""))
                    except Exception:
                        pass
                    for c in tags:
                        c = c.lower()
                        if not c or len(c) > 80:
                            continue
                        if c not in new_concepts or new_concepts[c] < KICK:
                            new_concepts[c] = KICK
                _meta_set(conn, "last_event_id", str(last_seen))

            # 2) Inject activation (max-merge: don't pile on)
            if new_concepts:
                for concept, kick in new_concepts.items():
                    conn.execute(
                        """
                        INSERT INTO concept_activation (concept, activation, last_kicked, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT(concept) DO UPDATE SET
                            activation = MAX(concept_activation.activation, excluded.activation),
                            last_kicked = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (concept, float(kick)),
                    )
                summary["concepts_kicked"] = len(new_concepts)

            # 3) Spread one hop: for each currently-active concept, push
            # SPREAD * activation * link_strength to its neighbors.
            # Bounded by top 100 active concepts so cost stays flat.
            active_rows = conn.execute(
                "SELECT concept, activation FROM concept_activation "
                "WHERE activation >= ? ORDER BY activation DESC LIMIT 100",
                (FLOOR * 2,),
            ).fetchall()
            spread_count = 0
            if active_rows:
                deltas: Dict[str, float] = {}
                for ar in active_rows:
                    src = ar["concept"]
                    src_a = float(ar["activation"])
                    nbr_rows = conn.execute(
                        """
                        SELECT concept_b AS nb, strength FROM concept_links
                        WHERE concept_a = ? AND strength >= 0.1
                        UNION
                        SELECT concept_a AS nb, strength FROM concept_links
                        WHERE concept_b = ? AND strength >= 0.1
                        ORDER BY strength DESC LIMIT 8
                        """,
                        (src, src),
                    ).fetchall()
                    for nr in nbr_rows:
                        nb = nr["nb"]
                        if nb == src:
                            continue
                        push = SPREAD * src_a * float(nr["strength"])
                        if push < FLOOR:
                            continue
                        if push > deltas.get(nb, 0.0):
                            deltas[nb] = push
                        spread_count += 1
                for nb, push in deltas.items():
                    conn.execute(
                        """
                        INSERT INTO concept_activation (concept, activation, last_kicked, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT(concept) DO UPDATE SET
                            activation = MAX(concept_activation.activation, excluded.activation),
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (nb, float(push)),
                    )
            summary["spread_edges"] = spread_count

            # 4) Decay everything; drop floor rows.
            conn.execute(
                "UPDATE concept_activation SET activation = activation * ?, "
                "updated_at = CURRENT_TIMESTAMP",
                (DECAY,),
            )
            cur = conn.execute(
                "DELETE FROM concept_activation WHERE activation < ?",
                (FLOOR,),
            )
            summary["decayed_rows"] = cur.rowcount or 0

            # 5) Refresh state_cache: top-K facts ordered by salience.
            # salience = weight * (1 + ALPHA * sum_active(concepts that
            # appear lowercased in the fact key or l1_value))
            # We keep this in pure SQL: a join from profile_facts to
            # concept_activation on token equality is cheap when
            # concept_activation is small (< 1k rows).
            # Strategy: compute per-fact salience boost as the MAX
            # activation of any concept whose token appears as an exact
            # key segment.  Cheap and safe.
            conn.execute("DELETE FROM state_cache")
            try:
                conn.execute(
                    """
                    INSERT INTO state_cache (profile_id, key, value, weight, salience)
                    SELECT
                        f.profile_id,
                        f.key,
                        f.l1_value,
                        f.weight,
                        f.weight * (1.0 + ? * COALESCE((
                            SELECT MAX(ca.activation) FROM concept_activation ca
                            WHERE INSTR(LOWER(f.key) || ' ' || LOWER(COALESCE(f.l1_value,'')), ca.concept) > 0
                        ), 0.0))
                    FROM profile_facts f
                    WHERE f.weight >= 0.3
                    ORDER BY 5 DESC
                    LIMIT ?
                    """,
                    (ALPHA, TOP_SALIENT),
                )
            except Exception:
                pass
            # Add philosophy facts (separate table — no UNION needed)
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO state_cache (profile_id, key, value, weight, salience)
                    SELECT
                        'phil:' || pf.profile_id,
                        pf.key,
                        pf.l1_value,
                        pf.weight,
                        pf.weight * (1.0 + ? * COALESCE((
                            SELECT MAX(ca.activation) FROM concept_activation ca
                            WHERE INSTR(LOWER(pf.key) || ' ' || LOWER(COALESCE(pf.l1_value,'')), ca.concept) > 0
                        ), 0.0))
                    FROM philosophy_profile_facts pf
                    WHERE pf.weight >= 0.5
                    LIMIT ?
                    """,
                    (ALPHA, TOP_SALIENT),
                )
            except Exception:
                pass
            n_row = conn.execute(
                "SELECT COUNT(*) AS n FROM state_cache"
            ).fetchone()
            summary["salience_rows"] = int(n_row["n"]) if n_row else 0

            conn.commit()
    except Exception as e:
        summary["error"] = f"{type(e).__name__}: {e}"

    # 6) Cheap overlays (separate connection — read-only).
    try:
        from agent.subconscious.salience_overlay import readiness
        r = readiness()
        summary["readiness"] = r.get("score", 0.0)
        summary["ready"] = r.get("ready", False)
    except Exception:
        pass

    # 7) Session-shift emit (rate-limited to once per ~5 min).
    try:
        with closing(get_connection()) as conn:
            now_s = time.time()
            last_emit = float(_meta_get(conn, "last_shift_emit_at", "0") or 0)
            if now_s - last_emit >= 300.0:
                mt_id = detect_session_shift(min_facts=3)
                if mt_id:
                    _meta_set(conn, "last_shift_emit_at", str(now_s))
                    summary["shift_meta_id"] = int(mt_id)
                    conn.commit()
    except Exception:
        pass

    summary["elapsed_ms"] = round((time.time() - t0) * 1000, 2)
    return summary


# ─────────────────────────────────────────────────────────────────────
# Read views — what surfaces actually consume
# ─────────────────────────────────────────────────────────────────────

def hot_concepts(limit: int = 25) -> List[Dict[str, Any]]:
    """Currently most-active concepts. The DB's 'working memory'."""
    try:
        with closing(get_connection(readonly=True)) as conn:
            _ensure_schema(conn)
            rows = conn.execute(
                "SELECT concept, activation, last_kicked FROM concept_activation "
                "ORDER BY activation DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
            return [
                {
                    "concept": r["concept"],
                    "activation": round(float(r["activation"]), 4),
                    "last_kicked": r["last_kicked"],
                }
                for r in rows
            ]
    except Exception:
        return []


def top_salient(limit: int = 25, profile_prefix: Optional[str] = None) -> List[Dict[str, Any]]:
    """Top-K facts by current salience (pre-baked)."""
    try:
        with closing(get_connection(readonly=True)) as conn:
            _ensure_schema(conn)
            if profile_prefix:
                rows = conn.execute(
                    "SELECT * FROM state_cache WHERE profile_id LIKE ? "
                    "ORDER BY salience DESC LIMIT ?",
                    (profile_prefix + "%", int(limit)),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM state_cache ORDER BY salience DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def detect_session_shift(window_minutes: int = 60, min_facts: int = 3) -> Optional[int]:
    """Emit a meta-thought when the substrate has shifted meaningfully.

    A "shift" = N≥min_facts new high-weight (>=0.7) profile_facts/
    philosophy_profile_facts written since our last shift watermark.

    Idempotent via meditation_meta key 'last_shift_fact_ts'. Returns the
    new meta_thought id or None.

    This is the bridge that turns "what just happened in the DB" into
    "what the next turn will see in HOT". Without it, big architectural
    sessions like this one slip past meta_thoughts entirely.
    """
    try:
        with closing(get_connection()) as conn:
            _ensure_schema(conn)
            last_ts = _meta_get(conn, "last_shift_fact_ts", "1970-01-01 00:00:00")

            # Pull recent high-weight facts from both fact tables.
            rows_pf = conn.execute(
                """
                SELECT 'pf' AS src, profile_id, key, value, weight, updated_at
                FROM profile_facts
                WHERE updated_at > ? AND weight >= 0.7
                ORDER BY updated_at ASC
                LIMIT 50
                """,
                (last_ts,),
            ).fetchall()
            try:
                rows_ph = conn.execute(
                    """
                    SELECT 'ph' AS src, profile_id, key, l1_value AS value, weight, updated_at
                    FROM philosophy_profile_facts
                    WHERE updated_at > ? AND weight >= 0.7
                    ORDER BY updated_at ASC
                    LIMIT 50
                    """,
                    (last_ts,),
                ).fetchall()
            except Exception:
                rows_ph = []
            rows = list(rows_pf) + list(rows_ph)
            if len(rows) < int(min_facts):
                return None

            # Advance watermark unconditionally so we don't re-scan.
            new_ts = max(r["updated_at"] for r in rows)
            _meta_set(conn, "last_shift_fact_ts", str(new_ts))
            conn.commit()

        # Build a compact shift summary.
        keys = []
        for r in rows[:10]:
            k = (r["key"] or "?")[:40]
            v = (r["value"] or "")[:60].replace("\n", " ")
            keys.append(f"{r['profile_id']}.{k}={v}")
        summary = (
            f"session shift: {len(rows)} new high-weight facts "
            f"in last window — " + " | ".join(keys)
        )[:500]

        from agent.threads.reflex.schema import add_meta_thought
        return int(add_meta_thought(
            kind="compression",
            content=summary,
            source="system",
            confidence=0.8,
            weight=0.65,
        ))
    except Exception:
        return None


def meditation_stats() -> Dict[str, Any]:
    try:
        with closing(get_connection(readonly=True)) as conn:
            _ensure_schema(conn)
            n_act = conn.execute(
                "SELECT COUNT(*) AS n, MAX(activation) AS mx FROM concept_activation"
            ).fetchone()
            n_cache = conn.execute(
                "SELECT COUNT(*) AS n, MAX(salience) AS mx FROM state_cache"
            ).fetchone()
            last_id = _meta_get(conn, "last_event_id", "0")
            return {
                "active_concepts": int(n_act["n"]) if n_act else 0,
                "max_activation": round(float(n_act["mx"] or 0.0), 4) if n_act else 0.0,
                "cached_facts": int(n_cache["n"]) if n_cache else 0,
                "max_salience": round(float(n_cache["mx"] or 0.0), 4) if n_cache else 0.0,
                "watermark": int(last_id) if last_id.isdigit() else 0,
            }
    except Exception:
        return {}


__all__ = ["tick", "hot_concepts", "top_salient", "meditation_stats", "detect_session_shift"]
