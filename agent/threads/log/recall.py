"""
log.recall — FTS5-backed event retrieval.
=========================================

Pure-SQL recall over unified_events. No LLM, no embeddings.
Uses SQLite FTS5 (BM25 ranking) optionally re-scored with recency.

The FTS index is rebuilt incrementally: a `unified_events_fts` virtual
table mirrors `unified_events.data`, and a small `_fts_meta` row tracks
the last-indexed event id so we only insert new rows on each refresh.

Public:
  ensure_fts_index()              — idempotent setup + incremental sync
  recall(query, k=10, recency_h=72) — top-k events by combined score
  recall_stats()                  — index size, lag, last refresh

Cheap to call on the heartbeat: `ensure_fts_index()` will be a no-op
when no new events exist.
"""

from __future__ import annotations

import math
import time
from contextlib import closing
from typing import List, Dict, Any, Optional

from data.db import get_connection


_FTS_TABLE = "unified_events_fts"
_FTS_META = "unified_events_fts_meta"


# ─────────────────────────────────────────────────────────────────────
# Schema / sync
# ─────────────────────────────────────────────────────────────────────

def _ensure_schema(conn) -> None:
    cur = conn.cursor()
    cur.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS {_FTS_TABLE}
        USING fts5(
            data,
            tags,
            thread_subject,
            content='',
            tokenize='unicode61 remove_diacritics 1'
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {_FTS_META} (
            k TEXT PRIMARY KEY,
            v TEXT
        )
    """)


def _get_last_id(conn) -> int:
    row = conn.execute(
        f"SELECT v FROM {_FTS_META} WHERE k='last_id'"
    ).fetchone()
    if not row:
        return 0
    try:
        return int(row["v"])
    except Exception:
        return 0


def _set_last_id(conn, last_id: int) -> None:
    conn.execute(
        f"INSERT INTO {_FTS_META} (k, v) VALUES ('last_id', ?) "
        f"ON CONFLICT(k) DO UPDATE SET v=excluded.v",
        (str(int(last_id)),),
    )
    conn.execute(
        f"INSERT INTO {_FTS_META} (k, v) VALUES ('last_refresh', ?) "
        f"ON CONFLICT(k) DO UPDATE SET v=excluded.v",
        (str(int(time.time())),),
    )


def ensure_fts_index(batch: int = 500) -> int:
    """Sync new events into the FTS index. Returns rows added.

    Idempotent. Safe to call from a hot loop — when there are no new
    events the cost is one SELECT MAX(id).
    """
    try:
        with closing(get_connection()) as conn:
            _ensure_schema(conn)
            last = _get_last_id(conn)
            row = conn.execute(
                "SELECT MAX(id) AS mx FROM unified_events"
            ).fetchone()
            mx = int(row["mx"] or 0)
            if mx <= last:
                return 0

            cur = conn.cursor()
            added = 0
            cursor_id = last
            while cursor_id < mx:
                rows = cur.execute(
                    """
                    SELECT id, data, tags_json, thread_subject
                    FROM unified_events
                    WHERE id > ? AND id <= ?
                    ORDER BY id ASC
                    """,
                    (cursor_id, min(cursor_id + batch, mx)),
                ).fetchall()
                if not rows:
                    break
                payload = []
                for r in rows:
                    rid = int(r["id"])
                    data = (r["data"] or "")[:4000]
                    tags = r["tags_json"] or ""
                    subj = r["thread_subject"] or ""
                    payload.append((rid, data, tags, subj))
                cur.executemany(
                    f"INSERT INTO {_FTS_TABLE} (rowid, data, tags, thread_subject) "
                    f"VALUES (?, ?, ?, ?)",
                    payload,
                )
                added += len(payload)
                cursor_id = int(rows[-1]["id"])

            _set_last_id(conn, mx)
            conn.commit()
            return added
    except Exception:
        return 0


# ─────────────────────────────────────────────────────────────────────
# Recall
# ─────────────────────────────────────────────────────────────────────

def _sanitize_query(q: str) -> str:
    """FTS5 query sanitizer — strip operators that would crash on user text."""
    if not q:
        return ""
    bad = '"'
    cleaned = q.replace(bad, " ").strip()
    # Use prefix matching on each token for forgiving recall.
    tokens = [t for t in cleaned.split() if len(t) > 1]
    if not tokens:
        return ""
    return " OR ".join(f"{t}*" for t in tokens[:10])


def recall(
    query: str,
    k: int = 10,
    recency_h: float = 72.0,
    recency_weight: float = 0.5,
) -> List[Dict[str, Any]]:
    """Top-k events for a query.

    Score = bm25 (lower=better, we negate) + recency_weight * exp(-age_h/recency_h)

    Returns list of dicts with keys: id, data, event_type, timestamp,
    score, bm25, recency.
    """
    fts_q = _sanitize_query(query)
    if not fts_q:
        return []
    try:
        ensure_fts_index()
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                f"""
                SELECT
                    e.id           AS id,
                    e.data         AS data,
                    e.event_type   AS event_type,
                    e.timestamp    AS timestamp,
                    e.thread_subject AS thread_subject,
                    bm25({_FTS_TABLE}) AS bm25,
                    (julianday('now') - julianday(e.timestamp)) * 24.0 AS age_h
                FROM {_FTS_TABLE} f
                JOIN unified_events e ON e.id = f.rowid
                WHERE {_FTS_TABLE} MATCH ?
                ORDER BY bm25 ASC
                LIMIT ?
                """,
                (fts_q, int(k * 4)),
            ).fetchall()
    except Exception:
        return []

    results: List[Dict[str, Any]] = []
    for r in rows:
        bm25 = float(r["bm25"] or 0.0)
        # bm25 in SQLite FTS5 returns negative-ish floats; smaller=better.
        # Map to a positive relevance: relevance = 1 / (1 + |bm25|).
        relevance = 1.0 / (1.0 + abs(bm25))
        try:
            age_h = float(r["age_h"] or 0.0)
        except Exception:
            age_h = 0.0
        recency = math.exp(-age_h / max(1e-3, recency_h)) if recency_h > 0 else 0.0
        score = relevance + recency_weight * recency
        results.append({
            "id": int(r["id"]),
            "data": (r["data"] or "")[:300],
            "event_type": r["event_type"],
            "timestamp": r["timestamp"],
            "thread_subject": r["thread_subject"],
            "score": round(score, 4),
            "bm25": round(bm25, 4),
            "recency": round(recency, 4),
            "age_h": round(age_h, 2),
        })

    results.sort(key=lambda d: d["score"], reverse=True)
    return results[:k]


def recall_stats() -> Dict[str, Any]:
    try:
        with closing(get_connection(readonly=True)) as conn:
            _ensure_schema(conn)
            n = conn.execute(
                f"SELECT COUNT(*) AS n FROM {_FTS_TABLE}"
            ).fetchone()
            last_id_row = conn.execute(
                f"SELECT v FROM {_FTS_META} WHERE k='last_id'"
            ).fetchone()
            last_refresh_row = conn.execute(
                f"SELECT v FROM {_FTS_META} WHERE k='last_refresh'"
            ).fetchone()
            mx = conn.execute(
                "SELECT MAX(id) AS mx FROM unified_events"
            ).fetchone()
            return {
                "indexed": int(n["n"]) if n else 0,
                "last_id": int(last_id_row["v"]) if last_id_row else 0,
                "last_refresh_unix": int(last_refresh_row["v"]) if last_refresh_row else 0,
                "max_event_id": int(mx["mx"] or 0) if mx else 0,
                "lag": (int(mx["mx"] or 0) - (int(last_id_row["v"]) if last_id_row else 0)),
            }
    except Exception:
        return {"indexed": 0, "lag": -1}


__all__ = ["ensure_fts_index", "recall", "recall_stats"]
