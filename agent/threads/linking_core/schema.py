"""
Linking Core Thread Schema
==========================
Database operations for concept links, co-occurrence, and spread activation.

LinkingCore is the SCORING/RETRIEVAL engine that maintains the concept graph
and determines what's relevant to the current context.

This is SELF-CONTAINED - all concept graph operations are defined here.
"""

import sqlite3
import re
import math
from contextlib import closing
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone

# ─────────────────────────────────────────────────────────────
# Database Connection
# ─────────────────────────────────────────────────────────────

from data.db import get_connection


# ─────────────────────────────────────────────────────────────
# Table Initialization
# ─────────────────────────────────────────────────────────────

def init_concept_links_table(conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Create concept_links table for spread activation.
    
    This is the core of associative memory:
    - When user mentions "coffee", we activate sarah.* if sarah+coffee linked
    - Strength decays over time, reinforces on co-occurrence
    - Supports hierarchical keys: "sarah" activates "sarah.likes.blue"
    """
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS concept_links (
            concept_a TEXT NOT NULL,
            concept_b TEXT NOT NULL,
            strength REAL DEFAULT 0.5,
            fire_count INTEGER DEFAULT 1,
            last_fired TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            potentiation TEXT DEFAULT 'SHORT',
            PRIMARY KEY (concept_a, concept_b)
        )
    """)
    
    # Add potentiation column if missing (migration for existing DBs)
    try:
        cur.execute("ALTER TABLE concept_links ADD COLUMN potentiation TEXT DEFAULT 'SHORT'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Indexes for fast spread activation queries
    cur.execute("CREATE INDEX IF NOT EXISTS idx_concept_a ON concept_links(concept_a)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_concept_b ON concept_links(concept_b)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_concept_strength ON concept_links(strength DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_concept_potentiation ON concept_links(potentiation)")
    
    if own_conn:
        conn.commit()
        conn.close()


def init_cooccurrence_table(conn: Optional[sqlite3.Connection] = None) -> None:
    """Create key_cooccurrence table for tracking concept co-occurrences."""
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS key_cooccurrence (
            key_a TEXT NOT NULL,
            key_b TEXT NOT NULL,
            count INTEGER DEFAULT 1,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (key_a, key_b)
        )
    """)
    
    if own_conn:
        conn.commit()
        conn.close()


# ─────────────────────────────────────────────────────────────
# Concept Linking (Hebbian Learning)
# ─────────────────────────────────────────────────────────────

def link_concepts(concept_a: str, concept_b: str, learning_rate: float = 0.1) -> float:
    """
    Strengthen the link between two concepts (Hebbian learning).
    
    strength += (1 - strength) * learning_rate
    
    Returns the new strength.
    """
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_concept_links_table(conn)
        
        # Canonical ordering for consistency
        if concept_a > concept_b:
            concept_a, concept_b = concept_b, concept_a
        
        # Check existing
        cur.execute("""
            SELECT strength, fire_count FROM concept_links 
            WHERE concept_a = ? AND concept_b = ?
        """, (concept_a, concept_b))
        row = cur.fetchone()
        
        if row:
            old_strength = row[0]
            fire_count = row[1]
            # Hebbian update: asymptotic approach to 1.0
            new_strength = old_strength + (1.0 - old_strength) * learning_rate
            cur.execute("""
                UPDATE concept_links 
                SET strength = ?, fire_count = ?, last_fired = CURRENT_TIMESTAMP
                WHERE concept_a = ? AND concept_b = ?
            """, (new_strength, fire_count + 1, concept_a, concept_b))
        else:
            # New link starts at learning_rate
            new_strength = learning_rate
            cur.execute("""
                INSERT INTO concept_links (concept_a, concept_b, strength, fire_count)
                VALUES (?, ?, ?, 1)
            """, (concept_a, concept_b, new_strength))
        
        conn.commit()
    return new_strength


def decay_concept_links(decay_rate: float = 0.95, min_strength: float = 0.05) -> int:
    """
    Apply decay to all concept links.
    
    Run periodically (e.g., daily) to let old associations fade.
    Links below min_strength are pruned.
    
    Returns number of links pruned.
    """
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        
        # Decay all links
        cur.execute("UPDATE concept_links SET strength = strength * ?", (decay_rate,))
        
        # Prune weak links
        cur.execute("DELETE FROM concept_links WHERE strength < ?", (min_strength,))
        pruned = cur.rowcount
        
        conn.commit()
    return pruned


def consolidate_links(fire_threshold: int = 5, strength_threshold: float = 0.5) -> Dict[str, Any]:
    """
    Consolidation pass — promote frequently-fired links from SHORT to LONG potentiation.
    
    This is the "sleep" phase for the concept graph:
    - SHORT links that have fired enough become LONG (stable memories)
    - LONG links are candidates for finetune export
    
    Args:
        fire_threshold: Minimum fire_count to promote to LONG
        strength_threshold: Minimum strength to promote to LONG
    
    Returns:
        {"promoted": int, "total_long": int, "total_short": int}
    """
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_concept_links_table(conn)
        
        # Promote high-fire SHORT links to LONG
        cur.execute("""
            UPDATE concept_links 
            SET potentiation = 'LONG'
            WHERE potentiation = 'SHORT' 
              AND fire_count >= ? 
              AND strength >= ?
        """, (fire_threshold, strength_threshold))
        promoted = cur.rowcount
        
        # Count totals
        cur.execute("SELECT COUNT(*) FROM concept_links WHERE potentiation = 'LONG'")
        total_long = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM concept_links WHERE potentiation = 'SHORT'")
        total_short = cur.fetchone()[0]
        
        conn.commit()
    
    return {
        "promoted": promoted,
        "total_long": total_long,
        "total_short": total_short
    }


def get_long_links(limit: int = 500) -> List[Dict[str, Any]]:
    """
    Get all LONG-potentiated links for finetune export.
    
    These are stable, consolidated memories ready to become training data.
    """
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT concept_a, concept_b, strength, fire_count, last_fired, created_at
            FROM concept_links
            WHERE potentiation = 'LONG'
            ORDER BY strength DESC, fire_count DESC
            LIMIT ?
        """, (limit,))
        
        links = []
        for row in cur.fetchall():
            links.append({
                "concept_a": row[0],
                "concept_b": row[1],
                "strength": row[2],
                "fire_count": row[3],
                "last_fired": row[4],
                "created_at": row[5],
                "potentiation": "LONG"
            })
    
    return links


