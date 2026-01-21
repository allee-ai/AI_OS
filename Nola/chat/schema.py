"""
Chat Schema - Conversation & Turn storage
-----------------------------------------
SQLite tables for conversation history.

Tables:
- convos: Conversation metadata
- convo_turns: Individual turns within conversations
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import sys

# Ensure project root is on path for data imports
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from data.db import get_connection


# =============================================================================
# Table Initialization
# =============================================================================

def init_convos_tables():
    """Initialize conversation tables."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Main conversations table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS convos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            channel TEXT DEFAULT 'react',
            name TEXT,
            started TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            archived BOOLEAN DEFAULT FALSE,
            weight REAL DEFAULT 0.5,
            turn_count INTEGER DEFAULT 0,
            indexed BOOLEAN DEFAULT FALSE,
            state_snapshot_json TEXT
        )
    """)
    
    # Index for listing
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_convos_updated 
        ON convos(last_updated DESC)
    """)
    
    # Conversation turns table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS convo_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            convo_id INTEGER NOT NULL,
            turn_index INTEGER NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_message TEXT,
            assistant_message TEXT,
            stimuli_type TEXT,
            context_level INTEGER DEFAULT 0,
            metadata_json TEXT,
            FOREIGN KEY (convo_id) REFERENCES convos(id) ON DELETE CASCADE
        )
    """)
    
    # Index for turn lookups
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_turns_convo 
        ON convo_turns(convo_id, turn_index)
    """)
    
    conn.commit()
    conn.close()


# =============================================================================
# Conversation CRUD
# =============================================================================

def save_conversation(
    session_id: str,
    name: Optional[str] = None,
    channel: str = "react",
    state_snapshot: Optional[Dict] = None,
) -> bool:
    """
    Create or update a conversation record.
    
    Args:
        session_id: Unique identifier for the conversation
        name: Human-readable name (optional)
        channel: Source channel (react, cli, etc.)
        state_snapshot: Optional snapshot of agent state at conversation start
    
    Returns:
        True if created/updated successfully
    """
    conn = get_connection()
    cur = conn.cursor()
    
    state_json = json.dumps(state_snapshot) if state_snapshot else None
    
    cur.execute("""
        INSERT INTO convos (session_id, name, channel, state_snapshot_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            name = COALESCE(excluded.name, convos.name),
            last_updated = CURRENT_TIMESTAMP
    """, (session_id, name, channel, state_json))
    
    conn.commit()
    conn.close()
    return True


def add_turn(
    session_id: str,
    user_message: str,
    assistant_message: str,
    stimuli_type: Optional[str] = None,
    context_level: int = 0,
    metadata: Optional[Dict] = None,
) -> int:
    """
    Add a turn to a conversation.
    Creates the conversation if it doesn't exist.
    
    Args:
        session_id: Conversation identifier
        user_message: What the user said
        assistant_message: What the assistant responded
        stimuli_type: Type of stimulus (user, scheduled, system, etc.)
        context_level: 0=none, 1=recent, 2=full
        metadata: Optional metadata dict
    
    Returns:
        Turn index (0-based)
    """
    conn = get_connection()
    cur = conn.cursor()
    
    # Get or create conversation
    cur.execute("SELECT id, turn_count FROM convos WHERE session_id = ?", (session_id,))
    row = cur.fetchone()
    
    if row:
        convo_id = row[0]
        turn_index = row[1]
    else:
        # Create new conversation
        cur.execute("""
            INSERT INTO convos (session_id, channel) VALUES (?, 'react')
        """, (session_id,))
        convo_id = cur.lastrowid
        turn_index = 0
    
    # Add the turn
    metadata_json = json.dumps(metadata) if metadata else None
    cur.execute("""
        INSERT INTO convo_turns (convo_id, turn_index, user_message, assistant_message, stimuli_type, context_level, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (convo_id, turn_index, user_message, assistant_message, stimuli_type, context_level, metadata_json))
    
    # Update conversation metadata
    cur.execute("""
        UPDATE convos SET 
            turn_count = turn_count + 1,
            last_updated = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (convo_id,))
    
    conn.commit()
    conn.close()
    return turn_index


