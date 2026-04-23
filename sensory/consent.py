"""Sensory consent gate — mechanism that enforces trust.mechanisms_must_match_trust.

Every (source, kind) pair must be explicitly enabled before `record_event` will
accept it. Writes without consent go to `sensory_blocked` (shadow log), never
to `sensory_events`. Consent flips are logged to `sensory_consent_log` for
audit. The agent has no write access to this table from inside — only the
HTTP endpoints (which require the API token) can flip a switch.

Default posture: everything OFF.
"""
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json

from data.db import get_connection


# ============================================================================
# Schema
# ============================================================================

def init_consent_tables() -> None:
    """Create consent + blocked + consent_log tables."""
    with closing(get_connection()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sensory_consent (
                source       TEXT NOT NULL,
                kind         TEXT NOT NULL,
                enabled      INTEGER NOT NULL DEFAULT 0,
                enabled_at   TEXT,
                enabled_by   TEXT,
                notes        TEXT,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL,
                PRIMARY KEY (source, kind)
            );

            CREATE TABLE IF NOT EXISTS sensory_blocked (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                source       TEXT NOT NULL,
                kind         TEXT NOT NULL,
                text         TEXT NOT NULL,
                confidence   REAL NOT NULL,
                reason       TEXT NOT NULL,
                meta_json    TEXT,
                created_at   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sensory_blocked_created
                ON sensory_blocked(created_at DESC);

            CREATE TABLE IF NOT EXISTS sensory_consent_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                source       TEXT NOT NULL,
                kind         TEXT NOT NULL,
                action       TEXT NOT NULL,   -- 'enable' | 'disable' | 'seed'
                actor        TEXT,
                notes        TEXT,
                created_at   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sensory_consent_log_created
                ON sensory_consent_log(created_at DESC);
            """
        )
        conn.commit()


def seed_consent_from_taxonomy() -> int:
    """Seed one row per (source, kind) from the canonical taxonomy, all disabled.

    Idempotent. Returns number of rows added (not rows already present).
    """
    from sensory.taxonomy import SOURCES

    init_consent_tables()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    added = 0
    with closing(get_connection()) as conn:
        for source, kinds in SOURCES.items():
            for kind in kinds.keys():
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO sensory_consent(
                        source, kind, enabled, created_at, updated_at
                    ) VALUES (?, ?, 0, ?, ?)
                    """,
                    (source, kind, now, now),
                )
                if cur.rowcount:
                    added += 1
                    conn.execute(
                        """
                        INSERT INTO sensory_consent_log(
                            source, kind, action, actor, notes, created_at
                        ) VALUES (?, ?, 'seed', 'system', 'seeded from taxonomy', ?)
                        """,
                        (source, kind, now),
                    )
        conn.commit()
    return added


# ============================================================================
# Consent check (read-only from agent write paths)
# ============================================================================

def is_allowed(source: str, kind: str) -> bool:
    """Return True only if (source, kind) has been explicitly enabled."""
    source = (source or "").strip().lower()[:40]
    kind = (kind or "").strip().lower()[:40]
    with closing(get_connection(readonly=True)) as conn:
        row = conn.execute(
            "SELECT enabled FROM sensory_consent WHERE source=? AND kind=?",
            (source, kind),
        ).fetchone()
    return bool(row and row["enabled"])


def record_blocked(
    source: str,
    kind: str,
    text: str,
    confidence: float,
    reason: str,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Shadow-log an event that was refused consent. Never touches sensory_events."""
    init_consent_tables()
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta_json = json.dumps(meta or {}, default=str)[:4000]
    with closing(get_connection()) as conn:
        conn.execute(
            """
            INSERT INTO sensory_blocked(
                source, kind, text, confidence, reason, meta_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (source, kind, text[:4000], float(confidence), reason, meta_json, ts),
        )
        conn.commit()


# ============================================================================
# Consent flips (HTTP-only — callers must come through the API)
# ============================================================================

def set_consent(
    source: str,
    kind: str,
    enabled: bool,
    actor: str = "http",
    notes: str = "",
) -> Dict[str, Any]:
    """Enable or disable a (source, kind). Logs to audit table."""
    init_consent_tables()
    source = (source or "").strip().lower()[:40]
    kind = (kind or "").strip().lower()[:40]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    action = "enable" if enabled else "disable"

    with closing(get_connection()) as conn:
        # upsert consent row
        conn.execute(
            """
            INSERT INTO sensory_consent(
                source, kind, enabled, enabled_at, enabled_by, notes,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, kind) DO UPDATE SET
                enabled    = excluded.enabled,
                enabled_at = CASE WHEN excluded.enabled=1 THEN ? ELSE enabled_at END,
                enabled_by = CASE WHEN excluded.enabled=1 THEN ? ELSE enabled_by END,
                notes      = excluded.notes,
                updated_at = ?
            """,
            (
                source, kind, 1 if enabled else 0, now if enabled else None,
                actor if enabled else None, notes, now, now,
                now, actor, now,
            ),
        )
        # audit log
        conn.execute(
            """
            INSERT INTO sensory_consent_log(
                source, kind, action, actor, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source, kind, action, actor, notes, now),
        )
        conn.commit()

    return {
        "source": source,
        "kind": kind,
        "enabled": enabled,
        "actor": actor,
        "at": now,
    }


def list_consent(source: Optional[str] = None) -> List[Dict[str, Any]]:
    init_consent_tables()
    with closing(get_connection(readonly=True)) as conn:
        if source:
            rows = conn.execute(
                "SELECT * FROM sensory_consent WHERE source=? ORDER BY source, kind",
                (source,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sensory_consent ORDER BY source, kind"
            ).fetchall()
    return [dict(r) for r in rows]


def recent_blocked(limit: int = 50, source: Optional[str] = None) -> List[Dict[str, Any]]:
    init_consent_tables()
    with closing(get_connection(readonly=True)) as conn:
        if source:
            rows = conn.execute(
                "SELECT * FROM sensory_blocked WHERE source=? "
                "ORDER BY created_at DESC LIMIT ?",
                (source, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sensory_blocked ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def recent_consent_log(limit: int = 100) -> List[Dict[str, Any]]:
    init_consent_tables()
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute(
            "SELECT * FROM sensory_consent_log ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
