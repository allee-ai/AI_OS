"""
Log Thread Schema
=================

Self-contained database operations for the Log thread.
Handles event logging, session tracking, and temporal data.

Tables:
- unified_events: All system/user events with timeline
- log_events: Module-specific event storage
- log_sessions: Session metadata
- log_system: Daemon/infrastructure logs
- log_server: HTTP requests, errors, performance (agent-monitorable)
- log_function_calls: Function call traces with dedup
- log_llm_inference: LLM call metrics (model, tokens, latency, cost)
- log_activations: LinkingCore concept activation traces
- log_loop_runs: Subconscious loop execution records
"""

import sqlite3
import json
from contextlib import closing
from typing import Dict, Any, List, Optional
from datetime import datetime

# Database connection from central location
from data.db import get_connection


# ============================================================================
# Table Initialization
# ============================================================================

def init_event_log_table(conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Create unified event log table.
    
    Single table for all events:
    - data = user-facing (what happened, the timeline)
    - metadata = program-facing (why/how, internal state)
    
    event_type: "convo" | "system" | "user_action" | "file" | "memory" | "activation"
    """
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS unified_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT NOT NULL,
            source TEXT DEFAULT 'system',
            data TEXT,
            metadata_json TEXT,
            session_id TEXT,
            
            -- Optional linking
            related_key TEXT,
            related_table TEXT,

            -- Thread + tag layer (added 2026-04-29 for timeline queries + training data)
            thread_subject TEXT,
            tags_json TEXT
        )
    """)

    # Idempotent migration: add columns if table predates them
    cur.execute("PRAGMA table_info(unified_events)")
    existing_cols = {row[1] for row in cur.fetchall()}
    if "thread_subject" not in existing_cols:
        cur.execute("ALTER TABLE unified_events ADD COLUMN thread_subject TEXT")
    if "tags_json" not in existing_cols:
        cur.execute("ALTER TABLE unified_events ADD COLUMN tags_json TEXT")

    # Indexes for fast queries
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON unified_events(event_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_time ON unified_events(timestamp DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON unified_events(session_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_source ON unified_events(source)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_thread ON unified_events(thread_subject)")

    if own_conn:
        conn.commit()
        conn.close()


def init_task_queue_table(conn: Optional[sqlite3.Connection] = None) -> None:
    """Create the task_queue table.

    A task is a structured request for the AIOS subconscious (or a worker)
    to do *one unit of thinking* via cloud LLM. The Copilot agent (or any
    surface) drops a row in `pending`. A worker claims it, runs it, writes
    result/cost/error back. Status flows:
        pending -> running -> done | failed | rate_limited
    """
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,                    -- e.g. 'summarize', 'extract', 'plan', 'classify'
            prompt TEXT NOT NULL,
            role TEXT DEFAULT 'PLANNER',           -- maps to agent.services.role_model
            params_json TEXT,                      -- max_tokens, temperature, system, etc.
            requested_by TEXT DEFAULT 'copilot',   -- who queued it
            business_id TEXT,                      -- multi-tenant tag (vanguard, aios, etc.)
            status TEXT DEFAULT 'pending',         -- pending|running|done|failed|rate_limited
            result TEXT,
            error TEXT,
            model_used TEXT,
            duration_ms INTEGER,
            tokens_in INTEGER,
            tokens_out INTEGER,
            attempts INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            claimed_at TEXT,
            finished_at TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_task_status ON task_queue(status, created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_task_business ON task_queue(business_id)")
    if own_conn:
        conn.commit()
        conn.close()


def enqueue_task(
    kind: str,
    prompt: str,
    role: str = "PLANNER",
    params: Optional[Dict[str, Any]] = None,
    requested_by: str = "copilot",
    business_id: Optional[str] = None,
) -> int:
    """Drop a task into the queue. Returns task id."""
    init_task_queue_table()
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO task_queue (kind, prompt, role, params_json, requested_by, business_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (kind, prompt, role, json.dumps(params or {}), requested_by, business_id))
        conn.commit()
        return cur.lastrowid


def claim_next_task() -> Optional[Dict[str, Any]]:
    """Atomically claim the oldest pending task. Returns row or None."""
    init_task_queue_table()
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        row = cur.execute("""
            SELECT * FROM task_queue
            WHERE status = 'pending'
            ORDER BY id ASC LIMIT 1
        """).fetchone()
        if not row:
            conn.commit()
            return None
        cur.execute("""
            UPDATE task_queue
            SET status = 'running',
                claimed_at = CURRENT_TIMESTAMP,
                attempts = attempts + 1
            WHERE id = ?
        """, (row["id"],))
        conn.commit()
        return dict(row)


def complete_task(
    task_id: int,
    result: str,
    model_used: Optional[str] = None,
    duration_ms: Optional[int] = None,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
) -> None:
    with closing(get_connection()) as conn:
        conn.execute("""
            UPDATE task_queue
            SET status='done', result=?, model_used=?, duration_ms=?,
                tokens_in=?, tokens_out=?, finished_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (result, model_used, duration_ms, tokens_in, tokens_out, task_id))
        conn.commit()


def fail_task(task_id: int, error: str, rate_limited: bool = False) -> None:
    status = "rate_limited" if rate_limited else "failed"
    with closing(get_connection()) as conn:
        conn.execute("""
            UPDATE task_queue
            SET status=?, error=?, finished_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (status, error[:1000], task_id))
        conn.commit()


def list_pending_tasks(limit: int = 20) -> List[Dict[str, Any]]:
    init_task_queue_table()
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute("""
            SELECT id, kind, role, requested_by, business_id, created_at, attempts
            FROM task_queue WHERE status='pending'
            ORDER BY id ASC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def list_recent_tasks(limit: int = 10) -> List[Dict[str, Any]]:
    init_task_queue_table()
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute("""
            SELECT id, kind, status, role, business_id, model_used, duration_ms,
                   created_at, finished_at,
                   substr(coalesce(result, error, ''), 1, 120) AS preview
            FROM task_queue
            WHERE status IN ('done','failed','rate_limited')
            ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def task_counts() -> Dict[str, int]:
    init_task_queue_table()
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute("""
            SELECT status, COUNT(*) c FROM task_queue GROUP BY status
        """).fetchall()
        return {r["status"]: r["c"] for r in rows}


def init_system_log_table(conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Create system/daemon log table.
    For infrastructure: daemon lifecycle, crashes, restarts.
    """
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS log_system (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            level TEXT NOT NULL DEFAULT 'info',
            source TEXT NOT NULL DEFAULT 'daemon',
            message TEXT NOT NULL,
            metadata_json TEXT,
            pid INTEGER
        )
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_system_time ON log_system(timestamp DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_system_level ON log_system(level)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_system_source ON log_system(source)")
    
    if own_conn:
        conn.commit()
        conn.close()


def init_server_log_table(conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Create server log table.
    HTTP requests, errors, performance - agent can monitor and respond.
    """
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS log_server (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            level TEXT NOT NULL DEFAULT 'info',
            method TEXT,
            path TEXT,
            status_code INTEGER,
            duration_ms REAL,
            client_ip TEXT,
            user_agent TEXT,
            error TEXT,
            metadata_json TEXT
        )
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_server_time ON log_server(timestamp DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_server_level ON log_server(level)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_server_path ON log_server(path)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_server_status ON log_server(status_code)")
    
    if own_conn:
        conn.commit()
        conn.close()


def init_log_module_table(module_name: str, conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Create a log module table (events, sessions, temporal).
    """
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    table_name = f"log_{module_name}"
    
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            key TEXT PRIMARY KEY,
            metadata_json TEXT NOT NULL,
            data_json TEXT NOT NULL,
            weight REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_created ON {table_name}(created_at DESC)")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_weight ON {table_name}(weight DESC)")
    
    if own_conn:
        conn.commit()
        conn.close()


# ============================================================================
# Event Logging (unified_events table)
# ============================================================================

def log_event(
    event_type: str,
    data: str,
    metadata: Dict[str, Any] = None,
    source: str = "system",
    session_id: str = None,
    related_key: str = None,
    related_table: str = None,
    thread_subject: str = None,
    tags: Optional[List[str]] = None,
    timestamp: Optional[str] = None,
) -> int:
    """
    Log an event to the unified timeline.

    Args:
        event_type: "convo" | "system" | "user_action" | "file" | "memory" | "activation"
        data: User-facing description (what happened)
        metadata: Program-facing context (why/how, internal state)
        source: "system" | "machine" | "user" | "local" | "web_public" | "daemon" | "agent"
        session_id: Groups related events
        related_key: Optional link to a fact/identity key
        related_table: Optional link to source table
        thread_subject: Thread/topic this event belongs to (e.g. "jake_retainer").
            Lets a stored arc be reconstructed via query rather than a metadata blob.
        tags: Flat list of lightweight tags (e.g. ["jake", "pitch", "money_neg"]).
            Stored as JSON, queryable via tag-any-match.
        timestamp: Optional explicit timestamp (ISO string). Used for predated
            user-added events. If None, defaults to CURRENT_TIMESTAMP.

    Returns:
        Event ID

    Examples:
        log_event("convo", "Conversation started with Jordan",
                  {"context_level": 2}, source="local", session_id="abc123")

        log_event("milestone", "pitch 2 sent to jake",
                  thread_subject="jake_retainer",
                  tags=["jake", "pitch_sent", "money_neg"],
                  source="machine")

        # User-added predated event (factual history recall)
        log_event("user_action", "sent retainer pitch v1",
                  thread_subject="jake_retainer",
                  tags=["jake", "pitch_sent"],
                  source="user",
                  timestamp="2026-04-28T19:03:00")
    """
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_event_log_table(conn)

        metadata_json = json.dumps(metadata) if metadata else None
        tags_json = json.dumps(tags) if tags else None

        if timestamp is not None:
            cur.execute("""
                INSERT INTO unified_events
                (timestamp, event_type, data, metadata_json, source, session_id,
                 related_key, related_table, thread_subject, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, event_type, data, metadata_json, source, session_id,
                  related_key, related_table, thread_subject, tags_json))
        else:
            cur.execute("""
                INSERT INTO unified_events
                (event_type, data, metadata_json, source, session_id,
                 related_key, related_table, thread_subject, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (event_type, data, metadata_json, source, session_id,
                  related_key, related_table, thread_subject, tags_json))

        event_id = cur.lastrowid
        conn.commit()
    return event_id


def get_events(
    event_type: str = None,
    source: str = None,
    session_id: str = None,
    since: str = None,
    until: str = None,
    thread_subject: str = None,
    tags_any: Optional[List[str]] = None,
    order: str = "DESC",
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Query events from the unified log.

    Args:
        event_type: Filter by type
        source: Filter by source ("system" | "machine" | "user" | ...)
        session_id: Filter by session
        since: ISO timestamp, get events strictly after this time
        until: ISO timestamp, get events strictly before this time
        thread_subject: Filter by thread (exact match)
        tags_any: List of tag strings; matches if event has ANY of them in tags_json
        order: "DESC" (newest first, default) or "ASC" (chronological reconstruction)
        limit: Max events to return

    Returns:
        List of event dicts with parsed metadata + tags
    """
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()

        # Ensure table exists
        init_event_log_table(conn)

        query = "SELECT * FROM unified_events WHERE 1=1"
        params: List[Any] = []

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if source:
            query += " AND source = ?"
            params.append(source)
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if since:
            query += " AND timestamp > ?"
            params.append(since)
        if until:
            query += " AND timestamp < ?"
            params.append(until)
        if thread_subject:
            query += " AND thread_subject = ?"
            params.append(thread_subject)
        if tags_any:
            # any-match: OR a LIKE per tag against the json string
            tag_clauses = " OR ".join(["tags_json LIKE ?"] * len(tags_any))
            query += f" AND ({tag_clauses})"
            for t in tags_any:
                # tags are stored as JSON arrays, so look for the quoted string
                params.append(f'%"{t}"%')

        order_sql = "ASC" if str(order).upper() == "ASC" else "DESC"
        query += f" ORDER BY timestamp {order_sql} LIMIT ?"
        params.append(limit)

        try:
            cur.execute(query, params)

            results = []
            for row in cur.fetchall():
                event = dict(row)
                if event.get("metadata_json"):
                    try:
                        event["metadata"] = json.loads(event["metadata_json"])
                    except Exception:
                        event["metadata"] = {}
                else:
                    event["metadata"] = {}
                del event["metadata_json"]

                if event.get("tags_json"):
                    try:
                        event["tags"] = json.loads(event["tags_json"])
                    except Exception:
                        event["tags"] = []
                else:
                    event["tags"] = []
                del event["tags_json"]
                results.append(event)

            return results
        except sqlite3.OperationalError:
            return []


def get_user_timeline(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get user-facing timeline (data column only, formatted for display).
    
    Returns events a user would care about:
    - Conversations
    - Things Agent learned
    - User actions
    """
    events = get_events(limit=limit * 2)  # Get extra to filter
    
    timeline = []
    for e in events:
        if e["event_type"] in ("convo", "memory", "user_action", "file"):
            timeline.append({
                "time": e["timestamp"],
                "type": e["event_type"],
                "what": e["data"],
                "source": e["source"]
            })
    
    return timeline[:limit]


def get_system_log(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get program-facing log (metadata included, for debugging).
    
    Returns all events with full metadata for debugging.
    """
    return get_events(limit=limit)


def delete_event(event_id: int) -> bool:
    """Delete an event by ID."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        
        cur.execute("DELETE FROM unified_events WHERE id = ?", (event_id,))
        conn.commit()
        deleted = cur.rowcount > 0
    return deleted


def clear_events(event_type: str = None, before: str = None) -> int:
    """
    Clear events, optionally filtered by type or date.
    
    Args:
        event_type: Only clear this type of event
        before: Clear events before this timestamp
    
    Returns:
        Number of events deleted
    """
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        
        query = "DELETE FROM unified_events WHERE 1=1"
        params = []
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if before:
            query += " AND timestamp < ?"
            params.append(before)
        
        cur.execute(query, params)
        conn.commit()
        count = cur.rowcount
    return count


# ============================================================================
# Log Module Storage (log_events, log_sessions tables)
# ============================================================================

def pull_log_events(
    module_name: str = "events",
    limit: int = 50,
    min_weight: float = 0.0
) -> List[Dict]:
    """
    Pull log events by recency and weight.
    
    Log events are temporal markers - query by timestamp DESC
    and weight to show recent + important events.
    
    Returns list of {key, metadata, data, weight, timestamp}
    """
    table_name = f"log_{module_name}"
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        
        # Check if table exists first (readonly-safe)
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cur.fetchone():
            return []  # Table doesn't exist yet, return empty
        
        try:
            cur.execute(f"""
                SELECT key, metadata_json, data_json, weight, created_at, updated_at
                FROM {table_name}
                WHERE weight >= ?
                ORDER BY created_at DESC, weight DESC
                LIMIT ?
            """, (min_weight, limit))
            
            rows = cur.fetchall()
            result = [{
                "key": r["key"],
                "metadata": json.loads(r["metadata_json"]) if r["metadata_json"] else {},
                "data": json.loads(r["data_json"]) if r["data_json"] else {},
                "weight": r["weight"],
                "timestamp": r["created_at"]
            } for r in rows]
            return result
        except sqlite3.OperationalError as e:
            try:
                log_event(
                    event_type="warn:db_lock",
                    data=f"get_log_entries failed: {e}",
                    metadata={"table": table_name, "error": str(e)},
                    source="log.schema",
                )
            except Exception:
                pass
            return []


def push_log_entry(
    module_name: str,
    key: str,
    metadata: Dict[str, Any],
    data: Dict[str, Any],
    weight: float = 1.0
) -> bool:
    """
    Push an entry to a log module table.
    """
    table_name = f"log_{module_name}"
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        
        # Ensure table exists
        init_log_module_table(module_name, conn)
        
        metadata_json = json.dumps(metadata)
        data_json = json.dumps(data)
        
        cur.execute(f"""
            INSERT INTO {table_name} (key, metadata_json, data_json, weight, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                metadata_json = ?,
                data_json = ?,
                weight = ?,
                updated_at = CURRENT_TIMESTAMP
        """, (key, metadata_json, data_json, weight, metadata_json, data_json, weight))
        
        conn.commit()
        updated = cur.rowcount > 0
    return updated


def get_log_entry(module_name: str, key: str) -> Optional[Dict]:
    """Get a specific log entry by key."""
    table_name = f"log_{module_name}"
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        
        try:
            cur.execute(f"""
                SELECT key, metadata_json, data_json, weight, created_at, updated_at
                FROM {table_name}
                WHERE key = ?
            """, (key,))
            
            row = cur.fetchone()
            if row:
                return {
                    "key": row["key"],
                    "metadata": json.loads(row["metadata_json"]) if row["metadata_json"] else {},
                    "data": json.loads(row["data_json"]) if row["data_json"] else {},
                    "weight": row["weight"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
            return None
        except sqlite3.OperationalError:
            return None


def delete_log_entry(module_name: str, key: str) -> bool:
    """Delete a log entry by key."""
    table_name = f"log_{module_name}"
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        
        try:
            cur.execute(f"DELETE FROM {table_name} WHERE key = ?", (key,))
            conn.commit()
            deleted = cur.rowcount > 0
            return deleted
        except sqlite3.OperationalError as e:
            try:
                log_event(
                    event_type="warn:db_lock",
                    data=f"delete_log_entry failed: {e}",
                    metadata={"table": table_name, "key": key, "error": str(e)},
                    source="log.schema",
                )
            except Exception:
                pass
            return False


# ============================================================================
# Session Management
# ============================================================================

def create_session(session_id: str, metadata: Dict[str, Any] = None) -> bool:
    """Create a new session record."""
    return push_log_entry(
        module_name="sessions",
        key=f"session_{session_id}",
        metadata={"type": "session", **(metadata or {})},
        data={
            "start_time": datetime.now().isoformat(),
            "status": "active"
        },
        weight=1.0
    )


def end_session(session_id: str, metadata: Dict[str, Any] = None) -> bool:
    """Mark a session as ended."""
    entry = get_log_entry("sessions", f"session_{session_id}")
    if entry:
        data = entry["data"]
        data["end_time"] = datetime.now().isoformat()
        data["status"] = "ended"
        return push_log_entry(
            module_name="sessions",
            key=f"session_{session_id}",
            metadata={**entry["metadata"], **(metadata or {})},
            data=data,
            weight=entry["weight"]
        )
    return False


def get_active_sessions() -> List[Dict]:
    """Get all active sessions."""
    sessions = pull_log_events(module_name="sessions", limit=100)
    return [s for s in sessions if s.get("data", {}).get("status") == "active"]


# ============================================================================
# Statistics
# ============================================================================

def get_log_stats() -> Dict[str, Any]:
    """Get log statistics."""
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        
        stats = {
            "total_events": 0,
            "events_by_type": {},
            "events_by_source": {},
            "sessions": {
                "total": 0,
                "active": 0
            },
            "recent_activity": []
        }
        
        try:
            # Total events
            cur.execute("SELECT COUNT(*) FROM unified_events")
            stats["total_events"] = cur.fetchone()[0]
            
            # By type
            cur.execute("SELECT event_type, COUNT(*) FROM unified_events GROUP BY event_type")
            stats["events_by_type"] = dict(cur.fetchall())
            
            # By source
            cur.execute("SELECT source, COUNT(*) FROM unified_events GROUP BY source")
            stats["events_by_source"] = dict(cur.fetchall())
            
            # Sessions
            sessions = pull_log_events("sessions", limit=1000)
            stats["sessions"]["total"] = len(sessions)
            stats["sessions"]["active"] = len([s for s in sessions if s.get("data", {}).get("status") == "active"])
            
            # Recent activity (last 24h by hour)
            cur.execute("""
                SELECT strftime('%Y-%m-%d %H:00', timestamp) as hour, COUNT(*)
                FROM unified_events
                WHERE timestamp > datetime('now', '-24 hours')
                GROUP BY hour
                ORDER BY hour DESC
            """)
            stats["recent_activity"] = [{"hour": h, "count": c} for h, c in cur.fetchall()]
            
        except sqlite3.OperationalError:
            pass
    
    return stats


# ============================================================================
# API Support Functions
# ============================================================================

def get_event_types() -> List[str]:
    """Get list of distinct event types."""
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        
        try:
            cur.execute("SELECT DISTINCT event_type FROM unified_events ORDER BY event_type")
            result = [row[0] for row in cur.fetchall()]
            return result
        except sqlite3.OperationalError:
            return ["convo", "system", "user_action", "file", "memory", "activation"]


def get_sources() -> List[str]:
    """Get list of distinct sources."""
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        
        try:
            cur.execute("SELECT DISTINCT source FROM unified_events ORDER BY source")
            result = [row[0] for row in cur.fetchall()]
            return result
        except sqlite3.OperationalError:
            return ["system", "local", "agent", "daemon"]


def search_events(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Search events by text content.
    """
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT * FROM unified_events
                WHERE data LIKE ? OR metadata_json LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", limit))
            
            results = []
            for row in cur.fetchall():
                event = dict(row)
                if event.get("metadata_json"):
                    try:
                        event["metadata"] = json.loads(event["metadata_json"])
                    except:
                        event["metadata"] = {}
                else:
                    event["metadata"] = {}
                del event["metadata_json"]
                results.append(event)
            
            return results
        except sqlite3.OperationalError:
            return []


# ============================================================================
# System Log Functions (Daemon/Infrastructure)
# ============================================================================

def log_system_event(
    level: str,
    message: str,
    source: str = "daemon",
    metadata: Dict[str, Any] = None,
    pid: int = None
) -> int:
    """
    Log a system/daemon event.
    
    Args:
        level: "debug" | "info" | "warning" | "error" | "critical"
        message: What happened
        source: Where from ("daemon", "scheduler", "watcher", etc)
        metadata: Additional context
        pid: Process ID (auto-detected if not provided)
    
    Returns:
        Log entry ID
    """
    import os
    
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_system_log_table(conn)
        
        metadata_json = json.dumps(metadata) if metadata else None
        actual_pid = pid or os.getpid()
        
        cur.execute("""
            INSERT INTO log_system (level, source, message, metadata_json, pid)
            VALUES (?, ?, ?, ?, ?)
        """, (level, source, message, metadata_json, actual_pid))
        
        log_id = cur.lastrowid
        conn.commit()
    return log_id


def get_system_logs(
    level: str = None,
    source: str = None,
    since: str = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Query system/daemon logs.
    
    Args:
        level: Filter by log level
        source: Filter by source component
        since: ISO timestamp, get logs after this time
        limit: Max logs to return
    
    Returns:
        List of log dicts
    """
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        init_system_log_table(conn)
        
        query = "SELECT * FROM log_system WHERE 1=1"
        params = []
        
        if level:
            query += " AND level = ?"
            params.append(level)
        if source:
            query += " AND source = ?"
            params.append(source)
        if since:
            query += " AND timestamp > ?"
            params.append(since)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        try:
            cur.execute(query, params)
            
            results = []
            for row in cur.fetchall():
                log = dict(row)
                if log.get("metadata_json"):
                    try:
                        log["metadata"] = json.loads(log["metadata_json"])
                    except:
                        log["metadata"] = {}
                else:
                    log["metadata"] = {}
                del log["metadata_json"]
                results.append(log)
            
            return results
        except sqlite3.OperationalError:
            return []


# ============================================================================
# Server Log Functions (HTTP Requests)
# ============================================================================

def log_server_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float = None,
    client_ip: str = None,
    user_agent: str = None,
    error: str = None,
    level: str = None,
    metadata: Dict[str, Any] = None
) -> int:
    """
    Log an HTTP request.
    
    Args:
        method: HTTP method (GET, POST, etc)
        path: Request path
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        client_ip: Client IP address
        user_agent: Client user agent
        error: Error message if request failed
        level: Log level (auto-determined from status_code if not provided)
        metadata: Additional context
    
    Returns:
        Log entry ID
    """
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_server_log_table(conn)
        
        # Auto-determine level from status code
        if level is None:
            if status_code >= 500:
                level = "error"
            elif status_code >= 400:
                level = "warning"
            else:
                level = "info"
        
        metadata_json = json.dumps(metadata) if metadata else None
        
        cur.execute("""
            INSERT INTO log_server 
            (level, method, path, status_code, duration_ms, client_ip, user_agent, error, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (level, method, path, status_code, duration_ms, client_ip, user_agent, error, metadata_json))
        
        log_id = cur.lastrowid
        conn.commit()
    return log_id


def get_server_logs(
    level: str = None,
    method: str = None,
    path_prefix: str = None,
    status_code: int = None,
    errors_only: bool = False,
    since: str = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Query server/HTTP logs.
    
    Args:
        level: Filter by log level
        method: Filter by HTTP method
        path_prefix: Filter by path prefix (e.g., "/api/feeds")
        status_code: Filter by exact status code
        errors_only: Only return error logs (status >= 400)
        since: ISO timestamp, get logs after this time
        limit: Max logs to return
    
    Returns:
        List of log dicts
    """
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        init_server_log_table(conn)
        
        query = "SELECT * FROM log_server WHERE 1=1"
        params = []
        
        if level:
            query += " AND level = ?"
            params.append(level)
        if method:
            query += " AND method = ?"
            params.append(method)
        if path_prefix:
            query += " AND path LIKE ?"
            params.append(f"{path_prefix}%")
        if status_code:
            query += " AND status_code = ?"
            params.append(status_code)
        if errors_only:
            query += " AND status_code >= 400"
        if since:
            query += " AND timestamp > ?"
            params.append(since)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        try:
            cur.execute(query, params)
            
            results = []
            for row in cur.fetchall():
                log = dict(row)
                if log.get("metadata_json"):
                    try:
                        log["metadata"] = json.loads(log["metadata_json"])
                    except:
                        log["metadata"] = {}
                else:
                    log["metadata"] = {}
                del log["metadata_json"]
                results.append(log)
            
            return results
        except sqlite3.OperationalError:
            return []


def get_server_stats(since: str = None) -> Dict[str, Any]:
    """
    Get server statistics for monitoring.
    
    Args:
        since: ISO timestamp, only count requests after this time
    
    Returns:
        Dict with request counts, error rates, avg duration
    """
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        init_server_log_table(conn)
        
        time_clause = ""
        params = []
        if since:
            time_clause = " WHERE timestamp > ?"
            params.append(since)
        
        try:
            # Total requests
            cur.execute(f"SELECT COUNT(*) FROM log_server{time_clause}", params)
            total = cur.fetchone()[0]
            
            # Error count (4xx and 5xx)
            error_clause = " WHERE status_code >= 400" if not since else " AND status_code >= 400"
            cur.execute(f"SELECT COUNT(*) FROM log_server{time_clause}{error_clause}", params)
            errors = cur.fetchone()[0]
            
            # Average duration
            cur.execute(f"SELECT AVG(duration_ms) FROM log_server{time_clause}", params)
            avg_duration = cur.fetchone()[0] or 0
            
            # Requests by status code
            cur.execute(f"""
                SELECT status_code, COUNT(*) as count 
                FROM log_server{time_clause}
                GROUP BY status_code
                ORDER BY count DESC
            """, params)
            by_status = {row[0]: row[1] for row in cur.fetchall()}
            
            # Requests by path (top 10)
            cur.execute(f"""
                SELECT path, COUNT(*) as count 
                FROM log_server{time_clause}
                GROUP BY path
                ORDER BY count DESC
                LIMIT 10
            """, params)
            by_path = {row[0]: row[1] for row in cur.fetchall()}
            
            return {
                "total_requests": total,
                "error_count": errors,
                "error_rate": (errors / total * 100) if total > 0 else 0,
                "avg_duration_ms": round(avg_duration, 2),
                "by_status": by_status,
                "top_paths": by_path
            }
        except sqlite3.OperationalError:
            return {
                "total_requests": 0,
                "error_count": 0,
                "error_rate": 0,
                "avg_duration_ms": 0,
                "by_status": {},
                "top_paths": {}
            }


# ============================================================================
# Function Call Logging & @trace_function Decorator
# ============================================================================

import functools
import time as _time
import hashlib as _hashlib
import traceback as _traceback


def init_function_log_table(conn: sqlite3.Connection = None) -> None:
    """Create table for function call traces."""
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS log_function_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            function_name TEXT NOT NULL,
            module TEXT,
            args_json TEXT,
            result_summary TEXT,
            duration_ms REAL,
            success INTEGER DEFAULT 1,
            error TEXT,
            dedup_hash TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fn_name ON log_function_calls(function_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fn_ts ON log_function_calls(timestamp DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_fn_dedup ON log_function_calls(dedup_hash)")
    if own_conn:
        conn.commit()
        conn.close()


def log_function_call(
    function_name: str,
    module: str = None,
    args_summary: Dict[str, Any] = None,
    result_summary: str = None,
    duration_ms: float = None,
    success: bool = True,
    error: str = None,
    dedup_hours: float = 48.0,
) -> Optional[int]:
    """
    Log a function call. Deduplicates identical calls within dedup_hours window.

    Returns log ID or None if deduped away.
    """
    # Build dedup hash from function name + args
    hash_input = function_name
    if args_summary:
        hash_input += json.dumps(args_summary, sort_keys=True, default=str)
    dedup_hash = _hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_function_log_table(conn)

        # Check for recent duplicate
        if dedup_hours > 0:
            cur.execute("""
                SELECT id FROM log_function_calls
                WHERE dedup_hash = ? AND timestamp > datetime('now', ?)
                LIMIT 1
            """, (dedup_hash, f"-{int(dedup_hours)} hours"))
            if cur.fetchone():
                return None  # Already logged recently

        args_json = json.dumps(args_summary, default=str) if args_summary else None
        cur.execute("""
            INSERT INTO log_function_calls
            (function_name, module, args_json, result_summary, duration_ms, success, error, dedup_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (function_name, module, args_json, result_summary, duration_ms, 1 if success else 0, error, dedup_hash))
        log_id = cur.lastrowid
        conn.commit()
    return log_id


def get_function_calls(
    function_name: str = None,
    module: str = None,
    limit: int = 100,
    since: str = None,
) -> List[Dict[str, Any]]:
    """Query function call logs."""
    # Ensure table exists (writable)
    init_function_log_table()

    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()

        query = "SELECT * FROM log_function_calls WHERE 1=1"
        params: list = []
        if function_name:
            query += " AND function_name = ?"
            params.append(function_name)
        if module:
            query += " AND module = ?"
            params.append(module)
        if since:
            query += " AND timestamp > ?"
            params.append(since)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        try:
            cur.execute(query, params)
            results = []
            for row in cur.fetchall():
                r = dict(row)
                if r.get("args_json"):
                    try:
                        r["args"] = json.loads(r["args_json"])
                    except Exception:
                        r["args"] = {}
                else:
                    r["args"] = {}
                del r["args_json"]
                results.append(r)
            return results
        except sqlite3.OperationalError:
            return []


def cleanup_old_function_logs(older_than_days: int = 30) -> int:
    """Remove function call logs older than N days."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_function_log_table(conn)
        cur.execute("""
            DELETE FROM log_function_calls
            WHERE timestamp < datetime('now', ?)
        """, (f"-{older_than_days} days",))
        deleted = cur.rowcount
        conn.commit()
    return deleted


def trace_function(
    module: str = None,
    dedup_hours: float = 48.0,
    log_args: bool = True,
    log_result: bool = True,
):
    """
    Decorator that logs function calls with timing, args, and result summary.
    48-hour dedup by default — identical calls won't spam the log.

    Usage:
        @trace_function(module="linking_core")
        def activate_concepts(text: str) -> dict:
            ...

        @trace_function(module="identity", dedup_hours=0)  # no dedup
        def get_profile(name: str) -> dict:
            ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            fn_name = fn.__qualname__
            mod = module or fn.__module__

            # Capture args summary (limit size)
            args_summary = None
            if log_args:
                try:
                    sig_args = {}
                    if args:
                        sig_args["positional"] = [repr(a)[:100] for a in args[:5]]
                    if kwargs:
                        sig_args["keyword"] = {k: repr(v)[:100] for k, v in list(kwargs.items())[:5]}
                    args_summary = sig_args if sig_args else None
                except Exception:
                    pass

            start = _time.time()
            try:
                result = fn(*args, **kwargs)
                elapsed = (_time.time() - start) * 1000

                result_str = None
                if log_result:
                    try:
                        result_str = repr(result)[:200]
                    except Exception:
                        result_str = "<unrepresentable>"

                log_function_call(
                    function_name=fn_name,
                    module=mod,
                    args_summary=args_summary,
                    result_summary=result_str,
                    duration_ms=elapsed,
                    success=True,
                    dedup_hours=dedup_hours,
                )
                return result
            except Exception as exc:
                elapsed = (_time.time() - start) * 1000
                log_function_call(
                    function_name=fn_name,
                    module=mod,
                    args_summary=args_summary,
                    result_summary=None,
                    duration_ms=elapsed,
                    success=False,
                    error=f"{type(exc).__name__}: {exc}",
                    dedup_hours=dedup_hours,
                )
                raise

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            fn_name = fn.__qualname__
            mod = module or fn.__module__

            args_summary = None
            if log_args:
                try:
                    sig_args = {}
                    if args:
                        sig_args["positional"] = [repr(a)[:100] for a in args[:5]]
                    if kwargs:
                        sig_args["keyword"] = {k: repr(v)[:100] for k, v in list(kwargs.items())[:5]}
                    args_summary = sig_args if sig_args else None
                except Exception:
                    pass

            start = _time.time()
            try:
                result = await fn(*args, **kwargs)
                elapsed = (_time.time() - start) * 1000

                result_str = None
                if log_result:
                    try:
                        result_str = repr(result)[:200]
                    except Exception:
                        result_str = "<unrepresentable>"

                log_function_call(
                    function_name=fn_name,
                    module=mod,
                    args_summary=args_summary,
                    result_summary=result_str,
                    duration_ms=elapsed,
                    success=True,
                    dedup_hours=dedup_hours,
                )
                return result
            except Exception as exc:
                elapsed = (_time.time() - start) * 1000
                log_function_call(
                    function_name=fn_name,
                    module=mod,
                    args_summary=args_summary,
                    result_summary=None,
                    duration_ms=elapsed,
                    success=False,
                    error=f"{type(exc).__name__}: {exc}",
                    dedup_hours=dedup_hours,
                )
                raise

        import asyncio
        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return wrapper
    return decorator


# ============================================================================
# LLM Inference Logging
# ============================================================================

def init_llm_inference_table(conn: sqlite3.Connection = None) -> None:
    """
    Create table for LLM inference metrics.
    Every LLM call gets logged — model, token counts, latency, cost.
    Enables: model switching decisions, cost tracking, self-diagnosis.
    """
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS log_llm_inference (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            model TEXT NOT NULL,
            provider TEXT DEFAULT 'local',
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            latency_ms REAL DEFAULT 0,
            success INTEGER DEFAULT 1,
            error TEXT,
            caller TEXT,
            session_id TEXT,
            metadata_json TEXT DEFAULT '{}'
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_llm_model ON log_llm_inference(model)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_llm_ts ON log_llm_inference(timestamp DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_llm_caller ON log_llm_inference(caller)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_llm_success ON log_llm_inference(success)")
    if own_conn:
        conn.commit()
        conn.close()


def log_llm_call(
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency_ms: float = 0,
    success: bool = True,
    error: str = None,
    caller: str = None,
    provider: str = "local",
    session_id: str = None,
    metadata: Dict[str, Any] = None,
) -> int:
    """
    Log an LLM inference call.

    Returns log ID.
    """
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_llm_inference_table(conn)
        metadata_json = json.dumps(metadata, default=str) if metadata else None
        cur.execute("""
            INSERT INTO log_llm_inference
            (model, provider, prompt_tokens, completion_tokens, total_tokens,
             latency_ms, success, error, caller, session_id, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            model, provider, prompt_tokens, completion_tokens,
            prompt_tokens + completion_tokens, latency_ms,
            1 if success else 0, error, caller, session_id, metadata_json,
        ))
        log_id = cur.lastrowid
        conn.commit()
    return log_id


def get_llm_calls(
    model: str = None,
    caller: str = None,
    success_only: bool = False,
    since: str = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Query LLM inference logs."""
    init_llm_inference_table()
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        query = "SELECT * FROM log_llm_inference WHERE 1=1"
        params: list = []
        if model:
            query += " AND model = ?"
            params.append(model)
        if caller:
            query += " AND caller = ?"
            params.append(caller)
        if success_only:
            query += " AND success = 1"
        if since:
            query += " AND timestamp > ?"
            params.append(since)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        try:
            cur.execute(query, params)
            results = []
            for row in cur.fetchall():
                r = dict(row)
                if r.get("metadata_json"):
                    try:
                        r["metadata"] = json.loads(r["metadata_json"])
                    except Exception:
                        r["metadata"] = {}
                else:
                    r["metadata"] = {}
                del r["metadata_json"]
                results.append(r)
            return results
        except sqlite3.OperationalError:
            return []


def get_llm_stats(since: str = None) -> Dict[str, Any]:
    """
    Get LLM usage statistics — total calls, tokens, cost estimate, error rate.
    Enables self-diagnosis: which model is failing? which caller is expensive?
    """
    init_llm_inference_table()
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        time_clause = ""
        params: list = []
        if since:
            time_clause = " WHERE timestamp > ?"
            params.append(since)
        try:
            cur.execute(f"SELECT COUNT(*) FROM log_llm_inference{time_clause}", params)
            total = cur.fetchone()[0]

            and_clause = " AND timestamp > ?" if since else ""
            err_params = list(params)
            cur.execute(
                f"SELECT COUNT(*) FROM log_llm_inference WHERE success = 0{and_clause}",
                err_params,
            )
            errors = cur.fetchone()[0]

            cur.execute(
                f"SELECT SUM(total_tokens), SUM(prompt_tokens), SUM(completion_tokens), "
                f"AVG(latency_ms) FROM log_llm_inference{time_clause}",
                params,
            )
            row = cur.fetchone()
            total_tokens = row[0] or 0
            prompt_tokens = row[1] or 0
            completion_tokens = row[2] or 0
            avg_latency = row[3] or 0

            cur.execute(
                f"SELECT model, COUNT(*) as cnt, SUM(total_tokens) as tok, AVG(latency_ms) as lat "
                f"FROM log_llm_inference{time_clause} GROUP BY model ORDER BY cnt DESC",
                params,
            )
            by_model = [
                {"model": r[0], "calls": r[1], "tokens": r[2] or 0, "avg_latency_ms": round(r[3] or 0, 2)}
                for r in cur.fetchall()
            ]

            return {
                "total_calls": total,
                "error_count": errors,
                "error_rate": round((errors / total * 100) if total else 0, 2),
                "total_tokens": total_tokens,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "avg_latency_ms": round(avg_latency, 2),
                "by_model": by_model,
            }
        except sqlite3.OperationalError:
            return {"total_calls": 0, "error_count": 0, "error_rate": 0,
                    "total_tokens": 0, "avg_latency_ms": 0, "by_model": []}


# ============================================================================
# Activation Logging (LinkingCore concept activation traces)
# ============================================================================

def init_activation_log_table(conn: sqlite3.Connection = None) -> None:
    """
    Create table for concept activation traces.
    Logs every spread_activate / concept link change for self-diagnosis.
    Enables: "which concepts fired?", "why did that link strengthen?"
    """
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS log_activations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            concept_a TEXT NOT NULL,
            concept_b TEXT,
            activation_type TEXT DEFAULT 'spread',
            strength_before REAL,
            strength_after REAL,
            strength_delta REAL,
            trigger TEXT,
            hops INTEGER DEFAULT 1,
            session_id TEXT,
            metadata_json TEXT DEFAULT '{}'
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_act_concept ON log_activations(concept_a)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_act_ts ON log_activations(timestamp DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_act_type ON log_activations(activation_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_act_trigger ON log_activations(trigger)")
    if own_conn:
        conn.commit()
        conn.close()


def log_activation(
    concept_a: str,
    concept_b: str = None,
    activation_type: str = "spread",
    strength_before: float = None,
    strength_after: float = None,
    trigger: str = None,
    hops: int = 1,
    session_id: str = None,
    metadata: Dict[str, Any] = None,
) -> int:
    """
    Log a concept activation event.

    activation_type: "spread" | "strengthen" | "weaken" | "create" | "prune"
    trigger: what caused it — "conversation", "memory_loop", "reflex", etc.
    """
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_activation_log_table(conn)
        delta = None
        if strength_before is not None and strength_after is not None:
            delta = strength_after - strength_before
        metadata_json = json.dumps(metadata, default=str) if metadata else None
        cur.execute("""
            INSERT INTO log_activations
            (concept_a, concept_b, activation_type, strength_before, strength_after,
             strength_delta, trigger, hops, session_id, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            concept_a, concept_b, activation_type,
            strength_before, strength_after, delta,
            trigger, hops, session_id, metadata_json,
        ))
        log_id = cur.lastrowid
        conn.commit()
    return log_id


def get_activations(
    concept: str = None,
    activation_type: str = None,
    trigger: str = None,
    since: str = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Query activation logs."""
    init_activation_log_table()
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        query = "SELECT * FROM log_activations WHERE 1=1"
        params: list = []
        if concept:
            query += " AND (concept_a = ? OR concept_b = ?)"
            params.extend([concept, concept])
        if activation_type:
            query += " AND activation_type = ?"
            params.append(activation_type)
        if trigger:
            query += " AND trigger = ?"
            params.append(trigger)
        if since:
            query += " AND timestamp > ?"
            params.append(since)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        try:
            cur.execute(query, params)
            results = []
            for row in cur.fetchall():
                r = dict(row)
                if r.get("metadata_json"):
                    try:
                        r["metadata"] = json.loads(r["metadata_json"])
                    except Exception:
                        r["metadata"] = {}
                else:
                    r["metadata"] = {}
                del r["metadata_json"]
                results.append(r)
            return results
        except sqlite3.OperationalError:
            return []


def get_activation_stats(since: str = None) -> Dict[str, Any]:
    """Activation statistics — top concepts, type breakdown."""
    init_activation_log_table()
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        time_clause = ""
        params: list = []
        if since:
            time_clause = " WHERE timestamp > ?"
            params.append(since)
        try:
            cur.execute(f"SELECT COUNT(*) FROM log_activations{time_clause}", params)
            total = cur.fetchone()[0]

            cur.execute(
                f"SELECT activation_type, COUNT(*) FROM log_activations{time_clause} GROUP BY activation_type",
                params,
            )
            by_type = dict(cur.fetchall())

            cur.execute(
                f"SELECT concept_a, COUNT(*) as cnt FROM log_activations{time_clause} "
                f"GROUP BY concept_a ORDER BY cnt DESC LIMIT 20",
                params,
            )
            top_concepts = [{"concept": r[0], "activations": r[1]} for r in cur.fetchall()]

            return {"total_activations": total, "by_type": by_type, "top_concepts": top_concepts}
        except sqlite3.OperationalError:
            return {"total_activations": 0, "by_type": {}, "top_concepts": []}


# ============================================================================
# Subconscious Loop Run Logging
# ============================================================================

def init_loop_run_table(conn: sqlite3.Connection = None) -> None:
    """
    Create table for subconscious loop execution records.
    Logs every loop tick — duration, items processed, errors.
    Enables: "is the memory loop stalling?", "which loop is slowest?"
    """
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS log_loop_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            loop_name TEXT NOT NULL,
            status TEXT DEFAULT 'completed',
            duration_ms REAL DEFAULT 0,
            items_processed INTEGER DEFAULT 0,
            items_changed INTEGER DEFAULT 0,
            error TEXT,
            metadata_json TEXT DEFAULT '{}'
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_loop_name ON log_loop_runs(loop_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_loop_ts ON log_loop_runs(timestamp DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_loop_status ON log_loop_runs(status)")
    if own_conn:
        conn.commit()
        conn.close()


def log_loop_run(
    loop_name: str,
    status: str = "completed",
    duration_ms: float = 0,
    items_processed: int = 0,
    items_changed: int = 0,
    error: str = None,
    metadata: Dict[str, Any] = None,
) -> int:
    """
    Log a subconscious loop execution.

    status: "completed" | "error" | "skipped" | "timeout"
    """
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_loop_run_table(conn)
        metadata_json = json.dumps(metadata, default=str) if metadata else None
        cur.execute("""
            INSERT INTO log_loop_runs
            (loop_name, status, duration_ms, items_processed, items_changed, error, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (loop_name, status, duration_ms, items_processed, items_changed, error, metadata_json))
        log_id = cur.lastrowid
        conn.commit()
    return log_id


def get_loop_runs(
    loop_name: str = None,
    status: str = None,
    since: str = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Query loop run logs."""
    init_loop_run_table()
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        query = "SELECT * FROM log_loop_runs WHERE 1=1"
        params: list = []
        if loop_name:
            query += " AND loop_name = ?"
            params.append(loop_name)
        if status:
            query += " AND status = ?"
            params.append(status)
        if since:
            query += " AND timestamp > ?"
            params.append(since)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        try:
            cur.execute(query, params)
            results = []
            for row in cur.fetchall():
                r = dict(row)
                if r.get("metadata_json"):
                    try:
                        r["metadata"] = json.loads(r["metadata_json"])
                    except Exception:
                        r["metadata"] = {}
                else:
                    r["metadata"] = {}
                del r["metadata_json"]
                results.append(r)
            return results
        except sqlite3.OperationalError:
            return []


def get_loop_stats(since: str = None) -> Dict[str, Any]:
    """Loop statistics — runs per loop, avg duration, error rates."""
    init_loop_run_table()
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        time_clause = ""
        params: list = []
        if since:
            time_clause = " WHERE timestamp > ?"
            params.append(since)
        try:
            cur.execute(f"SELECT COUNT(*) FROM log_loop_runs{time_clause}", params)
            total = cur.fetchone()[0]

            cur.execute(
                f"SELECT loop_name, COUNT(*) as runs, AVG(duration_ms) as avg_ms, "
                f"SUM(items_processed) as processed, SUM(items_changed) as changed, "
                f"SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors "
                f"FROM log_loop_runs{time_clause} GROUP BY loop_name ORDER BY runs DESC",
                params,
            )
            by_loop = [
                {
                    "loop": r[0], "runs": r[1],
                    "avg_duration_ms": round(r[2] or 0, 2),
                    "items_processed": r[3] or 0,
                    "items_changed": r[4] or 0,
                    "errors": r[5] or 0,
                }
                for r in cur.fetchall()
            ]

            return {"total_runs": total, "by_loop": by_loop}
        except sqlite3.OperationalError:
            return {"total_runs": 0, "by_loop": []}
