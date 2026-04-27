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
from contextlib import closing
from typing import List, Dict, Optional, Any

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
        conn.close()


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
        conn.close()


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
    
    # Seed defaults (INSERT OR IGNORE for existing databases)
    defaults = [
        ("name", "Full name", 0.9),
        ("email", "Email address", 0.7),
        ("phone", "Phone number", 0.6),
        ("location", "City/region/timezone", 0.5),
        ("occupation", "Job title or role", 0.6),
        ("organization", "Company or affiliation", 0.5),
        ("relationship", "Relationship to user", 0.7),
        ("birthday", "Birthday or age", 0.4),
        ("note", "Freeform notes", 0.3),
        ("os", "Operating system", 0.5),
        ("hardware", "Hardware specs", 0.4),
    ]
    cur.executemany("""
        INSERT OR IGNORE INTO fact_types (fact_type, description, default_weight)
        VALUES (?, ?, ?)
    """, defaults)
    
    if own_conn:
        conn.commit()
        conn.close()


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
    
    # Preset empty facts for primary_user (contact info)
    user_facts = [
        ("primary_user", "name", "name", 0.9),
        ("primary_user", "email", "email", 0.7),
        ("primary_user", "phone", "phone", 0.6),
        ("primary_user", "location", "location", 0.5),
        ("primary_user", "occupation", "occupation", 0.6),
        ("primary_user", "organization", "organization", 0.5),
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
        conn.close()


def ensure_initialized() -> None:
    """Thread-safe initialization - call this before any DB operation."""
    global _initialized
    if _initialized:
        return
    
    with _init_lock:
        if _initialized:  # Double-check after acquiring lock
            return
        with closing(get_connection()) as conn:
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
    with closing(get_connection()) as conn:
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
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM profile_types ORDER BY trust_level DESC")
        result = [dict(row) for row in cur.fetchall()]
    return result


def delete_profile_type(type_name: str) -> bool:
    """Delete a profile type (only if no profiles use it)."""
    with closing(get_connection()) as conn:
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
    """Create or update a profile with preset contact facts."""
    ensure_initialized()
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        
        # Check if profile already exists
        cur.execute("SELECT COUNT(*) FROM profiles WHERE profile_id = ?", (profile_id,))
        is_new = cur.fetchone()[0] == 0
        
        cur.execute("""
            INSERT INTO profiles (profile_id, type_name, display_name)
            VALUES (?, ?, ?)
            ON CONFLICT(profile_id) DO UPDATE SET
                type_name = excluded.type_name,
                display_name = excluded.display_name
        """, (profile_id, type_name, display_name or profile_id.split('.')[-1]))
        
        # Add preset contact facts for new profiles
        if is_new:
            preset_facts = [
                (profile_id, "name", "name", 0.9),
                (profile_id, "email", "email", 0.7),
                (profile_id, "phone", "phone", 0.6),
                (profile_id, "location", "location", 0.5),
                (profile_id, "occupation", "occupation", 0.6),
                (profile_id, "organization", "organization", 0.5),
                (profile_id, "relationship", "relationship", 0.7),
                (profile_id, "notes", "note", 0.3),
            ]
            for pid, key, fact_type, weight in preset_facts:
                cur.execute("""
                    INSERT OR IGNORE INTO profile_facts 
                    (profile_id, key, fact_type, weight)
                    VALUES (?, ?, ?, ?)
                """, (pid, key, fact_type, weight))
        
        conn.commit()


def get_profiles(type_name: str = None) -> List[Dict]: # pyright: ignore[reportArgumentType]
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
    with closing(get_connection()) as conn:
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
    with closing(get_connection()) as conn:
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
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM fact_types ORDER BY fact_type")
        result = [dict(row) for row in cur.fetchall()]
    return result


def delete_fact_type(fact_type: str) -> bool:
    """Delete a fact type (only if no facts use it)."""
    with closing(get_connection()) as conn:
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
    l1_value: str = None, # type: ignore
    l2_value: str = None,
    l3_value: str = None,
    weight: float = None
) -> None:
    """Push a fact to a profile with L1/L2/L3 verbosity levels.
    
    Protected facts are never overwritten.  For non-protected facts the
    update preserves existing l2/l3 values when the incoming value is NULL
    and keeps the original fact_type when it is a curated type (not 'learned').
    """
    
    with closing(get_connection()) as conn:
        with conn:
            cur = conn.cursor()
            
            if weight is None:
                cur.execute("SELECT default_weight FROM fact_types WHERE fact_type = ?", (fact_type,))
                row = cur.fetchone()
                weight = row[0] if row else 0.5
            
            cur.execute("""
                INSERT INTO profile_facts (profile_id, key, fact_type, l1_value, l2_value, l3_value, weight, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(profile_id, key) DO UPDATE SET
                    fact_type = CASE
                        WHEN profile_facts.protected THEN profile_facts.fact_type
                        WHEN profile_facts.fact_type != 'learned' THEN profile_facts.fact_type
                        ELSE excluded.fact_type
                    END,
                    l1_value = CASE
                        WHEN profile_facts.protected THEN profile_facts.l1_value
                        ELSE COALESCE(excluded.l1_value, profile_facts.l1_value)
                    END,
                    l2_value = CASE
                        WHEN profile_facts.protected THEN profile_facts.l2_value
                        ELSE COALESCE(excluded.l2_value, profile_facts.l2_value)
                    END,
                    l3_value = CASE
                        WHEN profile_facts.protected THEN profile_facts.l3_value
                        ELSE COALESCE(excluded.l3_value, profile_facts.l3_value)
                    END,
                    weight = CASE
                        WHEN profile_facts.protected THEN profile_facts.weight
                        ELSE excluded.weight
                    END,
                    access_count = access_count + 1,
                    last_accessed = CURRENT_TIMESTAMP,
                    updated_at = CASE
                        WHEN profile_facts.protected THEN profile_facts.updated_at
                        ELSE CURRENT_TIMESTAMP
                    END
            """, (profile_id, key, fact_type, l1_value, l2_value, l3_value, weight))


