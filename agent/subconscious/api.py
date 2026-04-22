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


@router.get("/loops/custom")
async def list_custom_loops():
    """List all custom loop configurations."""
    from .loops import get_custom_loop_configs, CUSTOM_LOOP_SOURCES, CUSTOM_LOOP_TARGETS
    
    configs = get_custom_loop_configs()
    
    # Augment with runtime stats if loops are running
    from . import _loop_manager
    if _loop_manager:
        for cfg in configs:
            loop = _loop_manager.get_loop(cfg["name"])
            if loop:
                cfg["runtime"] = loop.stats
    
    return {
        "custom_loops": configs,
        "count": len(configs),
        "available_sources": CUSTOM_LOOP_SOURCES,
        "available_targets": CUSTOM_LOOP_TARGETS,
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


@router.get("/loops/{loop_name}/output")
async def get_loop_output(loop_name: str):
    """Get the last text output of a loop's most recent run.
    
    Returns the raw text result from the loop's task function.
    If the loop hasn't produced output yet, returns null.
    """
    from . import _loop_manager
    
    if _loop_manager is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Loops not started")
    
    loop = _loop_manager.get_loop(loop_name)
    if not loop:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Loop '{loop_name}' not found")
    
    return {
        "loop": loop_name,
        "last_result": loop._last_result,
        "last_error": loop._last_error,
        "last_run": loop._last_run,
        "run_count": loop._run_count,
    }


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


@router.put("/loops/{loop_name}/context-aware")
async def set_loop_context_aware(loop_name: str, body: dict):
    """Toggle context_aware (orchestrator STATE injection) for a loop.
    
    When enabled, the loop's LLM calls receive the full consciousness STATE
    (identity, philosophy, linking, log, workspace) as additional context.
    
    Body: {"enabled": true/false}
    """
    from . import _loop_manager
    
    if _loop_manager is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Loops not started")
    
    loop = _loop_manager.get_loop(loop_name)
    if not loop:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Loop '{loop_name}' not found")
    
    enabled = body.get("enabled")
    if not isinstance(enabled, bool):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="'enabled' must be a boolean")
    
    loop.config.context_aware = enabled
    return {
        "status": "updated",
        "loop": loop_name,
        "context_aware": enabled,
    }


@router.get("/loops/{loop_name}/prompts")
async def get_loop_prompts(loop_name: str):
    """Get all editable prompts for a loop.
    
    Returns a dict of stage_name → prompt_text.
    Only loops with LLM prompts have prompt stages:
      - memory: extract
      - thought: think
      - task_planner: plan, execute_llm, synthesize
      - custom loops: (user-defined prompt field)
    """
    from . import _loop_manager
    
    if _loop_manager is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Loops not started")
    
    loop = _loop_manager.get_loop(loop_name)
    if not loop:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Loop '{loop_name}' not found")
    
    prompts = getattr(loop, '_prompts', None)
    if prompts is None:
        return {"loop": loop_name, "prompts": {}, "note": "This loop has no editable prompts"}
    
    return {"loop": loop_name, "prompts": dict(prompts)}


