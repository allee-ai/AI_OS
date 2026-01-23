"""
LinkingCore Thread - Relevance Scoring & Concept Graph
=======================================================

Maintains the concept graph and provides relevance scoring.

Usage:
    from agent.threads.linking_core import score_relevance, spread_activate
    
    # Score items against a query
    scores = score_relevance(query, items)
    
    # Spread activation from concepts
    activated = spread_activate(['sarah', 'coffee'])
"""

from .scoring import (
    score_relevance,
    rank_items,
    get_embedding,
    cosine_similarity,
    keyword_fallback_score,
    cache_stats,
    clear_cache,
)

# API router
from .api import router

# Adapter for subconscious integration
from .adapter import LinkingCoreThreadAdapter

# Schema functions (self-contained in this thread)
from .schema import (
    # Table init
    init_concept_links_table,
    init_cooccurrence_table,
    # Hebbian learning
    link_concepts,
    decay_concept_links,
    # Spread activation
    spread_activate,
    # Concept extraction
    extract_concepts_from_text,
    extract_concepts_from_value,
    # Co-occurrence
    get_cooccurrence_score,
    record_cooccurrence,
    record_concept_cooccurrence,
    # Fact retrieval
    get_keys_for_concepts,
    # Graph indexing
    index_key_in_concept_graph,
    # CRUD for API
    get_concepts, get_all_links, get_links_for_concept,
    create_link, delete_link, update_link_strength,
    get_graph_data, get_activation_path, get_stats,
    # Conversation processing
    extract_and_link_concepts,
    process_conversation_turn,
)

__all__ = [
    # Scoring
    "score_relevance",
    "rank_items", 
    "get_embedding",
    "cosine_similarity",
    "keyword_fallback_score",
    "cache_stats",
    "clear_cache",
    # Adapter
    "LinkingCoreThreadAdapter",
    # API
    "router",
    # Schema - core functions
    "init_concept_links_table",
    "link_concepts",
    "decay_concept_links",
    "spread_activate",
    "extract_concepts_from_text",
    "extract_concepts_from_value",
    "get_cooccurrence_score",
    "record_cooccurrence",
    "record_concept_cooccurrence",
    "get_keys_for_concepts",
    "index_key_in_concept_graph",
    # Schema - API CRUD
    "get_concepts", "get_all_links", "get_links_for_concept",
    "create_link", "delete_link", "update_link_strength",
    "get_graph_data", "get_activation_path", "get_stats",
    # Conversation processing
    "extract_and_link_concepts",
    "process_conversation_turn",
]