def pull_profile_facts(
    profile_id: str = None,
    fact_type: str = None,
    min_weight: float = 0.0,
    limit: int = 100
) -> List[Dict]:
    """Pull facts, optionally filtered by profile and/or fact type.
    
    Protected facts are always included regardless of weight or limit.
    """
    ensure_initialized()
    conn = get_connection(readonly=True)
    try:
        cur = conn.cursor()

        # --- filters shared by both halves of the UNION ----
        where_extra = ""
        base_params: list = []
        if profile_id:
            where_extra += " AND pf.profile_id = ?"
            base_params.append(profile_id)
        if fact_type:
            where_extra += " AND pf.fact_type = ?"
            base_params.append(fact_type)

        # Protected facts first (no weight / limit filter)
        # then regular facts by weight desc, up to limit
        query = f"""
            SELECT * FROM (
                SELECT pf.*, p.display_name, p.type_name AS profile_type, pt.trust_level, 0 AS _sort
                FROM profile_facts pf
                JOIN profiles p ON pf.profile_id = p.profile_id
                JOIN profile_types pt ON p.type_name = pt.type_name
                WHERE pf.protected = 1 {where_extra}
              UNION ALL
                SELECT * FROM (
                    SELECT pf.*, p.display_name, p.type_name AS profile_type, pt.trust_level, 1 AS _sort
                    FROM profile_facts pf
                    JOIN profiles p ON pf.profile_id = p.profile_id
                    JOIN profile_types pt ON p.type_name = pt.type_name
                    WHERE pf.protected != 1 AND pf.weight >= ? {where_extra}
                    ORDER BY pf.weight DESC, pf.key
                    LIMIT ?
                )
            )
            ORDER BY _sort, weight DESC, key
        """
        params = base_params + [min_weight] + base_params + [limit]

        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def update_fact_weight(profile_id: str, key: str, weight: float) -> None:
    """Update the weight of a specific fact."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE profile_facts 
            SET weight = ?, updated_at = CURRENT_TIMESTAMP
            WHERE profile_id = ? AND key = ?
        """, (weight, profile_id, key))
        conn.commit()