@router.put("/loops/{loop_name}/prompts/{stage}")
async def set_loop_prompt(loop_name: str, stage: str, body: dict):
    """Update a specific prompt stage for a loop.
    
    Body: {"prompt": "new prompt text..."}
    
    Set prompt to empty string "" to reset to default.
    """
    from . import _loop_manager
    
    if _loop_manager is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Loops not started")
    
    loop = _loop_manager.get_loop(loop_name)
    if not loop:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Loop '{loop_name}' not found")
    
    prompts = getattr(loop, '_prompts', None)
    if prompts is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Loop '{loop_name}' has no editable prompts")
    
    if stage not in prompts:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail=f"Stage '{stage}' not found. Available: {list(prompts.keys())}",
        )
    
    new_prompt = body.get("prompt")
    if new_prompt is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="'prompt' field is required")
    
    new_prompt = str(new_prompt).strip()
    
    if not new_prompt:
        # Reset to default
        from agent.subconscious.loops.memory import DEFAULT_PROMPTS as MEM_DEFAULTS
        from agent.subconscious.loops.thought import DEFAULT_PROMPTS as THOUGHT_DEFAULTS
        from agent.subconscious.loops.task_planner import DEFAULT_PROMPTS as TASK_DEFAULTS
        from agent.subconscious.loops.demo_audit import DEFAULT_PROMPTS as AUDIT_DEFAULTS
        from agent.subconscious.loops.training_gen import GENERATOR_SYSTEM
        from agent.subconscious.loops.convo_concepts import _EXTRACT_SYSTEM
        from agent.subconscious.loops.goals import GOAL_PROMPT
        from agent.subconscious.loops.self_improve import IMPROVE_PROMPT
        all_defaults = {
            **MEM_DEFAULTS, **THOUGHT_DEFAULTS, **TASK_DEFAULTS,
            **AUDIT_DEFAULTS,
            "system": GENERATOR_SYSTEM,
            "extract": _EXTRACT_SYSTEM,
            "generate": GOAL_PROMPT,
            "improve": IMPROVE_PROMPT,
        }
        if stage in all_defaults:
            prompts[stage] = all_defaults[stage]
            return {"status": "reset_to_default", "loop": loop_name, "stage": stage}
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"No default found for stage '{stage}'")
    
    prompts[stage] = new_prompt
    return {
        "status": "updated",
        "loop": loop_name,
        "stage": stage,
        "prompt_length": len(new_prompt),
    }


@router.put("/loops/memory/model")
async def set_memory_model(body: dict):
    """Set the LLM model (and optionally provider) used by the memory loop for fact extraction.
    
    Body:
        model: str  — model name (e.g. "gpt-4o-mini", "qwen2.5:7b")
        provider: str (optional) — "ollama" (default) or "openai"
    
    For cloud extraction, set provider="openai" and ensure OPENAI_API_KEY
    is set (or AIOS_EXTRACT_ENDPOINT for non-OpenAI compatible APIs).
    """
    from . import _loop_manager
    import os
    
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

    provider = body.get("provider", "").strip()
    if provider:
        os.environ["AIOS_EXTRACT_PROVIDER"] = provider

    return {
        "status": "updated",
        "model": model,
        "provider": loop.provider,
    }


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


@router.post("/preview")
async def preview_state(body: dict):
    """
    Preview the STATE block for a given query without sending to LLM.
    
    Returns thread scores, the full state block, and token estimate.
    Used by the dashboard test panel.
    """
    query = body.get("query", "").strip()
    if not query:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Query is required")
    
    from .orchestrator import get_subconscious
    sub = get_subconscious()
    result = sub.preview_state(query)
    return result


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


# ─────────────────────────────────────────────────────────────
# Custom Loop CRUD Endpoints
# ─────────────────────────────────────────────────────────────

@router.post("/loops/custom")
async def create_custom_loop(body: dict):
    """
    Create a new custom chain-of-thought loop.
    
    Required: name, source, prompt
    Optional: target (default: temp_memory), interval (default: 300), model, enabled,
              max_iterations (default: 1), max_tokens_per_iter (default: 2048)
    """
    from .loops import save_custom_loop_config, CustomLoop
    from . import _loop_manager
    
    name = body.get("name", "").strip()
    source = body.get("source", "").strip()
    prompt = body.get("prompt", "").strip()
    target = body.get("target", "temp_memory").strip()
    interval = body.get("interval", 300)
    model = body.get("model") or None
    enabled = body.get("enabled", True)
    max_iterations = int(body.get("max_iterations", 1))
    max_tokens_per_iter = int(body.get("max_tokens_per_iter", 2048))
    
    if not name or not source or not prompt:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="name, source, and prompt are required")
    
    # Check for name conflict with built-in loops
    builtin_names = {"memory", "consolidation", "sync", "health", "thought"}
    if name in builtin_names:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"'{name}' conflicts with a built-in loop name")
    
    try:
        config = save_custom_loop_config(
            name=name, source=source, target=target,
            interval=float(interval), model=model,
            prompt=prompt, enabled=enabled,
            max_iterations=max_iterations,
            max_tokens_per_iter=max_tokens_per_iter,
        )
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    
    # Start the loop if enabled and manager is available
    if enabled and _loop_manager:
        # Remove old version if exists
        _loop_manager.remove(name)
        loop = CustomLoop(
            name=name, source=source, target=target,
            interval=float(interval), model=model,
            prompt=prompt, enabled=enabled,
            max_iterations=max_iterations,
            max_tokens_per_iter=max_tokens_per_iter,
        )
        _loop_manager.add(loop)
        loop.start()
    
    return {"status": "created", "loop": config}