def get_potentiation_stats() -> Dict[str, Any]:
    """Get statistics on link potentiation states."""
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT potentiation, COUNT(*), AVG(strength), AVG(fire_count)
            FROM concept_links
            GROUP BY potentiation
        """)
        
        stats = {"SHORT": {"count": 0, "avg_strength": 0, "avg_fires": 0},
                 "LONG": {"count": 0, "avg_strength": 0, "avg_fires": 0}}
        
        for row in cur.fetchall():
            pot = row[0] or "SHORT"
            stats[pot] = {
                "count": row[1],
                "avg_strength": round(row[2] or 0, 3),
                "avg_fires": round(row[3] or 0, 1)
            }
    
    return stats


# ─────────────────────────────────────────────────────────────
# Spread Activation
# ─────────────────────────────────────────────────────────────

def spread_activate(
    input_concepts: List[str],
    activation_threshold: float = 0.1,
    max_hops: int = 1,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Spread activation from input concepts to find related concepts.
    
    Args:
        input_concepts: List of concepts extracted from user input
        activation_threshold: Minimum link strength to follow
        max_hops: How many hops to follow (1 = direct links only)
        limit: Max concepts to return
    
    Returns:
        List of {concept, activation, path} sorted by activation descending
    """
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        
        # Activation accumulator
        activations: Dict[str, float] = {}
        paths: Dict[str, List[str]] = {}
        
        # Start with input concepts at full activation
        frontier = [(c, 1.0, [c]) for c in input_concepts]
        
        for hop in range(max_hops + 1):
            if not frontier:
                break
            
            next_frontier = []
            for concept, current_activation, path in frontier:
                # Record activation (take max if multiple paths)
                if concept not in activations or activations[concept] < current_activation:
                    activations[concept] = current_activation
                    paths[concept] = path
                
                if hop < max_hops:
                    # Find linked concepts
                    cur.execute("""
                        SELECT concept_b, strength FROM concept_links 
                        WHERE concept_a = ? AND strength >= ?
                        UNION
                        SELECT concept_a, strength FROM concept_links 
                        WHERE concept_b = ? AND strength >= ?
                        ORDER BY strength DESC
                        LIMIT 20
                    """, (concept, activation_threshold, concept, activation_threshold))
                    
                    for row in cur.fetchall():
                        linked_concept = row[0]
                        link_strength = row[1]
                        # Activation diminishes with each hop
                        spread_activation_val = current_activation * link_strength
                        if spread_activation_val >= activation_threshold:
                            next_frontier.append((linked_concept, spread_activation_val, path + [linked_concept]))
            
            frontier = next_frontier
        
        # Also activate hierarchical children (sarah → sarah.likes.*)
        for concept in list(input_concepts):
            cur.execute("""
                SELECT DISTINCT concept_a FROM concept_links 
                WHERE concept_a LIKE ? || '.%'
                UNION
                SELECT DISTINCT concept_b FROM concept_links 
                WHERE concept_b LIKE ? || '.%'
            """, (concept, concept))
            for row in cur.fetchall():
                child = row[0]
                # Children get 80% of parent activation
                if child not in activations or activations[child] < 0.8:
                    activations[child] = 0.8
                    paths[child] = [concept, child]
    
    # Sort by activation and return
    results = [
        {"concept": c, "activation": a, "path": paths.get(c, [c])}
        for c, a in activations.items()
        if c not in input_concepts  # Don't return input concepts
    ]
    results.sort(key=lambda x: x["activation"], reverse=True)
    return results[:limit]


# ─────────────────────────────────────────────────────────────
# Concept Extraction
# ─────────────────────────────────────────────────────────────

