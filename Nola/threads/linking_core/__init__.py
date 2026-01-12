"""
LinkingCore - Relevance Scoring Utility
=======================================

A utility service, NOT a data thread.
Pure function: data in → scored/sorted data out.

Usage:
    from Nola.threads.linking_core import score_relevance, rank_items
    
    # Score items against a query
    scores = score_relevance(query, items)
    
    # Rank and filter
    top_items = rank_items(items, query, threshold=0.5, limit=10)
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

# Legacy adapter for backwards compatibility
from .adapter import LinkingCoreThreadAdapter

__all__ = [
    "score_relevance",
    "rank_items", 
    "get_embedding",
    "cosine_similarity",
    "keyword_fallback_score",
    "cache_stats",
    "clear_cache",
    "LinkingCoreThreadAdapter",
]

