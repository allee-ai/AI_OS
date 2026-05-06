"""
slots — per-thread state cache.
===============================

For every (thread_subject, tag) pair, remember the latest event id +
timestamp. Lets the system answer "is this thread live?" or "when was
the last pitch_sent for jake_retainer?" in one O(1) lookup, no LLM,
no scan.

The slots table is rebuilt incrementally from unified_events. A small
meta row tracks the last-scanned event id so each tick is cheap.
"""

from __future__ import annotations

import json
import time
from contextlib import closing
from typing import List, Dict, Any, Optional

from data.db import get_connection


_SLOTS_TABLE = "thread_slots"
_META_TABLE = "thread_slots_meta"


def _ensure_schema(conn) -> None:
    cur = conn.cursor()
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {_SLOTS_TABLE} (
            thread_subject TEXT NOT NULL,
            tag TEXT NOT NULL,
            last_event_id INTEGER NOT NULL,
            last_ts TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (thread_subject, tag)
        )
    """)
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS idx_slots_thread ON {_SLOTS_TABLE}(thread_subject)"
    )
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS idx_slots_ts ON {_SLOTS_TABLE}(last_ts DESC)"
    )
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {_META_TABLE} (
            k TEXT PRIMARY KEY,
            v TEXT
        )
    """)


def _get_last_id(conn) -> int:
    row = conn.execute(
        f"SELECT v FROM {_META_TABLE} WHERE k='last_id'"
    ).fetchone()
    if not row:
        return 0
    try:
        return int(row["v"])
    except Exception:
        return 0


def _set_last_id(conn, last_id: int) -> None:
    conn.execute(
        f"INSERT INTO {_META_TABLE} (k,v) VALUES ('last_id',?) "
        f"ON CONFLICT(k) DO UPDATE SET v=excluded.v",
        (str(int(last_id)),),
    )


def refresh_slots(batch: int = 1000) -> int:
    """Pull new events with thread_subject set; upsert (thread, tag) slots.

    Returns number of slot rows touched.
    """
    try:
        with closing(get_connection()) as conn:
            _ensure_schema(conn)
            last = _get_last_id(conn)
            mx_row = conn.execute(
                "SELECT MAX(id) AS mx FROM unified_events"
            ).fetchone()
            mx = int(mx_row["mx"] or 0)
            if mx <= last:
                return 0

            cur = conn.cursor()
            touched = 0
            cursor = last
            while cursor < mx:
                rows = cur.execute(
                    """
                    SELECT id, thread_subject, tags_json, timestamp
                    FROM unified_events
                    WHERE id > ? AND id <= ?
                      AND thread_subject IS NOT NULL
                      AND thread_subject != ''
                    ORDER BY id ASC
                    """,
                    (cursor, min(cursor + batch, mx)),
                ).fetchall()
                if not rows:
                    cursor = min(cursor + batch, mx)
                    continue
                for r in rows:
                    rid = int(r["id"])
                    subj = (r["thread_subject"] or "").strip()
                    ts = r["timestamp"]
                    tags: List[str] = []
                    if r["tags_json"]:
                        try:
                            decoded = json.loads(r["tags_json"])
                            if isinstance(decoded, list):
                                tags = [str(t).strip() for t in decoded if t]
                        except Exception:
                            pass
                    if not tags:
                        # Still record subject-only presence under "_any".
                        tags = ["_any"]
                    for tag in tags:
                        cur.execute(
                            f"""
                            INSERT INTO {_SLOTS_TABLE}
                                (thread_subject, tag, last_event_id, last_ts, count)
                            VALUES (?, ?, ?, ?, 1)
                            ON CONFLICT(thread_subject, tag) DO UPDATE SET
                                last_event_id = excluded.last_event_id,
                                last_ts = excluded.last_ts,
                                count = {_SLOTS_TABLE}.count + 1
                            """,
                            (subj, tag, rid, ts),
                        )
                        touched += 1
                cursor = int(rows[-1]["id"])

            _set_last_id(conn, mx)
            conn.commit()
            return touched
    except Exception:
        return 0


def threads_silent_for(hours: float = 168.0, limit: int = 20) -> List[Dict[str, Any]]:
    """Threads whose latest event is older than N hours, ordered oldest first."""
    try:
        with closing(get_connection(readonly=True)) as conn:
            _ensure_schema(conn)
            rows = conn.execute(
                f"""
                SELECT thread_subject,
                       MAX(last_ts) AS last_ts,
                       SUM(count)   AS total
                FROM {_SLOTS_TABLE}
                GROUP BY thread_subject
                HAVING (julianday('now') - julianday(MAX(last_ts))) * 24.0 > ?
                ORDER BY last_ts ASC
                LIMIT ?
                """,
                (float(hours), int(limit)),
            ).fetchall()
            return [
                {
                    "thread": r["thread_subject"],
                    "last_ts": r["last_ts"],
                    "total_events": int(r["total"] or 0),
                }
                for r in rows
            ]
    except Exception:
        return []


def thread_state(subject: str) -> Dict[str, Any]:
    """Full slot table for a single thread."""
    try:
        with closing(get_connection(readonly=True)) as conn:
            _ensure_schema(conn)
            rows = conn.execute(
                f"""
                SELECT tag, last_event_id, last_ts, count
                FROM {_SLOTS_TABLE}
                WHERE thread_subject = ?
                ORDER BY last_ts DESC
                """,
                (subject,),
            ).fetchall()
            return {
                "thread": subject,
                "tags": [
                    {
                        "tag": r["tag"],
                        "last_event_id": int(r["last_event_id"]),
                        "last_ts": r["last_ts"],
                        "count": int(r["count"]),
                    }
                    for r in rows
                ],
            }
    except Exception:
        return {"thread": subject, "tags": []}


def slot_stats() -> Dict[str, Any]:
    try:
        with closing(get_connection(readonly=True)) as conn:
            _ensure_schema(conn)
            n = conn.execute(
                f"SELECT COUNT(*) AS n FROM {_SLOTS_TABLE}"
            ).fetchone()
            t = conn.execute(
                f"SELECT COUNT(DISTINCT thread_subject) AS n FROM {_SLOTS_TABLE}"
            ).fetchone()
            li = conn.execute(
                f"SELECT v FROM {_META_TABLE} WHERE k='last_id'"
            ).fetchone()
            return {
                "rows": int(n["n"]) if n else 0,
                "threads": int(t["n"]) if t else 0,
                "last_id": int(li["v"]) if li else 0,
            }
    except Exception:
        return {"rows": 0, "threads": 0, "last_id": 0}


__all__ = [
    "refresh_slots",
    "threads_silent_for",
    "thread_state",
    "slot_stats",
]
