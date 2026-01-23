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
            PRIMARY KEY (concept_a, concept_b)
        )
    """)
    
    # Indexes for fast spread activation queries
    cur.execute("CREATE INDEX IF NOT EXISTS idx_concept_a ON concept_links(concept_a)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_concept_b ON concept_links(concept_b)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_concept_strength ON concept_links(strength DESC)")
    
    if own_conn:
        conn.commit()


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


# ─────────────────────────────────────────────────────────────
# Concept Linking (Hebbian Learning)
# ─────────────────────────────────────────────────────────────

def link_concepts(concept_a: str, concept_b: str, learning_rate: float = 0.1) -> float:
    """
    Strengthen the link between two concepts (Hebbian learning).
    
    strength += (1 - strength) * learning_rate
    
    Returns the new strength.
    """
    conn = get_connection()
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
    conn.close()
    return new_strength


def decay_concept_links(decay_rate: float = 0.95, min_strength: float = 0.05) -> int:
    """
    Apply decay to all concept links.
    
    Run periodically (e.g., daily) to let old associations fade.
    Links below min_strength are pruned.
    
    Returns number of links pruned.
    """
    conn = get_connection()
    cur = conn.cursor()
    
    # Decay all links
    cur.execute("UPDATE concept_links SET strength = strength * ?", (decay_rate,))
    
    # Prune weak links
    cur.execute("DELETE FROM concept_links WHERE strength < ?", (min_strength,))
    pruned = cur.rowcount
    
    conn.commit()
    conn.close()
    return pruned


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
    conn = get_connection(readonly=True)
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
    
    conn.close()
    
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
    
    conn = get_connection(readonly=True)
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
    
    conn.close()
    return min(total_boost, 0.3)


def record_cooccurrence(key_a: str, key_b: str) -> None:
    """Record that two keys appeared together in a conversation."""
    conn = get_connection()
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
    conn.close()


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
    
    conn = get_connection(readonly=True)
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
    
    conn.close()
    
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
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT DISTINCT concept FROM (
            SELECT concept_a as concept FROM concept_links
            UNION
            SELECT concept_b as concept FROM concept_links
        ) ORDER BY concept LIMIT ?
    """, (limit,))
    
    concepts = [{"concept": row[0]} for row in cur.fetchall()]
    conn.close()
    return concepts


def get_all_links(limit: int = 500) -> List[Dict[str, Any]]:
    """Get all concept links for graph visualization."""
    conn = get_connection(readonly=True)
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
    
    conn.close()
    return links


def get_links_for_concept(concept: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get all links connected to a specific concept."""
    conn = get_connection(readonly=True)
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
    
    conn.close()
    return links


def create_link(
    concept_a: str,
    concept_b: str,
    strength: float = 0.5,
    link_type: str = "related"
) -> bool:
    """Create a new concept link with explicit strength."""
    conn = get_connection()
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
    finally:
        conn.close()


def delete_link(concept_a: str, concept_b: str) -> bool:
    """Delete a concept link."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        DELETE FROM concept_links 
        WHERE (concept_a = ? AND concept_b = ?)
           OR (concept_a = ? AND concept_b = ?)
    """, (concept_a, concept_b, concept_b, concept_a))
    
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def update_link_strength(concept_a: str, concept_b: str, strength: float) -> bool:
    """Update the strength of a concept link."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE concept_links 
        SET strength = ?
        WHERE (concept_a = ? AND concept_b = ?)
           OR (concept_a = ? AND concept_b = ?)
    """, (strength, concept_a, concept_b, concept_b, concept_a))
    
    updated = cur.rowcount > 0
    conn.commit()
    conn.close()
    return updated


# ─────────────────────────────────────────────────────────────
# Graph Visualization
# ─────────────────────────────────────────────────────────────

def get_graph_data(center_concept: str = None, max_nodes: int = 100, min_strength: float = 0.1) -> Dict[str, Any]:
    """
    Get graph data for visualization (nodes and links).
    
    If center_concept is provided, returns subgraph around that concept.
    """
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
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
        """, (min_strength, max_nodes * 2))
    
    # Build nodes and links
    nodes_set = set()
    links = []
    total_strength = 0.0
    max_strength_val = 0.0
    
    for row in cur.fetchall():
        nodes_set.add(row[0])
        nodes_set.add(row[1])
        strength = row[2]
        total_strength += strength
        max_strength_val = max(max_strength_val, strength)
        links.append({
            "concept_a": row[0],
            "concept_b": row[1],
            "strength": strength,
            "fire_count": row[3] or 1,
            "last_fired": row[4]
        })
    
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
    
    conn.close()
    
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
    conn = get_connection(readonly=True)
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
    
    conn.close()
    
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