# Stop words for concept extraction
STOP_WORDS = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these',
    'those', 'what', 'which', 'who', 'whom', 'where', 'when', 'why', 'how',
    'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some',
    'such', 'only', 'same', 'than', 'too', 'very', 'just', 'also', 'now',
    'here', 'there', 'then', 'once', 'about', 'after', 'before', 'above',
    'below', 'between', 'into', 'through', 'during', 'under', 'again',
    'further', 'hey', 'hello', 'you', 'your', 'anything', 'something',
    'nothing', 'everything', 'anyone', 'someone', 'know', 'think', 'want',
    'need', 'like', 'tell', 'said', 'says', 'any', 'with', 'for', 'and',
    'but', 'or', 'not', 'no', 'yes', 'user', 'agent', 'to', 'of', 'in', 'on',
    'at', 'by', 'from', 'as', 'me', 'my', 'myself', 'we', 'our', 'ours',
    'he', 'him', 'his', 'she', 'her', 'hers', 'it', 'its', 'they', 'them'
}


def extract_concepts_from_text(text: str) -> List[str]:
    """
    Extract concept keys from free text for spread activation queries.
    
    Example:
        "Hey, did Sarah mention anything about coffee?"
        → ['sarah', 'coffee', 'mention']
    """
    # Lowercase
    text_lower = text.lower()
    
    # Find capitalized words (names)
    names = re.findall(r'\b([A-Z][a-z]+)\b', text)
    concepts = [n.lower() for n in names if n.lower() not in STOP_WORDS]
    
    # Find important words (> 2 chars, not stop words)
    words = re.findall(r'\b([a-z]{3,})\b', text_lower)
    for word in words:
        if word not in STOP_WORDS and word not in concepts:
            concepts.append(word)
    
    return concepts


def extract_concepts_from_value(value: str) -> List[str]:
    """
    Extract concept tokens from a fact value.
    
    "Sarah works at Blue Bottle Coffee" → ["sarah", "blue", "bottle", "coffee"]
    """
    text = value.lower()
    words = re.findall(r'\b[a-z][a-z0-9_]{1,}\b', text)
    concepts = [w for w in words if w not in STOP_WORDS]
    return list(set(concepts))


# ─────────────────────────────────────────────────────────────
# Co-occurrence Scoring
# ─────────────────────────────────────────────────────────────

def get_cooccurrence_score(key: str, context_keys: List[str]) -> float:
    """
    Get co-occurrence boost for a key given current context keys.
    
    Returns a value 0.0 - 0.3 based on how often this key
    has appeared with the context keys in past conversations.
    """
    if not context_keys:
        return 0.0
    
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        init_cooccurrence_table(conn)
        
        total_boost = 0.0
        
        for ctx_key in context_keys:
            # Check both orderings
            a, b = (key, ctx_key) if key < ctx_key else (ctx_key, key)
            
            cur.execute("""
                SELECT count FROM key_cooccurrence
                WHERE key_a = ? AND key_b = ?
            """, (a, b))
            
            row = cur.fetchone()
            if row:
                count = row[0]
                boost = min(math.log(count + 1) * 0.03, 0.15)
                total_boost += boost
    
    return min(total_boost, 0.3)


