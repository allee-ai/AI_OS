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

    # Consent gate FIRST (unless force=True). No consent → never touches sensory_events.
    if not force:
        try:
            from sensory.consent import is_allowed, record_blocked
            if not is_allowed(source, kind):
                record_blocked(source, kind, text, confidence, "no_consent", meta)
                return None
        except Exception:
            # Consent module failing is a closed-fail: block rather than leak.
            return None

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


# ---------------------------------------------------------------------------
# sensory_feeds — metadata for external feeds that write into sensory_events.
#
# The bus itself (sensory_events) is dumb and append-only. Real feeds (email,
# calendar, slack, ...) need somewhere to remember their cursor state, when
# they last ran, and whether they're enabled. That's this table.
#
# This is NOT a replication of STATE. It's the side-table that lets a worker
# loop know "I last polled Gmail at T, the next message after cursor C is
# what I should fetch next." The worker still writes the actual content to
# sensory_events with source='email' — same bus, same adapter, same STATE
# block. This table just answers "where was I?"
# ---------------------------------------------------------------------------

def init_sensory_feeds_table() -> None:
    """Create sensory_feeds table if missing. Called from server startup."""
    with closing(get_connection()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sensory_feeds (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                source        TEXT    NOT NULL,
                feed_kind     TEXT    NOT NULL,
                display_name  TEXT    NOT NULL,
                enabled       INTEGER NOT NULL DEFAULT 0,
                last_run_at   TEXT,
                last_cursor   TEXT,
                config_json   TEXT    NOT NULL DEFAULT '{}',
                error_count   INTEGER NOT NULL DEFAULT 0,
                last_error    TEXT,
                created_at    TEXT    NOT NULL,
                UNIQUE(source, feed_kind, display_name)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sensory_feeds_enabled "
            "ON sensory_feeds(enabled, source)"
        )
        conn.commit()


def register_feed(
    source: str,
    feed_kind: str,
    display_name: str,
    *,
    enabled: bool = False,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """Register (or upsert) a feed. Returns row id.

    Disabled by default — caller must explicitly enable. Idempotent on the
    (source, feed_kind, display_name) triple: re-registering merges config
    and preserves cursor state.
    """
    source = (source or "").strip().lower()[:40]
    feed_kind = (feed_kind or "").strip().lower()[:40]
    display_name = (display_name or "").strip()[:120]
    if not source or not feed_kind or not display_name:
        return None

    cfg_json = json.dumps(config or {}, default=str)[:4000]
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with closing(get_connection()) as conn:
        cur = conn.execute(
            "SELECT id FROM sensory_feeds "
            "WHERE source = ? AND feed_kind = ? AND display_name = ?",
            (source, feed_kind, display_name),
        )
        row = cur.fetchone()
        if row is not None:
            # Upsert: merge config, leave cursor + run state alone.
            fid = row["id"] if hasattr(row, "keys") else row[0]
            conn.execute(
                "UPDATE sensory_feeds SET config_json = ?, enabled = ? WHERE id = ?",
                (cfg_json, 1 if enabled else 0, fid),
            )
            conn.commit()
            return int(fid)
        cur = conn.execute(
            "INSERT INTO sensory_feeds "
            "(source, feed_kind, display_name, enabled, config_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (source, feed_kind, display_name, 1 if enabled else 0, cfg_json, ts),
        )
        conn.commit()
        return cur.lastrowid


def get_feeds(enabled_only: bool = False) -> List[Dict[str, Any]]:
    q = "SELECT id, source, feed_kind, display_name, enabled, last_run_at, last_cursor, config_json, error_count, last_error, created_at FROM sensory_feeds"
    if enabled_only:
        q += " WHERE enabled = 1"
    q += " ORDER BY source, display_name"
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute(q).fetchall()
    out: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        try:
            d["config"] = json.loads(d.pop("config_json") or "{}")
        except Exception:
            d["config"] = {}
        out.append(d)
    return out


def mark_feed_run(feed_id: int, cursor: Optional[str] = None) -> bool:
    """Mark a feed as just-ran. Optionally update its cursor.

    Resets error_count on success. Use this from a worker after a clean poll.
    """
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(get_connection()) as conn:
        if cursor is not None:
            cur = conn.execute(
                "UPDATE sensory_feeds "
                "SET last_run_at = ?, last_cursor = ?, error_count = 0, last_error = NULL "
                "WHERE id = ?",
                (ts, cursor[:1000], feed_id),
            )
        else:
            cur = conn.execute(
                "UPDATE sensory_feeds "
                "SET last_run_at = ?, error_count = 0, last_error = NULL "
                "WHERE id = ?",
                (ts, feed_id),
            )
        conn.commit()
        return cur.rowcount > 0


def mark_feed_error(feed_id: int, error: str) -> bool:
    """Record a feed-poll error. Increments error_count, stores last_error."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(get_connection()) as conn:
        cur = conn.execute(
            "UPDATE sensory_feeds "
            "SET last_run_at = ?, error_count = error_count + 1, last_error = ? "
            "WHERE id = ?",
            (ts, (error or "")[:500], feed_id),
        )
        conn.commit()
        return cur.rowcount > 0


def set_feed_enabled(feed_id: int, enabled: bool) -> bool:
    with closing(get_connection()) as conn:
        cur = conn.execute(
            "UPDATE sensory_feeds SET enabled = ? WHERE id = ?",
            (1 if enabled else 0, feed_id),
        )
        conn.commit()
        return cur.rowcount > 0
