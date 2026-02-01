"""
Reflex Thread Schema
====================
Quick patterns, shortcuts, triggers, and feed-to-tool automations.

Tables:
- reflex_greetings: Quick greeting patterns (in-memory legacy)
- reflex_shortcuts: User command shortcuts (in-memory legacy)
- reflex_triggers: Feed event → Tool action automations (SQLite)

Trigger types:
- poll: Run on interval or condition
- webhook: Run immediately on feed event
- schedule: Run on cron schedule
"""

import sqlite3
import json
from contextlib import closing
from typing import List, Dict, Any, Optional
from datetime import datetime


# Database connection
def get_connection():
    from data.db import get_connection as _get_conn
    return _get_conn()


# ============================================================================
# In-memory storage for legacy patterns (greetings, shortcuts)
# ============================================================================

_GREETINGS: Dict[str, Dict] = {}
_SHORTCUTS: Dict[str, Dict] = {}
_SYSTEM_REFLEXES: Dict[str, Dict] = {}


def get_greetings(level: int = 2) -> List[Dict]:
    """Get greeting patterns."""
    return [
        {"key": k, "data": v, "metadata": {"type": "pattern"}, "level": 1, "weight": v.get("weight", 0.8)}
        for k, v in _GREETINGS.items()
    ]


def get_shortcuts(level: int = 2) -> List[Dict]:
    """Get user shortcuts."""
    return [
        {"key": k, "data": v, "metadata": {"type": "shortcut"}, "level": 1, "weight": 0.7}
        for k, v in _SHORTCUTS.items()
    ]


def get_system_reflexes(level: int = 2) -> List[Dict]:
    """Get system reflexes."""
    return [
        {"key": k, "data": v, "metadata": {"type": "system"}, "level": 1, "weight": v.get("weight", 0.9)}
        for k, v in _SYSTEM_REFLEXES.items()
    ]


def add_greeting(key: str, response: str, weight: float = 0.8) -> None:
    """Add a greeting response."""
    _GREETINGS[key] = {"value": response, "weight": weight}


def add_shortcut(trigger: str, response: str, description: str = "") -> None:
    """Add a user shortcut."""
    key = f"shortcut_{trigger.lower().replace(' ', '_')}"
    _SHORTCUTS[key] = {"trigger": trigger, "response": response, "description": description}


def add_system_reflex(key: str, trigger_type: str, action: str, description: str = "", weight: float = 0.9) -> None:
    """Add a system reflex."""
    _SYSTEM_REFLEXES[key] = {
        "trigger_type": trigger_type,
        "action": action,
        "description": description,
        "weight": weight
    }


def delete_greeting(key: str) -> bool:
    """Delete a greeting."""
    if key in _GREETINGS:
        del _GREETINGS[key]
        return True
    return False


def delete_shortcut(key: str) -> bool:
    """Delete a shortcut."""
    if key in _SHORTCUTS:
        del _SHORTCUTS[key]
        return True
    return False


def delete_system_reflex(key: str) -> bool:
    """Delete a system reflex."""
    if key in _SYSTEM_REFLEXES:
        del _SYSTEM_REFLEXES[key]
        return True
    return False


# ============================================================================
# SQLite Triggers (Feed → Tool automations)
# ============================================================================

def init_triggers_table(conn: Optional[sqlite3.Connection] = None) -> None:
    """Create the triggers table if it doesn't exist."""
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reflex_triggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            
            -- Trigger source
            trigger_type TEXT NOT NULL DEFAULT 'webhook',
            feed_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            
            -- Condition (optional filter)
            condition_json TEXT,
            
            -- Action to execute
            tool_name TEXT NOT NULL,
            tool_action TEXT NOT NULL,
            tool_params_json TEXT,
            
            -- Settings
            enabled INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 5,
            
            -- For poll triggers
            poll_interval INTEGER,
            last_polled TEXT,
            
            -- For schedule triggers
            cron_expression TEXT,
            
            -- Stats
            execution_count INTEGER DEFAULT 0,
            last_executed TEXT,
            last_error TEXT,
            
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triggers_feed ON reflex_triggers(feed_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_triggers_enabled ON reflex_triggers(enabled)")
    
    if own_conn:
        conn.commit()
        conn.close()


def create_trigger(
    name: str,
    feed_name: str,
    event_type: str,
    tool_name: str,
    tool_action: str,
    description: str = "",
    trigger_type: str = "webhook",
    condition: Optional[Dict[str, Any]] = None,
    tool_params: Optional[Dict[str, Any]] = None,
    poll_interval: Optional[int] = None,
    cron_expression: Optional[str] = None,
    priority: int = 5,
) -> int:
    """Create a new trigger automation."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_triggers_table(conn)
        
        cur.execute("""
            INSERT INTO reflex_triggers 
            (name, description, trigger_type, feed_name, event_type, condition_json,
             tool_name, tool_action, tool_params_json, poll_interval, cron_expression, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, description, trigger_type, feed_name, event_type,
            json.dumps(condition) if condition else None,
            tool_name, tool_action,
            json.dumps(tool_params) if tool_params else None,
            poll_interval, cron_expression, priority,
        ))
        
        trigger_id = cur.lastrowid
        conn.commit()
        
        # Log the creation
        try:
            from agent.threads.log.schema import log_event
            log_event(
                event_type="system",
                data=f"Trigger created: {name} ({feed_name}/{event_type} → {tool_name}/{tool_action})",
                metadata={
                    "trigger_id": trigger_id,
                    "feed_name": feed_name,
                    "event_type": event_type,
                    "tool_name": tool_name,
                    "tool_action": tool_action,
                },
                source="reflex",
            )
        except ImportError:
            pass
        
        return trigger_id