def record_cooccurrence(key_a: str, key_b: str) -> None:
    """Record that two keys appeared together in a conversation."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_cooccurrence_table(conn)
        
        # Canonical ordering
        if key_a > key_b:
            key_a, key_b = key_b, key_a
        
        cur.execute("""
            INSERT INTO key_cooccurrence (key_a, key_b, count)
            VALUES (?, ?, 1)
            ON CONFLICT(key_a, key_b) DO UPDATE SET 
                count = count + 1,
                last_seen = CURRENT_TIMESTAMP
        """, (key_a, key_b))
        
        conn.commit()


def record_concept_cooccurrence(concepts: List[str], learning_rate: float = 0.1) -> int:
    """
    Record that these concepts appeared together in a conversation.
    Creates/strengthens links between all pairs.
    """
    if len(concepts) < 2:
        return 0
    
    unique = list(set(concepts))
    count = 0
    
    for i, a in enumerate(unique):
        for b in unique[i+1:]:
            link_concepts(a, b, learning_rate)
            count += 1
    
    return count


def extract_and_record_conversation_concepts(
    turns: List[Dict[str, str]],
    session_id: str = "",
    learning_rate: float = 0.1,
) -> Dict[str, Any]:
    """
    Extract concepts from an entire conversation and record co-occurrences.

    Operates on the aggregate text of all turns rather than individual messages,
    so the graph captures conversational context (e.g. if "sarah" and "coffee"
    appear in different turns of the same conversation, they still get linked).

    Works identically for live conversations and imported chats (Discord,
    ChatGPT, etc.) — anything that provides a list of turn dicts.

    Args:
        turns: List of dicts with at least ``"user"`` and/or ``"assistant"`` keys.
        session_id: Optional identifier for logging.
        learning_rate: Hebbian learning rate passed to ``record_concept_cooccurrence``.

    Returns:
        {"concepts": [...], "links_created": int, "turn_count": int}
    """
    # Build aggregate text from all turns
    chunks: List[str] = []
    for turn in turns:
        if turn.get("user"):
            chunks.append(turn["user"])
        if turn.get("assistant"):
            chunks.append(turn["assistant"])

    if not chunks:
        return {"concepts": [], "links_created": 0, "turn_count": 0}

    aggregate = " ".join(chunks)
    concepts = extract_concepts_from_text(aggregate)

    # Cap at 60 concepts to keep O(n²) manageable
    if len(concepts) > 60:
        # Prefer concepts by frequency in the text
        text_lower = aggregate.lower()
        concepts.sort(key=lambda c: text_lower.count(c), reverse=True)
        concepts = concepts[:60]

    links_created = record_concept_cooccurrence(concepts, learning_rate=learning_rate)

    return {
        "concepts": concepts,
        "links_created": links_created,
        "turn_count": len(turns),
    }


# ─────────────────────────────────────────────────────────────
# Fact Retrieval
# ─────────────────────────────────────────────────────────────

def get_keys_for_concepts(concepts: List[Any], limit: int = 30) -> List[Dict[str, Any]]:
    """
    Given activated concepts, retrieve matching fact keys from fact_relevance.
    
    Matches on:
    - Exact key match
    - Prefix match (sarah → sarah.likes.blue)
    """
    if not concepts:
        return []
    
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        
        results = []
        seen_keys = set()
        
        for concept_data in concepts if isinstance(concepts[0], dict) else [{"concept": c, "activation": 1.0} for c in concepts]:
            concept = concept_data["concept"] if isinstance(concept_data, dict) else concept_data
            activation = concept_data.get("activation", 1.0) if isinstance(concept_data, dict) else 1.0
            
            # Exact match or prefix match on fact_key
            cur.execute("""
                SELECT fact_key, fact_text, final_score 
                FROM fact_relevance
                WHERE fact_key = ? OR fact_key LIKE ? || '.%'
                ORDER BY final_score DESC
                LIMIT 10
            """, (concept, concept))
            
            for row in cur.fetchall():
                key = row[0]
                if key not in seen_keys:
                    seen_keys.add(key)
                    results.append({
                        "fact_key": key,
                        "fact_text": row[1],
                        "final_score": row[2],
                        "combined_score": activation * row[2],
                        "activated_by": concept
                    })
    
    # Sort by combined score
    results.sort(key=lambda x: x["combined_score"], reverse=True)
    return results[:limit]


# ─────────────────────────────────────────────────────────────
# Graph Indexing
# ─────────────────────────────────────────────────────────────

def index_key_in_concept_graph(key: str, value: str, learning_rate: float = 0.15) -> int:
    """
    Index a key:value pair into the concept graph.
    
    1. Links parent↔child along dot notation (identity → identity.user)
    2. Extracts concepts from value and cross-links them
    """
    links_created = 0
    
    # 1. Link parent↔child along the key hierarchy
    parts = key.split('.')
    for i in range(len(parts) - 1):
        parent = '.'.join(parts[:i+1])
        child = '.'.join(parts[:i+2])
        link_concepts(parent, child, learning_rate=0.3)
        links_created += 1
    
    # 2. Extract concepts from the value and link to the full key
    value_concepts = extract_concepts_from_value(value)
    for concept in value_concepts:
        link_concepts(key, concept, learning_rate=learning_rate)
        links_created += 1
        
        leaf = parts[-1] if parts else key
        if leaf != concept:
            link_concepts(leaf, concept, learning_rate=learning_rate)
            links_created += 1
    
    # 3. Link sibling concepts from the value together
    if len(value_concepts) >= 2:
        for i, a in enumerate(value_concepts):
            for b in value_concepts[i+1:]:
                link_concepts(a, b, learning_rate=learning_rate * 0.5)
                links_created += 1
    
    return links_created


# ─────────────────────────────────────────────────────────────
# CRUD Operations for API
# ─────────────────────────────────────────────────────────────

def get_concepts(limit: int = 100) -> List[Dict[str, Any]]:
    """Get all unique concepts from concept_links table."""
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT DISTINCT concept FROM (
                SELECT concept_a as concept FROM concept_links
                UNION
                SELECT concept_b as concept FROM concept_links
            ) ORDER BY concept LIMIT ?
        """, (limit,))
        
        concepts = [{"concept": row[0]} for row in cur.fetchall()]
    return concepts