@router.put("/loops/custom/{loop_name}")
async def update_custom_loop(loop_name: str, body: dict):
    """Update an existing custom loop's configuration."""
    from .loops import get_custom_loop_config, save_custom_loop_config, CustomLoop
    from . import _loop_manager
    
    existing = get_custom_loop_config(loop_name)
    if not existing:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Custom loop '{loop_name}' not found")
    
    # Merge with existing config
    source = body.get("source", existing["source"])
    target = body.get("target", existing["target"])
    interval = body.get("interval", existing["interval_seconds"])
    model = body.get("model", existing["model"])
    prompt = body.get("prompt", existing["prompt"])
    enabled = body.get("enabled", existing["enabled"])
    max_iterations = int(body.get("max_iterations", existing.get("max_iterations", 1)))
    max_tokens_per_iter = int(body.get("max_tokens_per_iter", existing.get("max_tokens_per_iter", 2048)))
    
    try:
        config = save_custom_loop_config(
            name=loop_name, source=source, target=target,
            interval=float(interval), model=model,
            prompt=prompt, enabled=enabled,
            max_iterations=max_iterations,
            max_tokens_per_iter=max_tokens_per_iter,
        )
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    
    # Restart the loop with new config
    if _loop_manager:
        _loop_manager.remove(loop_name)
        if enabled:
            loop = CustomLoop(
                name=loop_name, source=source, target=target,
                interval=float(interval), model=model,
                prompt=prompt, enabled=enabled,
                max_iterations=max_iterations,
                max_tokens_per_iter=max_tokens_per_iter,
            )
            _loop_manager.add(loop)
            loop.start()
    
    return {"status": "updated", "loop": config}


@router.delete("/loops/custom/{loop_name}")
async def delete_custom_loop(loop_name: str):
    """Delete a custom loop entirely."""
    from .loops import delete_custom_loop_config
    from . import _loop_manager
    
    # Stop it if running
    if _loop_manager:
        _loop_manager.remove(loop_name)
    
    success = delete_custom_loop_config(loop_name)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Custom loop '{loop_name}' not found")
    
    return {"status": "deleted", "loop": loop_name}


# ─────────────────────────────────────────────────────────────
# Thought Loop Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/thoughts")
async def list_thoughts(limit: int = 20, category: str = None):
    """
    Get recent thoughts from the proactive thought loop.
    
    Optional query params:
    - limit: max thoughts to return (default 20)
    - category: filter by category (insight, alert, reminder, suggestion, question)
    """
    from .loops import get_thought_log, THOUGHT_CATEGORIES, THOUGHT_PRIORITIES
    
    if category and category not in THOUGHT_CATEGORIES:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {THOUGHT_CATEGORIES}")
    
    thoughts = get_thought_log(limit=limit, category=category)
    return {
        "thoughts": thoughts,
        "count": len(thoughts),
        "categories": THOUGHT_CATEGORIES,
        "priorities": THOUGHT_PRIORITIES,
    }


