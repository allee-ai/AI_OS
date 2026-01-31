"""
Philosophy Thread Schema
========================
Database functions for philosophy profiles, types, and facts.

Tables:
    philosophy_profile_types - Categories of philosophical stances
    philosophy_profiles - Individual philosophy profiles
    philosophy_profile_facts - The actual philosophical stances/values
"""

import sqlite3
from contextlib import closing
from typing import List, Dict, Optional

# Database connection from central location
from data.db import get_connection


# ============================================================================
# Table Initialization
# ============================================================================

def init_philosophy_profile_types(conn: sqlite3.Connection = None) -> None:
    """Initialize philosophy profile types table with defaults."""
    conn = conn or get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS philosophy_profile_types (
            type_name TEXT PRIMARY KEY,
            description TEXT,
            priority INTEGER DEFAULT 5,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    defaults = [
        ("value_system", "Core values and what matters most", 10),
        ("ethical_framework", "Moral reasoning and ethical principles", 9),
        ("reasoning_style", "How to approach problems and decisions", 8),
        ("worldview", "Fundamental beliefs about reality and existence", 7),
        ("aesthetic", "Preferences in beauty, art, and expression", 6),
        ("meta_belief", "Beliefs about beliefs, epistemology", 5),
    ]
    for type_name, description, priority in defaults:
        cur.execute("INSERT OR IGNORE INTO philosophy_profile_types (type_name, description, priority) VALUES (?, ?, ?)", 
                    (type_name, description, priority))
    conn.commit()


def init_philosophy_profiles(conn: sqlite3.Connection = None) -> None:
    """Initialize philosophy profiles table."""
    conn = conn or get_connection()
    init_philosophy_profile_types(conn)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS philosophy_profiles (
            profile_id TEXT PRIMARY KEY,
            type_name TEXT NOT NULL,
            display_name TEXT,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""INSERT OR IGNORE INTO philosophy_profiles (profile_id, type_name, display_name, description) VALUES 
                   ('core.values', 'value_system', 'Core Values', 'Fundamental values')""")
    conn.commit()


def init_philosophy_profile_facts(conn: sqlite3.Connection = None) -> None:
    """Initialize philosophy profile facts table."""
    conn = conn or get_connection()
    init_philosophy_profiles(conn)
    init_philosophy_fact_types(conn)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS philosophy_profile_facts (
            id INTEGER PRIMARY KEY,
            profile_id TEXT NOT NULL,
            key TEXT NOT NULL,
            fact_type TEXT DEFAULT 'stance',
            l1_value TEXT,
            l2_value TEXT,
            l3_value TEXT,
            weight REAL DEFAULT 0.5,
            access_count INTEGER DEFAULT 0,
            last_accessed TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(profile_id, key)
        )
    """)
    conn.commit()


def init_philosophy_fact_types(conn: sqlite3.Connection = None) -> None:
    """Initialize philosophy fact types table with defaults."""
    conn = conn or get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS philosophy_fact_types (
            fact_type TEXT PRIMARY KEY,
            description TEXT,
            default_weight REAL DEFAULT 0.5,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Seed defaults
    cur.execute("SELECT COUNT(*) FROM philosophy_fact_types")
    if cur.fetchone()[0] == 0:
        defaults = [
            ("stance", "A position or viewpoint on a topic", 0.5),
            ("principle", "A fundamental rule or belief", 0.7),
            ("value", "Something considered important or worthwhile", 0.8),
            ("constraint", "A limitation or ethical boundary", 0.6),
            ("preference", "A favored choice or tendency", 0.4),
        ]
        cur.executemany("""
            INSERT INTO philosophy_fact_types (fact_type, description, default_weight)
            VALUES (?, ?, ?)
        """, defaults)
    conn.commit()


def get_philosophy_fact_types() -> List[Dict]:
    """Get all philosophy fact types."""
    with closing(get_connection(readonly=True)) as conn:
        init_philosophy_fact_types(conn)
        cur = conn.cursor()
        cur.execute("SELECT * FROM philosophy_fact_types ORDER BY fact_type")
        result = [dict(row) for row in cur.fetchall()]
    return result


def create_philosophy_fact_type(fact_type: str, description: str = "", default_weight: float = 0.5) -> None:
    """Create or update a philosophy fact type."""
    with closing(get_connection()) as conn:
        init_philosophy_fact_types(conn)
        conn.cursor().execute("""
            INSERT INTO philosophy_fact_types (fact_type, description, default_weight)
            VALUES (?, ?, ?)
            ON CONFLICT(fact_type) DO UPDATE SET
                description = excluded.description,
                default_weight = excluded.default_weight
        """, (fact_type, description, default_weight))
        conn.commit()


# ============================================================================
# Profile Types CRUD
# ============================================================================

def create_philosophy_profile_type(type_name: str, description: str = "", priority: int = 5) -> None:
    """Create or update a philosophy profile type."""
    with closing(get_connection()) as conn:
        init_philosophy_profile_types(conn)
        conn.cursor().execute("""
            INSERT INTO philosophy_profile_types (type_name, description, priority) VALUES (?, ?, ?)
            ON CONFLICT(type_name) DO UPDATE SET description=excluded.description, priority=excluded.priority
        """, (type_name, description, priority))
        conn.commit()


def get_philosophy_profile_types() -> List[Dict]:
    """Get all philosophy profile types."""
    with closing(get_connection(readonly=False)) as conn:
        init_philosophy_profile_types(conn)
        cur = conn.cursor()
        cur.execute("SELECT * FROM philosophy_profile_types ORDER BY priority DESC")
        result = [dict(row) for row in cur.fetchall()]
    return result


# ============================================================================
# Profiles CRUD
# ============================================================================

def create_philosophy_profile(profile_id: str, type_name: str, display_name: str = "", description: str = "") -> None:
    """Create or update a philosophy profile."""
    with closing(get_connection()) as conn:
        init_philosophy_profiles(conn)
        conn.cursor().execute("""
            INSERT INTO philosophy_profiles (profile_id, type_name, display_name, description) VALUES (?, ?, ?, ?)
            ON CONFLICT(profile_id) DO UPDATE SET 
                type_name=excluded.type_name, 
                display_name=excluded.display_name, 
                description=excluded.description
        """, (profile_id, type_name, display_name or profile_id.split('.')[-1], description))
        conn.commit()


def get_philosophy_profiles(type_name: str = None) -> List[Dict]:
    """Get all philosophy profiles, optionally filtered by type."""
    with closing(get_connection(readonly=False)) as conn:
        init_philosophy_profiles(conn)
        cur = conn.cursor()
        if type_name:
            cur.execute("""
                SELECT p.*, pt.priority, pt.description as type_description
                FROM philosophy_profiles p 
                JOIN philosophy_profile_types pt ON p.type_name = pt.type_name
                WHERE p.type_name = ? ORDER BY p.created_at
            """, (type_name,))
        else:
            cur.execute("""
                SELECT p.*, pt.priority, pt.description as type_description
                FROM philosophy_profiles p 
                JOIN philosophy_profile_types pt ON p.type_name = pt.type_name
                ORDER BY pt.priority DESC, p.created_at
            """)
        result = [dict(row) for row in cur.fetchall()]
    return result


def delete_philosophy_profile(profile_id: str) -> bool:
    """Delete a philosophy profile and all its facts."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM philosophy_profile_facts WHERE profile_id = ?", (profile_id,))
        cur.execute("DELETE FROM philosophy_profiles WHERE profile_id = ?", (profile_id,))
        conn.commit()
    return True


# ============================================================================
# Facts CRUD
# ============================================================================

def push_philosophy_profile_fact(
    profile_id: str, 
    key: str, 
    l1_value: str = None,
    l2_value: str = None, 
    l3_value: str = None, 
    weight: float = 0.5
) -> None:
    """Create or update a philosophy fact."""
    with closing(get_connection()) as conn:
        with conn:
            init_philosophy_profile_facts(conn)
            conn.cursor().execute("""
                INSERT INTO philosophy_profile_facts (profile_id, key, l1_value, l2_value, l3_value, weight, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(profile_id, key) DO UPDATE SET
                    l1_value = excluded.l1_value,
                    l2_value = excluded.l2_value,
                    l3_value = excluded.l3_value,
                    weight = excluded.weight,
                    access_count = access_count + 1,
                    last_accessed = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
            """, (profile_id, key, l1_value, l2_value, l3_value, weight))


def pull_philosophy_profile_facts(profile_id: str = None, min_weight: float = 0.0, limit: int = 100) -> List[Dict]:
    """Pull philosophy facts, optionally filtered by profile."""
    with closing(get_connection(readonly=False)) as conn:
        init_philosophy_profile_facts(conn)
        cur = conn.cursor()
        
        if profile_id:
            cur.execute("""
                SELECT pf.*, p.display_name, p.type_name, pt.priority
                FROM philosophy_profile_facts pf
                JOIN philosophy_profiles p ON pf.profile_id = p.profile_id
                JOIN philosophy_profile_types pt ON p.type_name = pt.type_name
                WHERE pf.profile_id = ? AND pf.weight >= ?
                ORDER BY pf.weight DESC, pf.key LIMIT ?
            """, (profile_id, min_weight, limit))
        else:
            cur.execute("""
                SELECT pf.*, p.display_name, p.type_name, pt.priority
                FROM philosophy_profile_facts pf
                JOIN philosophy_profiles p ON pf.profile_id = p.profile_id
                JOIN philosophy_profile_types pt ON p.type_name = pt.type_name
                WHERE pf.weight >= ?
                ORDER BY pt.priority DESC, pf.weight DESC, pf.key LIMIT ?
            """, (min_weight, limit))
        
        result = [dict(row) for row in cur.fetchall()]
    return result


def delete_philosophy_profile_fact(profile_id: str, key: str) -> bool:
    """Delete a specific philosophy fact."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM philosophy_profile_facts WHERE profile_id = ? AND key = ?", (profile_id, key))
        conn.commit()
        deleted = cur.rowcount > 0
    return deleted


# ============================================================================
# Utility
# ============================================================================

def get_value_by_weight(fact: Dict, weight: float = None) -> str:
    """Get appropriate verbosity level based on weight."""
    w = weight if weight is not None else fact.get('weight', 0.5)
    if w >= 0.7:
        return fact.get('l3_value', '') or fact.get('l2_value', '') or fact.get('l1_value', '')
    elif w >= 0.4:
        return fact.get('l2_value', '') or fact.get('l1_value', '')
    else:
        return fact.get('l1_value', '') or fact.get('l2_value', '')


__all__ = [
    'init_philosophy_profile_types',
    'init_philosophy_profiles', 
    'init_philosophy_profile_facts',
    'init_philosophy_fact_types',
    'create_philosophy_profile_type',
    'get_philosophy_profile_types',
    'create_philosophy_profile',
    'get_philosophy_profiles',
    'delete_philosophy_profile',
    'push_philosophy_profile_fact',
    'pull_philosophy_profile_facts',
    'delete_philosophy_profile_fact',
    'get_philosophy_fact_types',
    'create_philosophy_fact_type',
    'get_value_by_weight',
]