def get_all_links(limit: int = 500) -> List[Dict[str, Any]]:
    """Get all concept links for graph visualization."""
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT concept_a, concept_b, strength, created_at
            FROM concept_links
            ORDER BY strength DESC
            LIMIT ?
        """, (limit,))
        
        links = []
        for row in cur.fetchall():
            links.append({
                "source": row[0],
                "target": row[1],
                "strength": row[2],
                "type": "related",
                "created_at": row[3]
            })
    
    return links


def get_links_for_concept(concept: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get all links connected to a specific concept."""
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT concept_a, concept_b, strength
            FROM concept_links
            WHERE concept_a = ? OR concept_b = ?
            ORDER BY strength DESC
            LIMIT ?
        """, (concept, concept, limit))
        
        links = []
        for row in cur.fetchall():
            other = row[1] if row[0] == concept else row[0]
            links.append({
                "concept": other,
                "strength": row[2],
                "type": "related",
                "direction": "outgoing" if row[0] == concept else "incoming"
            })
    
    return links


def create_link(
    concept_a: str,
    concept_b: str,
    strength: float = 0.5,
    link_type: str = "related"
) -> bool:
    """Create a new concept link with explicit strength."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        init_concept_links_table(conn)
        
        # Canonical ordering
        if concept_a > concept_b:
            concept_a, concept_b = concept_b, concept_a
        
        try:
            cur.execute("""
                INSERT OR REPLACE INTO concept_links (concept_a, concept_b, strength)
                VALUES (?, ?, ?)
            """, (concept_a, concept_b, strength))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error creating link: {e}")
            return False


