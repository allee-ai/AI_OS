"""
Linking Core Thread API
=======================
Endpoints for concept graphs, spread activation, and relevance scoring.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from .schema import (
    get_concepts, get_all_links, get_links_for_concept,
    create_link, delete_link, update_link_strength,
    get_graph_data, get_activation_path, get_stats,
    spread_activate, extract_concepts_from_text,
)
from .adapter import LinkingCoreThreadAdapter

router = APIRouter(prefix="/api/linking_core", tags=["linking"])


# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────

class LinkCreate(BaseModel):
    concept_a: str
    concept_b: str
    strength: float = 0.5
    link_type: str = "related"


class LinkUpdate(BaseModel):
    strength: float


class ActivationRequest(BaseModel):
    concepts: List[str]
    max_hops: int = 2
    threshold: float = 0.1
    limit: int = 50


class ScoreRequest(BaseModel):
    input_text: str
    facts: List[str]
    top_k: int = 10


# ─────────────────────────────────────────────────────────────
# Concept Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/concepts")
async def list_concepts(limit: int = Query(100, ge=1, le=1000)):
    """List all unique concepts in the graph."""
    concepts = get_concepts(limit=limit)
    return {"concepts": concepts, "count": len(concepts)}


@router.post("/concepts/extract")
async def extract_concepts(text: str):
    """Extract concepts from input text."""
    concepts = extract_concepts_from_text(text)
    return {"text": text, "concepts": concepts, "count": len(concepts)}


# ─────────────────────────────────────────────────────────────
# Link Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/links")
async def list_links(limit: int = Query(500, ge=1, le=2000)):
    """List all concept links."""
    links = get_all_links(limit=limit)
    return {"links": links, "count": len(links)}


@router.get("/links/{concept}")
async def get_concept_links_endpoint(concept: str, limit: int = Query(50, ge=1, le=200)):
    """Get all links for a specific concept."""
    links = get_links_for_concept(concept, limit=limit)
    return {"concept": concept, "links": links, "count": len(links)}


@router.post("/links")
async def create_concept_link(link: LinkCreate):
    """Create a new concept link."""
    if create_link(link.concept_a, link.concept_b, link.strength, link.link_type):
        return {"status": "created", "link": link.dict()}
    raise HTTPException(status_code=500, detail="Failed to create link")


@router.put("/links")
async def update_concept_link(concept_a: str, concept_b: str, update: LinkUpdate):
    """Update link strength."""
    if update_link_strength(concept_a, concept_b, update.strength):
        return {"status": "updated", "concept_a": concept_a, "concept_b": concept_b, "strength": update.strength}
    raise HTTPException(status_code=404, detail="Link not found")


@router.delete("/links")
async def remove_concept_link(concept_a: str, concept_b: str):
    """Delete a concept link."""
    if delete_link(concept_a, concept_b):
        return {"status": "deleted", "concept_a": concept_a, "concept_b": concept_b}
    raise HTTPException(status_code=404, detail="Link not found")


# ─────────────────────────────────────────────────────────────
# Graph Visualization Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/graph")
async def get_graph(
    center: Optional[str] = None,
    max_nodes: int = Query(100, ge=10, le=500),
    min_strength: float = Query(0.1, ge=0, le=1)
):
    """
    Get graph data for visualization.
    
    Returns nodes and edges suitable for D3.js or similar.
    If center is provided, returns subgraph around that concept.
    """
    return get_graph_data(center_concept=center, max_nodes=max_nodes, min_strength=min_strength)


@router.get("/graph/path")
async def find_path(source: str, target: str, max_hops: int = Query(3, ge=1, le=5)):
    """Find activation path between two concepts."""
    result = get_activation_path(source, target, max_hops)
    return result


# ─────────────────────────────────────────────────────────────
# Activation Endpoints
# ─────────────────────────────────────────────────────────────

@router.post("/activate")
async def activate_concepts(request: ActivationRequest):
    """
    Run spread activation from input concepts.
    
    Returns activated concepts with their activation levels.
    """
    activated = spread_activate(
        request.concepts,
        activation_threshold=request.threshold,
        max_hops=request.max_hops,
        limit=request.limit
    )
    return {
        "input_concepts": request.concepts,
        "activated": activated,
        "count": len(activated)
    }


@router.get("/activate/{text}")
async def activate_from_text(
    text: str,
    max_hops: int = Query(2, ge=1, le=3),
    threshold: float = Query(0.1, ge=0, le=1),
    limit: int = Query(30, ge=1, le=100)
):
    """
    Extract concepts from text and run spread activation.
    
    Convenience endpoint that combines extraction and activation.
    """
    concepts = extract_concepts_from_text(text)
    if not concepts:
        return {"text": text, "concepts": [], "activated": [], "count": 0}
    
    activated = spread_activate(
        concepts,
        activation_threshold=threshold,
        max_hops=max_hops,
        limit=limit
    )
    
    return {
        "text": text,
        "concepts": concepts,
        "activated": activated,
        "count": len(activated)
    }


# ─────────────────────────────────────────────────────────────
# Scoring Endpoints
# ─────────────────────────────────────────────────────────────

@router.post("/score")
async def score_facts(request: ScoreRequest):
    """
    Score facts by relevance to input text.
    
    Uses embedding similarity, co-occurrence, and spread activation.
    """
    adapter = LinkingCoreThreadAdapter()
    scored = adapter.score_relevance(
        request.input_text,
        request.facts,
        use_embeddings=True,
        use_cooccurrence=True,
        use_spread_activation=True
    )
    
    return {
        "input": request.input_text,
        "scored_facts": [{"fact": f, "score": round(s, 4)} for f, s in scored[:request.top_k]],
        "count": len(scored)
    }


@router.post("/score/threads")
async def score_threads(feeds: str):
    """
    Score all threads for relevance to feeds.
    
    Used for context gating (deciding which threads to include).
    """
    adapter = LinkingCoreThreadAdapter()
    scores = adapter.score_threads(feeds)
    return {
        "feeds": feeds,
        "thread_scores": scores
    }


# ─────────────────────────────────────────────────────────────
# Stats Endpoint
# ─────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_linking_stats():
    """Get linking core statistics."""
    stats = get_stats()
    
    # Add adapter health info
    adapter = LinkingCoreThreadAdapter()
    health = adapter.health()
    stats["health"] = {
        "status": health.status.value,
        "message": health.message,
        "details": health.details
    }
    
    return stats


# ─────────────────────────────────────────────────────────────
# Introspection (Thread owns its state block)
# ─────────────────────────────────────────────────────────────

@router.get("/introspect")
async def introspect_linking(level: int = 2, query: Optional[str] = None):
    """
    Get linking_core thread's contribution to STATE block.
    
    LinkingCore doesn't have facts per se - it provides:
    - Graph stats
    - Relevant concepts (if query provided)
    - Health status
    """
    adapter = LinkingCoreThreadAdapter()
    result = adapter.introspect(context_level=level, query=query)
    return result.to_dict()


@router.get("/health")
async def get_linking_health():
    """Get linking core thread health status."""
    adapter = LinkingCoreThreadAdapter()
    return adapter.health().to_dict()


@router.post("/reindex")
async def reindex_concept_graph():
    """
    Reindex all profile facts into the concept graph.
    
    Scans identity and philosophy facts and creates/updates concept links.
    """
    from .schema import index_key_in_concept_graph, get_stats
    
    try:
        # Import profile facts from identity and philosophy
        from agent.threads.identity.schema import pull_profile_facts
        from agent.threads.philosophy.schema import pull_philosophy_profile_facts
        
        total_indexed = 0
        
        # Index identity facts
        identity_facts = pull_profile_facts()
        for fact in identity_facts:
            key = fact.get('key', '')
            l3 = fact.get('l3_value', '') or fact.get('l2_value', '')
            if key and l3:
                index_key_in_concept_graph(key, l3, learning_rate=0.15)
                total_indexed += 1
        
        # Index philosophy facts
        philosophy_facts = pull_philosophy_profile_facts()
        for fact in philosophy_facts:
            key = fact.get('key', '')
            l3 = fact.get('l3_value', '') or fact.get('l2_value', '')
            if key and l3:
                index_key_in_concept_graph(key, l3, learning_rate=0.15)
                total_indexed += 1
        
        stats = get_stats()
        return {
            "status": "ok",
            "indexed_facts": total_indexed,
            "total_links": stats.get("link_count", 0)
        }
    except Exception as e:
        raise HTTPException(500, f"Reindex failed: {str(e)}")
