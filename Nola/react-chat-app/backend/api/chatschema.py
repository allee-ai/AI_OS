"""
Chat Schema - Database tables for conversation storage

Stores conversations in state.db instead of JSON files.
Respects NOLA_MODE for demo vs personal database switching.

Tables:
- convos: Conversation metadata (session_id, name, timestamps, weight)
- convo_turns: Individual turns within conversations

TODO: Wire into linking_core for concept graph indexing
      High-weight convos (>0.3) should be indexed for spread activation
"""

import sqlite3
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path
import sys

# Ensure project root is on path for Nola imports
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parents[4]  # Up to AI_OS/
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Import DB path from central schema (respects demo/personal mode)
try:
    from Nola.threads.schema import get_db_path, _get_current_mode
except ImportError:
    # Fallback if schema not available - must still respect mode!
    import os
    _MODE_FILE = _PROJECT_ROOT / "data" / ".nola_mode"
    
    def _get_current_mode() -> str:
        """Get current mode - checks file first, then env var."""
        if _MODE_FILE.exists():
            return _MODE_FILE.read_text().strip().lower()
        return os.getenv("NOLA_MODE", "personal").lower()
    
    def get_db_path() -> Path:
        """Get database path based on current mode."""
        mode = _get_current_mode()
        db_file = "state_demo.db" if mode == "demo" else "state.db"
        return _PROJECT_ROOT / "data" / "db" / db_file


def get_connection(readonly: bool = False) -> sqlite3.Connection:
    """Get SQLite connection using central DB path."""
    db_path = get_db_path()
    # Debug: log which DB we're connecting to
    print(f"📀 chatschema connecting to: {db_path.name}")
    if not readonly:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _get_connection_for_db(db_path: Path, readonly: bool = False) -> sqlite3.Connection:
    """Get SQLite connection for a specific database path."""
    if not readonly:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _init_convos_tables_for_db(db_path: Path):
    """Create convos and convo_turns tables in a specific database."""
    conn = _get_connection_for_db(db_path)
    cur = conn.cursor()
    
    # Main conversations table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS convos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            channel TEXT DEFAULT 'react-chat',
            name TEXT,
            started TIMESTAMP NOT NULL,
            last_updated TIMESTAMP,
            archived BOOLEAN DEFAULT FALSE,
            weight REAL DEFAULT 0.5,
            indexed BOOLEAN DEFAULT FALSE,
            turn_count INTEGER DEFAULT 0,
            state_snapshot_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Conversation turns table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS convo_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            convo_id INTEGER NOT NULL,
            turn_index INTEGER NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            user_message TEXT,
            assistant_message TEXT,
            stimuli_type TEXT,
            context_level INTEGER,
            metadata_json TEXT,
            FOREIGN KEY (convo_id) REFERENCES convos(id) ON DELETE CASCADE
        )
    """)
    
    # Indexes for common queries
    cur.execute("CREATE INDEX IF NOT EXISTS idx_convos_session ON convos(session_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_convos_archived ON convos(archived)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_convos_started ON convos(started DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_convos_weight ON convos(weight)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_convos_indexed ON convos(indexed)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_turns_convo ON convo_turns(convo_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_turns_timestamp ON convo_turns(timestamp)")
    
    conn.commit()
    conn.close()


def init_convos_tables():
    """
    Create convos and convo_turns tables in BOTH databases.
    
    This ensures tables exist regardless of which mode is active,
    preventing crossover issues when switching modes.
    """
    db_dir = _PROJECT_ROOT / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize in both databases
    for db_file in ["state.db", "state_demo.db"]:
        db_path = db_dir / db_file
        try:
            _init_convos_tables_for_db(db_path)
        except Exception as e:
            print(f"⚠️ Could not init convos tables in {db_file}: {e}")


# =============================================================================
# CRUD Operations
# =============================================================================

def save_conversation(
    session_id: str,
    channel: str = "react-chat",
    name: Optional[str] = None,
    started: Optional[datetime] = None,
    state_snapshot: Optional[Dict] = None,
    weight: float = 0.5
) -> Optional[int]:
    """
    Create or update a conversation.
    
    Returns:
        convo_id (primary key)
    """
    conn = get_connection()
    cur = conn.cursor()
    
    now = datetime.now(timezone.utc).isoformat()
    started_str = started.isoformat() if started else now
    snapshot_json = json.dumps(state_snapshot) if state_snapshot else None
    
    # Upsert - update if exists, insert if not
    cur.execute("""
        INSERT INTO convos (session_id, channel, name, started, last_updated, state_snapshot_json, weight)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            name = COALESCE(excluded.name, convos.name),
            last_updated = excluded.last_updated,
            state_snapshot_json = COALESCE(excluded.state_snapshot_json, convos.state_snapshot_json)
    """, (session_id, channel, name, started_str, now, snapshot_json, weight))
    
    # Get the convo_id
    cur.execute("SELECT id FROM convos WHERE session_id = ?", (session_id,))
    row = cur.fetchone()
    convo_id = row[0] if row else cur.lastrowid
    
    conn.commit()
    conn.close()
    
    return convo_id


def add_turn(
    session_id: str,
    user_message: str,
    assistant_message: str,
    stimuli_type: Optional[str] = None,
    context_level: Optional[int] = None,
    metadata: Optional[Dict] = None
) -> Optional[int]:
    """
    Add a turn to a conversation.
    
    Creates the conversation if it doesn't exist.
    
    Returns:
        turn_id
    """
    conn = get_connection()
    cur = conn.cursor()
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Ensure conversation exists
    cur.execute("SELECT id, turn_count FROM convos WHERE session_id = ?", (session_id,))
    row = cur.fetchone()
    
    if row:
        convo_id = row[0]
        turn_index = row[1]
    else:
        # Create conversation
        cur.execute("""
            INSERT INTO convos (session_id, started, last_updated, turn_count)
            VALUES (?, ?, ?, 0)
        """, (session_id, now, now))
        convo_id = cur.lastrowid
        turn_index = 0
    
    # Add the turn
    metadata_json = json.dumps(metadata) if metadata else None
    cur.execute("""
        INSERT INTO convo_turns (convo_id, turn_index, timestamp, user_message, assistant_message, stimuli_type, context_level, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (convo_id, turn_index, now, user_message, assistant_message, stimuli_type, context_level, metadata_json))
    turn_id = cur.lastrowid
    
    # Update conversation metadata
    cur.execute("""
        UPDATE convos 
        SET turn_count = turn_count + 1, last_updated = ?
        WHERE id = ?
    """, (now, convo_id))
    
    conn.commit()
    conn.close()
    
    return turn_id


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