def delete_link(concept_a: str, concept_b: str) -> bool:
    """Delete a concept link."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        
        cur.execute("""
            DELETE FROM concept_links 
            WHERE (concept_a = ? AND concept_b = ?)
               OR (concept_a = ? AND concept_b = ?)
        """, (concept_a, concept_b, concept_b, concept_a))
        
        deleted = cur.rowcount > 0
        conn.commit()
    return deleted


def update_link_strength(concept_a: str, concept_b: str, strength: float) -> bool:
    """Update the strength of a concept link."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE concept_links 
            SET strength = ?
            WHERE (concept_a = ? AND concept_b = ?)
               OR (concept_a = ? AND concept_b = ?)
        """, (strength, concept_a, concept_b, concept_b, concept_a))
        
        updated = cur.rowcount > 0
        conn.commit()
    return updated


# ─────────────────────────────────────────────────────────────
# Structural Mind Map — the shape of the machine
# ─────────────────────────────────────────────────────────────

def get_structural_graph(
    include_cross_links: bool = True,
    min_cross_strength: float = 0.15,
    max_cross_links: int = 200,
) -> Dict[str, Any]:
    """
    Build a hierarchical graph of the entire agent architecture.

    Returns *two* kinds of edges:
      1. **structural** — parent→child within a thread's data hierarchy
         (identity → primary_user → name, philosophy → core.values → honesty, etc.)
      2. **associative** — cross-thread concept_links discovered by LinkingCore
         (an identity fact linked to a philosophy stance, a tool to a concept, etc.)

    Nodes carry a ``thread``, ``depth``, and ``kind`` field so the frontend can
    size / colour them by hierarchy level and thread membership.
    """
    nodes: Dict[str, Dict[str, Any]] = {}   # id → node dict
    structural_links: list = []              # parent→child edges
    cross_links: list = []                   # associative edges

    def _add_node(node_id: str, label: str, thread: str, kind: str, depth: int = 0,
                  weight: float = 1.0, data: dict = None):
        nodes[node_id] = {
            "id":     node_id,
            "label":  label,
            "thread": thread,
            "kind":   kind,     # thread | group | fact | tool | trigger | event
            "depth":  depth,
            "weight": weight,
            "data":   data or {},
        }

    def _add_structural(parent_id: str, child_id: str):
        structural_links.append({
            "source": parent_id,
            "target": child_id,
            "type":   "structural",
        })

    # ── 1. Identity thread ───────────────────────────────────────────
    _add_node("identity", "Identity", "identity", "thread", depth=0, weight=10)
    try:
        from agent.threads.identity.schema import get_profiles, pull_profile_facts
        for profile in get_profiles():
            pid = profile.get("profile_id", "")
            p_node = f"identity.{pid}"
            _add_node(p_node, pid, "identity", "group", depth=1,
                      data={"type_name": profile.get("type_name", "")})
            _add_structural("identity", p_node)

            for fact in pull_profile_facts(profile_id=pid, limit=200):
                key   = fact.get("key", "")
                value = fact.get("l1_value", "") or fact.get("l2_value", "") or ""
                if not key:
                    continue
                f_node = f"identity.{pid}.{key}"
                _add_node(f_node, key, "identity", "fact", depth=2,
                          weight=fact.get("weight", 0.5),
                          data={"value": value, "fact_type": fact.get("fact_type", "")})
                _add_structural(p_node, f_node)
    except Exception:
        pass

    # ── 2. Philosophy thread ─────────────────────────────────────────
    _add_node("philosophy", "Philosophy", "philosophy", "thread", depth=0, weight=10)
    try:
        from agent.threads.philosophy.schema import (
            get_philosophy_profiles, pull_philosophy_profile_facts,
        )
        for profile in get_philosophy_profiles():
            pid = profile.get("profile_id", "")
            p_node = f"philosophy.{pid}"
            _add_node(p_node, pid, "philosophy", "group", depth=1,
                      data={"type_name": profile.get("type_name", "")})
            _add_structural("philosophy", p_node)

            for fact in pull_philosophy_profile_facts(profile_id=pid, limit=200):
                key   = fact.get("key", "")
                value = fact.get("l1_value", "") or fact.get("l2_value", "") or ""
                if not key:
                    continue
                f_node = f"philosophy.{pid}.{key}"
                _add_node(f_node, key, "philosophy", "fact", depth=2,
                          weight=fact.get("weight", 0.5),
                          data={"value": value, "fact_type": fact.get("fact_type", "")})
                _add_structural(p_node, f_node)
    except Exception:
        pass

    # ── 3. Form thread (tools) ───────────────────────────────────────
    _add_node("form", "Form", "form", "thread", depth=0, weight=10)
    try:
        from agent.threads.form.schema import get_tools
        for tool in get_tools():
            name = tool.get("name", "")
            t_node = f"form.{name}"
            _add_node(t_node, name, "form", "tool", depth=1,
                      weight=tool.get("weight", 0.5),
                      data={"category": tool.get("category", ""),
                            "enabled": tool.get("enabled", True)})
            _add_structural("form", t_node)

            # Actions as children of the tool
            actions = tool.get("actions", [])
            if isinstance(actions, str):
                import json as _json
                try: actions = _json.loads(actions)
                except Exception: actions = []
            for action in (actions or []):
                a_name = action if isinstance(action, str) else action.get("name", "")
                if a_name:
                    a_node = f"form.{name}.{a_name}"
                    _add_node(a_node, a_name, "form", "fact", depth=2)
                    _add_structural(t_node, a_node)
    except Exception:
        pass

    # ── 4. Reflex thread (triggers) ──────────────────────────────────
    _add_node("reflex", "Reflex", "reflex", "thread", depth=0, weight=10)
    try:
        from agent.threads.reflex.schema import get_triggers
        for trig in get_triggers():
            t_id = trig.get("id", "")
            name  = trig.get("name", f"trigger_{t_id}")
            t_node = f"reflex.{name}"
            _add_node(t_node, name, "reflex", "trigger", depth=1,
                      data={"feed_name": trig.get("feed_name", ""),
                            "event_type": trig.get("event_type", ""),
                            "response_mode": trig.get("response_mode", "tool"),
                            "enabled": trig.get("enabled", True)})
            _add_structural("reflex", t_node)
    except Exception:
        pass

    # ── 5. Log thread (summary only — not every event) ───────────────
    _add_node("log", "Log", "log", "thread", depth=0, weight=10)
    try:
        from data.db import get_connection as _get_conn
        from contextlib import closing
        with closing(_get_conn(readonly=True)) as conn:
            cur = conn.cursor()
            # Show event type distribution
            cur.execute("""
                SELECT event_type, COUNT(*) as cnt
                FROM unified_events
                GROUP BY event_type
                ORDER BY cnt DESC
                LIMIT 20
            """)
            for row in cur.fetchall():
                etype = row[0] or "unknown"
                count = row[1]
                e_node = f"log.{etype}"
                _add_node(e_node, etype, "log", "group", depth=1,
                          weight=min(10, count / 10),
                          data={"count": count})
                _add_structural("log", e_node)
    except Exception:
        pass

    # ── 6. Linking Core (the graph itself — meta node) ───────────────
    _add_node("linking_core", "Linking Core", "linking_core", "thread", depth=0, weight=10)
    try:
        stats = get_stats()
        _add_node("linking_core.concepts", f"{stats.get('concept_count', 0)} concepts",
                  "linking_core", "group", depth=1,
                  data={"concept_count": stats.get("concept_count", 0)})
        _add_structural("linking_core", "linking_core.concepts")
        _add_node("linking_core.links", f"{stats.get('link_count', 0)} links",
                  "linking_core", "group", depth=1,
                  data={"link_count": stats.get("link_count", 0),
                        "avg_strength": stats.get("average_strength", 0)})
        _add_structural("linking_core", "linking_core.links")
    except Exception:
        pass

    # ── 7. Cross-thread associative links (from concept_links) ───────
    if include_cross_links:
        try:
            # Build a set of all node IDs for matching
            node_ids = set(nodes.keys())
            # Also build a reverse map: leaf label → full node IDs
            label_to_nodes: Dict[str, list] = {}
            for nid, ndata in nodes.items():
                label_lower = ndata["label"].lower()
                label_to_nodes.setdefault(label_lower, []).append(nid)
                # Also map the last segment of the node id
                last_seg = nid.rsplit(".", 1)[-1].lower()
                if last_seg != label_lower:
                    label_to_nodes.setdefault(last_seg, []).append(nid)

            with closing(get_connection(readonly=True)) as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT concept_a, concept_b, strength, fire_count
                    FROM concept_links
                    WHERE strength >= ?
                    ORDER BY strength DESC
                    LIMIT ?
                """, (min_cross_strength, max_cross_links * 4))

                for row in cur.fetchall():
                    ca, cb, strength, fire_count = row[0].lower(), row[1].lower(), row[2], row[3]

                    # Try to match each concept to a structural node
                    a_matches = label_to_nodes.get(ca, [])
                    b_matches = label_to_nodes.get(cb, [])

                    if not a_matches or not b_matches:
                        continue

                    # Find cross-thread links (skip same-node self-links)
                    for a_id in a_matches:
                        a_thread = nodes[a_id]["thread"]
                        for b_id in b_matches:
                            b_thread = nodes[b_id]["thread"]
                            if a_id != b_id:
                                cross_links.append({
                                    "source":     a_id,
                                    "target":     b_id,
                                    "type":       "associative",
                                    "strength":   strength,
                                    "fire_count": fire_count or 1,
                                    "cross_thread": a_thread != b_thread,
                                })
                    if len(cross_links) >= max_cross_links:
                        break
        except Exception:
            pass

    return {
        "nodes":      list(nodes.values()),
        "structural": structural_links,
        "associative": cross_links,
        "stats": {
            "node_count":       len(nodes),
            "structural_count": len(structural_links),
            "associative_count": len(cross_links),
            "threads":          ["identity", "philosophy", "form", "reflex", "log", "linking_core"],
        },
    }


