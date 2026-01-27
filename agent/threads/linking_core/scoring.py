"""
LinkingCore Scoring Functions
=============================

Pure functions for relevance scoring. No state, no side effects.
Data in → scores out.

These functions use embeddings when available, with keyword fallback.
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np

# Cache for embeddings during a session
_EMBEDDING_CACHE: Dict[str, np.ndarray] = {}
_OLLAMA_CHECKED: bool = False
_OLLAMA_AVAILABLE: bool = False


def _check_ollama() -> bool:
    """Check if Ollama embedding model is available."""
    global _OLLAMA_CHECKED, _OLLAMA_AVAILABLE
    if _OLLAMA_CHECKED:
        return _OLLAMA_AVAILABLE
    
    try:
        import ollama
        response = ollama.embeddings(model="nomic-embed-text", prompt="test")
        _OLLAMA_AVAILABLE = "embedding" in response
    except Exception:
        _OLLAMA_AVAILABLE = False
    
    _OLLAMA_CHECKED = True
    return _OLLAMA_AVAILABLE


def get_embedding(text: str, use_cache: bool = True) -> Optional[np.ndarray]:
    """
    Get embedding for a text string.
    
    Args:
        text: Text to embed
        use_cache: Whether to use/update the session cache
    
    Returns:
        Numpy array of embedding, or None if unavailable
    """
    if not text:
        return None
    
    # Check cache
    if use_cache and text in _EMBEDDING_CACHE:
        return _EMBEDDING_CACHE[text]
    
    if not _check_ollama():
        return None
    
    try:
        import ollama
        response = ollama.embeddings(model="nomic-embed-text", prompt=text)
        embedding = np.array(response["embedding"])
        
        if use_cache:
            _EMBEDDING_CACHE[text] = embedding
        
        return embedding
    except Exception:
        return None


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    if a is None or b is None:
        return 0.0
    
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return float(np.dot(a, b) / (norm_a * norm_b))


def keyword_fallback_score(query: str, text: str) -> float:
    """
    Simple keyword overlap scoring as fallback.
    
    Returns 0.0-1.0 based on word overlap.
    """
    if not query or not text:
        return 0.0
    
    query_words = set(query.lower().split())
    text_words = set(text.lower().split())
    
    if not query_words:
        return 0.0
    
    overlap = len(query_words & text_words)
    return min(1.0, overlap / len(query_words))


def _item_to_text(item: Dict[str, Any]) -> str:
    """
    Convert an item dict to embeddable text.
    
    Expected item format from schema.pull_from_module():
    {
        "key": "user_name",
        "metadata": {"type": "fact", "description": "User's name"},
        "data": {"value": "Jordan"},
        "level": 1,
        "weight": 0.9
    }
    """
    parts = []
    
    # Key
    key = item.get("key", "")
    if key:
        parts.append(key.replace("_", " "))
    
    # Description from metadata
    metadata = item.get("metadata", {})
    if isinstance(metadata, dict):
        desc = metadata.get("description", "")
        if desc:
            parts.append(desc)
    
    # Value from data
    data = item.get("data", {})
    if isinstance(data, dict):
        value = data.get("value", "")
        if value:
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, list):
                parts.append(", ".join(str(v) for v in value[:5]))
            else:
                parts.append(str(value))
    elif isinstance(data, str):
        parts.append(data)
    
    return " ".join(parts)


def score_relevance(
    query: str,
    items: List[Dict[str, Any]],
    use_embeddings: bool = True
) -> List[Tuple[str, float]]:
    """
    Score items against a query.
    
    Args:
        query: The user's query/message
        items: List of items from schema.pull_from_module()
        use_embeddings: Whether to try embeddings (falls back to keywords)
    
    Returns:
        List of (key, score) tuples sorted by score descending.
        Scores are 0.0-1.0.
    """
    if not items:
        return []
    
    if not query:
        # No query = all items equal score based on weight
        return [(item.get("key", ""), item.get("weight", 0.5)) for item in items]
    
    scores = []
    
    # Try embedding-based scoring
    query_emb = None
    if use_embeddings:
        query_emb = get_embedding(query)
    
    for item in items:
        key = item.get("key", "unknown")
        text = _item_to_text(item)
        weight = item.get("weight", 0.5)
        
        if query_emb is not None:
            # Embedding-based scoring
            item_emb = get_embedding(text)
            if item_emb is not None:
                sim = cosine_similarity(query_emb, item_emb)
                # Blend with weight: 70% similarity, 30% weight
                score = 0.7 * sim + 0.3 * weight
            else:
                # Fallback for this item
                score = keyword_fallback_score(query, text) * 0.7 + weight * 0.3
        else:
            # Pure keyword fallback
            score = keyword_fallback_score(query, text) * 0.7 + weight * 0.3
        
        scores.append((key, score))
    
    # Sort by score descending
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def rank_items(
    items: List[Dict[str, Any]],
    query: str,
    threshold: float = 0.0,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Score, filter, and return top items.
    
    Args:
        items: List of items from schema.pull_from_module()
        query: The user's query/message
        threshold: Minimum score to include (0.0-1.0)
        limit: Maximum items to return
    
    Returns:
        Filtered and sorted list of items, each with added "score" field.
    """
    if not items:
        return []
    
    # Score all items
    scores = score_relevance(query, items)
    score_map = {key: score for key, score in scores}
    
    # Add scores to items and filter
    result = []
    for item in items:
        key = item.get("key", "")
        score = score_map.get(key, 0.0)
        
        if score >= threshold:
            item_with_score = {**item, "score": score}
            result.append(item_with_score)
    
    # Sort by score and limit
    result.sort(key=lambda x: x.get("score", 0), reverse=True)
    return result[:limit]


