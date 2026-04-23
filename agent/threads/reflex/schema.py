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
            
            -- Response mode: tool (execute tool), agent (generate via bridge),
            -- notify (surface in UI only)
            response_mode TEXT NOT NULL DEFAULT 'tool',

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
    
    # Migrations for existing tables
    try:
        cur.execute("ALTER TABLE reflex_triggers ADD COLUMN response_mode TEXT NOT NULL DEFAULT 'tool'")
    except Exception:
        pass  # Column already exists

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
    response_mode: str = "tool",
) -> int:
    """Create a new trigger automation.

    Args:
        response_mode: 'tool' (execute tool), 'agent' (generate via bridge),
                       or 'notify' (surface in UI only).
    """
    if response_mode not in ("tool", "agent", "notify", "protocol"):
        raise ValueError(f"Invalid response_mode: {response_mode}")

    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_triggers_table(conn)
        
        cur.execute("""
            INSERT INTO reflex_triggers 
            (name, description, trigger_type, feed_name, event_type, condition_json,
             tool_name, tool_action, tool_params_json, poll_interval, cron_expression,
             priority, response_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, description, trigger_type, feed_name, event_type,
            json.dumps(condition) if condition else None,
            tool_name, tool_action,
            json.dumps(tool_params) if tool_params else None,
            poll_interval, cron_expression, priority, response_mode,
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
    # Meta-thoughts (cognitive residue surfaced in STATE)
    'init_meta_thoughts_table',
    'add_meta_thought',
    'get_recent_meta_thoughts',
    'grade_expectation',
    'META_THOUGHT_KINDS',
    'META_THOUGHT_SOURCES',
]


# ============================================================================
# Meta-thoughts (cognitive residue)
# ============================================================================
#
# Meta-thoughts are what the agent thought ABOUT a turn — hypotheses it
# rejected, effects it expected, things it noticed it didn't know, and
# compressions of what actually happened.  They are written (Phase 1: by
# a seed path; Phase 2: by the model via response tags) and READ back
# into STATE on later turns so the agent can see its own prior cognition.
#
# Schema is strict: the set of kinds and sources is closed.  Unknown
# kinds/sources are silent-dropped at write time.  This is the "schema
# is the fence" rule — callers cannot create new categories.
#
# NOTE: All writes are best-effort.  A failed meta-thought write MUST
# NOT fail the turn that produced it.  All callers wrap writes in
# try/except and log silently on failure.

META_THOUGHT_KINDS = ("rejected", "expected", "unknown", "compression")
# "copilot" = notes left by the VS Code agent (Claude) across turns.
# First-class source so these are distinguishable from model/user/system thoughts.
META_THOUGHT_SOURCES = ("model", "user_correction", "seed", "system", "copilot")


def init_meta_thoughts_table(conn: Optional[sqlite3.Connection] = None) -> None:
    """Create the reflex_meta_thoughts table if it doesn't exist.

    Columns:
      id               - PK
      turn_id          - FK to convo_turns.id (nullable; some thoughts aren't tied to a turn)
      session_id       - denormalised session for cheap filtering
      kind             - one of META_THOUGHT_KINDS
      content          - the thought itself (short text)
      source           - one of META_THOUGHT_SOURCES
      confidence       - 0.0..1.0 model-reported confidence (default 0.5)
      weight           - 0.0..1.0 for STATE-inclusion filtering (default 0.5)
      first_asserted_at
      last_confirmed_at
      graded           - 0/1, true once an 'expected' has been compared to reality
      grade_delta      - JSON text: {"actual": "...", "match": bool, "notes": "..."}
      created_at
    """
    own_conn = conn is None
    conn = conn or get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reflex_meta_thoughts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn_id INTEGER,
                session_id TEXT,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'seed',
                confidence REAL NOT NULL DEFAULT 0.5,
                weight REAL NOT NULL DEFAULT 0.5,
                first_asserted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_confirmed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                graded INTEGER NOT NULL DEFAULT 0,
                grade_delta TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_meta_thoughts_session "
            "ON reflex_meta_thoughts(session_id, created_at DESC)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_meta_thoughts_kind "
            "ON reflex_meta_thoughts(kind, created_at DESC)"
        )
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()


def add_meta_thought(
    kind: str,
    content: str,
    *,
    turn_id: Optional[int] = None,
    session_id: Optional[str] = None,
    source: str = "seed",
    confidence: float = 0.5,
    weight: float = 0.5,
) -> Optional[int]:
    """Insert a meta-thought.  Returns row id, or None on any failure.

    Silent-drop semantics:
      - Unknown `kind` → drop (return None).
      - Unknown `source` → drop.
      - Empty/whitespace `content` → drop.
      - DB failure → log and return None; never raises.
    """
    if kind not in META_THOUGHT_KINDS:
        return None
    if source not in META_THOUGHT_SOURCES:
        return None
    if not content or not content.strip():
        return None

    content = content.strip()
    # Clamp numerics defensively
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except Exception:
        confidence = 0.5
    try:
        weight = max(0.0, min(1.0, float(weight)))
    except Exception:
        weight = 0.5

    # Cap content length so a runaway model can't flood the table
    if len(content) > 500:
        content = content[:500]

    try:
        with closing(get_connection()) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO reflex_meta_thoughts
                    (turn_id, session_id, kind, content, source, confidence, weight)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (turn_id, session_id, kind, content, source, confidence, weight),
            )
            conn.commit()
            return cur.lastrowid
    except Exception:
        # Never fail the turn.
        return None


def get_recent_meta_thoughts(
    session_id: Optional[str] = None,
    kinds: Optional[List[str]] = None,
    min_weight: float = 0.0,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Return recent meta-thoughts, newest first.

    If session_id is given, scoped to that session.
    If kinds is given, filtered to those kinds.
    Returns [] on any failure (never raises).
    """
    try:
        with closing(get_connection()) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            where = ["weight >= ?"]
            params: List[Any] = [min_weight]
            if session_id:
                where.append("session_id = ?")
                params.append(session_id)
            if kinds:
                # Validate against allowlist before interpolating
                safe_kinds = [k for k in kinds if k in META_THOUGHT_KINDS]
                if safe_kinds:
                    where.append(
                        "kind IN (" + ",".join(["?"] * len(safe_kinds)) + ")"
                    )
                    params.extend(safe_kinds)
            sql = (
                "SELECT id, turn_id, session_id, kind, content, source, "
                "confidence, weight, first_asserted_at, last_confirmed_at, "
                "graded, grade_delta, created_at "
                "FROM reflex_meta_thoughts "
                "WHERE " + " AND ".join(where) + " "
                "ORDER BY created_at DESC LIMIT ?"
            )
            params.append(int(max(1, limit)))
            rows = cur.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def grade_expectation(
    thought_id: int,
    actual: str,
    match: bool,
    notes: str = "",
) -> bool:
    """Grade an 'expected' meta-thought against what actually happened.

    Returns True on success, False on any failure.  Never raises.
    """
    try:
        delta = json.dumps({"actual": actual[:500], "match": bool(match), "notes": notes[:500]})
        with closing(get_connection()) as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE reflex_meta_thoughts "
                "SET graded = 1, grade_delta = ?, last_confirmed_at = CURRENT_TIMESTAMP "
                "WHERE id = ? AND kind = 'expected'",
                (delta, int(thought_id)),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception:
        return False