@router.post("/thoughts/{thought_id}/act")
async def act_on_thought(thought_id: int):
    """Mark a thought as acted upon."""
    from .loops import mark_thought_acted
    
    success = mark_thought_acted(thought_id)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Thought {thought_id} not found")
    
    return {"status": "marked", "thought_id": thought_id}


@router.post("/thoughts/think-now")
async def trigger_thought_cycle():
    """
    Manually trigger one thought cycle immediately.
    Returns the thoughts generated (if any).
    """
    from . import _loop_manager
    from .loops import get_thought_log
    
    if not _loop_manager:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Loops not started")
    
    thought_loop = _loop_manager.get_loop("thought")
    if not thought_loop:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Thought loop not found")
    
    # Get thought count before
    before = get_thought_log(limit=1)
    before_id = before[0]["id"] if before else 0
    
    # Run one cycle
    try:
        thought_loop.task()
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Thought cycle failed: {e}")
    
    # Get new thoughts
    new_thoughts = get_thought_log(limit=5)
    new_thoughts = [t for t in new_thoughts if t["id"] > before_id]
    
    return {
        "status": "completed",
        "new_thoughts": new_thoughts,
        "count": len(new_thoughts),
    }


# ─────────────────────────────────────────────────────────────
# Task Planner endpoints
# ─────────────────────────────────────────────────────────────

class CreateTaskRequest(BaseModel):
    goal: str
    execute_now: bool = False


@router.post("/tasks")
async def create_new_task(req: CreateTaskRequest):
    """
    Create a new task for the planner.
    
    If execute_now=True, the task is immediately planned and executed
    (synchronous — may take a while for multi-step tasks).
    Otherwise, the task is queued for the background planner loop.
    """
    from .loops import create_task
    
    if not req.goal.strip():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Goal cannot be empty")
    
    task = create_task(req.goal.strip(), source="api")
    
    if req.execute_now:
        from . import _loop_manager
        if _loop_manager:
            planner = _loop_manager.get_loop("task_planner")
            if planner and hasattr(planner, 'execute_task'):
                task = planner.execute_task(task["id"])
            else:
                # No planner loop — create ad-hoc planner and execute
                from .loops import TaskPlanner
                adhoc = TaskPlanner(enabled=False)
                task = adhoc.execute_task(task["id"])
        else:
            from .loops import TaskPlanner
            adhoc = TaskPlanner(enabled=False)
            task = adhoc.execute_task(task["id"])
    
    return task


