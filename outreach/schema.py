"""
outreach/schema.py — outbound queue table + CRUD.

Status lifecycle:
    drafted   → approved → sent
        ↓           ↓
     rejected   failed (retryable)

Every state transition logs into the log thread (unified_events) so it
shows up in STATE the standard way.
"""

from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from data.db import get_connection


# ── Schema ────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS outreach_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_key     TEXT,                 -- identity profile key, e.g. "external.jane@x.com"
    to_email        TEXT NOT NULL,
    to_name         TEXT,
    subject         TEXT NOT NULL,
    body            TEXT NOT NULL,
    purpose         TEXT,                 -- short tag: "outreach", "followup", "reply", "thanks"
    thread_ref      TEXT,                 -- optional: parent message-id (for replies)
    status          TEXT NOT NULL DEFAULT 'drafted',  -- drafted|approved|sent|failed|rejected
    drafted_by      TEXT DEFAULT 'nola',  -- who wrote this draft (for audit)
    approved_by     TEXT,
    send_after      TEXT,                 -- ISO timestamp; if NULL, send immediately on approval
    sent_at         TEXT,
    sent_message_id TEXT,
    error           TEXT,
    retry_count     INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata_json   TEXT
);

CREATE INDEX IF NOT EXISTS idx_outreach_status   ON outreach_queue(status);
CREATE INDEX IF NOT EXISTS idx_outreach_contact  ON outreach_queue(contact_key);
CREATE INDEX IF NOT EXISTS idx_outreach_send_after ON outreach_queue(send_after) WHERE status='approved';
"""


def init_outreach_tables() -> None:
    """Create the outreach_queue table.  Safe to call repeatedly."""
    with closing(get_connection()) as conn:
        conn.executescript(_DDL)
        conn.commit()


# ── Helpers ───────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_dict(row) -> Dict[str, Any]:
    d = dict(row)
    if d.get("metadata_json"):
        try:
            d["metadata"] = json.loads(d["metadata_json"])
        except Exception:
            d["metadata"] = {}
    else:
        d["metadata"] = {}
    return d


def _log(event_type: str, data: str, metadata: Optional[Dict[str, Any]] = None,
         related_key: Optional[str] = None) -> None:
    """Best-effort log into the log thread.  Never raises."""
    try:
        from agent.threads.log.schema import log_event
        log_event(
            event_type=event_type,
            data=data,
            metadata=metadata or {},
            source="outreach",
            related_key=related_key,
            related_table="outreach_queue",
        )
    except Exception:
        pass


# ── CRUD ──────────────────────────────────────────────────────────────

def queue_draft(
    *,
    to_email: str,
    subject: str,
    body: str,
    to_name: Optional[str] = None,
    contact_key: Optional[str] = None,
    purpose: str = "outreach",
    thread_ref: Optional[str] = None,
    drafted_by: str = "nola",
    metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """Insert a new drafted outreach item.  Returns its id.

    The draft sits in 'drafted' state until approve_draft() is called.
    Nothing is sent until --send moves it from approved → sent.
    """
    init_outreach_tables()
    md_json = json.dumps(metadata) if metadata else None
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO outreach_queue
                (contact_key, to_email, to_name, subject, body, purpose,
                 thread_ref, status, drafted_by, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'drafted', ?, ?)
            """,
            (contact_key, to_email, to_name, subject, body, purpose,
             thread_ref, drafted_by, md_json),
        )
        new_id = cur.lastrowid
        conn.commit()
    _log(
        event_type="outreach",
        data=f"drafted #{new_id} → {to_email} :: {subject[:80]}",
        metadata={"id": new_id, "purpose": purpose, "to": to_email},
        related_key=f"outreach.{new_id}",
    )
    return new_id


def approve_draft(item_id: int, *, approved_by: str = "cade",
                  send_after: Optional[str] = None) -> bool:
    """Move drafted → approved.  Optional send_after = ISO timestamp."""
    init_outreach_tables()
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE outreach_queue
               SET status='approved',
                   approved_by=?,
                   send_after=?,
                   updated_at=?
             WHERE id=? AND status='drafted'
            """,
            (approved_by, send_after, _now_iso(), item_id),
        )
        ok = cur.rowcount > 0
        conn.commit()
    if ok:
        _log(
            event_type="outreach",
            data=f"approved #{item_id} (by {approved_by})",
            metadata={"id": item_id, "send_after": send_after},
            related_key=f"outreach.{item_id}",
        )
    return ok


def reject_draft(item_id: int, *, reason: str = "") -> bool:
    """Move drafted → rejected (won't be sent)."""
    init_outreach_tables()
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE outreach_queue
               SET status='rejected', error=?, updated_at=?
             WHERE id=? AND status IN ('drafted','approved')
            """,
            (reason or None, _now_iso(), item_id),
        )
        ok = cur.rowcount > 0
        conn.commit()
    if ok:
        _log(
            event_type="outreach",
            data=f"rejected #{item_id}: {reason or '(no reason)'}",
            metadata={"id": item_id, "reason": reason},
            related_key=f"outreach.{item_id}",
        )
    return ok


def set_send_after(item_id: int, send_after: Optional[str]) -> bool:
    init_outreach_tables()
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE outreach_queue SET send_after=?, updated_at=? WHERE id=?",
            (send_after, _now_iso(), item_id),
        )
        ok = cur.rowcount > 0
        conn.commit()
    return ok


def mark_sent(item_id: int, *, message_id: str = "") -> bool:
    init_outreach_tables()
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE outreach_queue
               SET status='sent', sent_at=?, sent_message_id=?, updated_at=?, error=NULL
             WHERE id=? AND status='approved'
            """,
            (_now_iso(), message_id or None, _now_iso(), item_id),
        )
        ok = cur.rowcount > 0
        conn.commit()
    if ok:
        _log(
            event_type="outreach",
            data=f"sent #{item_id} message_id={message_id or '(none)'}",
            metadata={"id": item_id, "message_id": message_id},
            related_key=f"outreach.{item_id}",
        )
    return ok


def mark_failed(item_id: int, *, error: str) -> bool:
    init_outreach_tables()
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE outreach_queue
               SET status='failed', error=?, retry_count=retry_count+1, updated_at=?
             WHERE id=?
            """,
            (error[:1000], _now_iso(), item_id),
        )
        ok = cur.rowcount > 0
        conn.commit()
    if ok:
        _log(
            event_type="outreach",
            data=f"failed #{item_id}: {error[:200]}",
            metadata={"id": item_id, "error": error[:500]},
            related_key=f"outreach.{item_id}",
        )
    return ok


def list_queue(status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    init_outreach_tables()
    with closing(get_connection(readonly=True)) as conn:
        if status:
            cur = conn.execute(
                "SELECT * FROM outreach_queue WHERE status=? ORDER BY id DESC LIMIT ?",
                (status, limit),
            )
        else:
            cur = conn.execute(
                "SELECT * FROM outreach_queue ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        return [_row_to_dict(r) for r in cur.fetchall()]


def get_item(item_id: int) -> Optional[Dict[str, Any]]:
    init_outreach_tables()
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.execute(
            "SELECT * FROM outreach_queue WHERE id=?", (item_id,),
        )
        row = cur.fetchone()
        return _row_to_dict(row) if row else None
