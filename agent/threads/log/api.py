"""
Log Thread API
==============
Endpoints for event logging, timeline, and session management.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from .schema import (
    # Event operations
    log_event, get_events, delete_event, clear_events,
    get_user_timeline, get_system_log, search_events,
    # Session operations
    create_session, end_session, get_active_sessions,
    # Log module operations
    pull_log_events, push_log_entry, get_log_entry, delete_log_entry,
    # Stats and metadata
    get_log_stats, get_event_types, get_sources,
    # System log operations
    log_system_event, get_system_logs,
    # Server log operations
    log_server_request, get_server_logs, get_server_stats,
)

router = APIRouter(prefix="/api/log", tags=["log"])


# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────

class EventCreate(BaseModel):
    event_type: str
    data: str
    metadata: Optional[Dict[str, Any]] = None
    source: str = "api"
    session_id: Optional[str] = None
    related_key: Optional[str] = None
    related_table: Optional[str] = None
    # Thread + tag layer
    thread_subject: Optional[str] = None
    tags: Optional[List[str]] = None
    # Predated timestamp (ISO string). When omitted server uses CURRENT_TIMESTAMP.
    timestamp: Optional[str] = None


class LogEntryCreate(BaseModel):
    module: str
    key: str
    metadata: Dict[str, Any] = {}
    data: Dict[str, Any] = {}
    weight: float = 1.0


class SessionCreate(BaseModel):
    session_id: str
    metadata: Optional[Dict[str, Any]] = None


# ─────────────────────────────────────────────────────────────
# Event Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/events")
async def list_events(
    event_type: Optional[str] = None,
    source: Optional[str] = None,
    session_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    thread_subject: Optional[str] = None,
    tag: Optional[List[str]] = Query(None, description="Repeat ?tag=foo&tag=bar for any-match"),
    order: str = Query("DESC", pattern="^(?i)(ASC|DESC)$"),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Query events from the unified log.

    Filters:
    - event_type: convo, system, user_action, file, memory, activation, milestone, ...
    - source: system | machine | user | local | web_public | daemon | agent | api
    - session_id: Group by session
    - since / until: ISO timestamp range
    - thread_subject: exact match on thread name (e.g. "jake_retainer")
    - tag: any-match against tags_json (repeatable query param)
    - order: ASC for chronological reconstruction, DESC for newest-first (default)
    """
    events = get_events(
        event_type=event_type,
        source=source,
        session_id=session_id,
        since=since,
        until=until,
        thread_subject=thread_subject,
        tags_any=tag,
        order=order,
        limit=limit,
    )
    return {"events": events, "count": len(events)}


@router.post("/events")
async def create_event(event: EventCreate):
    """Log a new event. Supports thread_subject, tags, and predated timestamp."""
    event_id = log_event(
        event_type=event.event_type,
        data=event.data,
        metadata=event.metadata,
        source=event.source,
        session_id=event.session_id,
        related_key=event.related_key,
        related_table=event.related_table,
        thread_subject=event.thread_subject,
        tags=event.tags,
        timestamp=event.timestamp,
    )
    return {"status": "created", "event_id": event_id}


@router.delete("/events/{event_id}")
async def remove_event(event_id: int):
    """Delete an event by ID."""
    if delete_event(event_id):
        return {"status": "deleted", "event_id": event_id}
    raise HTTPException(status_code=404, detail="Event not found")


@router.delete("/events")
async def clear_events_endpoint(
    event_type: Optional[str] = None,
    before: Optional[str] = None
):
    """
    Clear events.
    
    - event_type: Only clear this type
    - before: Clear events before this timestamp
    """
    count = clear_events(event_type=event_type, before=before)
    return {"status": "cleared", "count": count}


@router.get("/events/search")
async def search_events_endpoint(
    q: str,
    limit: int = Query(50, ge=1, le=500)
):
    """Search events by text content."""
    events = search_events(q, limit=limit)
    return {"query": q, "events": events, "count": len(events)}


# ─────────────────────────────────────────────────────────────
# Timeline Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/timeline")
async def get_timeline(limit: int = Query(50, ge=1, le=200)):
    """
    Get user-facing timeline.
    
    Returns events a user would care about:
    conversations, memories, user actions, file operations.
    """
    timeline = get_user_timeline(limit=limit)
    return {"timeline": timeline, "count": len(timeline)}


@router.get("/system")
async def get_system_log_endpoint(limit: int = Query(100, ge=1, le=1000)):
    """
    Get full system log (for debugging).
    
    Includes all events with full metadata.
    """
    events = get_system_log(limit=limit)
    return {"events": events, "count": len(events)}