# ─────────────────────────────────────────────────────────────
# Graph Visualization
# ─────────────────────────────────────────────────────────────

def _get_fact_anchor_prefixes(conn: sqlite3.Connection) -> set:
    """
    Load all fact keys from profile_facts, philosophy_profile_facts, and form_tools.
    Returns a set of keys used to anchor concept nodes to real stored knowledge.
    """
    anchors: set = set()
    cur = conn.cursor()
    for table, col in [
        ("profile_facts", "key"),
        ("philosophy_profile_facts", "key"),
        ("form_tools", "name"),
    ]:
        try:
            cur.execute(f"SELECT DISTINCT {col} FROM {table}")
            for row in cur.fetchall():
                if row[0]:
                    anchors.add(row[0].strip().lower())
        except sqlite3.OperationalError:
            pass  # Table doesn't exist yet
    return anchors


def _is_concept_anchored(concept: str, anchor_keys: set) -> bool:
    """
    Return True if the concept is anchored to a real stored fact.

    A concept 'a.b.c' is anchored when any stored key is:
      - an exact match ('a.b.c'), OR
      - a prefix of the concept ('a.b' → 'a.b.c' is a child), OR
      - the concept itself is a prefix of a stored key ('a.b' stored, concept 'a' is its parent)

    This accepts both parents and children of fact keys so the whole
    identity subtree stays connected.
    """
    c = concept.strip().lower()
    for key in anchor_keys:
        if c == key:
            return True
        # concept is a child: key is 'sarah.email', concept is 'sarah.email.work'
        if c.startswith(key + "."):
            return True
        # concept is a parent: key is 'sarah.email', concept is 'sarah'
        if key.startswith(c + "."):
            return True
    return False


def get_graph_data(center_concept: str = None, max_nodes: int = 100, min_strength: float = 0.1, anchored_only: bool = False) -> Dict[str, Any]: # pyright: ignore[reportArgumentType]
    """
    Get graph data for visualization (nodes and links).

    If center_concept is provided, returns subgraph around that concept.
    If anchored_only is True, only concepts that anchor to real stored facts
    (profile_facts, philosophy_profile_facts, form_tools) are included.
    """
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()

        # Pre-load anchor keys when filtering is requested
        anchor_keys = _get_fact_anchor_prefixes(conn) if anchored_only else set()

        if center_concept:
            # Get subgraph around center concept using spread activation
            activated = spread_activate([center_concept], activation_threshold=min_strength, max_hops=2, limit=max_nodes)
            concepts = [center_concept] + [a["concept"] for a in activated]
            
            # Get links between these concepts
            placeholders = ",".join("?" for _ in concepts)
            cur.execute(f"""
                SELECT concept_a, concept_b, strength, fire_count, last_fired
                FROM concept_links
                WHERE concept_a IN ({placeholders}) AND concept_b IN ({placeholders})
                  AND strength >= ?
                ORDER BY strength DESC
            """, concepts + concepts + [min_strength])
        else:
            # Get top links globally
            cur.execute("""
                SELECT concept_a, concept_b, strength, fire_count, last_fired
                FROM concept_links
                WHERE strength >= ?
                ORDER BY strength DESC
                LIMIT ?
            """, (min_strength, max_nodes * 4))
        
        # Build nodes and links
        nodes_set = set()
        links = []
        total_strength = 0.0
        max_strength_val = 0.0
        
        for row in cur.fetchall():
            ca, cb = row[0], row[1]
            # When anchored_only: skip links where neither endpoint is anchored
            if anchored_only and not (_is_concept_anchored(ca, anchor_keys) or _is_concept_anchored(cb, anchor_keys)):
                continue
            nodes_set.add(ca)
            nodes_set.add(cb)
            strength = row[2]
            total_strength += strength
            max_strength_val = max(max_strength_val, strength)
            links.append({
                "concept_a": ca,
                "concept_b": cb,
                "strength": strength,
                "fire_count": row[3] or 1,
                "last_fired": row[4]
            })
            if len(nodes_set) >= max_nodes:
                break

        # When anchored_only, further filter nodes — remove unanchored orphans
        if anchored_only:
            anchored_nodes = {n for n in nodes_set if _is_concept_anchored(n, anchor_keys)}
            # Keep links where BOTH endpoints survived
            links = [l for l in links if l["concept_a"] in anchored_nodes and l["concept_b"] in anchored_nodes]
            nodes_set = anchored_nodes

        # Rebuild total_strength from filtered links
        if anchored_only and links:
            total_strength = sum(l["strength"] for l in links)
            max_strength_val = max(l["strength"] for l in links)

        # Build node list with metadata
        nodes = []
        for concept in list(nodes_set)[:max_nodes]:
            cur.execute("""
                SELECT COUNT(*) FROM concept_links 
                WHERE concept_a = ? OR concept_b = ?
            """, (concept, concept))
            connection_count = cur.fetchone()[0]
            
            nodes.append({
                "id": concept,
                "label": concept.split(".")[-1],
                "connections": connection_count,
                "is_center": concept == center_concept if center_concept else False
            })
    
    # Build stats
    stats = {
        "total_links": len(links),
        "avg_strength": total_strength / len(links) if links else 0.0,
        "max_strength": max_strength_val,
        "unique_concepts": len(nodes)
    }
    
    return {
        "nodes": nodes,
        "links": links,
        "stats": stats,
        "center": center_concept,
        "node_count": len(nodes),
        "edge_count": len(links)
    }


