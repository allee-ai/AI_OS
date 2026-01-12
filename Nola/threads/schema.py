"""
Thread Schema - Database tables for the 5 data threads

Architecture:
- threads_registry: Lists all threads and their modules
- Each module gets its own table: {thread}_{module}
- Each row has: key, metadata_json, data_json, level, weight

LinkingCore reads from all module tables, scores relevance,
and returns top-k keys per module within token budget.
"""

import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

# Database path - use absolute path to avoid cache/import issues
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent.parent.parent  # AI_OS/
DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "db" / "state.db"
DB_PATH = Path(os.getenv("STATE_DB_PATH", str(DEFAULT_DB_PATH)))

# Debug: print on first import
if not DEFAULT_DB_PATH.exists():
    print(f"⚠️ WARNING: Database not found at {DEFAULT_DB_PATH}")
    print(f"   __file__ resolved to: {_THIS_FILE}")


def get_connection(readonly: bool = False) -> sqlite3.Connection:
    """Get a SQLite connection."""
    if not readonly:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    else:
        uri = f"file:{DB_PATH}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ============================================================================
# SCHEMA: Unified Event Log
# ============================================================================

def init_event_log_table(conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Create unified event log table.
    
    Single table for all events:
    - data = user-facing (what happened, the timeline)
    - metadata = program-facing (why/how, internal state)
    
    event_type: "convo" | "system" | "user_action" | "file" | "memory" | "activation"
    """
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS unified_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT NOT NULL,
            source TEXT DEFAULT 'system',
            data TEXT,
            metadata_json TEXT,
            session_id TEXT,
            
            -- Optional linking
            related_key TEXT,
            related_table TEXT
        )
    """)
    
    # Indexes for fast queries
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON unified_events(event_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_time ON unified_events(timestamp DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON unified_events(session_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_source ON unified_events(source)")
    
    if own_conn:
        conn.commit()


def log_event(
    event_type: str,
    data: str,
    metadata: Dict[str, Any] = None,
    source: str = "system",
    session_id: str = None,
    related_key: str = None,
    related_table: str = None
) -> int:
    """
    Log an event to the unified timeline.
    
    Args:
        event_type: "convo" | "system" | "user_action" | "file" | "memory" | "activation"
        data: User-facing description (what happened)
        metadata: Program-facing context (why/how, internal state)
        source: Where this came from ("local", "web_public", "daemon", "agent")
        session_id: Groups related events
        related_key: Optional link to a fact/identity key
        related_table: Optional link to source table
    
    Returns:
        Event ID
    
    Examples:
        log_event("convo", "Conversation started with Jordan", 
                  {"context_level": 2}, source="local", session_id="abc123")
        
        log_event("memory", "Learned: Sarah likes coffee",
                  {"hier_key": "sarah.likes.coffee", "score": 0.72}, 
                  related_key="sarah.likes.coffee")
        
        log_event("activation", "Spread activation fired",
                  {"query": "coffee", "activated": ["sarah"], "links": 2})
        
        log_event("user_action", "Edited agent_name",
                  {"old": "Nola", "new": "Nova", "table": "identity"})
    """
    conn = get_connection()
    cur = conn.cursor()
    init_event_log_table(conn)
    
    metadata_json = json.dumps(metadata) if metadata else None
    
    cur.execute("""
        INSERT INTO unified_events 
        (event_type, data, metadata_json, source, session_id, related_key, related_table)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (event_type, data, metadata_json, source, session_id, related_key, related_table))
    
    event_id = cur.lastrowid
    conn.commit()
    return event_id


def get_events(
    event_type: str = None,
    source: str = None,
    session_id: str = None,
    since: str = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Query events from the unified log.
    
    Args:
        event_type: Filter by type
        source: Filter by source
        session_id: Filter by session
        since: ISO timestamp, get events after this time
        limit: Max events to return
    
    Returns:
        List of event dicts with parsed metadata
    """
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    query = "SELECT * FROM unified_events WHERE 1=1"
    params = []
    
    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)
    if source:
        query += " AND source = ?"
        params.append(source)
    if session_id:
        query += " AND session_id = ?"
        params.append(session_id)
    if since:
        query += " AND timestamp > ?"
        params.append(since)
    
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
    cur.execute(query, params)
    
    results = []
    for row in cur.fetchall():
        event = dict(row)
        if event.get("metadata_json"):
            try:
                event["metadata"] = json.loads(event["metadata_json"])
            except:
                event["metadata"] = {}
        else:
            event["metadata"] = {}
        del event["metadata_json"]
        results.append(event)
    
    return results


def get_user_timeline(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get user-facing timeline (data column only, formatted for display).
    
    Returns events a user would care about:
    - Conversations
    - Things Nola learned
    - User actions
    """
    events = get_events(limit=limit)
    
    timeline = []
    for e in events:
        if e["event_type"] in ("convo", "memory", "user_action", "file"):
            timeline.append({
                "time": e["timestamp"],
                "type": e["event_type"],
                "what": e["data"],
                "source": e["source"]
            })
    
    return timeline


def get_system_log(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get program-facing log (metadata included, for debugging).
    
    Returns all events with full metadata for debugging.
    """
    return get_events(limit=limit)


# ============================================================================
# SCHEMA: Co-occurrence Learning (Hebbian)
# ============================================================================

def init_cooccurrence_table(conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Create the co-occurrence table for Hebbian learning.
    
    Tracks which keys appear together in conversations.
    'Neurons that fire together, wire together.'
    """
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
    
    # Index for fast lookups
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cooccur_a ON key_cooccurrence(key_a)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_cooccur_b ON key_cooccurrence(key_b)
    """)
    
    if own_conn:
        conn.commit()


def record_cooccurrence(keys: List[str]) -> int:
    """
    Record that these keys appeared together in a conversation turn.
    
    For each pair (A, B) where A < B (alphabetically), increment count.
    Returns number of pairs recorded.
    """
    if len(keys) < 2:
        return 0
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Ensure table exists
    init_cooccurrence_table(conn)
    
    # Generate unique pairs (A < B to avoid duplicates)
    pairs_recorded = 0
    unique_keys = list(set(keys))  # Dedupe
    
    for i, key_a in enumerate(unique_keys):
        for key_b in unique_keys[i+1:]:
            # Ensure consistent ordering
            if key_a > key_b:
                key_a, key_b = key_b, key_a
            
            cur.execute("""
                INSERT INTO key_cooccurrence (key_a, key_b, count, last_seen)
                VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(key_a, key_b) DO UPDATE SET
                    count = count + 1,
                    last_seen = CURRENT_TIMESTAMP
            """, (key_a, key_b))
            pairs_recorded += 1
    
    conn.commit()
    return pairs_recorded


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
            # More co-occurrences = higher boost, log scale
            # 1 co-occurrence = ~0.02, 10 = ~0.07, 50 = ~0.12
            import math
            count = row[0]
            boost = min(math.log(count + 1) * 0.03, 0.15)
            total_boost += boost
    
    # Cap total boost at 0.3
    return min(total_boost, 0.3)


# ============================================================================
# SCHEMA: Concept Links (Spread Activation Network)
# ============================================================================

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
    
    log_data = None  # Defer logging until after commit
    
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
        
        log_data = ("system", f"Link strengthened: {concept_a} ↔ {concept_b}",
                    {"concept_a": concept_a, "concept_b": concept_b, 
                     "old_strength": round(old_strength, 3), "new_strength": round(new_strength, 3),
                     "fire_count": fire_count + 1})
    else:
        # New link starts at learning_rate
        new_strength = learning_rate
        cur.execute("""
            INSERT INTO concept_links (concept_a, concept_b, strength, fire_count)
            VALUES (?, ?, ?, 1)
        """, (concept_a, concept_b, new_strength))
        
        log_data = ("system", f"New link created: {concept_a} ↔ {concept_b}",
                    {"concept_a": concept_a, "concept_b": concept_b, "strength": new_strength})
    
    conn.commit()
    
    # Log after commit to avoid db lock
    if log_data:
        log_event(log_data[0], log_data[1], log_data[2])
    
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
    cur.execute("""
        UPDATE concept_links SET strength = strength * ?
    """, (decay_rate,))
    
    # Prune weak links
    cur.execute("""
        DELETE FROM concept_links WHERE strength < ?
    """, (min_strength,))
    pruned = cur.rowcount
    
    conn.commit()
    return pruned


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
                    spread_activation = current_activation * link_strength
                    if spread_activation >= activation_threshold:
                        next_frontier.append((linked_concept, spread_activation, path + [linked_concept]))
        
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
    final_results = results[:limit]
    
    # Log spread activation if any concepts were activated
    if final_results:
        log_event(
            "activation",
            f"Spread activation: {input_concepts} → {len(final_results)} concepts",
            {
                "input": input_concepts,
                "activated": [r["concept"] for r in final_results[:5]],
                "top_activation": round(final_results[0]["activation"], 3) if final_results else 0,
                "total_activated": len(final_results)
            }
        )
    
    return final_results


def get_keys_for_concepts(concepts: List[str], limit: int = 30) -> List[Dict[str, Any]]:
    """
    Given activated concepts, retrieve matching fact keys from fact_relevance.
    
    Matches on:
    - Exact key match
    - Prefix match (sarah → sarah.likes.blue)
    - Text search in fact_text
    
    Returns fact_relevance rows sorted by (activation * final_score).
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
    
    # Sort by combined score
    results.sort(key=lambda x: x["combined_score"], reverse=True)
    return results[:limit]


def record_concept_cooccurrence(concepts: List[str], learning_rate: float = 0.1) -> int:
    """
    Record that these concepts appeared together in a conversation.
    
    Creates/strengthens links between all pairs.
    Returns number of links created/updated.
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


# ============================================================================
# SCHEMA: Hierarchical Key Generation
# ============================================================================

def generate_hierarchical_key(fact_text: str) -> str:
    """
    Convert a fact into a hierarchical dot-notation key.
    
    Examples:
        "User's friend Sarah likes blue" → "sarah.likes.blue"
        "Sarah lives in NYC" → "sarah.location.nyc"
        "User prefers Python" → "user.prefers.python"
        "Sarah mentioned coffee yesterday" → "sarah.mentioned.coffee"
    
    This enables spread activation:
        - Query "sarah" activates sarah.*, sarah.likes.*, etc.
        - Query "coffee" activates all keys containing coffee
    """
    import re
    
    # Lowercase and clean
    text = fact_text.lower().strip()
    
    # Remove common prefixes
    text = re.sub(r"^(the |a |user'?s? |nola'?s? )", "", text)
    
    # Extract subject (first noun/name)
    # Look for capitalized words first (names)
    orig = fact_text.strip()
    names = re.findall(r'\b([A-Z][a-z]+)\b', orig)
    
    # Common relation words
    relation_words = {
        'likes': 'likes', 'loves': 'loves', 'prefers': 'prefers',
        'hates': 'hates', 'dislikes': 'dislikes',
        'lives': 'location', 'works': 'work', 'studies': 'studies',
        'is from': 'origin', 'born': 'birth',
        'mentioned': 'mentioned', 'said': 'said', 'told': 'told',
        'wants': 'wants', 'needs': 'needs',
        'has': 'has', 'owns': 'owns',
        'favorite': 'favorite', 'enjoys': 'enjoys'
    }
    
    # Find subject
    subject = None
    if names:
        # Use first name found (not "User")
        for name in names:
            if name.lower() not in ('user', 'nola', 'the', 'a', 'i'):
                subject = name.lower()
                break
    
    if not subject:
        # Default to 'user' if about the user
        if 'user' in text or text.startswith('i '):
            subject = 'user'
        else:
            # Use first word
            words = text.split()
            subject = words[0] if words else 'unknown'
    
    # Find relation
    relation = None
    for word, rel in relation_words.items():
        if word in text:
            relation = rel
            break
    
    if not relation:
        # Default relation based on verb
        verbs = re.findall(r'\b(is|are|was|were|has|have|had)\b', text)
        relation = 'is' if verbs else 'related'
    
    # Find object (what comes after the relation)
    object_part = None
    
    # Try to extract the key object/noun
    # Look for words after relation word
    for word in relation_words.keys():
        if word in text:
            idx = text.find(word)
            after = text[idx + len(word):].strip()
            # Get first meaningful word(s)
            after_words = re.findall(r'\b([a-z]{2,})\b', after)
            # Filter out stop words
            stop = {'the', 'a', 'an', 'to', 'in', 'on', 'at', 'for', 'and', 'or', 'is', 'are'}
            after_words = [w for w in after_words if w not in stop]
            if after_words:
                object_part = after_words[0]
                break
    
    if not object_part:
        # Try to find nouns at end
        words = text.split()
        if len(words) > 2:
            object_part = words[-1].rstrip('.,!?')
        else:
            object_part = 'general'
    
    # Clean parts
    subject = re.sub(r'[^a-z0-9]', '', subject)
    relation = re.sub(r'[^a-z0-9]', '', relation)
    object_part = re.sub(r'[^a-z0-9]', '', object_part)
    
    # Build key
    key = f"{subject}.{relation}.{object_part}"
    
    return key


def extract_concepts_from_text(text: str) -> List[str]:
    """
    Extract concept keys from free text for spread activation queries.
    
    This is used to find what to activate when user sends a message.
    
    Example:
        "Hey, did Sarah mention anything about coffee?"
        → ['sarah', 'coffee', 'mentioned']
    """
    import re
    
    # Lowercase
    text_lower = text.lower()
    
    # Find capitalized words (names)
    names = re.findall(r'\b([A-Z][a-z]+)\b', text)
    concepts = [n.lower() for n in names if n.lower() not in ('i', 'the', 'a', 'hey', 'hi', 'what', 'how', 'when', 'where', 'why')]
    
    # Find important nouns (simple heuristic)
    # Words > 3 chars that aren't stop words
    stop_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these',
        'those', 'what', 'which', 'who', 'whom', 'where', 'when', 'why', 'how',
        'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some',
        'such', 'only', 'same', 'than', 'too', 'very', 'just', 'also', 'now',
        'here', 'there', 'then', 'once', 'about', 'after', 'before', 'above',
        'below', 'between', 'into', 'through', 'during', 'under', 'again',
        'further', 'then', 'once', 'hey', 'hello', 'you', 'your', 'anything',
        'something', 'nothing', 'everything', 'anyone', 'someone', 'know',
        'think', 'want', 'need', 'like', 'tell', 'said', 'says', 'any', 'with'
    }
    
    words = re.findall(r'\b([a-z]{3,})\b', text_lower)
    for word in words:
        if word not in stop_words and word not in concepts:
            concepts.append(word)
    
    return concepts


# ============================================================================
# SCHEMA: Fact Relevance Matrix (Multi-dimensional, Auditable)
# ============================================================================

def init_fact_relevance_table(conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Create the fact_relevance table for multi-dimensional scoring.
    
    Each thread writes its own column. Final score is weighted sum.
    This is AUDITABLE - every score is stored and queryable.
    """
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fact_relevance (
            fact_key TEXT PRIMARY KEY,
            fact_text TEXT,
            
            -- Each thread writes its dimension (0.0 - 1.0)
            identity_score REAL DEFAULT 0.5,    -- PFC: goal/value match
            log_score REAL DEFAULT 0.5,         -- Hippocampus: recency
            form_score REAL DEFAULT 0.5,        -- Temporal: semantic sim
            philosophy_score REAL DEFAULT 0.5,  -- Amygdala: emotional salience
            reflex_score REAL DEFAULT 0.5,      -- Basal Ganglia: frequency
            
            -- LinkingCore aggregates
            cooccurrence_score REAL DEFAULT 0.0,
            final_score REAL DEFAULT 0.5,
            
            -- Audit trail
            access_count INTEGER DEFAULT 0,
            last_accessed TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source_thread TEXT,
            session_id TEXT
        )
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_fact_final ON fact_relevance(final_score DESC)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_fact_updated ON fact_relevance(updated_at DESC)
    """)
    
    if own_conn:
        conn.commit()


def upsert_fact_relevance(
    fact_key: str,
    fact_text: str = None,
    scores: Dict[str, float] = None,
    source_thread: str = None,
    session_id: str = None
) -> None:
    """
    Insert or update a fact's relevance scores.
    
    Args:
        fact_key: Unique identifier (first 50 chars of fact)
        fact_text: Full fact text
        scores: Dict of {dimension: score} e.g. {'identity_score': 0.8}
        source_thread: Which thread created this fact
        session_id: Which session it came from
    """
    conn = get_connection()
    cur = conn.cursor()
    
    init_fact_relevance_table(conn)
    
    # Check if exists
    cur.execute("SELECT fact_key FROM fact_relevance WHERE fact_key = ?", (fact_key,))
    exists = cur.fetchone() is not None
    
    if exists:
        # Update only provided scores
        if scores:
            set_clauses = []
            values = []
            for dim, score in scores.items():
                if dim in ('identity_score', 'log_score', 'form_score', 
                          'philosophy_score', 'reflex_score', 'cooccurrence_score', 'final_score'):
                    set_clauses.append(f"{dim} = ?")
                    values.append(score)
            
            if set_clauses:
                set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                values.append(fact_key)
                cur.execute(f"""
                    UPDATE fact_relevance 
                    SET {', '.join(set_clauses)}
                    WHERE fact_key = ?
                """, values)
    else:
        # Insert new
        cur.execute("""
            INSERT INTO fact_relevance 
            (fact_key, fact_text, source_thread, session_id,
             identity_score, log_score, form_score, philosophy_score, reflex_score,
             cooccurrence_score, final_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fact_key,
            fact_text or fact_key,
            source_thread,
            session_id,
            scores.get('identity_score', 0.5) if scores else 0.5,
            scores.get('log_score', 0.5) if scores else 0.5,
            scores.get('form_score', 0.5) if scores else 0.5,
            scores.get('philosophy_score', 0.5) if scores else 0.5,
            scores.get('reflex_score', 0.5) if scores else 0.5,
            scores.get('cooccurrence_score', 0.0) if scores else 0.0,
            scores.get('final_score', 0.5) if scores else 0.5,
        ))
    
    conn.commit()


def get_fact_relevance(fact_key: str) -> Optional[Dict[str, Any]]:
    """
    Get full relevance breakdown for a fact.
    
    Returns dict with all scores - FULLY AUDITABLE.
    """
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM fact_relevance WHERE fact_key = ?
    """, (fact_key,))
    
    row = cur.fetchone()
    if row:
        return dict(row)
    return None


def increment_fact_access(fact_key: str) -> None:
    """Record that a fact was accessed (for frequency tracking)."""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        UPDATE fact_relevance 
        SET access_count = access_count + 1,
            last_accessed = CURRENT_TIMESTAMP
        WHERE fact_key = ?
    """, (fact_key,))
    
    conn.commit()


def compute_final_score(
    identity: float = 0.5,
    log: float = 0.5,
    form: float = 0.5,
    philosophy: float = 0.5,
    reflex: float = 0.5,
    cooccurrence: float = 0.0,
    weights: Dict[str, float] = None
) -> float:
    """
    Compute weighted final score from all dimensions.
    
    Default weights (can be learned/tuned):
        identity: 0.25 (goal match matters most)
        log: 0.15 (recency)
        form: 0.20 (semantic similarity)
        philosophy: 0.15 (emotional salience)
        reflex: 0.10 (frequency)
        cooccurrence: 0.15 (Hebbian)
    """
    if weights is None:
        weights = {
            'identity': 0.25,
            'log': 0.15,
            'form': 0.20,
            'philosophy': 0.15,
            'reflex': 0.10,
            'cooccurrence': 0.15,
        }
    
    return (
        weights['identity'] * identity +
        weights['log'] * log +
        weights['form'] * form +
        weights['philosophy'] * philosophy +
        weights['reflex'] * reflex +
        weights['cooccurrence'] * cooccurrence
    )


def get_top_facts_by_relevance(limit: int = 50, min_score: float = 0.0) -> List[Dict]:
    """Get facts sorted by final_score for retrieval."""
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM fact_relevance 
        WHERE final_score >= ?
        ORDER BY final_score DESC
        LIMIT ?
    """, (min_score, limit))
    
    return [dict(row) for row in cur.fetchall()]


def explain_relevance(fact_key: str) -> str:
    """
    Human-readable explanation of why a fact has its score.
    
    This is the AUDIT function - shows exactly why something was retrieved.
    """
    fact = get_fact_relevance(fact_key)
    if not fact:
        return f"No relevance data for: {fact_key}"
    
    lines = [
        f"=== Relevance Audit: {fact_key[:50]}... ===",
        f"",
        f"Final Score: {fact.get('final_score', 0):.3f}",
        f"",
        f"Dimension Breakdown:",
        f"  Identity (goal match):     {fact.get('identity_score', 0):.3f} × 0.25 = {fact.get('identity_score', 0) * 0.25:.3f}",
        f"  Log (recency):             {fact.get('log_score', 0):.3f} × 0.15 = {fact.get('log_score', 0) * 0.15:.3f}",
        f"  Form (semantic):           {fact.get('form_score', 0):.3f} × 0.20 = {fact.get('form_score', 0) * 0.20:.3f}",
        f"  Philosophy (salience):     {fact.get('philosophy_score', 0):.3f} × 0.15 = {fact.get('philosophy_score', 0) * 0.15:.3f}",
        f"  Reflex (frequency):        {fact.get('reflex_score', 0):.3f} × 0.10 = {fact.get('reflex_score', 0) * 0.10:.3f}",
        f"  Co-occurrence (Hebbian):   {fact.get('cooccurrence_score', 0):.3f} × 0.15 = {fact.get('cooccurrence_score', 0) * 0.15:.3f}",
        f"",
        f"Metadata:",
        f"  Access count: {fact.get('access_count', 0)}",
        f"  Last accessed: {fact.get('last_accessed', 'never')}",
        f"  Created: {fact.get('created_at', 'unknown')}",
        f"  Source thread: {fact.get('source_thread', 'unknown')}",
    ]
    
    return "\n".join(lines)


# ============================================================================
# SCHEMA: Thread Registry
# ============================================================================

def init_threads_registry(conn: Optional[sqlite3.Connection] = None) -> None:
    """Create the threads registry table."""
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS threads_registry (
            thread_name TEXT NOT NULL,
            module_name TEXT NOT NULL,
            table_name TEXT NOT NULL,
            description TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (thread_name, module_name)
        )
    """)
    
    if own_conn:
        conn.commit()


def register_module(
    thread_name: str,
    module_name: str,
    description: str = "",
    conn: Optional[sqlite3.Connection] = None
) -> str:
    """
    Register a module in the threads registry and create its table.
    
    Returns the table name.
    """
    table_name = f"{thread_name}_{module_name}"
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    # Ensure registry exists
    init_threads_registry(conn)
    
    # Insert or update registry
    cur.execute("""
        INSERT INTO threads_registry (thread_name, module_name, table_name, description)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(thread_name, module_name) DO UPDATE SET
            description = excluded.description,
            active = 1
    """, (thread_name, module_name, table_name, description))
    
    # Create the module table
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            key TEXT PRIMARY KEY,
            metadata_json TEXT NOT NULL,
            data_json TEXT NOT NULL,
            level INTEGER DEFAULT 2,
            weight REAL DEFAULT 0.5,
            access_count INTEGER DEFAULT 0,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    if own_conn:
        conn.commit()
    
    return table_name


def get_registered_modules(thread_name: Optional[str] = None) -> List[Dict]:
    """Get all registered modules, optionally filtered by thread."""
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    if thread_name:
        cur.execute("""
            SELECT thread_name, module_name, table_name, description, active
            FROM threads_registry
            WHERE thread_name = ? AND active = 1
            ORDER BY module_name
        """, (thread_name,))
    else:
        cur.execute("""
            SELECT thread_name, module_name, table_name, description, active
            FROM threads_registry
            WHERE active = 1
            ORDER BY thread_name, module_name
        """)
    
    return [dict(row) for row in cur.fetchall()]


# ============================================================================
# SCHEMA: Module Data Operations
# ============================================================================

def push_to_module(
    thread_name: str,
    module_name: str,
    key: str,
    metadata: Dict[str, Any],
    data: Dict[str, Any],
    level: int = 2,
    weight: float = 0.5
) -> None:
    """
    Push a row to a module table.
    
    Args:
        thread_name: The thread (identity, log, form, philosophy, reflex)
        module_name: The module within the thread
        key: Unique key for this row
        metadata: What this row provides (description, type, etc.)
        data: The actual content (value, facts, etc.)
        level: Context level (1=minimal, 2=standard, 3=full)
        weight: Importance weight 0.0-1.0
    """
    table_name = f"{thread_name}_{module_name}"
    conn = get_connection()
    cur = conn.cursor()
    
    # Ensure table exists
    register_module(thread_name, module_name, conn=conn)
    
    cur.execute(f"""
        INSERT INTO {table_name} (key, metadata_json, data_json, level, weight, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            metadata_json = excluded.metadata_json,
            data_json = excluded.data_json,
            level = excluded.level,
            weight = excluded.weight,
            access_count = access_count + 1,
            last_accessed = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
    """, (key, json.dumps(metadata), json.dumps(data), level, weight))
    
    conn.commit()


def pull_from_module(
    thread_name: str,
    module_name: str,
    level: int = 2,
    limit: int = 50
) -> List[Dict]:
    """
    Pull rows from a module table at or below the given level.
    
    Returns list of {key, metadata, data, level, weight}
    """
    table_name = f"{thread_name}_{module_name}"
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    try:
        cur.execute(f"""
            SELECT key, metadata_json, data_json, level, weight, last_accessed
            FROM {table_name}
            WHERE level <= ?
            ORDER BY weight DESC, last_accessed DESC
            LIMIT ?
        """, (level, limit))
        
        rows = cur.fetchall()
        return [{
            "key": r["key"],
            "metadata": json.loads(r["metadata_json"]),
            "data": json.loads(r["data_json"]),
            "level": r["level"],
            "weight": r["weight"]
        } for r in rows]
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return []


def delete_from_module(
    thread_name: str,
    module_name: str,
    key: str
) -> bool:
    """
    Delete a row from a module table.
    
    Args:
        thread_name: The thread (identity, log, form, philosophy, reflex)
        module_name: The module within the thread
        key: Key of the row to delete
        
    Returns:
        True if a row was deleted, False otherwise
    """
    table_name = f"{thread_name}_{module_name}"
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute(f"DELETE FROM {table_name} WHERE key = ?", (key,))
        conn.commit()
        return cur.rowcount > 0
    except sqlite3.OperationalError:
        return False


def pull_log_events(
    module_name: str = "events",
    limit: int = 50,
    min_weight: float = 0.0
) -> List[Dict]:
    """
    Pull log events by recency and weight (no level filtering).
    
    Log events are temporal markers - they don't need HEA levels.
    Query by timestamp DESC and weight to show recent + important events.
    
    Returns list of {key, metadata, data, weight, timestamp}
    """
    table_name = f"log_{module_name}"
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    try:
        cur.execute(f"""
            SELECT key, metadata_json, data_json, weight, created_at, updated_at
            FROM {table_name}
            WHERE weight >= ?
            ORDER BY created_at DESC, weight DESC
            LIMIT ?
        """, (min_weight, limit))
        
        rows = cur.fetchall()
        return [{
            "key": r["key"],
            "metadata": json.loads(r["metadata_json"]),
            "data": json.loads(r["data_json"]),
            "weight": r["weight"],
            "timestamp": r["created_at"]
        } for r in rows]
    except sqlite3.OperationalError:
        return []


def pull_all_thread_data(thread_name: str, level: int = 2) -> Dict[str, List[Dict]]:
    """
    Pull all data from all modules of a thread.
    
    Returns {module_name: [rows...]}
    """
    modules = get_registered_modules(thread_name)
    result = {}
    
    for mod in modules:
        rows = pull_from_module(thread_name, mod["module_name"], level)
        if rows:
            result[mod["module_name"]] = rows
    
    return result


# ============================================================================
# BOOTSTRAP: Initialize default threads and modules
# ============================================================================

DEFAULT_THREADS = {
    "identity": {
        "user_profile": "User identity facts (name, preferences, projects)",
        "machine_context": "Machine/environment context",
        "nola_self": "Nola's self-model and personality",
    },
    "log": {
        "events": "System events (start, stop, errors)",
        "sessions": "Conversation session metadata",
        "temporal": "Time-based patterns and facts",
    },
    "form": {
        "tool_registry": "Available tools and capabilities",
        "action_history": "Record of actions taken",
        "browser": "Browser/Kernel state",
    },
    "philosophy": {
        "core_values": "Fundamental values and principles",
        "ethical_bounds": "Hard constraints on behavior",
        "reasoning_style": "How to approach problems",
    },
    "reflex": {
        "greetings": "Quick greeting patterns",
        "shortcuts": "User-defined shortcuts",
        "system": "System reflexes (resource management)",
    },
}


def bootstrap_threads() -> None:
    """Initialize all default threads and modules."""
    conn = get_connection()
    
    for thread_name, modules in DEFAULT_THREADS.items():
        for module_name, description in modules.items():
            register_module(thread_name, module_name, description, conn)
    
    conn.commit()
    print(f"✓ Bootstrapped {len(DEFAULT_THREADS)} threads with {sum(len(m) for m in DEFAULT_THREADS.values())} modules")


def get_thread_summary() -> Dict[str, Any]:
    """Get summary of all threads and their modules."""
    modules = get_registered_modules()
    
    summary = {}
    for mod in modules:
        thread = mod["thread_name"]
        if thread not in summary:
            summary[thread] = {"modules": [], "total_rows": 0}
        summary[thread]["modules"].append(mod["module_name"])
        
        # Count rows in this module
        try:
            conn = get_connection(readonly=True)
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {mod['table_name']}")
            count = cur.fetchone()[0]
            summary[thread]["total_rows"] += count
        except:
            pass
    
    return summary


# ============================================================================
# MIGRATION: Move old data to new schema
# ============================================================================

def migrate_from_identity_sections() -> int:
    """
    Migrate data from old identity_sections table to new thread schema.
    
    Returns count of rows migrated.
    """
    conn = get_connection()
    cur = conn.cursor()
    
    # Check if old table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='identity_sections'")
    if not cur.fetchone():
        return 0
    
    # Ensure new schema exists
    bootstrap_threads()
    
    # Read old data
    cur.execute("SELECT key, data_l2_json, metadata_json, weight, section FROM identity_sections")
    rows = cur.fetchall()
    
    migrated = 0
    for row in rows:
        key = row["key"]
        data = json.loads(row["data_l2_json"]) if row["data_l2_json"] else {}
        metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
        weight = row["weight"] or 0.5
        section = row["section"] or "core"
        
        # Determine which module this belongs to
        if section in ("machineID", "machine"):
            module = "machine_context"
        elif section in ("userID", "user", "facts"):
            module = "user_profile"
        else:
            module = "nola_self"
        
        push_to_module(
            thread_name="identity",
            module_name=module,
            key=key,
            metadata=metadata,
            data=data,
            level=2,
            weight=weight
        )
        migrated += 1
    
    print(f"✓ Migrated {migrated} rows from identity_sections to new schema")
    return migrated


# ============================================================================
# SCHEMA: Flat Identity Table (HEA-native)
# ============================================================================

def init_identity_flat(conn: Optional[sqlite3.Connection] = None) -> None:
    """Create the flat identity table with L1/L2/L3 columns."""
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS identity_flat (
            key TEXT PRIMARY KEY,
            metadata_type TEXT,
            metadata_desc TEXT,
            l1 TEXT NOT NULL,
            l2 TEXT NOT NULL,
            l3 TEXT NOT NULL,
            weight REAL DEFAULT 0.5,
            access_count INTEGER DEFAULT 0,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_identity_flat_weight ON identity_flat(weight DESC)
    """)
    
    if own_conn:
        conn.commit()


def push_identity_row(
    key: str,
    l1: str,
    l2: str,
    l3: str,
    metadata_type: str = "fact",
    metadata_desc: str = "",
    weight: float = 0.5
) -> None:
    """Push a row to identity_flat table."""
    conn = get_connection()
    cur = conn.cursor()
    
    init_identity_flat(conn)
    
    cur.execute("""
        INSERT INTO identity_flat (key, metadata_type, metadata_desc, l1, l2, l3, weight, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            metadata_type = excluded.metadata_type,
            metadata_desc = excluded.metadata_desc,
            l1 = excluded.l1,
            l2 = excluded.l2,
            l3 = excluded.l3,
            weight = excluded.weight,
            access_count = access_count + 1,
            last_accessed = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
    """, (key, metadata_type, metadata_desc, l1, l2, l3, weight))
    
    conn.commit()


def pull_identity_flat(level: int = 2, min_weight: float = 0.0, limit: int = 50) -> List[Dict]:
    """
    Pull identity rows at the specified HEA level.
    
    Returns list of {key, metadata_type, metadata_desc, value, weight}
    where 'value' is L1, L2, or L3 depending on level.
    """
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    level_col = {1: 'l1', 2: 'l2', 3: 'l3'}.get(level, 'l2')
    
    cur.execute(f"""
        SELECT key, metadata_type, metadata_desc, {level_col} as value, l1, l2, l3, weight, access_count
        FROM identity_flat
        WHERE weight >= ?
        ORDER BY weight DESC
        LIMIT ?
    """, (min_weight, limit))
    
    return [dict(row) for row in cur.fetchall()]


def get_identity_context(level: int = 2, token_budget: int = 500) -> str:
    """
    Build identity context string for agent prompt at given HEA level.
    
    Returns formatted string of identity facts within token budget.
    Estimates ~4 chars per token.
    """
    rows = pull_identity_flat(level=level, min_weight=0.0)
    
    char_budget = token_budget * 4
    lines = []
    total_chars = 0
    
    for row in rows:
        line = f"- {row['key']}: {row['value']}"
        if total_chars + len(line) > char_budget:
            break
        lines.append(line)
        total_chars += len(line) + 1  # +1 for newline
    
    return "\n".join(lines)


def get_identity_table_data() -> List[Dict]:
    """
    Get all identity rows with full L1/L2/L3 data for UI table display.
    
    Returns list of {key, metadata_type, metadata_desc, l1, l2, l3, weight}
    """
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT key, metadata_type, metadata_desc, l1, l2, l3, weight
        FROM identity_flat
        ORDER BY weight DESC
    """)
    
    return [dict(row) for row in cur.fetchall()]


# ============================================================================
# SCHEMA: Flat Philosophy Table (HEA-native, like identity_flat)
# ============================================================================

def init_philosophy_flat(conn: Optional[sqlite3.Connection] = None) -> None:
    """Create the flat philosophy table with L1/L2/L3 columns."""
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS philosophy_flat (
            key TEXT PRIMARY KEY,
            metadata_type TEXT,
            metadata_desc TEXT,
            l1 TEXT NOT NULL,
            l2 TEXT NOT NULL,
            l3 TEXT NOT NULL,
            weight REAL DEFAULT 0.5,
            access_count INTEGER DEFAULT 0,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_philosophy_flat_weight ON philosophy_flat(weight DESC)
    """)
    
    if own_conn:
        conn.commit()


def push_philosophy_row(
    key: str,
    l1: str,
    l2: str,
    l3: str,
    metadata_type: str = "value",
    metadata_desc: str = "",
    weight: float = 0.5
) -> None:
    """Push a row to philosophy_flat table."""
    conn = get_connection()
    cur = conn.cursor()
    
    init_philosophy_flat(conn)
    
    cur.execute("""
        INSERT INTO philosophy_flat (key, metadata_type, metadata_desc, l1, l2, l3, weight, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            metadata_type = excluded.metadata_type,
            metadata_desc = excluded.metadata_desc,
            l1 = excluded.l1,
            l2 = excluded.l2,
            l3 = excluded.l3,
            weight = excluded.weight,
            access_count = access_count + 1,
            last_accessed = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
    """, (key, metadata_type, metadata_desc, l1, l2, l3, weight))
    
    conn.commit()


def pull_philosophy_flat(level: int = 2, min_weight: float = 0.0, limit: int = 50) -> List[Dict]:
    """
    Pull philosophy rows at the specified HEA level.
    
    Returns list of {key, metadata_type, metadata_desc, value, weight}
    where 'value' is L1, L2, or L3 depending on level.
    """
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    # Ensure table exists
    init_philosophy_flat(conn)
    
    level_col = {1: 'l1', 2: 'l2', 3: 'l3'}.get(level, 'l2')
    
    cur.execute(f"""
        SELECT key, metadata_type, metadata_desc, {level_col} as value, l1, l2, l3, weight, access_count
        FROM philosophy_flat
        WHERE weight >= ?
        ORDER BY weight DESC
        LIMIT ?
    """, (min_weight, limit))
    
    return [dict(row) for row in cur.fetchall()]


def get_philosophy_table_data() -> List[Dict]:
    """
    Get all philosophy rows with full L1/L2/L3 data for UI table display.
    
    Returns list of {key, metadata_type, metadata_desc, l1, l2, l3, weight}
    """
    conn = get_connection(readonly=True)
    cur = conn.cursor()
    
    # Ensure table exists
    init_philosophy_flat(conn)
    
    cur.execute("""
        SELECT key, metadata_type, metadata_desc, l1, l2, l3, weight
        FROM philosophy_flat
        ORDER BY weight DESC
    """)
    
    return [dict(row) for row in cur.fetchall()]


def migrate_philosophy_to_flat() -> int:
    """
    Migrate existing philosophy_* tables to philosophy_flat format.
    
    Converts:
    - philosophy_core_values -> metadata_type="value"
    - philosophy_ethical_bounds -> metadata_type="constraint"
    - philosophy_reasoning_style -> metadata_type="style"
    """
    import json
    
    conn = get_connection()
    cur = conn.cursor()
    init_philosophy_flat(conn)
    
    migrated = 0
    
    # Migrate from each old table
    migrations = [
        ("philosophy_core_values", "value"),
        ("philosophy_ethical_bounds", "constraint"),
        ("philosophy_reasoning_style", "style"),
    ]
    
    for table_name, metadata_type in migrations:
        try:
            cur.execute(f"""
                SELECT key, metadata_json, data_json, weight
                FROM {table_name}
            """)
            rows = cur.fetchall()
            
            for row in rows:
                key = row["key"]
                metadata = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                data = json.loads(row["data_json"]) if row["data_json"] else {}
                weight = row["weight"] or 0.5
                
                # Extract description
                desc = metadata.get("description", "")
                
                # Extract value/constraint/style from data
                value_text = data.get("value") or data.get("constraint") or data.get("style") or ""
                
                # Build L1/L2/L3 from single value (can be refined later)
                l1 = value_text[:50] if value_text else key
                l2 = value_text if value_text else key
                l3 = value_text if value_text else key
                
                push_philosophy_row(
                    key=key,
                    l1=l1,
                    l2=l2,
                    l3=l3,
                    metadata_type=metadata_type,
                    metadata_desc=desc,
                    weight=weight
                )
                migrated += 1
                
        except Exception as e:
            print(f"⚠ Could not migrate {table_name}: {e}")
    
    print(f"✓ Migrated {migrated} rows to philosophy_flat")
    return migrated


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python schema.py [bootstrap|migrate|summary|push|pull]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "bootstrap":
        bootstrap_threads()
    
    elif cmd == "migrate":
        migrate_from_identity_sections()
    
    elif cmd == "summary":
        summary = get_thread_summary()
        print("\n=== Thread Summary ===")
        for thread, info in summary.items():
            print(f"\n{thread}:")
            print(f"  Modules: {', '.join(info['modules'])}")
            print(f"  Total rows: {info['total_rows']}")
    
    elif cmd == "push":
        # Example: python schema.py push identity user_profile user_name
        if len(sys.argv) < 5:
            print("Usage: python schema.py push <thread> <module> <key> [value]")
            sys.exit(1)
        thread, module, key = sys.argv[2:5]
        value = sys.argv[5] if len(sys.argv) > 5 else "test_value"
        push_to_module(
            thread, module, key,
            metadata={"type": "fact", "description": f"Test {key}"},
            data={"value": value}
        )
        print(f"✓ Pushed {key} to {thread}.{module}")
    
    elif cmd == "pull":
        # Example: python schema.py pull identity user_profile
        if len(sys.argv) < 4:
            print("Usage: python schema.py pull <thread> <module> [level]")
            sys.exit(1)
        thread, module = sys.argv[2:4]
        level = int(sys.argv[4]) if len(sys.argv) > 4 else 2
        rows = pull_from_module(thread, module, level)
        print(f"\n=== {thread}.{module} (level≤{level}) ===")
        for r in rows:
            print(f"  {r['key']}: {r['data']}")
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
