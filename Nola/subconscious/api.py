"""
Subconscious API
================
The aggregation layer - calls all threads and combines their state.

This is the ONLY introspection endpoint needed. It replaces introspection.py.

Endpoints:
    GET /api/subconscious/state     - Full state from all threads
    GET /api/subconscious/health    - Health status from all threads  
    GET /api/subconscious/context   - Context string for system prompt
    POST /api/subconscious/record   - Record an interaction
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from .orchestrator import get_subconscious, THREADS

router = APIRouter(prefix="/api/subconscious", tags=["subconscious"])


# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────

class InteractionRecord(BaseModel):
    user_message: str
    agent_response: str
    metadata: Optional[Dict[str, Any]] = None


# ─────────────────────────────────────────────────────────────
# Main Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/state")
async def get_full_state(
    level: int = Query(2, ge=1, le=3),
    query: Optional[str] = None,
    threads: Optional[str] = None
):
    """
    Get full state from all threads (the aggregator).
    
    This is the main introspection endpoint. It calls each thread's
    introspect() method and combines the results.
    
    Args:
        level: HEA level (1=minimal, 2=moderate, 3=full)
        query: Optional query for relevance filtering
        threads: Comma-separated thread names (default: all)
    
    Returns:
        {
            "state": {thread: {health, state, fact_count}},
            "context": [{fact, source}, ...],
            "relevant_concepts": [...],
            "meta": {level, total_facts, timestamp, ...}
        }
    """
    sub = get_subconscious()
    
    # Parse threads
    thread_list = None
    if threads:
        thread_list = [t.strip() for t in threads.split(",")]
    
    return sub.build_context(level=level, query=query or "", threads=thread_list)


@router.get("/health")
async def get_all_health():
    """
    Get health status from all threads.
    
    Returns:
        {thread_name: {status, message, details}, ...}
    """
    sub = get_subconscious()
    return {
        "threads": sub.get_all_health(),
        "available_threads": THREADS
    }


@router.get("/context")
async def get_context_string(
    level: int = Query(2, ge=1, le=3),
    query: Optional[str] = None
):
    """
    Get context as formatted string for system prompt.
    
    This is what gets injected into the agent's system prompt.
    """
    sub = get_subconscious()
    context_str = sub.get_context_string(level=level, query=query or "")
    
    return {
        "level": level,
        "query": query,
        "context": context_str,
        "char_count": len(context_str)
    }


@router.post("/record")
async def record_interaction(data: InteractionRecord):
    """
    Record an interaction to the log thread.
    
    Call this after each agent response to build conversation history.
    """
    sub = get_subconscious()
    sub.record_interaction(
        user_message=data.user_message,
        agent_response=data.agent_response,
        metadata=data.metadata
    )
    return {"status": "recorded"}


@router.get("/threads")
async def list_threads():
    """List all available threads with health info as object keyed by thread name."""
    sub = get_subconscious()
    health = sub.get_all_health()
    
    # Build object keyed by thread name (frontend expects this format)
    threads_obj = {}
    for thread in THREADS:
        thread_health = health.get(thread, {})
        status = thread_health.get("status", "unknown")
        message = thread_health.get("message", "")
        # Determine has_data: healthy and message doesn't start with "0 "
        has_data = status == "ok" and message and not message.startswith("0 ")
        
        threads_obj[thread] = {
            "name": thread,
            "status": status,
            "message": message,
            "has_data": has_data
        }
    
    return {"threads": threads_obj}


# ─────────────────────────────────────────────────────────────
# Backwards Compatibility (can remove later)
# ─────────────────────────────────────────────────────────────

@router.get("/identity-facts")
async def get_identity_facts(level: int = Query(2, ge=1, le=3)):
    """Get identity facts as simple list (backwards compatibility)."""
    sub = get_subconscious()
    facts = sub.get_identity_facts(level=level)
    return {"facts": facts, "count": len(facts)}