def get_triggers(
    feed_name: Optional[str] = None,
    event_type: Optional[str] = None,
    enabled_only: bool = False,
) -> List[Dict[str, Any]]:
    """Get all triggers, optionally filtered."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_triggers_table(conn)
        
        query = "SELECT * FROM reflex_triggers WHERE 1=1"
        params = []
        
        if feed_name:
            query += " AND feed_name = ?"
            params.append(feed_name)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if enabled_only:
            query += " AND enabled = 1"
        
        query += " ORDER BY priority DESC, created_at DESC"
        
        cur.execute(query, params)
        
        columns = [desc[0] for desc in cur.description]
        results = []
        for row in cur.fetchall():
            trigger = dict(zip(columns, row))
            # Parse JSON fields
            if trigger.get("condition_json"):
                trigger["condition"] = json.loads(trigger["condition_json"])
            if trigger.get("tool_params_json"):
                trigger["tool_params"] = json.loads(trigger["tool_params_json"])
            results.append(trigger)
        
        return results


def get_trigger(trigger_id: int) -> Optional[Dict[str, Any]]:
    """Get a single trigger by ID."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_triggers_table(conn)
        
        cur.execute("SELECT * FROM reflex_triggers WHERE id = ?", (trigger_id,))
        row = cur.fetchone()
        
        if not row:
            return None
        
        columns = [desc[0] for desc in cur.description]
        trigger = dict(zip(columns, row))
        
        if trigger.get("condition_json"):
            trigger["condition"] = json.loads(trigger["condition_json"])
        if trigger.get("tool_params_json"):
            trigger["tool_params"] = json.loads(trigger["tool_params_json"])
        
        return trigger


def update_trigger(trigger_id: int, **updates) -> bool:
    """Update trigger fields."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_triggers_table(conn)
        
        # Handle JSON fields
        if "condition" in updates:
            updates["condition_json"] = json.dumps(updates.pop("condition"))
        if "tool_params" in updates:
            updates["tool_params_json"] = json.dumps(updates.pop("tool_params"))
        
        updates["updated_at"] = datetime.utcnow().isoformat()
        
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [trigger_id]
        
        cur.execute(f"UPDATE reflex_triggers SET {set_clause} WHERE id = ?", values)
        conn.commit()
        
        return cur.rowcount > 0


def delete_trigger(trigger_id: int) -> bool:
    """Delete a trigger."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_triggers_table(conn)
        
        cur.execute("DELETE FROM reflex_triggers WHERE id = ?", (trigger_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        
        return deleted


def toggle_trigger(trigger_id: int) -> Optional[bool]:
    """Toggle trigger enabled state. Returns new state or None if not found."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_triggers_table(conn)
        
        cur.execute("SELECT enabled FROM reflex_triggers WHERE id = ?", (trigger_id,))
        row = cur.fetchone()
        if not row:
            return None
        
        new_state = 0 if row[0] else 1
        cur.execute(
            "UPDATE reflex_triggers SET enabled = ?, updated_at = ? WHERE id = ?",
            (new_state, datetime.utcnow().isoformat(), trigger_id)
        )
        conn.commit()
        
        return bool(new_state)


def record_trigger_execution(
    trigger_id: int,
    success: bool,
    error: Optional[str] = None,
) -> None:
    """Record that a trigger was executed."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        if success:
            cur.execute("""
                UPDATE reflex_triggers 
                SET execution_count = execution_count + 1, last_executed = ?, last_error = NULL
                WHERE id = ?
            """, (now, trigger_id))
        else:
            cur.execute("""
                UPDATE reflex_triggers 
                SET execution_count = execution_count + 1, last_executed = ?, last_error = ?
                WHERE id = ?
            """, (now, error, trigger_id))
        
        conn.commit()


__all__ = [
    # Legacy in-memory
    'get_greetings',
    'get_shortcuts',
    'get_system_reflexes',
    'add_greeting',
    'add_shortcut',
    'add_system_reflex',
    'delete_greeting',
    'delete_shortcut',
    'delete_system_reflex',
    # SQLite triggers
    'init_triggers_table',
    'create_trigger',
    'get_triggers',
    'get_trigger',
    'update_trigger',
    'delete_trigger',
    'toggle_trigger',
    'record_trigger_execution',
]
