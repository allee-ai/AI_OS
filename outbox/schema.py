"""
Outbox Schema
=============
Single table `outbox` plus CRUD. A card is a proposed action awaiting
operator review.

motor: which subsystem produced it (goal_proposal, email_draft, message,
       file_edit, thought_share, promise_nag, weekly_review, ...).
title: one-line summary, what would happen if approved.
body:  full draft / detail (may be empty for simple yes/no cards).
context: JSON blob with evidence, reasoning, source events.
priority: 0..1 sort key. Higher = more urgent / important.
status:  pending → approved | rejected | edited | expired.
related_table / related_id: optional FK back to the producing row
                            (e.g. proposed_goals.id=42).
resolution_note: operator's reason (free text).
edited_body: if status='edited', the user's revised text.

Approving / rejecting / editing emits a unified_events row so reflex
and meditation can learn from the supervision signal.
"""

import json
import time
from contextlib import closing
from typing import Any, Dict, List, Optional

from data.db import get_connection


# ─────────────────────────────────────────────────────────────
# Table
# ─────────────────────────────────────────────────────────────

def init_outbox_table() -> None:
    """Create outbox table + indexes if they don't exist."""
    with closing(get_connection()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                motor TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                context_json TEXT NOT NULL DEFAULT '{}',
                priority REAL NOT NULL DEFAULT 0.5,
                status TEXT NOT NULL DEFAULT 'pending',
                related_table TEXT,
                related_id INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                resolved_at TEXT,
                resolution_note TEXT,
                edited_body TEXT,
                expires_at TEXT
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_outbox_status_priority "
            "ON outbox(status, priority DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_outbox_motor "
            "ON outbox(motor, status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_outbox_related "
            "ON outbox(related_table, related_id)"
        )
        conn.commit()


def _ensure() -> None:
    init_outbox_table()


# ─────────────────────────────────────────────────────────────
# Writes
# ─────────────────────────────────────────────────────────────