@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    List tasks, optionally filtered by status.
    
    Status values: pending, planning, executing, completed, failed, cancelled
    """
    from .loops import get_tasks, TASK_STATUSES
    
    if status and status not in TASK_STATUSES:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {TASK_STATUSES}")
    
    tasks = get_tasks(status=status, limit=limit)
    return {
        "tasks": tasks,
        "count": len(tasks),
        "statuses": TASK_STATUSES,
    }


@router.get("/tasks/{task_id}")
async def get_single_task(task_id: int):
    """Get a single task by ID with full step details."""
    from .loops import get_task
    
    task = get_task(task_id)
    if not task:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return task


@router.post("/tasks/{task_id}/execute")
async def execute_task_now(task_id: int):
    """
    Execute a pending task immediately (synchronous).
    Returns the completed/failed task state.
    """
    from .loops import get_task, TaskPlanner
    from . import _loop_manager
    
    task = get_task(task_id)
    if not task:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    if task["status"] not in ("pending", "executing"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Task status is '{task['status']}', cannot execute")
    
    if _loop_manager:
        planner = _loop_manager.get_loop("task_planner")
        if planner and hasattr(planner, 'execute_task'):
            result = planner.execute_task(task_id)
            return result
    
    # Fallback: ad-hoc planner
    adhoc = TaskPlanner(enabled=False)
    return adhoc.execute_task(task_id)


@router.post("/tasks/{task_id}/cancel")
async def cancel_task_endpoint(task_id: int):
    """Cancel a pending or executing task."""
    from .loops import cancel_task
    
    success = cancel_task(task_id)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Cannot cancel — task not found or already completed/failed")
    
    return {"status": "cancelled", "task_id": task_id}


# ─────────────────────────────────────────────────────────────
# Goals
# ─────────────────────────────────────────────────────────────

@router.get("/goals")
async def list_goals(status: str = "pending", limit: int = 20):
    """List proposed goals, default pending."""
    from .loops.goals import get_proposed_goals
    return get_proposed_goals(status=status, limit=limit)


@router.post("/goals/{goal_id}/resolve")
async def resolve_goal_endpoint(goal_id: int, action: str = "approved"):
    """Approve, reject, or dismiss a proposed goal."""
    from .loops.goals import resolve_goal
    if action not in ("approved", "rejected", "dismissed"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="action must be approved, rejected, or dismissed")
    ok = resolve_goal(goal_id, status=action)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Goal not found or already resolved")
    return {"status": action, "goal_id": goal_id}


# ─────────────────────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────────────────────

@router.get("/notifications")
async def list_notifications(limit: int = 20, unread_only: bool = False):
    """List notifications for the user."""
    from agent.threads.form.tools.executables.notify import _list_notifications
    # _list_notifications returns a string, but we want structured data
    from agent.threads.form.tools.executables.notify import _ensure_notifications_table
    _ensure_notifications_table()
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        if unread_only:
            cur.execute(
                "SELECT id, type, message, priority, read, dismissed, response, created_at "
                "FROM notifications WHERE read = 0 AND dismissed = 0 ORDER BY id DESC LIMIT ?",
                (limit,)
            )
        else:
            cur.execute(
                "SELECT id, type, message, priority, read, dismissed, response, created_at "
                "FROM notifications ORDER BY id DESC LIMIT ?",
                (limit,)
            )
        return [
            {"id": r[0], "type": r[1], "message": r[2], "priority": r[3],
             "read": bool(r[4]), "dismissed": bool(r[5]), "response": r[6], "created_at": r[7]}
            for r in cur.fetchall()
        ]


@router.post("/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: int):
    """Mark a notification as read."""
    from agent.threads.form.tools.executables.notify import _ensure_notifications_table
    _ensure_notifications_table()
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE notifications SET read = 1 WHERE id = ?", (notif_id,))
        conn.commit()
        if cur.rowcount == 0:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "read", "id": notif_id}


@router.post("/notifications/{notif_id}/dismiss")
async def dismiss_notification(notif_id: int):
    """Dismiss a notification."""
    from agent.threads.form.tools.executables.notify import _ensure_notifications_table
    _ensure_notifications_table()
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE notifications SET dismissed = 1 WHERE id = ?", (notif_id,))
        conn.commit()
        if cur.rowcount == 0:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "dismissed", "id": notif_id}


@router.post("/notifications/{notif_id}/respond")
async def respond_to_notification(notif_id: int, body: Dict[str, Any]):
    """Respond to a confirm-type notification."""
    response = body.get("response", "")
    from agent.threads.form.tools.executables.notify import _ensure_notifications_table
    _ensure_notifications_table()
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE notifications SET response = ?, read = 1 WHERE id = ? AND type = 'confirm'",
            (response, notif_id)
        )
        conn.commit()
        if cur.rowcount == 0:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Confirm notification not found")
    return {"status": "responded", "id": notif_id, "response": response}


# ─────────────────────────────────────────────────────────────
# Self-Improvements
# ─────────────────────────────────────────────────────────────

@router.get("/improvements")
async def list_improvements(status: str = "pending", limit: int = 20):
    """List proposed code improvements."""
    from .loops.self_improve import get_proposed_improvements
    return get_proposed_improvements(status=status, limit=limit)


@router.post("/improvements/{imp_id}/resolve")
async def resolve_improvement_endpoint(imp_id: int, action: str = "approved"):
    """Approve or reject a proposed improvement."""
    from .loops.self_improve import resolve_improvement
    if action not in ("approved", "rejected"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="action must be approved or rejected")
    ok = resolve_improvement(imp_id, status=action)
    if not ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Improvement not found or already resolved")
    return {"status": action, "improvement_id": imp_id}


@router.post("/improvements/{imp_id}/apply")
async def apply_improvement_endpoint(imp_id: int):
    """Apply an approved improvement (writes the file change)."""
    from .loops.self_improve import apply_improvement, resolve_improvement
    # Ensure it's approved first
    resolve_improvement(imp_id, status="approved")
    result = apply_improvement(imp_id)
    return {"status": "applied", "improvement_id": imp_id, "result": result}


# ─────────────────────────────────────────────────────────────
# Backfill — conversation concept extraction
# ─────────────────────────────────────────────────────────────

@router.get("/backfill")
async def get_backfill_status_endpoint():
    """Get conversation concept backfill progress."""
    from .loops.convo_concepts import get_backfill_status
    return get_backfill_status()


@router.post("/backfill/run")
async def run_backfill_batch():
    """Process one batch of un-extracted conversations."""
    from .loops.convo_concepts import ConvoConceptLoop, get_backfill_status
    loop = ConvoConceptLoop(enabled=False)
    loop._process_batch()
    return {**loop.stats, **get_backfill_status()}


@router.post("/backfill/reset")
async def reset_backfill_endpoint():
    """Reset backfill progress so all conversations are reprocessed."""
    from .loops.convo_concepts import reset_backfill, get_backfill_status
    reset_backfill()
    return get_backfill_status()


# ─────────────────────────────────────────────────────────────
# Notes — simple user scratch notes
# ─────────────────────────────────────────────────────────────

def _ensure_notes_table():
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()


class NoteCreate(BaseModel):
    text: str

class NoteUpdate(BaseModel):
    text: str


@router.get("/notes")
async def list_notes():
    """List all user notes, newest first."""
    _ensure_notes_table()
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute(
            "SELECT id, text, created_at, updated_at FROM user_notes ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


@router.post("/notes")
async def create_note(body: NoteCreate):
    """Create a new note."""
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Note cannot be empty")
    _ensure_notes_table()
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection()) as conn:
        cur = conn.execute(
            "INSERT INTO user_notes (text) VALUES (?)", (body.text.strip(),)
        )
        conn.commit()
        return {"id": cur.lastrowid, "text": body.text.strip(), "status": "created"}


@router.put("/notes/{note_id}")
async def update_note(note_id: int, body: NoteUpdate):
    """Update an existing note."""
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Note cannot be empty")
    _ensure_notes_table()
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection()) as conn:
        cur = conn.execute(
            "UPDATE user_notes SET text = ?, updated_at = datetime('now') WHERE id = ?",
            (body.text.strip(), note_id)
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"id": note_id, "status": "updated"}


@router.delete("/notes/{note_id}")
async def delete_note(note_id: int):
    """Delete a note."""
    _ensure_notes_table()
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection()) as conn:
        cur = conn.execute("DELETE FROM user_notes WHERE id = ?", (note_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"id": note_id, "status": "deleted"}


# ─────────────────────────────────────────────────────────────
# Evolution — autonomous self-improvement showdown
# ─────────────────────────────────────────────────────────────

@router.get("/evolution")
async def get_evolution_log_endpoint(limit: int = 50):
    """Get the evolution log (all cycles, most recent first)."""
    from .loops.evolve import get_evolution_log
    return {"log": get_evolution_log(limit=limit)}


@router.post("/evolution/trigger")
async def trigger_evolution_cycle():
    """Manually trigger one evolution cycle (for testing)."""
    from .loops.evolve import _run_evolution_cycle
    import os
    provider = os.getenv("AIOS_MODEL_PROVIDER", "ollama")
    model = os.getenv("AIOS_MODEL_NAME", "qwen2.5:7b")
    result = _run_evolution_cycle(cycle=0, provider=provider, model=model)
    return {"result": result}


# ─────────────────────────────────────────────────────────────
# Redeploy — pull latest code and restart the service
# ─────────────────────────────────────────────────────────────

@router.post("/redeploy")
async def redeploy():
    """Pull latest git changes and restart the systemd service.

    This is used by the evolution loop's optional auto-restart,
    and can be called manually from the mobile dashboard.
    """
    import subprocess
    from pathlib import Path

    workspace = Path(__file__).resolve().parents[2]  # → AI_OS/

    steps = []

    # 1. Git pull
    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=str(workspace), capture_output=True, text=True, timeout=30,
        )
        steps.append({"step": "git_pull", "ok": result.returncode == 0,
                       "output": (result.stdout + result.stderr).strip()[:500]})
    except Exception as e:
        steps.append({"step": "git_pull", "ok": False, "output": str(e)})

    # 2. Sync dependencies
    try:
        result = subprocess.run(
            ["uv", "sync", "--frozen", "--no-dev"],
            cwd=str(workspace), capture_output=True, text=True, timeout=120,
        )
        steps.append({"step": "uv_sync", "ok": result.returncode == 0,
                       "output": (result.stdout + result.stderr).strip()[:500]})
    except Exception as e:
        steps.append({"step": "uv_sync", "ok": False, "output": str(e)})

    # 3. Restart service (systemd)
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "restart", "aios"],
            capture_output=True, text=True, timeout=10,
        )
        steps.append({"step": "restart", "ok": result.returncode == 0,
                       "output": (result.stdout + result.stderr).strip()[:500]})
    except Exception as e:
        steps.append({"step": "restart", "ok": False, "output": str(e)})

    all_ok = all(s["ok"] for s in steps)
    return {"status": "ok" if all_ok else "partial_failure", "steps": steps}


# ─────────────────────────────────────────────────────────────
# Heartbeat (dashboard visibility for the 60s conductor)
# ─────────────────────────────────────────────────────────────

@router.get("/heartbeat")
async def heartbeat_latest():
    """Latest heartbeat snapshot + tick summary.

    Returns an object the dashboard can render as a single card:
        {
          "enabled": bool,
          "interval_seconds": float | None,
          "last_tick": {"id", "ts", "snapshot", "actions", "duration_ms"} | None,
          "stats": {...}  # BackgroundLoop stats for "heartbeat"
        }
    """
    try:
        from .heartbeat import get_recent_ticks
        from . import _loop_manager
        ticks = get_recent_ticks(limit=1)
        last = ticks[0] if ticks else None
        stats = {}
        interval = None
        enabled = False
        if _loop_manager is not None:
            loop = _loop_manager.get_loop("heartbeat")
            if loop is not None:
                stats = loop.stats
                interval = stats.get("interval")
                enabled = stats.get("status") == "running"
        return {
            "enabled": enabled,
            "interval_seconds": interval,
            "last_tick": last,
            "stats": stats,
        }
    except Exception as e:
        return {"enabled": False, "error": str(e)}


@router.get("/heartbeat/ticks")
async def heartbeat_ticks(limit: int = Query(50, ge=1, le=500)):
    """Recent heartbeat ticks for the dashboard timeline."""
    try:
        from .heartbeat import get_recent_ticks
        ticks = get_recent_ticks(limit=limit)
        return {"ticks": ticks, "count": len(ticks)}
    except Exception as e:
        return {"ticks": [], "error": str(e)}


@router.get("/heartbeat/snapshot")
async def heartbeat_snapshot_now():
    """Compute and return a fresh snapshot without writing a tick.
    Useful for the dashboard 'peek' button.
    """
    try:
        from .heartbeat import build_snapshot
        return {"snapshot": build_snapshot()}
    except Exception as e:
        return {"snapshot": {}, "error": str(e)}


@router.post("/heartbeat/tick")
async def heartbeat_tick_now():
    """Force a heartbeat tick right now (bypasses the 60s timer).
    Useful for testing faculties from the dashboard.
    """
    try:
        from . import _loop_manager
        if _loop_manager is None:
            return {"status": "no_manager"}
        loop = _loop_manager.get_loop("heartbeat")
        if loop is None:
            return {"status": "not_running"}
        # Call the task directly (bypasses pool, runs on caller thread)
        summary = loop.task()  # type: ignore[attr-defined]
        return {"status": "ok", "summary": summary}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─────────────────────────────────────────────────────────────
# Goals — risk + manual promotion
# ─────────────────────────────────────────────────────────────

@router.get("/goals/full")
async def goals_full(status: Optional[str] = None, limit: int = 50):
    """Goals with risk + auto_promoted + timestamps for dashboard."""
    from data.db import get_connection
    from contextlib import closing
    try:
        from .faculties import _ensure_risk_column
        _ensure_risk_column()
    except Exception:
        pass
    try:
        with closing(get_connection(readonly=True)) as conn:
            if status:
                rows = conn.execute(
                    "SELECT id, goal, rationale, priority, status, "
                    "       COALESCE(risk,'medium'), COALESCE(auto_promoted,0), "
                    "       created_at, resolved_at "
                    "FROM proposed_goals WHERE status=? "
                    "ORDER BY id DESC LIMIT ?",
                    (status, int(limit)),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, goal, rationale, priority, status, "
                    "       COALESCE(risk,'medium'), COALESCE(auto_promoted,0), "
                    "       created_at, resolved_at "
                    "FROM proposed_goals ORDER BY id DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
            return [
                {"id": r[0], "goal": r[1], "rationale": r[2],
                 "priority": r[3], "status": r[4], "risk": r[5],
                 "auto_promoted": bool(r[6]),
                 "created_at": r[7], "resolved_at": r[8]}
                for r in rows
            ]
    except Exception as e:
        return {"error": str(e), "goals": []}


@router.post("/goals/{goal_id}/risk")
async def set_goal_risk(goal_id: int, body: Dict[str, Any]):
    """Set or override a goal's risk tier (low|medium|high)."""
    risk = (body or {}).get("risk", "").lower().strip()
    from .faculties import RISK_TIERS, _ensure_risk_column
    if risk not in RISK_TIERS:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"risk must be one of {RISK_TIERS}",
        )
    _ensure_risk_column()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE proposed_goals SET risk=? WHERE id=?",
                (risk, goal_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Goal not found")
        return {"status": "ok", "goal_id": goal_id, "risk": risk}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/goals/{goal_id}/promote")
async def promote_goal_now(goal_id: int):
    """Manually promote an approved goal to a task, bypassing faculty."""
    from data.db import get_connection
    from contextlib import closing
    from .loops.task_planner import create_task
    try:
        with closing(get_connection()) as conn:
            row = conn.execute(
                "SELECT goal, status, COALESCE(risk,'medium'), "
                "       COALESCE(auto_promoted,0) "
                "FROM proposed_goals WHERE id=?",
                (goal_id,),
            ).fetchone()
            if not row:
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Goal not found")
            goal, status, risk, promoted = row
            if status != "approved":
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=400,
                    detail=f"Goal must be approved (current: {status})",
                )
            t = create_task(goal=goal or "(unnamed)",
                            source=f"manual_promote:{risk}")
            conn.execute(
                "UPDATE proposed_goals SET auto_promoted=1 WHERE id=?",
                (goal_id,),
            )
            conn.commit()
        return {"status": "promoted",
                "goal_id": goal_id,
                "task_id": t.get("id") if isinstance(t, dict) else None,
                "risk": risk}
    except Exception as e:
        from fastapi import HTTPException
        if hasattr(e, "status_code"):
            raise
        raise HTTPException(status_code=500, detail=str(e))
