"""
Field Thread Schema
===================

Situational awareness — what's around me right now.

Privacy model:
    - All identifiers (MAC, BLE ID, beacon UUID) are SHA-256 hashed on insert
      with a per-install salt; raw values never touch disk.
    - Default TTL = 1 hour for raw observations.
    - Default TTL = 24 hours for aggregated presence patterns.
    - Default TTL = 7 days for alerts (the only thing worth remembering).
    - The cleanup() function MUST be called by a periodic loop.
    - There is no API to retrieve the salt — observations cannot be reversed.

Tables:
    field_environments  - places the user has been (home, cafe, work)
    field_observations  - ephemeral signals (hashed MAC + signal + ts)
    field_presences     - aggregated: hash X seen in env Y, N times
    field_alerts        - patterns worth surfacing ("unfamiliar device 3 days running")
    field_meta          - the install salt + last-cleanup timestamp
"""

import sqlite3
import threading
import hashlib
import secrets
import time
from contextlib import closing
from typing import List, Dict, Optional

from data.db import get_connection

_init_lock = threading.Lock()
_initialized = False
_salt_cache: Optional[str] = None


# ============================================================================
# Salt management (privacy foundation)
# ============================================================================

def _get_salt(conn: sqlite3.Connection) -> str:
    """Get or create the per-install hashing salt. Cached after first read."""
    global _salt_cache
    if _salt_cache:
        return _salt_cache
    cur = conn.cursor()
    row = cur.execute("SELECT value FROM field_meta WHERE key='salt'").fetchone()
    if row:
        _salt_cache = row[0] if not hasattr(row, "keys") else row["value"]
        return _salt_cache
    salt = secrets.token_hex(32)
    cur.execute("INSERT INTO field_meta (key, value) VALUES ('salt', ?)", (salt,))
    conn.commit()
    _salt_cache = salt
    return salt


def hash_identifier(raw: str, conn: Optional[sqlite3.Connection] = None) -> str:
    """One-way hash of any identifier (MAC, BLE id, etc). Salted per-install."""
    own = conn is None
    conn = conn or get_connection()
    try:
        salt = _get_salt(conn)
        return hashlib.sha256(f"{salt}:{raw.lower().strip()}".encode()).hexdigest()[:16]
    finally:
        if own:
            conn.close()


# ============================================================================
# Tables
# ============================================================================

def init_field_meta(conn: Optional[sqlite3.Connection] = None) -> None:
    own = conn is None
    conn = conn or get_connection()
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS field_meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    if own:
        conn.commit()
        conn.close()


