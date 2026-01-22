"""
Nola Temp Memory - Short-Term Fact Store
=========================================
Session-scoped storage for facts extracted from conversations.
Facts live here until the consolidation daemon processes them.

Architecture:
    Conversation → _extract_facts() → temp_memory.add_fact()
                                            ↓
                              consolidation daemon (periodic)
                                            ↓
                              score → summarize → long-term DB

Storage: SQLite table in shared state.db (not separate JSON files)
This ensures atomic operations and easy querying for consolidation.

Usage:
    from Nola.subconscious.temp_memory import add_fact, get_all_pending, mark_consolidated
    
    # During conversation
    add_fact(session_id, "User prefers Python over JavaScript", source="conversation")
    
    # During consolidation
    pending = get_all_pending()
    for fact in pending:
        score = score_fact(fact.text)
        if score > threshold:
            push_to_longterm(fact)
            mark_consolidated(fact.id)
"""

import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Optional
import sqlite3

# Import DB connection from central location
from data.db import get_connection


# Thread lock for DB operations
_db_lock = threading.Lock()


@dataclass
class Fact:
    """A fact extracted from conversation, pending consolidation."""
    id: Optional[int]  # DB row ID, None if not yet saved
    text: str
    timestamp: str
    source: str  # "conversation", "explicit", "inferred"
    session_id: str
    consolidated: bool = False
    score_json: Optional[str] = None  # JSON of importance scores once computed
    hier_key: Optional[str] = None  # Hierarchical key (e.g., "sarah.likes.blue")
    metadata_json: Optional[str] = None  # Additional metadata as JSON
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Fact":
        return cls(
            id=row["id"],
            text=row["text"],
            timestamp=row["timestamp"],
            source=row["source"],
            session_id=row["session_id"],
            consolidated=bool(row["consolidated"]),
            score_json=row["score_json"],
            hier_key=row["hier_key"] if "hier_key" in row.keys() else None,
            metadata_json=row["metadata_json"] if "metadata_json" in row.keys() else None
        )


