"""
Subconscious API
================
The aggregation layer - calls all threads and combines their state.

This is the ONLY introspection endpoint needed. It replaces introspection.py.

Endpoints:
    GET /api/subconscious/build_state  - Build STATE block (primary endpoint)
    GET /api/subconscious/state        - Full state from all threads (legacy)
    GET /api/subconscious/health       - Health status from all threads  
    GET /api/subconscious/context      - Context string for system prompt
    POST /api/subconscious/record      - Record an interaction
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
# Primary Endpoint: STATE + ASSESS
# ─────────────────────────────────────────────────────────────

@router.get("/build_state")
async def build_state(
    query: Optional[str] = Query(None, description="The assess block content")
):
    """
    Build STATE block from all threads, ordered by relevance.
    
    This is the primary state assembly endpoint for the architecture:
        state_t+1 = f(state_t, assess)
    
    The query parameter is the "assess block" - what you're assessing against state:
    - User message (conversation)
    - File chunk (reading)
    - Memory segment (consolidation)
    - External data (sync)
    - Own state (reflection)
    
    Returns:
        {
            "state": "== STATE ==\\n\\nidentity - 8.2\\n...",
            "query": "the assess block",
            "char_count": N
        }
    """
    sub = get_subconscious()
    # get_state does score() + build_state() in one call
    state_str = sub.get_state(query=query or "")
    
    return {
        "state": state_str,
        "query": query,
        "char_count": len(state_str)
    }


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
    """List all available threads with health info as object keyed by thread name.
    
    This endpoint is fault-tolerant: if any thread fails, others still return.
    """
    try:
        sub = get_subconscious()
        health = sub.get_all_health()
    except Exception as e:
        # Even if subconscious itself fails, return empty threads
        print(f"⚠️ Subconscious failed: {e}")
        health = {}
    
    # Build object keyed by thread name (frontend expects this format)
    threads_obj = {}
    for thread in THREADS:
        try:
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
        except Exception as e:
            # Even if processing one thread fails, continue with others
            threads_obj[thread] = {
                "name": thread,
                "status": "error",
                "message": f"Processing failed: {str(e)[:50]}",
                "has_data": False
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


# ─────────────────────────────────────────────────────────────
# Loop Status Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/loops")
async def get_loops_status():
    """
    Get status of all background loops.
    
    Returns loop name, status, interval, last run, run count, errors.
    """
    try:
        from . import _loop_manager
        
        if _loop_manager is not None:
            stats = _loop_manager.get_stats()
        else:
            stats = []
        
        return {
            "loops": stats,
            "count": len(stats)
        }
    except Exception as e:
        return {
            "loops": [],
            "error": str(e)
        }


@router.get("/loops/{loop_name}")
async def get_loop_status(loop_name: str):
    """Get status of a specific loop."""
    try:
        from . import _loop_manager
        
        if _loop_manager is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail="Loops not started")
        loop = _loop_manager.get_loop(loop_name)
        
        if not loop:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Loop '{loop_name}' not found")
        
        return loop.stats
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/temp-facts")
async def get_temp_facts_summary():
    """Get summary of temp_facts for dashboard."""
    try:
        from .temp_memory import get_stats, get_all_pending
        
        stats = get_stats()
        pending = get_all_pending()
        
        # Count by status
        by_status = {}
        for fact in pending:
            status = fact.status if hasattr(fact, 'status') else 'pending'
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "stats": stats,
            "by_status": by_status,
            "pending_count": len(pending),
            "recent": [fact.to_dict() for fact in pending[:50]]
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/temp-facts/review")
async def get_facts_for_review():
    """Get all facts needing human review."""
    try:
        from .temp_memory import get_pending_review, get_all_pending
        
        review = get_pending_review()
        pending = [f for f in get_all_pending() if f.status == 'pending']
        
        all_facts = review + pending
        return {
            "facts": [f.to_dict() for f in all_facts],
            "count": len(all_facts)
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/temp-facts/{fact_id}/approve")
async def approve_temp_fact(fact_id: int):
    """Approve a temp fact for promotion to long-term memory."""
    from .temp_memory import approve_fact
    
    success = approve_fact(fact_id)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Fact {fact_id} not found")
    return {"status": "approved", "fact_id": fact_id}


@router.post("/temp-facts/{fact_id}/reject")
async def reject_temp_fact(fact_id: int):
    """Reject a temp fact — it will never enter long-term memory."""
    from .temp_memory import reject_fact
    
    success = reject_fact(fact_id)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Fact {fact_id} not found")
    return {"status": "rejected", "fact_id": fact_id}


@router.put("/temp-facts/{fact_id}")
async def edit_temp_fact(fact_id: int, body: dict):
    """Edit a temp fact's text before it enters long-term memory."""
    from .temp_memory import update_fact_text
    
    text = body.get("text", "").strip()
    if not text:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="text is required")
    
    success = update_fact_text(fact_id, text)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Fact {fact_id} not found")
    return {"status": "updated", "fact_id": fact_id, "text": text}