# ─────────────────────────────────────────────────────────────
# Daemon/Infrastructure Log Endpoints (log_system table)
# ─────────────────────────────────────────────────────────────

class SystemLogCreate(BaseModel):
    level: str = "info"
    message: str
    source: str = "api"
    metadata: Optional[Dict[str, Any]] = None


@router.get("/daemon")
async def list_daemon_logs(
    level: Optional[str] = None,
    source: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000)
):
    """
    Query daemon/infrastructure logs.
    
    Filters:
    - level: debug, info, warning, error, critical
    - source: daemon, scheduler, watcher, etc
    - since: ISO timestamp
    """
    logs = get_system_logs(
        level=level,
        source=source,
        since=since,
        limit=limit
    )
    return {"logs": logs, "count": len(logs)}


@router.post("/daemon")
async def create_daemon_log(entry: SystemLogCreate):
    """Log a daemon/infrastructure event."""
    log_id = log_system_event(
        level=entry.level,
        message=entry.message,
        source=entry.source,
        metadata=entry.metadata
    )
    return {"status": "created", "log_id": log_id}


# ─────────────────────────────────────────────────────────────
# Server/HTTP Log Endpoints (log_server table)
# ─────────────────────────────────────────────────────────────

@router.get("/server")
async def list_server_logs(
    level: Optional[str] = None,
    method: Optional[str] = None,
    path_prefix: Optional[str] = None,
    status_code: Optional[int] = None,
    errors_only: bool = False,
    since: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000)
):
    """
    Query HTTP server logs.
    
    Filters:
    - level: info, warning, error
    - method: GET, POST, PUT, DELETE
    - path_prefix: Filter by path start (e.g., "/api/feeds")
    - status_code: Exact status code
    - errors_only: Only 4xx and 5xx responses
    - since: ISO timestamp
    """
    logs = get_server_logs(
        level=level,
        method=method,
        path_prefix=path_prefix,
        status_code=status_code,
        errors_only=errors_only,
        since=since,
        limit=limit
    )
    return {"logs": logs, "count": len(logs)}


@router.get("/server/stats")
async def server_statistics(since: Optional[str] = None):
    """
    Get server statistics for monitoring.
    
    Returns request counts, error rates, avg duration, top paths.
    Use `since` to limit time window (e.g., last hour).
    """
    stats = get_server_stats(since=since)
    return stats


# ─────────────────────────────────────────────────────────────
# Session Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(active_only: bool = False):
    """List sessions."""
    if active_only:
        sessions = get_active_sessions()
    else:
        sessions = pull_log_events(module_name="sessions", limit=100)
    return {"sessions": sessions, "count": len(sessions)}


@router.post("/sessions")
async def start_session(session: SessionCreate):
    """Create a new session."""
    if create_session(session.session_id, session.metadata):
        return {"status": "created", "session_id": session.session_id}
    raise HTTPException(status_code=500, detail="Failed to create session")