def _ensure_table() -> None:
    """Ensure the temp_facts table exists."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS temp_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL,
            session_id TEXT NOT NULL,
            consolidated INTEGER DEFAULT 0,
            score_json TEXT,
            hier_key TEXT,
            metadata_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Index for finding pending facts
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_temp_facts_pending 
        ON temp_facts(consolidated, created_at)
    """)
    
    # Index for session lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_temp_facts_session 
        ON temp_facts(session_id)
    """)
    
    # Index for hierarchical key lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_temp_facts_hier_key 
        ON temp_facts(hier_key)
    """)
    
    # Add columns if they don't exist (migration for existing DBs)
    try:
        cursor.execute("ALTER TABLE temp_facts ADD COLUMN hier_key TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute("ALTER TABLE temp_facts ADD COLUMN metadata_json TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.commit()


def add_fact(
    session_id: str,
    text: str,
    source: str = "conversation",
    timestamp: Optional[str] = None,
    metadata: Optional[dict] = None
) -> Fact:
    """
    Add a fact to short-term memory.
    
    Args:
        session_id: Conversation/session identifier
        text: The fact text (e.g., "User prefers Python")
        source: Where this fact came from ("conversation", "explicit", "inferred")
        timestamp: ISO timestamp, defaults to now
        metadata: Optional dict with extra data (hier_key, concepts, etc.)
    
    Returns:
        The created Fact with its database ID
    """
    import json as json_mod
    
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    
    # Extract hier_key from metadata if provided
    hier_key = metadata.get("hier_key") if metadata else None
    metadata_json = json_mod.dumps(metadata) if metadata else None
    
    with _db_lock:
        _ensure_table()
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO temp_facts (text, timestamp, source, session_id, consolidated, hier_key, metadata_json)
            VALUES (?, ?, ?, ?, 0, ?, ?)
        """, (text, timestamp, source, session_id, hier_key, metadata_json))
        
        fact_id = cursor.lastrowid
        conn.commit()
        
        # Log the extraction
        try:
            from Nola.threads.log import log_event
            log_event(
                "memory:extract",
                "temp_memory",
                f"Added fact: {text[:50]}...",
                fact_id=fact_id,
                session_id=session_id,
                fact_source=source,  # renamed to avoid conflict with log_event's source param
                hier_key=hier_key
            )
        except ImportError:
            pass  # log_thread not available
        
        return Fact(
            id=fact_id,
            text=text,
            timestamp=timestamp,
            source=source,
            session_id=session_id,
            consolidated=False,
            score_json=None,
            hier_key=hier_key,
            metadata_json=metadata_json
        )


def get_facts(limit: int = 100, include_consolidated: bool = False) -> List[Fact]:
    """
    Get facts from temp memory.
    
    Args:
        limit: Maximum number of facts to return
        include_consolidated: If True, include already-consolidated facts
    
    Returns:
        List of Fact objects
    """
    with _db_lock:
        _ensure_table()
        
        conn = get_connection(readonly=True)
        cursor = conn.cursor()
        
        if include_consolidated:
            cursor.execute("""
                SELECT * FROM temp_facts 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
        else:
            cursor.execute("""
                SELECT * FROM temp_facts 
                WHERE consolidated = 0
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
        
        return [Fact.from_row(row) for row in cursor.fetchall()]


def get_session_facts(session_id: str, include_consolidated: bool = False) -> List[Fact]:
    """
    Get all facts for a specific session.
    
    Args:
        session_id: The session to get facts for
        include_consolidated: If True, include already-consolidated facts
    
    Returns:
        List of Fact objects for this session
    """
    with _db_lock:
        _ensure_table()
        
        conn = get_connection(readonly=True)
        cursor = conn.cursor()
        
        if include_consolidated:
            cursor.execute("""
                SELECT * FROM temp_facts 
                WHERE session_id = ?
                ORDER BY created_at ASC
            """, (session_id,))
        else:
            cursor.execute("""
                SELECT * FROM temp_facts 
                WHERE session_id = ? AND consolidated = 0
                ORDER BY created_at ASC
            """, (session_id,))
        
        return [Fact.from_row(row) for row in cursor.fetchall()]


def get_all_pending() -> List[Fact]:
    """
    Get all facts pending consolidation (across all sessions).
    Used by the consolidation daemon.
    
    Returns:
        List of unconsolidated Fact objects
    """
    with _db_lock:
        _ensure_table()
        
        conn = get_connection(readonly=True)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM temp_facts 
            WHERE consolidated = 0
            ORDER BY created_at ASC
        """)
        
        return [Fact.from_row(row) for row in cursor.fetchall()]


def mark_consolidated(fact_id: int, score_json: Optional[str] = None) -> bool:
    """
    Mark a fact as consolidated (processed by consolidation daemon).
    
    Args:
        fact_id: Database ID of the fact
        score_json: Optional JSON string of importance scores
    
    Returns:
        True if fact was found and updated, False otherwise
    """
    with _db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        
        if score_json:
            cursor.execute("""
                UPDATE temp_facts 
                SET consolidated = 1, score_json = ?
                WHERE id = ?
            """, (score_json, fact_id))
        else:
            cursor.execute("""
                UPDATE temp_facts 
                SET consolidated = 1
                WHERE id = ?
            """, (fact_id,))
        
        conn.commit()
        return cursor.rowcount > 0


def clear_session(session_id: str, only_consolidated: bool = True) -> int:
    """
    Clear facts for a session.
    
    Args:
        session_id: The session to clear
        only_consolidated: If True, only delete facts that have been consolidated
    
    Returns:
        Number of facts deleted
    """
    with _db_lock:
        conn = get_connection()
        cursor = conn.cursor()
        
        if only_consolidated:
            cursor.execute("""
                DELETE FROM temp_facts 
                WHERE session_id = ? AND consolidated = 1
            """, (session_id,))
        else:
            cursor.execute("""
                DELETE FROM temp_facts 
                WHERE session_id = ?
            """, (session_id,))
        
        conn.commit()
        return cursor.rowcount


def get_stats() -> dict:
    """
    Get statistics about temp memory.
    
    Returns:
        Dict with counts and session info
    """
    with _db_lock:
        _ensure_table()
        
        conn = get_connection(readonly=True)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM temp_facts WHERE consolidated = 0")
        pending = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM temp_facts WHERE consolidated = 1")
        consolidated = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT session_id) FROM temp_facts")
        sessions = cursor.fetchone()[0]
        
        return {
            "pending": pending,
            "consolidated": consolidated,
            "total": pending + consolidated,
            "sessions": sessions
        }
