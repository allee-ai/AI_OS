"""
Identity Thread Schema
======================
Database functions for identity profiles, types, and facts.

Tables:
    profile_types - Categories of profiles (self, admin, family, etc.)
    profiles - Individual identity profiles
    fact_types - Types of facts (name, preference, belief, etc.)
    profile_facts - The actual identity facts
"""

import sqlite3
import threading
from typing import List, Dict, Optional

# Database connection from central location
from data.db import get_connection

# Thread-safe initialization lock
_init_lock = threading.Lock()
_initialized = False


# ============================================================================
# Table Initialization
# ============================================================================

def init_profile_types(conn: Optional[sqlite3.Connection] = None) -> None:
    """Initialize profile types table with defaults."""
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profile_types (
            type_name TEXT PRIMARY KEY,
            trust_level INTEGER DEFAULT 1,
            context_priority INTEGER DEFAULT 2,
            can_edit BOOLEAN DEFAULT FALSE,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Seed defaults if empty
    cur.execute("SELECT COUNT(*) FROM profile_types")
    if cur.fetchone()[0] == 0:
        defaults = [
            ("user", 10, 3, True, "Primary user"),
            ("machine", 8, 2, True, "Host machine"),
        ]
        cur.executemany("""
            INSERT INTO profile_types (type_name, trust_level, context_priority, can_edit, description)
            VALUES (?, ?, ?, ?, ?)
        """, defaults)
    
    if own_conn:
        conn.commit()


def init_profiles(conn: Optional[sqlite3.Connection] = None) -> None:
    """Initialize profiles table with core protected profiles."""
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    init_profile_types(conn)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            profile_id TEXT PRIMARY KEY,
            type_name TEXT NOT NULL,
            display_name TEXT,
            protected BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (type_name) REFERENCES profile_types(type_name)
        )
    """)
    
    # Migration: Add protected column if it doesn't exist (for existing databases)
    cur.execute("PRAGMA table_info(profiles)")
    columns = [row[1] for row in cur.fetchall()]
    if "protected" not in columns:
        cur.execute("ALTER TABLE profiles ADD COLUMN protected BOOLEAN DEFAULT FALSE")
    
    # Core protected profiles
    core_profiles = [
        ("primary_user", "user", "Primary User", True),
        ("machine", "machine", "Machine", True),
    ]
    for profile_id, type_name, display_name, protected in core_profiles:
        cur.execute("SELECT COUNT(*) FROM profiles WHERE profile_id = ?", (profile_id,))
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO profiles (profile_id, type_name, display_name, protected)
                VALUES (?, ?, ?, ?)
            """, (profile_id, type_name, display_name, protected))
    
    if own_conn:
        conn.commit()