def init_field_environments(conn: Optional[sqlite3.Connection] = None) -> None:
    own = conn is None
    conn = conn or get_connection()
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS field_environments (
            env_id      TEXT PRIMARY KEY,
            label       TEXT NOT NULL,           -- 'home', 'cafe-mission', 'work'
            kind        TEXT DEFAULT 'unknown',  -- home/work/transit/public/unknown
            wifi_bssid_hash TEXT,                -- gateway hash, if known
            first_seen  REAL DEFAULT (strftime('%s','now')),
            last_seen   REAL DEFAULT (strftime('%s','now')),
            visit_count INTEGER DEFAULT 1,
            notes       TEXT
        )
    """)
    if own:
        conn.commit()
        conn.close()


def init_field_observations(conn: Optional[sqlite3.Connection] = None) -> None:
    """Raw signal sightings — TTL 1h by default."""
    own = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS field_observations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            id_hash     TEXT NOT NULL,           -- hashed MAC / BLE / beacon
            kind        TEXT NOT NULL,           -- wifi/ble/audio/visual
            env_id      TEXT,                    -- which environment
            rssi        INTEGER,                 -- signal strength
            ts          REAL DEFAULT (strftime('%s','now'))
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_field_obs_ts ON field_observations(ts)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_field_obs_hash ON field_observations(id_hash)")
    if own:
        conn.commit()
        conn.close()


def init_field_presences(conn: Optional[sqlite3.Connection] = None) -> None:
    """Aggregated: hash X has been seen in env Y, N times. TTL 24h."""
    own = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS field_presences (
            id_hash      TEXT NOT NULL,
            env_id       TEXT NOT NULL,
            kind         TEXT NOT NULL,
            sightings    INTEGER DEFAULT 1,
            first_seen   REAL DEFAULT (strftime('%s','now')),
            last_seen    REAL DEFAULT (strftime('%s','now')),
            familiarity  REAL DEFAULT 0.0,        -- 0=stranger, 1=daily fixture
            PRIMARY KEY (id_hash, env_id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_field_pres_seen ON field_presences(last_seen)")
    if own:
        conn.commit()
        conn.close()


def init_field_alerts(conn: Optional[sqlite3.Connection] = None) -> None:
    """Surfaced patterns — the only thing field 'remembers' long-term. TTL 7d."""
    own = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS field_alerts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            severity     TEXT NOT NULL,           -- info/notice/concern
            title        TEXT NOT NULL,
            detail       TEXT,
            evidence     TEXT,                    -- JSON: {hash, envs, count}
            ts           REAL DEFAULT (strftime('%s','now')),
            acknowledged INTEGER DEFAULT 0
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_field_alert_ts ON field_alerts(ts)")
    if own:
        conn.commit()
        conn.close()


def init_field_tables(conn: Optional[sqlite3.Connection] = None) -> None:
    """Initialize all field thread tables. Idempotent."""
    global _initialized
    with _init_lock:
        if _initialized:
            return
        own = conn is None
        conn = conn or get_connection()
        try:
            init_field_meta(conn)
            _get_salt(conn)  # ensure salt exists
            init_field_environments(conn)
            init_field_observations(conn)
            init_field_presences(conn)
            init_field_alerts(conn)
            if own:
                conn.commit()
        finally:
            if own:
                conn.close()
        _initialized = True


# ============================================================================
# CRUD
# ============================================================================

def record_observation(
    raw_id: str,
    kind: str,
    env_id: Optional[str] = None,
    rssi: Optional[int] = None,
) -> str:
    """Hash the identifier and record a single sighting. Returns the hash."""
    with closing(get_connection()) as conn:
        h = hash_identifier(raw_id, conn)
        conn.execute(
            "INSERT INTO field_observations (id_hash, kind, env_id, rssi) VALUES (?, ?, ?, ?)",
            (h, kind, env_id, rssi),
        )
        # Roll up into presences
        conn.execute("""
            INSERT INTO field_presences (id_hash, env_id, kind, sightings)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(id_hash, env_id) DO UPDATE SET
                sightings = sightings + 1,
                last_seen = strftime('%s','now'),
                kind = excluded.kind
        """, (h, env_id or "_unknown", kind))
        conn.commit()
        return h


def upsert_environment(label: str, kind: str = "unknown", wifi_bssid: Optional[str] = None) -> str:
    """Create or update an environment. env_id = slug of label."""
    env_id = label.lower().replace(" ", "-")[:48]
    with closing(get_connection()) as conn:
        bssid_hash = hash_identifier(wifi_bssid, conn) if wifi_bssid else None
        conn.execute("""
            INSERT INTO field_environments (env_id, label, kind, wifi_bssid_hash)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(env_id) DO UPDATE SET
                last_seen = strftime('%s','now'),
                visit_count = visit_count + 1,
                kind = excluded.kind
        """, (env_id, label, kind, bssid_hash))
        conn.commit()
        return env_id


def list_environments(limit: int = 50) -> List[Dict]:
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute(
            "SELECT * FROM field_environments ORDER BY last_seen DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_presences(env_id: Optional[str] = None, since_secs: int = 86400, limit: int = 100) -> List[Dict]:
    cutoff = time.time() - since_secs
    with closing(get_connection(readonly=True)) as conn:
        if env_id:
            rows = conn.execute("""
                SELECT * FROM field_presences
                WHERE env_id = ? AND last_seen > ?
                ORDER BY sightings DESC LIMIT ?
            """, (env_id, cutoff, limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM field_presences
                WHERE last_seen > ?
                ORDER BY last_seen DESC LIMIT ?
            """, (cutoff, limit)).fetchall()
        return [dict(r) for r in rows]