def clear_cache() -> int:
    """Clear the embedding cache. Returns number of entries cleared."""
    global _EMBEDDING_CACHE
    count = len(_EMBEDDING_CACHE)
    _EMBEDDING_CACHE.clear()
    return count


def cache_stats() -> Dict[str, Any]:
    """Get embedding cache statistics."""
    return {
        "size": len(_EMBEDDING_CACHE),
        "ollama_available": _OLLAMA_AVAILABLE if _OLLAMA_CHECKED else "unknown",
    }


# =============================================================================
# Thread Summary Scoring
# =============================================================================

# Cached thread summaries + embeddings (populated on consolidation/wake)
_THREAD_SUMMARIES: Dict[str, str] = {}
_THREAD_EMBEDDINGS: Dict[str, np.ndarray] = {}


def set_thread_summary(thread_name: str, summary: str) -> None:
    """
    Store a thread summary and compute its embedding.
    
    Called during consolidation to update thread summaries.
    """
    _THREAD_SUMMARIES[thread_name] = summary
    
    # Pre-compute embedding
    emb = get_embedding(summary, use_cache=False)
    if emb is not None:
        _THREAD_EMBEDDINGS[thread_name] = emb


def get_thread_summary(thread_name: str) -> Optional[str]:
    """Get stored thread summary."""
    return _THREAD_SUMMARIES.get(thread_name)


def score_threads_by_embedding(query: str) -> Dict[str, float]:
    """
    Score all threads against query using embedding similarity.
    
    Args:
        query: User query/message
    
    Returns:
        Dict mapping thread_name → score (0-10 scale)
    """
    if not _THREAD_EMBEDDINGS:
        return {}  # No summaries yet, fall back to keyword scoring
    
    query_emb = get_embedding(query)
    if query_emb is None:
        return {}  # Can't embed query, fall back
    
    scores = {}
    for thread_name, thread_emb in _THREAD_EMBEDDINGS.items():
        sim = cosine_similarity(query_emb, thread_emb)
        # Convert 0-1 similarity to 0-10 scale
        # Apply slight boost so relevant threads score higher
        scores[thread_name] = min(10.0, sim * 12.0)  # 0.83 sim = 10.0
    
    return scores


def get_thread_summary_stats() -> Dict[str, Any]:
    """Get stats about cached thread summaries."""
    return {
        "threads_with_summaries": list(_THREAD_SUMMARIES.keys()),
        "threads_with_embeddings": list(_THREAD_EMBEDDINGS.keys()),
        "summary_count": len(_THREAD_SUMMARIES),
    }