@router.put("/sessions/{session_id}/end")
async def stop_session(session_id: str):
    """End a session."""
    if end_session(session_id):
        return {"status": "ended", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Session not found")


# ─────────────────────────────────────────────────────────────
# Log Module Endpoints (for direct module access)
# ─────────────────────────────────────────────────────────────

@router.get("/modules/{module}")
async def get_module_entries(
    module: str,
    limit: int = Query(50, ge=1, le=500),
    min_weight: float = Query(0.0, ge=0, le=1)
):
    """Get entries from a specific log module (events, sessions, temporal)."""
    entries = pull_log_events(module_name=module, limit=limit, min_weight=min_weight)
    return {"module": module, "entries": entries, "count": len(entries)}


@router.get("/modules/{module}/{key}")
async def get_module_entry(module: str, key: str):
    """Get a specific entry from a log module."""
    entry = get_log_entry(module, key)
    if entry:
        return entry
    raise HTTPException(status_code=404, detail="Entry not found")


@router.post("/modules")
async def push_module_entry(entry: LogEntryCreate):
    """Push an entry to a log module."""
    if push_log_entry(entry.module, entry.key, entry.metadata, entry.data, entry.weight):
        return {"status": "created", "module": entry.module, "key": entry.key}
    raise HTTPException(status_code=500, detail="Failed to create entry")


@router.delete("/modules/{module}/{key}")
async def remove_module_entry(module: str, key: str):
    """Delete an entry from a log module."""
    if delete_log_entry(module, key):
        return {"status": "deleted", "module": module, "key": key}
    raise HTTPException(status_code=404, detail="Entry not found")


# ─────────────────────────────────────────────────────────────
# Metadata Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/types")
async def list_event_types():
    """Get list of event types."""
    types = get_event_types()
    return {"types": types}


@router.get("/sources")
async def list_sources():
    """Get list of event sources."""
    sources = get_sources()
    return {"sources": sources}


# ─────────────────────────────────────────────────────────────
# Stats Endpoint
# ─────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats():
    """Get log statistics."""
    return get_log_stats()


# ─────────────────────────────────────────────────────────────
# Introspection (Thread owns its state block)
# ─────────────────────────────────────────────────────────────

@router.get("/introspect")
async def introspect_log(level: int = 2, query: Optional[str] = None):
    """
    Get log thread's contribution to STATE block.
    
    Each thread is responsible for building its own state.
    If query provided, filters to relevant events via LinkingCore.
    """
    from .adapter import LogThreadAdapter
    adapter = LogThreadAdapter()
    result = adapter.introspect(context_level=level, query=query)
    return result.to_dict()


@router.get("/health")
async def get_log_health():
    """Get log thread health status."""
    from .adapter import LogThreadAdapter
    adapter = LogThreadAdapter()
    return adapter.health().to_dict()


# ─────────────────────────────────────────────────────────────
# Function Call Tracing
# ─────────────────────────────────────────────────────────────

@router.get("/functions")
async def get_function_call_logs(
    function_name: Optional[str] = None,
    module: Optional[str] = None,
    limit: int = 100,
    since: Optional[str] = None,
):
    """Query function call trace logs."""
    from .schema import get_function_calls
    calls = get_function_calls(
        function_name=function_name,
        module=module,
        limit=limit,
        since=since,
    )
    return {"calls": calls, "count": len(calls)}


@router.delete("/functions/cleanup")
async def cleanup_function_logs(older_than_days: int = 30):
    """Remove old function call logs."""
    from .schema import cleanup_old_function_logs
    deleted = cleanup_old_function_logs(older_than_days=older_than_days)
    return {"deleted": deleted}


# ─────────────────────────────────────────────────────────────
# Log Tables Discovery
# ─────────────────────────────────────────────────────────────

@router.get("/tables")
async def list_log_tables():
    """List all log tables with row counts for the log dashboard."""
    from .schema import get_connection
    from contextlib import closing

    tables = []
    # Core tables with known schemas
    core_tables = {
        "unified_events": {"icon": "📋", "label": "Events", "columns": ["id", "timestamp", "event_type", "source", "data", "session_id"]},
        "log_system": {"icon": "🖥️", "label": "System / Daemon", "columns": ["id", "timestamp", "level", "source", "message"]},
        "log_server": {"icon": "🌐", "label": "Server / HTTP", "columns": ["id", "timestamp", "method", "path", "status_code", "duration_ms"]},
        "log_function_calls": {"icon": "🔍", "label": "Function Calls", "columns": ["id", "timestamp", "function_name", "module", "duration_ms", "success"]},
        "log_llm_inference": {"icon": "🧠", "label": "LLM Inference", "columns": ["id", "timestamp", "model", "prompt_tokens", "completion_tokens", "latency_ms", "success"]},
        "log_activations": {"icon": "⚡", "label": "Activations", "columns": ["id", "timestamp", "concept_a", "concept_b", "activation_type", "strength_delta", "trigger"]},
        "log_loop_runs": {"icon": "🔄", "label": "Loop Runs", "columns": ["id", "timestamp", "loop_name", "status", "duration_ms", "items_processed"]},
    }

    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        # Get all tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'log_%' ORDER BY name")
        db_tables = [r[0] for r in cur.fetchall()]

        # Also include unified_events
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='unified_events'")
        if cur.fetchone():
            db_tables = ["unified_events"] + db_tables

        for tname in db_tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM [{tname}]")
                count = cur.fetchone()[0]
            except Exception:
                count = 0

            if tname in core_tables:
                info = core_tables[tname]
                tables.append({"name": tname, "count": count, "icon": info["icon"], "label": info["label"], "columns": info["columns"]})
            else:
                # Dynamic module tables (log_events, log_sessions, log_temporal, etc.)
                label = tname.replace("log_", "").replace("_", " ").title()
                tables.append({"name": tname, "count": count, "icon": "📦", "label": label, "columns": ["key", "created_at", "weight", "metadata_json", "data_json"]})

    return {"tables": tables}


# ─────────────────────────────────────────────────────────────
# LLM Inference Log Endpoints
# ─────────────────────────────────────────────────────────────

class LLMLogCreate(BaseModel):
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0
    success: bool = True
    error: Optional[str] = None
    caller: Optional[str] = None
    provider: str = "local"
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.get("/llm")
async def list_llm_calls(
    model: Optional[str] = None,
    caller: Optional[str] = None,
    success_only: bool = False,
    since: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
):
    """Query LLM inference logs."""
    from .schema import get_llm_calls
    calls = get_llm_calls(
        model=model, caller=caller,
        success_only=success_only, since=since, limit=limit,
    )
    return {"calls": calls, "count": len(calls)}


@router.post("/llm")
async def create_llm_log(entry: LLMLogCreate):
    """Log an LLM inference call."""
    from .schema import log_llm_call
    log_id = log_llm_call(
        model=entry.model,
        prompt_tokens=entry.prompt_tokens,
        completion_tokens=entry.completion_tokens,
        latency_ms=entry.latency_ms,
        success=entry.success,
        error=entry.error,
        caller=entry.caller,
        provider=entry.provider,
        session_id=entry.session_id,
        metadata=entry.metadata,
    )
    return {"status": "created", "log_id": log_id}


@router.get("/llm/stats")
async def llm_statistics(since: Optional[str] = None):
    """
    LLM usage statistics — calls, tokens, latency, error rate per model.
    Use for self-diagnosis and model switching decisions.
    """
    from .schema import get_llm_stats
    return get_llm_stats(since=since)


# ─────────────────────────────────────────────────────────────
# Activation Log Endpoints
# ─────────────────────────────────────────────────────────────

class ActivationLogCreate(BaseModel):
    concept_a: str
    concept_b: Optional[str] = None
    activation_type: str = "spread"
    strength_before: Optional[float] = None
    strength_after: Optional[float] = None
    trigger: Optional[str] = None
    hops: int = 1
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.get("/activations")
async def list_activations(
    concept: Optional[str] = None,
    activation_type: Optional[str] = None,
    trigger: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
):
    """Query concept activation logs."""
    from .schema import get_activations
    acts = get_activations(
        concept=concept, activation_type=activation_type,
        trigger=trigger, since=since, limit=limit,
    )
    return {"activations": acts, "count": len(acts)}


@router.post("/activations")
async def create_activation_log(entry: ActivationLogCreate):
    """Log a concept activation event."""
    from .schema import log_activation
    log_id = log_activation(
        concept_a=entry.concept_a,
        concept_b=entry.concept_b,
        activation_type=entry.activation_type,
        strength_before=entry.strength_before,
        strength_after=entry.strength_after,
        trigger=entry.trigger,
        hops=entry.hops,
        session_id=entry.session_id,
        metadata=entry.metadata,
    )
    return {"status": "created", "log_id": log_id}


@router.get("/activations/stats")
async def activation_statistics(since: Optional[str] = None):
    """Activation statistics — top concepts, type breakdown."""
    from .schema import get_activation_stats
    return get_activation_stats(since=since)


# ─────────────────────────────────────────────────────────────
# Loop Run Log Endpoints
# ─────────────────────────────────────────────────────────────

class LoopRunCreate(BaseModel):
    loop_name: str
    status: str = "completed"
    duration_ms: float = 0
    items_processed: int = 0
    items_changed: int = 0
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@router.get("/loops")
async def list_loop_runs(
    loop_name: Optional[str] = None,
    status: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
):
    """Query subconscious loop run logs."""
    from .schema import get_loop_runs
    runs = get_loop_runs(
        loop_name=loop_name, status=status,
        since=since, limit=limit,
    )
    return {"runs": runs, "count": len(runs)}


@router.post("/loops")
async def create_loop_run(entry: LoopRunCreate):
    """Log a subconscious loop execution."""
    from .schema import log_loop_run
    log_id = log_loop_run(
        loop_name=entry.loop_name,
        status=entry.status,
        duration_ms=entry.duration_ms,
        items_processed=entry.items_processed,
        items_changed=entry.items_changed,
        error=entry.error,
        metadata=entry.metadata,
    )
    return {"status": "created", "log_id": log_id}


@router.get("/loops/stats")
async def loop_statistics(since: Optional[str] = None):
    """Loop statistics — runs per loop, avg duration, error rates."""
    from .schema import get_loop_stats
    return get_loop_stats(since=since)