def list_alerts(unack_only: bool = False, limit: int = 50) -> List[Dict]:
    with closing(get_connection(readonly=True)) as conn:
        sql = "SELECT * FROM field_alerts"
        if unack_only:
            sql += " WHERE acknowledged = 0"
        sql += " ORDER BY ts DESC LIMIT ?"
        rows = conn.execute(sql, (limit,)).fetchall()
        return [dict(r) for r in rows]


def raise_alert(severity: str, title: str, detail: str = "", evidence: str = "") -> int:
    with closing(get_connection()) as conn:
        cur = conn.execute(
            "INSERT INTO field_alerts (severity, title, detail, evidence) VALUES (?, ?, ?, ?)",
            (severity, title, detail, evidence),
        )
        conn.commit()
        return cur.lastrowid


def ack_alert(alert_id: int) -> None:
    with closing(get_connection()) as conn:
        conn.execute("UPDATE field_alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))
        conn.commit()


# ============================================================================
# Pattern detection (the actual value)
# ============================================================================

def detect_persistent_strangers(min_envs: int = 2, min_days: int = 2) -> List[Dict]:
    """Find hashes seen in >=N environments over >=M days, but with low familiarity.

    This is the 'is someone following me' signal — same device showing up in
    multiple of my environments without being a daily fixture.
    """
    cutoff = time.time() - (min_days * 86400)
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute("""
            SELECT id_hash,
                   COUNT(DISTINCT env_id) AS env_count,
                   SUM(sightings) AS total_sightings,
                   MAX(last_seen) AS last_seen,
                   MIN(first_seen) AS first_seen,
                   MAX(familiarity) AS max_familiarity
            FROM field_presences
            WHERE first_seen > ? AND env_id != '_unknown'
            GROUP BY id_hash
            HAVING env_count >= ? AND max_familiarity < 0.5
            ORDER BY env_count DESC, total_sightings DESC
        """, (cutoff, min_envs)).fetchall()
        return [dict(r) for r in rows]


# ============================================================================
# TTL cleanup — MUST be called periodically
# ============================================================================

def cleanup(
    obs_ttl_secs: int = 3600,
    presence_ttl_secs: int = 86400,
    alert_ttl_secs: int = 7 * 86400,
) -> Dict[str, int]:
    """Apply TTLs. Returns counts of deleted rows per table."""
    now = time.time()
    deleted = {}
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM field_observations WHERE ts < ?", (now - obs_ttl_secs,))
        deleted["observations"] = cur.rowcount
        cur.execute("DELETE FROM field_presences WHERE last_seen < ?", (now - presence_ttl_secs,))
        deleted["presences"] = cur.rowcount
        cur.execute(
            "DELETE FROM field_alerts WHERE ts < ? AND acknowledged = 1",
            (now - alert_ttl_secs,),
        )
        deleted["alerts"] = cur.rowcount
        conn.commit()
        cur.execute("UPDATE field_meta SET value = ? WHERE key = 'last_cleanup'", (str(now),))
        if cur.rowcount == 0:
            cur.execute("INSERT INTO field_meta (key, value) VALUES ('last_cleanup', ?)", (str(now),))
        conn.commit()
    return deleted


def get_stats() -> Dict[str, int]:
    with closing(get_connection(readonly=True)) as conn:
        out = {}
        for t in ("field_environments", "field_observations", "field_presences", "field_alerts"):
            try:
                out[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except Exception:
                out[t] = 0
        out["unack_alerts"] = conn.execute(
            "SELECT COUNT(*) FROM field_alerts WHERE acknowledged = 0"
        ).fetchone()[0]
        return out
