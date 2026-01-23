"""
Log Thread Schema
=================

Self-contained database operations for the Log thread.
Handles event logging, session tracking, and temporal data.

Tables:
- unified_events: All system/user events with timeline
- log_events: Module-specific event storage
- log_sessions: Session metadata
"""

import sqlite3
import json
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
            related_table TEXT
        )
    """)
    
    # Indexes for fast queries
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON unified_events(event_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_time ON unified_events(timestamp DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON unified_events(session_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_source ON unified_events(source)")
    
    if own_conn:
        conn.commit()


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
    related_table: str = None
) -> int:
    """
    Log an event to the unified timeline.
    
    Args:
        event_type: "convo" | "system" | "user_action" | "file" | "memory" | "activation"
        data: User-facing description (what happened)
        metadata: Program-facing context (why/how, internal state)
        source: Where this came from ("local", "web_public", "daemon", "agent")
        session_id: Groups related events
        related_key: Optional link to a fact/identity key
        related_table: Optional link to source table
    
    Returns:
        Event ID
    
    Examples:
        log_event("convo", "Conversation started with Jordan", 
                  {"context_level": 2}, source="local", session_id="abc123")
        
        log_event("memory", "Learned: Sarah likes coffee",
                  {"hier_key": "sarah.likes.coffee", "score": 0.72}, 
                  related_key="sarah.likes.coffee")
    """
    conn = get_connection()
    cur = conn.cursor()
    init_event_log_table(conn)
    
    metadata_json = json.dumps(metadata) if metadata else None
    
    cur.execute("""
        INSERT INTO unified_events 
        (event_type, data, metadata_json, source, session_id, related_key, related_table)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (event_type, data, metadata_json, source, session_id, related_key, related_table))
    
    event_id = cur.lastrowid
    conn.commit()
    return event_id


def get_events(
    event_type: str = None,
    source: str = None,
    session_id: str = None,
    since: str = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Query events from the unified log.
    
    Args:
        event_type: Filter by type
        source: Filter by source
        session_id: Filter by session
        since: ISO timestamp, get events after this time
        limit: Max events to return
    
    Returns:
        List of event dicts with parsed metadata
    """
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    # Ensure table exists
    init_event_log_table(conn)
    
    query = "SELECT * FROM unified_events WHERE 1=1"
    params = []
    
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
    
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
    try:
        cur.execute(query, params)
        
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
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("DELETE FROM unified_events WHERE id = ?", (event_id,))
    conn.commit()
    return cur.rowcount > 0


def clear_events(event_type: str = None, before: str = None) -> int:
    """
    Clear events, optionally filtered by type or date.
    
    Args:
        event_type: Only clear this type of event
        before: Clear events before this timestamp
    
    Returns:
        Number of events deleted
    """
    conn = get_connection()
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
    return cur.rowcount


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
    conn = get_connection(readonly=True)
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
        return [{
            "key": r["key"],
            "metadata": json.loads(r["metadata_json"]) if r["metadata_json"] else {},
            "data": json.loads(r["data_json"]) if r["data_json"] else {},
            "weight": r["weight"],
            "timestamp": r["created_at"]
        } for r in rows]
    except sqlite3.OperationalError:
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
    conn = get_connection()
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
    return cur.rowcount > 0


def get_log_entry(module_name: str, key: str) -> Optional[Dict]:
    """Get a specific log entry by key."""
    table_name = f"log_{module_name}"
    conn = get_connection(readonly=True)
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
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(f"DELETE FROM {table_name} WHERE key = ?", (key,))
        conn.commit()
        return cur.rowcount > 0
    except sqlite3.OperationalError:
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
    conn = get_connection(readonly=True)
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
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT DISTINCT event_type FROM unified_events ORDER BY event_type")
        return [row[0] for row in cur.fetchall()]
    except sqlite3.OperationalError:
        return ["convo", "system", "user_action", "file", "memory", "activation"]


def get_sources() -> List[str]:
    """Get list of distinct sources."""
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT DISTINCT source FROM unified_events ORDER BY source")
        return [row[0] for row in cur.fetchall()]
    except sqlite3.OperationalError:
        return ["system", "local", "agent", "daemon"]


def search_events(query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Search events by text content.
    """
    conn = get_connection(readonly=True)
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
