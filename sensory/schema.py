"""
sensory/schema.py — the uniform sensory event bus.

One table. Any text-convertible sense writes here:
  source:  mic | vision | screen | clipboard | ambient | ...
  kind:    speech | caption | ocr | alert | ...
  text:    the actual content (already converted to text)
  meta:    optional JSON (image size, speaker, confidence, ...)
  ts:      created_at

Everything downstream (STATE adapter, feeds, search) reads from this
one table. New sense? Insert rows with a new source= value. No schema
changes needed.
"""
from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from data.db import get_connection


def init_sensory_tables() -> None:
    """Create sensory_events table if missing. Called from server startup."""
    with closing(get_connection()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sensory_events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                source     TEXT    NOT NULL,
                kind       TEXT    NOT NULL DEFAULT 'unknown',
                text       TEXT    NOT NULL,
                confidence REAL    DEFAULT 1.0,
                meta_json  TEXT    DEFAULT '{}',
                created_at TEXT    NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sensory_created ON sensory_events(created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sensory_source_created "
            "ON sensory_events(source, created_at DESC)"
        )
        conn.commit()


def record_event(
    source: str,
    text: str,
    *,
    kind: str = "unknown",
    confidence: float = 1.0,
    meta: Optional[Dict[str, Any]] = None,
    force: bool = False,
) -> Optional[int]:
    """Write a sensory event. Returns row id, or None on empty/dropped text.

    Runs the salience filter first. Below-threshold events are shadow-logged
    to `sensory_dropped` instead of appearing in STATE. Pass force=True to
    bypass the filter (user-explicit writes, migrations, tests).
    """
    text = (text or "").strip()
    if not text:
        return None
    source = (source or "unknown").strip().lower()[:40]
    kind = (kind or "unknown").strip().lower()[:40]
    confidence = max(0.0, min(1.0, float(confidence)))

    # Salience gate (unless force=True)
    if not force:
        try:
            from sensory.salience import should_promote, record_dropped
            promote, score, reason = should_promote(source, kind, text, confidence, meta)
            if not promote:
                record_dropped(source, kind, text, score, reason, meta)
                return None
        except Exception:
            # Salience module failing shouldn't block the write path
            pass

    meta_json = json.dumps(meta or {}, default=str)[:4000]
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with closing(get_connection()) as conn:
        cur = conn.execute(
            """
            INSERT INTO sensory_events(source, kind, text, confidence, meta_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source, kind, text[:4000], confidence, meta_json, ts),
        )
        conn.commit()
        return cur.lastrowid


def get_recent_events(
    limit: int = 50,
    source: Optional[str] = None,
    kinds: Optional[List[str]] = None,
    since_iso: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Read recent sensory events, newest-first."""
    q = "SELECT id, source, kind, text, confidence, meta_json, created_at FROM sensory_events"
    where: List[str] = []
    params: List[Any] = []
    if source:
        where.append("source = ?")
        params.append(source.lower())
    if kinds:
        placeholders = ",".join("?" for _ in kinds)
        where.append(f"kind IN ({placeholders})")
        params.extend(k.lower() for k in kinds)
    if since_iso:
        where.append("created_at >= ?")
        params.append(since_iso)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(max(1, min(limit, 500)))

    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute(q, params).fetchall()
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        try:
            d["meta"] = json.loads(d.pop("meta_json") or "{}")
        except Exception:
            d["meta"] = {}
        out.append(d)
    return out


def counts_by_source(since_iso: Optional[str] = None) -> Dict[str, int]:
    q = "SELECT source, COUNT(*) as n FROM sensory_events"
    params: List[Any] = []
    if since_iso:
        q += " WHERE created_at >= ?"
        params.append(since_iso)
    q += " GROUP BY source ORDER BY n DESC"
    with closing(get_connection(readonly=True)) as conn:
        return {r["source"]: r["n"] for r in conn.execute(q, params).fetchall()}


def delete_event(event_id: int) -> bool:
    with closing(get_connection()) as conn:
        cur = conn.execute("DELETE FROM sensory_events WHERE id = ?", (event_id,))
        conn.commit()
        return cur.rowcount > 0