def get_conversation(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a conversation with all its turns.
    
    Returns:
        Dict with session_id, name, started, turns, state_snapshot, etc.
        None if not found
    """
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    # Get conversation
    cur.execute("""
        SELECT id, session_id, channel, name, started, last_updated, archived, weight, turn_count, state_snapshot_json
        FROM convos WHERE session_id = ?
    """, (session_id,))
    row = cur.fetchone()
    
    if not row:
        conn.close()
        return None
    
    convo_id = row[0]
    state_snapshot = json.loads(row[9]) if row[9] else None
    
    # Get turns
    cur.execute("""
        SELECT turn_index, timestamp, user_message, assistant_message, stimuli_type, context_level, metadata_json
        FROM convo_turns WHERE convo_id = ? ORDER BY turn_index
    """, (convo_id,))
    
    turns = []
    for turn_row in cur.fetchall():
        turn = {
            "timestamp": turn_row[1],
            "user": turn_row[2],
            "assistant": turn_row[3],
            "stimuli_type": turn_row[4],
            "context_level": turn_row[5],
        }
        if turn_row[6]:
            turn["metadata"] = json.loads(turn_row[6])
        turns.append(turn)
    
    conn.close()
    
    return {
        "session_id": row[1],
        "channel": row[2],
        "name": row[3] or _generate_fallback_name(row[1]),
        "started": row[4],
        "last_updated": row[5],
        "archived": bool(row[6]),
        "weight": row[7],
        "turn_count": row[8],
        "turns": turns,
        "state_snapshot": state_snapshot,
    }


def list_conversations(
    limit: int = 50,
    archived: bool = False,
    min_weight: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    List conversations, newest first.
    
    Args:
        limit: Max conversations to return
        archived: Filter by archived status
        min_weight: Only return convos with weight >= this value
    """
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    query = """
        SELECT session_id, name, started, last_updated, archived, weight, turn_count
        FROM convos
        WHERE archived = ?
    """
    params: List[Any] = [archived]
    
    if min_weight is not None:
        query += " AND weight >= ?"
        params.append(min_weight)
    
    query += " ORDER BY last_updated DESC LIMIT ?"
    params.append(limit)
    
    cur.execute(query, params)
    
    conversations = []
    for row in cur.fetchall():
        # Get preview (first user message)
        cur.execute("""
            SELECT user_message FROM convo_turns 
            WHERE convo_id = (SELECT id FROM convos WHERE session_id = ?)
            ORDER BY turn_index LIMIT 1
        """, (row[0],))
        preview_row = cur.fetchone()
        preview = preview_row[0][:100] + "..." if preview_row and preview_row[0] and len(preview_row[0]) > 100 else (preview_row[0] if preview_row else "")
        
        # Get last assistant message
        cur.execute("""
            SELECT assistant_message FROM convo_turns 
            WHERE convo_id = (SELECT id FROM convos WHERE session_id = ?)
            ORDER BY turn_index DESC LIMIT 1
        """, (row[0],))
        last_row = cur.fetchone()
        last_message = last_row[0][:100] if last_row and last_row[0] else None
        
        conversations.append({
            "session_id": row[0],
            "name": row[1] or _generate_fallback_name(row[0]),
            "started": row[2],
            "last_updated": row[3],
            "archived": bool(row[4]),
            "weight": row[5],
            "turn_count": row[6],
            "preview": preview,
            "last_message": last_message,
        })
    
    conn.close()
    return conversations


def rename_conversation(session_id: str, name: str) -> bool:
    """Rename a conversation. Returns True if found and updated."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE convos SET name = ? WHERE session_id = ?", (name, session_id))
    updated = cur.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def archive_conversation(session_id: str, archived: bool = True) -> bool:
    """Archive or unarchive a conversation. Returns True if found and updated."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE convos SET archived = ? WHERE session_id = ?", (archived, session_id))
    updated = cur.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def delete_conversation(session_id: str) -> bool:
    """Delete a conversation and all its turns. Returns True if found and deleted."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM convos WHERE session_id = ?", (session_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def update_conversation_weight(session_id: str, weight: float) -> bool:
    """Update a conversation's weight. Returns True if found and updated."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE convos SET weight = ? WHERE session_id = ?", (weight, session_id))
    updated = cur.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def increment_conversation_weight(session_id: str, amount: float = 0.05) -> float:
    """
    Increment a conversation's weight (e.g., when user references it).
    Weight is capped at 1.0.
    
    Returns:
        New weight value
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE convos 
        SET weight = MIN(1.0, weight + ?)
        WHERE session_id = ?
    """, (amount, session_id))
    
    cur.execute("SELECT weight FROM convos WHERE session_id = ?", (session_id,))
    row = cur.fetchone()
    new_weight = row[0] if row else 0.5
    
    conn.commit()
    conn.close()
    return new_weight


def get_unindexed_high_weight_convos(min_weight: float = 0.3, limit: int = 10) -> List[Dict]:
    """
    Get conversations that haven't been indexed into linking_core yet
    and have weight above threshold.
    
    For use by linking_core indexer.
    """
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    cur.execute("""
        SELECT session_id, name, weight, turn_count
        FROM convos
        WHERE indexed = FALSE AND weight >= ?
        ORDER BY weight DESC
        LIMIT ?
    """, (min_weight, limit))
    
    convos = [{"session_id": r[0], "name": r[1], "weight": r[2], "turn_count": r[3]} for r in cur.fetchall()]
    conn.close()
    return convos


def mark_conversation_indexed(session_id: str) -> bool:
    """Mark a conversation as indexed by linking_core."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE convos SET indexed = TRUE WHERE session_id = ?", (session_id,))
    updated = cur.rowcount > 0
    conn.commit()
    conn.close()
    return updated


# =============================================================================
# Helpers
# =============================================================================

def _generate_fallback_name(session_id: str) -> str:
    """Generate a name from session_id if none set."""
    try:
        # Format: react_20260120_115611
        parts = session_id.split("_")
        if len(parts) >= 2:
            date_str = parts[1]
            return f"Chat {date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    except:
        pass
    return "Unnamed Conversation"


# =============================================================================
# Auto-initialize tables on import
# =============================================================================

init_convos_tables()