def init_fact_types(conn: Optional[sqlite3.Connection] = None) -> None:
    """Initialize fact types table."""
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fact_types (
            fact_type TEXT PRIMARY KEY,
            description TEXT,
            default_weight REAL DEFAULT 0.5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Seed defaults
    cur.execute("SELECT COUNT(*) FROM fact_types")
    if cur.fetchone()[0] == 0:
        defaults = [
            ("name", "Display name", 0.9),
            ("email", "Email address", 0.6),
            ("location", "Location or timezone", 0.5),
            ("occupation", "Job or role", 0.6),
            ("note", "Freeform notes", 0.3),
            ("os", "Operating system", 0.5),
            ("hardware", "Hardware specs", 0.4),
        ]
        cur.executemany("""
            INSERT INTO fact_types (fact_type, description, default_weight)
            VALUES (?, ?, ?)
        """, defaults)
    
    if own_conn:
        conn.commit()


def init_profile_facts(conn: Optional[sqlite3.Connection] = None) -> None:
    """Initialize profile facts table with core fact keys (empty values)."""
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    init_profiles(conn)
    init_fact_types(conn)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profile_facts (
            profile_id TEXT NOT NULL,
            key TEXT NOT NULL,
            fact_type TEXT NOT NULL,
            l1_value TEXT,
            l2_value TEXT,
            l3_value TEXT,
            weight REAL DEFAULT 0.5,
            protected BOOLEAN DEFAULT FALSE,
            access_count INTEGER DEFAULT 0,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (profile_id, key),
            FOREIGN KEY (profile_id) REFERENCES profiles(profile_id),
            FOREIGN KEY (fact_type) REFERENCES fact_types(fact_type)
        )
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_profile_facts_weight ON profile_facts(weight DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_profile_facts_type ON profile_facts(fact_type)")
    
    # Migration: Add protected column if it doesn't exist (for existing databases)
    cur.execute("PRAGMA table_info(profile_facts)")
    columns = [row[1] for row in cur.fetchall()]
    if "protected" not in columns:
        cur.execute("ALTER TABLE profile_facts ADD COLUMN protected BOOLEAN DEFAULT FALSE")
    
    # Preset empty facts for primary_user
    user_facts = [
        ("primary_user", "name", "name", 0.9),
        ("primary_user", "email", "email", 0.6),
        ("primary_user", "location", "location", 0.5),
        ("primary_user", "occupation", "occupation", 0.6),
        ("primary_user", "notes", "note", 0.3),
    ]
    
    # Preset empty facts for machine
    machine_facts = [
        ("machine", "name", "name", 0.8),
        ("machine", "os", "os", 0.7),
        ("machine", "hardware", "hardware", 0.5),
        ("machine", "location", "location", 0.4),
        ("machine", "notes", "note", 0.3),
    ]
    
    for profile_id, key, fact_type, weight in user_facts + machine_facts:
        cur.execute(
            "SELECT COUNT(*) FROM profile_facts WHERE profile_id = ? AND key = ?",
            (profile_id, key)
        )
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO profile_facts (profile_id, key, fact_type, weight)
                VALUES (?, ?, ?, ?)
            """, (profile_id, key, fact_type, weight))
    
    if own_conn:
        conn.commit()


def ensure_initialized() -> None:
    """Thread-safe initialization - call this before any DB operation."""
    global _initialized
    if _initialized:
        return
    
    with _init_lock:
        if _initialized:  # Double-check after acquiring lock
            return
        conn = get_connection()
        init_profile_types(conn)
        init_profiles(conn)
        init_fact_types(conn)
        init_profile_facts(conn)
        conn.commit()
        _initialized = True


# ============================================================================
# Profile Types CRUD
# ============================================================================

def create_profile_type(
    type_name: str,
    trust_level: int = 1,
    context_priority: int = 2,
    can_edit: bool = False,
    description: str = ""
) -> None:
    """Create or update a profile type."""
    ensure_initialized()
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO profile_types (type_name, trust_level, context_priority, can_edit, description)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(type_name) DO UPDATE SET
            trust_level = excluded.trust_level,
            context_priority = excluded.context_priority,
            can_edit = excluded.can_edit,
            description = excluded.description
    """, (type_name, trust_level, context_priority, can_edit, description))
    conn.commit()


def get_profile_types() -> List[Dict]:
    """Get all profile types."""
    ensure_initialized()
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM profile_types ORDER BY trust_level DESC")
    return [dict(row) for row in cur.fetchall()]


def delete_profile_type(type_name: str) -> bool:
    """Delete a profile type (only if no profiles use it)."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM profiles WHERE type_name = ?", (type_name,))
    if cur.fetchone()[0] > 0:
        return False
    
    cur.execute("DELETE FROM profile_types WHERE type_name = ?", (type_name,))
    conn.commit()
    return True


# ============================================================================
# Profiles CRUD
# ============================================================================

def create_profile(profile_id: str, type_name: str, display_name: str = "") -> None:
    """Create or update a profile."""
    ensure_initialized()
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO profiles (profile_id, type_name, display_name)
        VALUES (?, ?, ?)
        ON CONFLICT(profile_id) DO UPDATE SET
            type_name = excluded.type_name,
            display_name = excluded.display_name
    """, (profile_id, type_name, display_name or profile_id.split('.')[-1]))
    conn.commit()


def get_profiles(type_name: str = None) -> List[Dict]:
    """Get all profiles, optionally filtered by type."""
    ensure_initialized()
    conn = get_connection(readonly=True)
    try:
        cur = conn.cursor()
        
        if type_name:
            cur.execute("""
                SELECT p.*, pt.trust_level, pt.context_priority, pt.can_edit
                FROM profiles p
                JOIN profile_types pt ON p.type_name = pt.type_name
                WHERE p.type_name = ?
                ORDER BY p.created_at
            """, (type_name,))
        else:
            cur.execute("""
                SELECT p.*, pt.trust_level, pt.context_priority, pt.can_edit
                FROM profiles p
                JOIN profile_types pt ON p.type_name = pt.type_name
                ORDER BY pt.trust_level DESC, p.created_at
            """)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def delete_profile(profile_id: str) -> bool:
    """Delete a profile and all its facts (only if not protected)."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Check if protected
    cur.execute("SELECT protected FROM profiles WHERE profile_id = ?", (profile_id,))
    row = cur.fetchone()
    if row and row[0]:
        return False  # Cannot delete protected profile
    
    cur.execute("DELETE FROM profile_facts WHERE profile_id = ?", (profile_id,))
    cur.execute("DELETE FROM profiles WHERE profile_id = ?", (profile_id,))
    conn.commit()
    return True


# ============================================================================
# Fact Types CRUD
# ============================================================================

def create_fact_type(fact_type: str, description: str = "", default_weight: float = 0.5) -> None:
    """Create or update a fact type."""
    ensure_initialized()
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO fact_types (fact_type, description, default_weight)
        VALUES (?, ?, ?)
        ON CONFLICT(fact_type) DO UPDATE SET
            description = excluded.description,
            default_weight = excluded.default_weight
    """, (fact_type, description, default_weight))
    conn.commit()