def create_card(
    motor: str,
    title: str,
    body: str = "",
    context: Optional[Dict[str, Any]] = None,
    priority: float = 0.5,
    related_table: Optional[str] = None,
    related_id: Optional[int] = None,
    expires_at: Optional[str] = None,
) -> int:
    """Drop a new card in the outbox. Returns its id.

    De-duplicates on (motor, related_table, related_id) when both refs are
    set and an existing pending card already points at the same row — in
    that case the existing card's id is returned without creating a new one.
    """
    _ensure()
    motor = (motor or "unknown").strip()
    title = (title or "").strip() or "(untitled)"
    body = body or ""
    priority = max(0.0, min(1.0, float(priority)))
    ctx_json = json.dumps(context or {})

    with closing(get_connection()) as conn:
        if related_table and related_id is not None:
            row = conn.execute(
                "SELECT id FROM outbox WHERE motor=? AND related_table=? "
                "AND related_id=? AND status='pending' LIMIT 1",
                (motor, related_table, int(related_id)),
            ).fetchone()
            if row:
                return int(row[0] if not isinstance(row, dict) else row["id"])

        cur = conn.execute(
            """
            INSERT INTO outbox
                (motor, title, body, context_json, priority,
                 related_table, related_id, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (motor, title, body, ctx_json, priority,
             related_table, related_id, expires_at),
        )
        conn.commit()
        return int(cur.lastrowid)


def resolve_card(
    card_id: int,
    status: str,
    note: Optional[str] = None,
    edited_body: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Mark a card resolved. status ∈ {approved, rejected, edited, expired}.

    Emits a unified_events row so reflex / meditation can learn from the
    supervision signal. Returns the updated card dict, or None if the
    card doesn't exist.
    """
    _ensure()
    if status not in {"approved", "rejected", "edited", "expired"}:
        raise ValueError(f"invalid outbox resolution status: {status!r}")

    with closing(get_connection()) as conn:
        row = conn.execute(
            "SELECT * FROM outbox WHERE id=?", (card_id,)
        ).fetchone()
        if not row:
            return None

        conn.execute(
            """
            UPDATE outbox
               SET status=?,
                   resolved_at=datetime('now'),
                   resolution_note=COALESCE(?, resolution_note),
                   edited_body=COALESCE(?, edited_body)
             WHERE id=?
            """,
            (status, note, edited_body, card_id),
        )
        conn.commit()

        updated = conn.execute(
            "SELECT * FROM outbox WHERE id=?", (card_id,)
        ).fetchone()

    card = _row_to_dict(updated)
    _emit_resolution_event(card)
    return card


def _emit_resolution_event(card: Dict[str, Any]) -> None:
    """Record an outbox.resolved event in unified_events.

    Best-effort — never raise. The supervision signal is valuable
    training data for reflex and the meditation overlay.
    """
    try:
        from agent.threads.log.schema import log_event
        title = card.get("title") or "(untitled)"
        motor = card.get("motor") or "unknown"
        status = card.get("status") or "?"
        log_event(
            event_type="outbox",
            data=f"[{motor}] {status}: {title}",
            metadata={
                "card_id": card.get("id"),
                "motor": motor,
                "status": status,
                "priority": card.get("priority"),
                "resolution_note": card.get("resolution_note"),
                "related_table": card.get("related_table"),
                "related_id": card.get("related_id"),
            },
            source="user",
            related_table="outbox",
            tags=["outbox", motor, status],
        )
    except Exception as e:  # noqa: BLE001
        # Never let logging failure poison the resolve path.
        try:
            print(f"[outbox] log_event failed: {e}")
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# Reads
# ─────────────────────────────────────────────────────────────

def _row_to_dict(row) -> Dict[str, Any]:
    if row is None:
        return {}
    d = dict(row)
    raw = d.get("context_json") or "{}"
    try:
        d["context"] = json.loads(raw)
    except Exception:
        d["context"] = {}
    d.pop("context_json", None)
    return d


def list_cards(
    status: Optional[str] = "pending",
    motor: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List cards, default = pending, sorted by (priority desc, created_at desc)."""
    _ensure()
    sql = "SELECT * FROM outbox WHERE 1=1"
    args: List[Any] = []
    if status and status != "all":
        sql += " AND status=?"
        args.append(status)
    if motor:
        sql += " AND motor=?"
        args.append(motor)
    sql += " ORDER BY priority DESC, created_at DESC LIMIT ?"
    args.append(int(max(1, min(500, limit))))

    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute(sql, tuple(args)).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_card(card_id: int) -> Optional[Dict[str, Any]]:
    _ensure()
    with closing(get_connection(readonly=True)) as conn:
        row = conn.execute(
            "SELECT * FROM outbox WHERE id=?", (int(card_id),)
        ).fetchone()
    return _row_to_dict(row) if row else None


def count_pending(motor: Optional[str] = None) -> int:
    _ensure()
    sql = "SELECT COUNT(*) AS c FROM outbox WHERE status='pending'"
    args: List[Any] = []
    if motor:
        sql += " AND motor=?"
        args.append(motor)
    with closing(get_connection(readonly=True)) as conn:
        row = conn.execute(sql, tuple(args)).fetchone()
    if row is None:
        return 0
    try:
        return int(row["c"])
    except Exception:
        return int(row[0])


def expire_old_cards(max_age_hours: float = 168.0) -> int:
    """Mark very old pending cards as expired. Returns count expired."""
    _ensure()
    cutoff = time.time() - (max_age_hours * 3600.0)
    # SQLite stores datetime('now') as ISO 'YYYY-MM-DD HH:MM:SS'
    import datetime as _dt
    cutoff_iso = _dt.datetime.utcfromtimestamp(cutoff).strftime("%Y-%m-%d %H:%M:%S")
    with closing(get_connection()) as conn:
        cur = conn.execute(
            "UPDATE outbox SET status='expired', resolved_at=datetime('now') "
            "WHERE status='pending' AND created_at < ?",
            (cutoff_iso,),
        )
        conn.commit()
        return int(cur.rowcount or 0)