def delete_profile_fact(profile_id: str, key: str) -> bool:
    """Delete a specific fact (only if not protected)."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        
        # Check if protected
        cur.execute("SELECT protected FROM profile_facts WHERE profile_id = ? AND key = ?", (profile_id, key))
        row = cur.fetchone()
        if row and row[0]:
            return False  # Cannot delete protected fact
        
        cur.execute("DELETE FROM profile_facts WHERE profile_id = ? AND key = ?", (profile_id, key))
        conn.commit()
        deleted = cur.rowcount > 0
    return deleted


# ============================================================================
# Decay
# ============================================================================

def decay_learned_facts(
    grace_days: int = 14,
    delete_age_days: int = 30,
    delete_max_access: int = 1,
    half_life_days: int = 30,
    min_weight_floor: float = 0.05,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Decay and prune facts of fact_type='learned'.

    Two passes, both restricted to ``fact_type='learned'`` and
    ``protected=0`` so curated facts (name/email/location/etc.) and
    machine/operator-set facts are never touched:

    1. **Prune** — DELETE learned facts whose ``last_accessed`` is older
       than ``delete_age_days`` AND whose ``access_count`` is at most
       ``delete_max_access``.  Captures auto-extracted noise that never
       got reused.
    2. **Decay** — for every other learned fact older than ``grace_days``
       since last access, multiply weight by ``0.5 ** (age / half_life)``,
       clamping to ``min_weight_floor``.  After decay, any fact whose
       weight is at or below the floor AND whose access_count is 0 is
       also deleted.

    Args:
        grace_days: Skip decay for facts touched in the last N days.
        delete_age_days: Hard-prune cutoff for unused learned facts.
        delete_max_access: An access_count <= this counts as 'unused'.
        half_life_days: Weight halves every N days of inactivity.
        min_weight_floor: Decay never drops below this; anything at or
            below this with access_count=0 is then deleted.
        dry_run: If True, no DB writes happen; the return dict shows
            what *would* be done.

    Returns:
        {
            "pruned": [{profile_id, key, weight, access_count, age_days}, ...],
            "decayed": [{profile_id, key, old_weight, new_weight, age_days}, ...],
            "floor_deleted": [{profile_id, key}, ...],
            "skipped_recent": int,
            "dry_run": bool,
        }
    """
    out: Dict[str, Any] = {
        "pruned": [],
        "decayed": [],
        "floor_deleted": [],
        "skipped_recent": 0,
        "dry_run": dry_run,
    }

    with closing(get_connection()) as conn:
        cur = conn.cursor()

        # Pass 1 — hard-prune unused learned facts.
        cur.execute(
            """
            SELECT profile_id, key, weight, access_count, last_accessed,
                   CAST(julianday('now') - julianday(last_accessed) AS REAL) AS age_days
            FROM profile_facts
            WHERE fact_type = 'learned'
              AND protected = 0
              AND access_count <= ?
              AND CAST(julianday('now') - julianday(last_accessed) AS REAL) >= ?
            """,
            (delete_max_access, delete_age_days),
        )
        prune_rows = cur.fetchall()
        pruned_keys: set = set()
        for r in prune_rows:
            pruned_keys.add((r["profile_id"], r["key"]))
            out["pruned"].append({
                "profile_id": r["profile_id"],
                "key": r["key"],
                "weight": r["weight"],
                "access_count": r["access_count"],
                "age_days": round(r["age_days"], 1),
            })
            if not dry_run:
                cur.execute(
                    "DELETE FROM profile_facts WHERE profile_id = ? AND key = ? "
                    "AND fact_type = 'learned' AND protected = 0",
                    (r["profile_id"], r["key"]),
                )

        # Pass 2 — exponential decay on remaining learned facts past grace.
        cur.execute(
            """
            SELECT profile_id, key, weight, access_count,
                   CAST(julianday('now') - julianday(last_accessed) AS REAL) AS age_days
            FROM profile_facts
            WHERE fact_type = 'learned'
              AND protected = 0
            """
        )
        for r in cur.fetchall():
            # In dry_run, pass 1 didn't actually delete — skip those rows here
            # so the report doesn't double-count.
            if (r["profile_id"], r["key"]) in pruned_keys:
                continue
            age = float(r["age_days"] or 0.0)
            if age < grace_days:
                out["skipped_recent"] += 1
                continue
            old_w = float(r["weight"] or 0.0)
            decay_mult = 0.5 ** (age / float(half_life_days))
            new_w = max(min_weight_floor, old_w * decay_mult)
            # Skip no-op updates
            if abs(new_w - old_w) < 1e-4:
                continue
            out["decayed"].append({
                "profile_id": r["profile_id"],
                "key": r["key"],
                "old_weight": round(old_w, 3),
                "new_weight": round(new_w, 3),
                "age_days": round(age, 1),
            })
            if not dry_run:
                cur.execute(
                    "UPDATE profile_facts SET weight = ? "
                    "WHERE profile_id = ? AND key = ? "
                    "AND fact_type = 'learned' AND protected = 0",
                    (new_w, r["profile_id"], r["key"]),
                )

        # Pass 3 — facts that hit the floor with no access ever, drop them.
        cur.execute(
            """
            SELECT profile_id, key
            FROM profile_facts
            WHERE fact_type = 'learned'
              AND protected = 0
              AND access_count = 0
              AND weight <= ?
            """,
            (min_weight_floor,),
        )
        for r in cur.fetchall():
            out["floor_deleted"].append({
                "profile_id": r["profile_id"],
                "key": r["key"],
            })
            if not dry_run:
                cur.execute(
                    "DELETE FROM profile_facts WHERE profile_id = ? AND key = ? "
                    "AND fact_type = 'learned' AND protected = 0",
                    (r["profile_id"], r["key"]),
                )

        if not dry_run:
            conn.commit()

    return out


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
    'decay_learned_facts',
    'get_value_by_weight',
]