def get_fact_types() -> List[Dict]:
    """Get all fact types."""
    ensure_initialized()
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM fact_types ORDER BY fact_type")
    return [dict(row) for row in cur.fetchall()]


def delete_fact_type(fact_type: str) -> bool:
    """Delete a fact type (only if no facts use it)."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM profile_facts WHERE fact_type = ?", (fact_type,))
    if cur.fetchone()[0] > 0:
        return False
    
    cur.execute("DELETE FROM fact_types WHERE fact_type = ?", (fact_type,))
    conn.commit()
    return True


# ============================================================================
# Profile Facts CRUD
# ============================================================================

def push_profile_fact(
    profile_id: str,
    key: str,
    fact_type: str,
    l1_value: str = None,
    l2_value: str = None,
    l3_value: str = None,
    weight: float = None
) -> None:
    """Push a fact to a profile with L1/L2/L3 verbosity levels."""
    ensure_initialized()
    conn = get_connection()
    cur = conn.cursor()
    
    if weight is None:
        cur.execute("SELECT default_weight FROM fact_types WHERE fact_type = ?", (fact_type,))
        row = cur.fetchone()
        weight = row[0] if row else 0.5
    
    cur.execute("""
        INSERT INTO profile_facts (profile_id, key, fact_type, l1_value, l2_value, l3_value, weight, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(profile_id, key) DO UPDATE SET
            fact_type = excluded.fact_type,
            l1_value = excluded.l1_value,
            l2_value = excluded.l2_value,
            l3_value = excluded.l3_value,
            weight = excluded.weight,
            access_count = access_count + 1,
            last_accessed = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
    """, (profile_id, key, fact_type, l1_value, l2_value, l3_value, weight))
    conn.commit()


def pull_profile_facts(
    profile_id: str = None,
    fact_type: str = None,
    min_weight: float = 0.0,
    limit: int = 100
) -> List[Dict]:
    """Pull facts, optionally filtered by profile and/or fact type."""
    ensure_initialized()
    conn = get_connection(readonly=True)
    try:
        cur = conn.cursor()
        
        query = """
            SELECT pf.*, p.display_name, p.type_name, pt.trust_level
            FROM profile_facts pf
            JOIN profiles p ON pf.profile_id = p.profile_id
            JOIN profile_types pt ON p.type_name = pt.type_name
            WHERE pf.weight >= ?
        """
        params = [min_weight]
        
        if profile_id:
            query += " AND pf.profile_id = ?"
            params.append(profile_id)
        
        if fact_type:
            query += " AND pf.fact_type = ?"
            params.append(fact_type)
        
        query += " ORDER BY pf.weight DESC, pf.key LIMIT ?"
        params.append(limit)
        
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def update_fact_weight(profile_id: str, key: str, weight: float) -> None:
    """Update the weight of a specific fact."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE profile_facts 
        SET weight = ?, updated_at = CURRENT_TIMESTAMP
        WHERE profile_id = ? AND key = ?
    """, (weight, profile_id, key))
    conn.commit()


def delete_profile_fact(profile_id: str, key: str) -> bool:
    """Delete a specific fact (only if not protected)."""
    conn = get_connection()
    cur = conn.cursor()
    
    # Check if protected
    cur.execute("SELECT protected FROM profile_facts WHERE profile_id = ? AND key = ?", (profile_id, key))
    row = cur.fetchone()
    if row and row[0]:
        return False  # Cannot delete protected fact
    
    cur.execute("DELETE FROM profile_facts WHERE profile_id = ? AND key = ?", (profile_id, key))
    conn.commit()
    return cur.rowcount > 0


# ============================================================================
# Utility
# ============================================================================

def get_value_by_weight(fact: Dict, weight: float = None) -> str:
    """Get appropriate verbosity level based on weight.
    
    Falls back through l3 -> l2 -> l1 based on weight threshold.
    If only l1 exists, always returns l1 regardless of weight.
    """
    l1 = fact.get('l1_value', '') or ''
    l2 = fact.get('l2_value', '') or ''
    l3 = fact.get('l3_value', '') or ''
    
    # If only l1 exists, use it
    if l1 and not l2 and not l3:
        return l1
    
    w = weight if weight is not None else fact.get('weight', 0.5)
    if w >= 0.7:
        return l3 or l2 or l1
    elif w >= 0.4:
        return l2 or l1
    else:
        return l1 or l2


__all__ = [
    'init_profile_types',
    'init_profiles',
    'init_fact_types',
    'init_profile_facts',
    'create_profile_type',
    'get_profile_types',
    'delete_profile_type',
    'create_profile',
    'get_profiles',
    'delete_profile',
    'create_fact_type',
    'get_fact_types',
    'delete_fact_type',
    'push_profile_fact',
    'pull_profile_facts',
    'update_fact_weight',
    'delete_profile_fact',
    'get_value_by_weight',
]