def get_activation_path(source: str, target: str, max_hops: int = 3) -> Optional[Dict[str, Any]]:
    """Find activation path between two concepts."""
    activated = spread_activate([source], activation_threshold=0.05, max_hops=max_hops, limit=200)
    
    for item in activated:
        if item["concept"] == target:
            return {
                "found": True,
                "path": item["path"],
                "activation": item["activation"],
                "hops": len(item["path"]) - 1
            }
    
    return {"found": False, "path": [], "activation": 0, "hops": -1}


def get_stats() -> Dict[str, Any]:
    """Get linking core statistics."""
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        
        # Count concepts
        cur.execute("""
            SELECT COUNT(DISTINCT concept) FROM (
                SELECT concept_a as concept FROM concept_links
                UNION
                SELECT concept_b as concept FROM concept_links
            )
        """)
        concept_count = cur.fetchone()[0] or 0
        
        # Count links
        cur.execute("SELECT COUNT(*) FROM concept_links")
        link_count = cur.fetchone()[0] or 0
        
        # Average strength
        cur.execute("SELECT AVG(strength) FROM concept_links")
        avg_strength = cur.fetchone()[0] or 0
    
    return {
        "concept_count": concept_count,
        "link_count": link_count,
        "average_strength": round(avg_strength, 3) if avg_strength else 0,
    }


# ============================================================================
# Concept Extraction & Linking (from conversation)
# ============================================================================

def extract_and_link_concepts(text: str, learning_rate: float = 0.1) -> Dict[str, Any]:
    """
    Extract concepts from text and create/strengthen links between them.
    
    This is the main entry point for the linking_core to process new text.
    
    Returns:
        {"concepts": [...], "links_created": int, "links_strengthened": int}
    """
    concepts = extract_concepts_from_text(text)
    
    if len(concepts) < 2:
        return {"concepts": concepts, "links_created": 0, "links_strengthened": 0}
    
    links_created = 0
    links_strengthened = 0
    
    # Link all concept pairs
    for i, c1 in enumerate(concepts):
        for c2 in concepts[i+1:]:
            # Check if link exists
            conn = get_connection(readonly=True)
            cur = conn.cursor()
            cur.execute("""
                SELECT strength FROM concept_links 
                WHERE (concept_a = ? AND concept_b = ?) OR (concept_a = ? AND concept_b = ?)
            """, (c1, c2, c2, c1))
            existing = cur.fetchone()
            conn.close()
            
            if existing:
                links_strengthened += 1
            else:
                links_created += 1
            
            # Create or strengthen link
            link_concepts(c1, c2, learning_rate)
    
    return {
        "concepts": concepts,
        "links_created": links_created,
        "links_strengthened": links_strengthened
    }


def process_conversation_turn(user_input: str, agent_response: str, learning_rate: float = 0.1) -> Dict[str, Any]:
    """
    Process a conversation turn for concept linking.
    
    Extracts concepts from both user input and agent response,
    creates links between co-occurring concepts.
    """
    # Combine both sides of conversation
    combined = f"{user_input} {agent_response}"
    
    result = extract_and_link_concepts(combined, learning_rate)
    
    # Also index significant phrases
    from agent.threads.log import log_event
    try:
        log_event(
            event_type="linking",
            data=f"Processed {len(result['concepts'])} concepts",
            source="linking_core",
            metadata={"concepts": result["concepts"][:10]}  # Limit for logging
        )
    except Exception:
        pass
    
    return result