@router.delete("/temp-facts/{fact_id}")
async def delete_temp_fact(fact_id: int):
    """Delete a temp fact entirely."""
    from .temp_memory import delete_fact
    
    success = delete_fact(fact_id)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Fact {fact_id} not found")
    return {"status": "deleted", "fact_id": fact_id}


@router.post("/temp-facts/approve-all")
async def approve_all_pending():
    """Approve all pending/pending_review facts at once."""
    from .temp_memory import get_all_pending, approve_fact
    
    pending = [f for f in get_all_pending() if f.status in ('pending', 'pending_review')]
    approved = 0
    for fact in pending:
        if approve_fact(fact.id):
            approved += 1
    return {"approved": approved}


@router.post("/temp-facts/reject-all")
async def reject_all_pending():
    """Reject all pending/pending_review facts at once."""
    from .temp_memory import get_all_pending, reject_fact
    
    pending = [f for f in get_all_pending() if f.status in ('pending', 'pending_review')]
    rejected = 0
    for fact in pending:
        if reject_fact(fact.id):
            rejected += 1
    return {"rejected": rejected}


# ─────────────────────────────────────────────────────────────
# Loop Configuration Endpoints
# ─────────────────────────────────────────────────────────────

@router.put("/loops/{loop_name}/interval")
async def set_loop_interval(loop_name: str, body: dict):
    """Update a loop's interval in seconds."""
    from . import _loop_manager
    
    if _loop_manager is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Loops not started")
    
    loop = _loop_manager.get_loop(loop_name)
    if not loop:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Loop '{loop_name}' not found")
    
    interval = body.get("interval")
    if interval is None or not isinstance(interval, (int, float)) or interval < 5:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="interval must be a number >= 5")
    
    loop.config.interval_seconds = float(interval)
    return {"status": "updated", "loop": loop_name, "interval": interval}


@router.post("/loops/{loop_name}/pause")
async def pause_loop(loop_name: str):
    """Pause a running loop."""
    from . import _loop_manager
    
    if _loop_manager is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Loops not started")
    
    loop = _loop_manager.get_loop(loop_name)
    if not loop:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Loop '{loop_name}' not found")
    
    loop.pause()
    return {"status": "paused", "loop": loop_name}


@router.post("/loops/{loop_name}/resume")
async def resume_loop(loop_name: str):
    """Resume a paused loop."""
    from . import _loop_manager
    
    if _loop_manager is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Loops not started")
    
    loop = _loop_manager.get_loop(loop_name)
    if not loop:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Loop '{loop_name}' not found")
    
    loop.resume()
    return {"status": "resumed", "loop": loop_name}


@router.put("/loops/memory/model")
async def set_memory_model(body: dict):
    """Set the LLM model used by the memory loop for fact extraction."""
    from . import _loop_manager
    
    if _loop_manager is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Loops not started")
    
    loop = _loop_manager.get_loop("memory")
    if not loop or not hasattr(loop, 'model'):
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Memory loop not available")
    
    model = body.get("model", "").strip()
    if not model:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="model is required")
    
    loop.model = model
    return {"status": "updated", "model": model}


@router.get("/queue")
async def get_unprocessed_queue():
    """
    Get the number of unprocessed conversation turns waiting to be read.
    Shows the user how many conversations the memory loop still needs to process.
    """
    from . import _loop_manager
    
    unprocessed = 0
    last_id = None
    model = None
    
    if _loop_manager:
        loop = _loop_manager.get_loop("memory")
        if loop and hasattr(loop, 'get_unprocessed_count'):
            unprocessed = loop.get_unprocessed_count()
            last_id = getattr(loop, '_last_processed_turn_id', None)
            model = getattr(loop, 'model', None)
    
    # Also get total turns for context
    total_turns = 0
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM convo_turns")
            total_turns = cur.fetchone()[0]
    except Exception:
        pass
    
    return {
        "unprocessed": unprocessed,
        "total_turns": total_turns,
        "last_processed_turn_id": last_id,
        "model": model
    }


@router.get("/potentiation")
async def get_potentiation_status():
    """Get concept link potentiation stats (SHORT vs LONG)."""
    try:
        from agent.threads.linking_core.schema import get_potentiation_stats, consolidate_links
        
        stats = get_potentiation_stats()
        
        return {
            "potentiation": stats,
            "ready_for_export": stats.get("LONG", {}).get("count", 0)
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/consolidate")
async def trigger_consolidation():
    """Manually trigger consolidation of concept links."""
    try:
        from agent.threads.linking_core.schema import consolidate_links
        
        result = consolidate_links(fire_threshold=5, strength_threshold=0.5)
        return {"status": "consolidated", "result": result}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))
