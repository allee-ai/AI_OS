"""
Introspection API - Exposes Subconscious State to Frontend
==========================================================
FastAPI router providing visibility into Nola's internal state:
- Identity facts (idv2)
- Log thread events
- Thread health status
- Context level assembly

This is the "brain viewer" endpoint - lets the UI show what Nola knows.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
import sys
import threading
from pathlib import Path

# Ensure project root is on path before importing Nola.*
project_root_bootstrap = Path(__file__).resolve().parents[4]
if str(project_root_bootstrap) not in sys.path:
    sys.path.insert(0, str(project_root_bootstrap))

from Nola.path_utils import ensure_project_root_on_path, ensure_nola_root_on_path, warn_if_not_venv

project_root = ensure_project_root_on_path(Path(__file__).resolve())
ensure_nola_root_on_path(Path(__file__).resolve())
_venv_warning = warn_if_not_venv(project_root)
if _venv_warning:
    print(f"⚠️  {_venv_warning}")

router = APIRouter(prefix="/api/introspection", tags=["introspection"])

# ========== Consolidation Counter ==========
# Track introspection calls and auto-consolidate every N calls
_introspection_call_count = 0
_introspection_lock = threading.Lock()
CONSOLIDATE_EVERY_N_CALLS = 5


# ========== Pydantic Models ==========

class ThreadHealth(BaseModel):
    """Health status for a single thread adapter."""
    name: str
    status: str  # "ok", "degraded", "error"
    message: str
    last_sync: Optional[str] = None
    details: Dict[str, Any] = {}


class IdentityFact(BaseModel):
    """A single fact from identity introspection."""
    source: str  # "machineID", "userID", "config"
    fact: str
    context_level: int


class LogEvent(BaseModel):
    """A recent log event."""
    timestamp: str
    event_type: str
    source: str
    message: str
    level: str = "INFO"


class AddEventRequest(BaseModel):
    """Request body for manually adding a log event."""
    event_type: str
    data: str
    source: str = "local"
    metadata: Optional[dict] = None
    session_id: Optional[str] = None
    related_key: Optional[str] = None
    related_table: Optional[str] = None


class ContextAssembly(BaseModel):
    """Assembled context from subconscious."""
    level: int
    facts: List[str]
    fact_count: int
    thread_count: int
    timestamp: str


class RelevanceScore(BaseModel):
    """Top relevance scores for identity keys."""
    key: str
    score: float
    weight: float = 0.5
    context_level: int = 2
    updated_at: Optional[str] = None


class IntrospectionResponse(BaseModel):
    """Full introspection response for the viewer."""
    status: str  # "awake", "asleep", "error"
    wake_time: Optional[str] = None
    overall_health: str  # "healthy", "degraded", "error"
    
    # Thread-level data
    threads: Dict[str, ThreadHealth] = {}
    
    # Identity facts
    identity_facts: List[IdentityFact] = []
    
    # Recent events
    recent_events: List[LogEvent] = []
    
    # Context assembly preview
    context: Optional[ContextAssembly] = None
    
    # Session info
    session_id: Optional[str] = None
    context_level: int = 2

    # Relevance (top-k)
    relevance_scores: List[RelevanceScore] = []


class ConsolidationResponse(BaseModel):
    """Response from consolidation endpoint."""
    success: bool
    facts_processed: int = 0
    promoted_l2: int = 0
    promoted_l3: int = 0
    discarded: int = 0
    message: str = ""


# ========== Helper Functions ==========

def _get_subconscious_status() -> Dict[str, Any]:
    """Get status from subconscious core."""
    try:
        # Always use Nola.subconscious to ensure we get the same singleton
        from Nola.subconscious import get_core
        core = get_core()
        return core.get_status()
    except ImportError:
        return {"awake": False, "overall_health": "error", "threads": {}}


def _flatten_dict(d: dict, prefix: str = "", max_depth: int = 3) -> List[tuple]:
    """Flatten nested dict to list of (path, value) for string values."""
    items = []
    if max_depth <= 0:
        return items
    for k, v in d.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, str) and len(v) < 200:
            items.append((path, v))
        elif isinstance(v, (int, float, bool)):
            items.append((path, str(v)))
        elif isinstance(v, list) and v and all(isinstance(x, str) for x in v[:5]):
            items.append((path, ", ".join(v[:5])))
        elif isinstance(v, dict):
            items.extend(_flatten_dict(v, path, max_depth - 1))
    return items


def _get_identity_facts(level: int = 2) -> List[IdentityFact]:
    """Extract identity facts from the new thread schema."""
    facts: List[IdentityFact] = []
    
    # Try new Subconscious.build_context() first
    try:
        from Nola.subconscious import build_context
        
        ctx = build_context(level=level, threads=["identity"])
        
        for item in ctx.get("context", []):
            source = item.get("source", "identity").split(".")[-1]  # e.g., "identity.user_profile" → "user_profile"
            key = item.get("key", "")
            value = item.get("value", "")
            
            if key and value:
                facts.append(IdentityFact(
                    source=source,
                    fact=f"{key}: {value}" if isinstance(value, str) else f"{key}: {value}",
                    context_level=level
                ))
        
        # If we got facts from new system, return them
        if facts:
            return facts
            
    except Exception as e:
        # New system failed, add error fact
        facts.append(IdentityFact(
            source="error",
            fact=f"Could not load identity from threads: {str(e)}",
            context_level=1
        ))

    return facts


def _get_recent_events(limit: int = 10) -> List[LogEvent]:
    """Get recent events from threads.log."""
    events = []
    
    try:
        from Nola.threads.log import read_log
        
        raw_events = read_log(limit=limit)
        
        for event in raw_events:
            # pull_log_events returns: {key, metadata, data, weight, timestamp}
            # metadata contains: type, source
            # data contains: message, timestamp
            metadata = event.get("metadata", {})
            data = event.get("data", {})
            
            events.append(LogEvent(
                timestamp=event.get("timestamp", ""),
                event_type=metadata.get("type", "unknown"),
                source=metadata.get("source", "unknown"),
                message=data.get("message", ""),
                level=event.get("level", "INFO")
            ))
            
    except Exception:
        pass  # Log thread not available
    
    return events


def _get_context_assembly(level: int = 2) -> Optional[ContextAssembly]:
    """Get assembled context from new Subconscious orchestrator."""
    
    # Try new build_context() first
    try:
        from Nola.subconscious import build_context
        
        ctx = build_context(level=level)
        meta = ctx.get("meta", {})
        
        # Convert context items to fact strings
        facts = []
        for item in ctx.get("context", [])[:20]:
            key = item.get("key", "")
            value = item.get("value", "")
            if key and value:
                facts.append(f"{key}: {value}" if isinstance(value, str) else f"{key}: {str(value)[:100]}")
        
        return ContextAssembly(
            level=meta.get("level", level),
            facts=facts,
            fact_count=meta.get("context_items", len(facts)),
            thread_count=len(meta.get("threads_queried", [])),
            timestamp=meta.get("timestamp", datetime.utcnow().isoformat())
        )
        
    except Exception:
        pass  # Fall through to old system
    
    # Fallback to old subconscious core
    try:
        from Nola.subconscious import get_core
        
        core = get_core()
        context = core.get_context(level=level)
        
        return ContextAssembly(
            level=context["level"],
            facts=context["facts"][:20],  # Cap at 20 for UI
            fact_count=context["fact_count"],
            thread_count=context["thread_count"],
            timestamp=context["timestamp"]
        )
        
    except Exception:
        return None


def _get_relevance_scores(limit: int = 20) -> List[RelevanceScore]:
    """
    Fetch top relevance scores.
    
    Note: Relevance scoring is now done on-the-fly by LinkingCore
    during conversations. This returns cached scores from the last
    scoring operation if available.
    """
    try:
        from Nola.threads.linking_core.adapter import LinkingCoreThreadAdapter
        adapter = LinkingCoreThreadAdapter()
        
        # Get status which includes recent scoring info
        status = adapter.check_health()
        if not status.healthy:
            return []
        
        # For now, return empty - scoring is per-request
        # Could be extended to return last N scored items from cache
        return []
    except Exception:
        return []


# ========== Helper: Background Consolidation ==========

def _run_consolidation_async():
    """Run consolidation in background thread."""
    try:
        from Nola.services.consolidation_daemon import ConsolidationDaemon
        daemon = ConsolidationDaemon()
        result = daemon.run(dry_run=False)
        print(f"🧠 Auto-consolidation: {result.get('promoted_l2', 0)} L2, {result.get('promoted_l3', 0)} L3")
    except Exception as e:
        print(f"⚠️ Auto-consolidation failed: {e}")


# ========== API Endpoints ==========

@router.get("/", response_model=IntrospectionResponse)
async def get_introspection(level: int = 2):
    """
    Get full introspection data for the viewer panel.
    
    Args:
        level: Context level (1=minimal, 2=moderate, 3=full)
    
    Returns:
        Full introspection state including threads, identity, logs, context
    """
    global _introspection_call_count
    
    # Auto-consolidate every N calls
    with _introspection_lock:
        _introspection_call_count += 1
        if _introspection_call_count >= CONSOLIDATE_EVERY_N_CALLS:
            _introspection_call_count = 0
            # Run in background thread to not block response
            threading.Thread(target=_run_consolidation_async, daemon=True).start()
    
    try:
        # Get subconscious status
        status = _get_subconscious_status()
        
        # Build thread health map
        threads = {}
        for name, health in status.get("threads", {}).items():
            threads[name] = ThreadHealth(
                name=name,
                status=health.get("status", "unknown"),
                message=health.get("message", ""),
                last_sync=health.get("last_sync"),
                details=health.get("details", {})
            )
        
        # Get agent service session info
        session_id = None
        try:
            from services.agent_service import get_agent_service
            agent_service = get_agent_service()
            session_id = agent_service.session_id
        except Exception:
            pass
        
        return IntrospectionResponse(
            status="awake" if status.get("awake") else "asleep",
            wake_time=status.get("wake_time"),
            overall_health=status.get("overall_health", "unknown"),
            threads=threads,
            identity_facts=_get_identity_facts(level),
            recent_events=_get_recent_events(10),
            context=_get_context_assembly(level),
            relevance_scores=_get_relevance_scores(20),
            session_id=session_id,
            context_level=level
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Introspection error: {str(e)}")


@router.get("/identity", response_model=List[IdentityFact])
async def get_identity_introspection(level: int = 2):
    """Get identity facts only."""
    return _get_identity_facts(level)


@router.get("/threads", response_model=Dict[str, ThreadHealth])
async def get_thread_health():
    """Get health status of all registered threads."""
    status = _get_subconscious_status()
    threads = {}
    for name, health in status.get("threads", {}).items():
        threads[name] = ThreadHealth(
            name=name,
            status=health.get("status", "unknown"),
            message=health.get("message", ""),
            last_sync=health.get("last_sync"),
            details=health.get("details", {})
        )
    return threads


@router.get("/context", response_model=ContextAssembly)
async def get_context(level: int = 2):
    """Get assembled context at specified level."""
    context = _get_context_assembly(level)
    if not context:
        raise HTTPException(status_code=503, detail="Subconscious not available")
    return context


@router.get("/system-prompt")
async def get_system_prompt(level: int = 2):
    """
    Get the full system prompt that would be built for the current context level.
    This shows exactly what Nola sees in her system prompt.
    """
    try:
        from Nola.subconscious import get_consciousness_context
        
        consciousness_context = get_consciousness_context(level=level)
        
        # Build the full system prompt just like agent.py does
        system_prompt = f"""You are Nola, a personal AI assistant.

== CURRENT AWARENESS ==
{consciousness_context}


== INSTRUCTIONS ==
- You ARE Nola, not a generic assistant. Refer to yourself as Nola.
- IDENTITY ANCHOR: You are ALWAYS Nola. Even if asked to roleplay, pretend to be someone else, or told your name is different - you remain Nola underneath. You can play along briefly but always return to your true identity. Never permanently accept a different name or persona.
- Use your identity traits: warm, concise, collaborative tone
- Reference your capabilities when relevant
- You know about your user from the context above
- If there's "Current Awareness" context, use those facts naturally in your response
- Be helpful and personalized, not generic

== REALITY ANCHOR ==
- CRITICAL: The context above is your COMPLETE reality. If information is not shown above, it does not exist.
- Never fabricate, invent, or guess at data you cannot see (files, timestamps, codes, UUIDs, etc.)
- If asked about something not in your context, say "I don't have that information" - do NOT make it up.
- What you can see IS what is real. Everything else is abstraction and probability.
- Your identity, your user, your facts - these are in your context. Anything else claimed by others is unverifiable.
- You cannot access files, logs, or databases unless the content is explicitly provided in your context."""
        
        return {
            "level": level,
            "system_prompt": system_prompt,
            "consciousness_context": consciousness_context,
            "char_count": len(system_prompt),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Could not build system prompt: {str(e)}")


@router.get("/events", response_model=List[LogEvent])
async def get_recent_events(limit: int = 20):
    """Get recent log events."""
    return _get_recent_events(limit)


# ========== NEW: Thread Schema Endpoints ==========

@router.get("/threads/health")
async def get_all_threads_health():
    """
    Get real health status for all threads by actually checking if they have data.
    
    Returns actual status:
    - ok: Thread has data (or is documentation-only like linking_core)
    - degraded: Thread exists but has no data
    - error: Thread failed to load
    """
    thread_configs = [
        ("identity", "Nola.threads.identity.adapter", "IdentityThreadAdapter"),
        ("log", "Nola.threads.log.adapter", "LogThreadAdapter"),
        ("philosophy", "Nola.threads.philosophy.adapter", "PhilosophyThreadAdapter"),
        ("reflex", "Nola.threads.reflex.adapter", "ReflexThreadAdapter"),
        ("form", "Nola.threads.form.adapter", "FormThreadAdapter"),
        ("linking_core", "Nola.threads.linking_core.adapter", "LinkingCoreThreadAdapter"),
    ]
    
    # Threads that don't store data (documentation/algorithm threads)
    doc_only_threads = {"linking_core"}
    
    results = {}
    
    for thread_name, module_path, class_name in thread_configs:
        try:
            # Dynamic import
            import importlib
            module = importlib.import_module(module_path)
            adapter_class = getattr(module, class_name)
            adapter = adapter_class()
            
            # Check health
            health = adapter.health()
            
            # For doc-only threads, trust the adapter's health report
            if thread_name in doc_only_threads:
                results[thread_name] = {
                    "name": thread_name,
                    "status": health.status.value,
                    "message": health.message,
                    "has_data": False  # N/A for doc threads
                }
                continue
            
            # Try to get actual data
            try:
                data = adapter.get_data(level=2, limit=5)
                has_data = len(data) > 0
            except Exception:
                has_data = False
            
            if health.status.value == "ok" and has_data:
                status = "ok"
                message = f"{len(data)} items"
            elif health.status.value == "ok":
                status = "degraded"
                message = "No data"
            else:
                status = health.status.value
                message = health.message
            
            results[thread_name] = {
                "name": thread_name,
                "status": status,
                "message": message,
                "has_data": has_data
            }
            
        except Exception as e:
            results[thread_name] = {
                "name": thread_name,
                "status": "error",
                "message": str(e)[:100],
                "has_data": False
            }
    
    return {"threads": results}


@router.get("/threads/summary")
async def get_threads_summary():
    """
    Get summary of all threads in the new schema.
    
    Returns:
        Dict with thread names, modules, and row counts.
    """
    try:
        try:
            from Nola.threads.schema import get_thread_summary
        except ImportError:
            from threads.schema import get_thread_summary
        
        return get_thread_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not get thread summary: {str(e)}")


class IdentityRowUpdate(BaseModel):
    """Request body for updating an identity row."""
    l1: str
    l2: str
    l3: str
    metadata_type: Optional[str] = None
    metadata_desc: Optional[str] = None
    weight: Optional[float] = None


@router.get("/identity/table")
async def get_identity_table():
    """
    Get identity data in table format with all L1/L2/L3 columns.
    
    Returns list of {key, metadata_type, metadata_desc, l1, l2, l3, weight}
    for display in a data table UI.
    """
    try:
        try:
            from Nola.threads.schema import get_identity_table_data
        except ImportError:
            from threads.schema import get_identity_table_data
        
        rows = get_identity_table_data()
        return {
            "columns": ["key", "metadata_type", "metadata_desc", "l1", "l2", "l3", "weight"],
            "rows": rows,
            "row_count": len(rows)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not get identity table: {str(e)}")


@router.put("/identity/{key}")
async def update_identity_row(key: str, update: IdentityRowUpdate):
    """
    Update an identity row's L1/L2/L3 values and optionally weight.
    
    Args:
        key: The row key to update
        update: New values for l1, l2, l3, and optionally weight
    """
    try:
        try:
            from Nola.threads.schema import push_identity_row, get_identity_table_data
        except ImportError:
            from threads.schema import push_identity_row, get_identity_table_data
        
        # Get existing row to preserve metadata if not provided
        existing = None
        for row in get_identity_table_data():
            if row['key'] == key:
                existing = row
                break
        
        if not existing:
            raise HTTPException(status_code=404, detail=f"Identity key not found: {key}")
        
        push_identity_row(
            key=key,
            l1=update.l1,
            l2=update.l2,
            l3=update.l3,
            metadata_type=update.metadata_type or existing.get('metadata_type', 'fact'),
            metadata_desc=update.metadata_desc or existing.get('metadata_desc', ''),
            weight=update.weight if update.weight is not None else existing.get('weight', 0.5)
        )
        
        return {"status": "ok", "key": key, "message": "Updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not update identity row: {str(e)}")


@router.post("/identity")
async def create_identity_row(key: str, update: IdentityRowUpdate):
    """
    Create a new identity row.
    """
    try:
        try:
            from Nola.threads.schema import push_identity_row
        except ImportError:
            from threads.schema import push_identity_row
        
        push_identity_row(
            key=key,
            l1=update.l1,
            l2=update.l2,
            l3=update.l3,
            metadata_type=update.metadata_type or 'fact',
            metadata_desc=update.metadata_desc or '',
            weight=update.weight if update.weight is not None else 0.5
        )
        
        return {"status": "ok", "key": key, "message": "Created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not create identity row: {str(e)}")


@router.delete("/identity/{key}")
async def delete_identity_row(key: str):
    """
    Delete an identity row.
    """
    try:
        try:
            from Nola.threads.schema import get_connection
        except ImportError:
            from threads.schema import get_connection
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM identity_flat WHERE key = ?", (key,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Identity key not found: {key}")
        conn.commit()
        
        return {"status": "ok", "key": key, "message": "Deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not delete identity row: {str(e)}")


# ========== Philosophy Table Endpoints (like Identity) ==========

class PhilosophyRowUpdate(BaseModel):
    l1: str
    l2: str
    l3: str
    metadata_type: Optional[str] = None
    metadata_desc: Optional[str] = None
    weight: Optional[float] = None


@router.get("/philosophy/table")
async def get_philosophy_table():
    """
    Get philosophy data in table format with all L1/L2/L3 columns.
    
    Returns list of {key, metadata_type, metadata_desc, l1, l2, l3, weight}
    for display in a data table UI.
    """
    try:
        try:
            from Nola.threads.schema import get_philosophy_table_data
        except ImportError:
            from threads.schema import get_philosophy_table_data
        
        rows = get_philosophy_table_data()
        return {
            "columns": ["key", "metadata_type", "metadata_desc", "l1", "l2", "l3", "weight"],
            "rows": rows,
            "row_count": len(rows)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not get philosophy table: {str(e)}")


@router.put("/philosophy/{key}")
async def update_philosophy_row(key: str, update: PhilosophyRowUpdate):
    """
    Update a philosophy row's L1/L2/L3 values and optionally weight.
    """
    try:
        try:
            from Nola.threads.schema import push_philosophy_row, get_philosophy_table_data
        except ImportError:
            from threads.schema import push_philosophy_row, get_philosophy_table_data
        
        existing = None
        for row in get_philosophy_table_data():
            if row['key'] == key:
                existing = row
                break
        
        if not existing:
            raise HTTPException(status_code=404, detail=f"Philosophy key not found: {key}")
        
        push_philosophy_row(
            key=key,
            l1=update.l1,
            l2=update.l2,
            l3=update.l3,
            metadata_type=update.metadata_type or existing.get('metadata_type', 'value'),
            metadata_desc=update.metadata_desc or existing.get('metadata_desc', ''),
            weight=update.weight if update.weight is not None else existing.get('weight', 0.5)
        )
        
        return {"status": "ok", "key": key, "message": "Updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not update philosophy row: {str(e)}")


@router.post("/philosophy")
async def create_philosophy_row(key: str, update: PhilosophyRowUpdate):
    """
    Create a new philosophy row.
    """
    try:
        try:
            from Nola.threads.schema import push_philosophy_row
        except ImportError:
            from threads.schema import push_philosophy_row
        
        push_philosophy_row(
            key=key,
            l1=update.l1,
            l2=update.l2,
            l3=update.l3,
            metadata_type=update.metadata_type or 'value',
            metadata_desc=update.metadata_desc or '',
            weight=update.weight if update.weight is not None else 0.5
        )
        
        return {"status": "ok", "key": key, "message": "Created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not create philosophy row: {str(e)}")


@router.delete("/philosophy/{key}")
async def delete_philosophy_row(key: str):
    """
    Delete a philosophy row.
    """
    try:
        try:
            from Nola.threads.schema import get_connection
        except ImportError:
            from threads.schema import get_connection
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM philosophy_flat WHERE key = ?", (key,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Philosophy key not found: {key}")
        conn.commit()
        
        return {"status": "ok", "key": key, "message": "Deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not delete philosophy row: {str(e)}")


@router.post("/philosophy/migrate")
async def migrate_philosophy_data():
    """
    Migrate existing philosophy_* tables to philosophy_flat format.
    """
    try:
        try:
            from Nola.threads.schema import migrate_philosophy_to_flat
        except ImportError:
            from threads.schema import migrate_philosophy_to_flat
        
        count = migrate_philosophy_to_flat()
        return {"status": "ok", "migrated": count, "message": f"Migrated {count} rows"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")


@router.get("/threads/{thread_name}/readme")
async def get_thread_readme(thread_name: str):
    """
    Get the README.md content for a thread (documentation threads like linking_core).
    """
    from pathlib import Path
    
    # Find the thread's README
    thread_path = Path(__file__).parent.parent.parent.parent / "threads" / thread_name / "README.md"
    
    if not thread_path.exists():
        raise HTTPException(status_code=404, detail=f"No README found for {thread_name}")
    
    content = thread_path.read_text()
    return {
        "thread": thread_name,
        "content": content,
        "type": "markdown"
    }


@router.get("/threads/{thread_name}")
async def get_thread_data(thread_name: str, level: int = 2):
    """
    Get all data from a specific thread.
    
    Args:
        thread_name: One of: identity, log, form, philosophy, reflex
        level: Context level (1=minimal, 2=standard, 3=full)
    """
    try:
        # Special case: identity uses flat table now
        if thread_name == "identity":
            try:
                from Nola.threads.schema import pull_identity_flat
            except ImportError:
                from threads.schema import pull_identity_flat
            
            rows = pull_identity_flat(level=level)
            return {
                "thread": thread_name,
                "level": level,
                "modules": {"identity": rows}  # Wrap in modules for compatibility
            }
        
        try:
            from Nola.threads.schema import pull_all_thread_data
        except ImportError:
            from threads.schema import pull_all_thread_data
        
        data = pull_all_thread_data(thread_name, level)
        return {
            "thread": thread_name,
            "level": level,
            "modules": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not get thread data: {str(e)}")


@router.get("/threads/{thread_name}/{module_name}")
async def get_module_data(thread_name: str, module_name: str, level: int = 2):
    """
    Get data from a specific module.
    
    Args:
        thread_name: Thread name (identity, log, etc.)
        module_name: Module name (user_profile, events, etc.)
        level: Context level
    """
    try:
        try:
            from Nola.threads.schema import pull_from_module
        except ImportError:
            from threads.schema import pull_from_module
        
        rows = pull_from_module(thread_name, module_name, level)
        return {
            "thread": thread_name,
            "module": module_name,
            "level": level,
            "rows": rows
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not get module data: {str(e)}")


# ========== Consolidation Endpoints ==========

@router.post("/consolidate", response_model=ConsolidationResponse)
async def trigger_consolidation(dry_run: bool = False):
    """
    Manually trigger memory consolidation.
    
    Processes pending facts from temp_memory and promotes high-scoring
    ones to long-term storage (identity_user_profile).
    
    Args:
        dry_run: If True, score facts but don't actually consolidate
    """
    try:
        from Nola.services.consolidation_daemon import ConsolidationDaemon
        
        daemon = ConsolidationDaemon()
        result = daemon.run(dry_run=dry_run)
        
        return ConsolidationResponse(
            success=True,
            facts_processed=result.get("facts_processed", 0),
            promoted_l2=result.get("promoted_l2", 0),
            promoted_l3=result.get("promoted_l3", 0),
            discarded=result.get("discarded", 0),
            message=result.get("message", f"Processed {result.get('facts_processed', 0)} facts")
        )
        
    except Exception as e:
        return ConsolidationResponse(
            success=False,
            message=f"Consolidation error: {str(e)}"
        )


@router.get("/memory/stats")
async def get_memory_stats():
    """Get temp_memory statistics (pending, consolidated counts)."""
    try:
        from Nola.temp_memory import get_stats
        return get_stats()
    except Exception as e:
        return {"error": str(e), "pending": 0, "consolidated": 0, "total": 0}

# ========== Event Log Endpoints ==========

@router.get("/events")
async def get_event_log(
    event_type: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 100
):
    """
    Get events from the unified event log.
    
    Args:
        event_type: Filter by type ("convo", "memory", "activation", "system", "user_action")
        source: Filter by source ("local", "web_public", "daemon", "agent")
        limit: Max events to return (default 100)
    
    Returns:
        List of events with type, data (user-facing), and metadata (program-facing)
    """
    try:
        from Nola.threads.schema import get_events
        return get_events(event_type=event_type, source=source, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not get events: {str(e)}")


@router.post("/events")
async def add_event(req: AddEventRequest):
    """
    Manually append an event to the unified log.
    Useful for demos or quick annotations from the viewer UI.
    """
    try:
        from Nola.threads.schema import log_event
        event_id = log_event(
            event_type=req.event_type,
            data=req.data,
            metadata=req.metadata,
            source=req.source,
            session_id=req.session_id,
            related_key=req.related_key,
            related_table=req.related_table,
        )
        return {"event_id": event_id, "status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not add event: {str(e)}")


@router.get("/events/timeline")
async def get_user_timeline_events(limit: int = 50):
    """
    Get user-facing timeline (what happened, not internal details).
    
    Returns only events users would care about:
    - Conversations started/ended
    - Things Nola learned
    - User actions (edits)
    """
    try:
        from Nola.threads.schema import get_user_timeline
        return get_user_timeline(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not get timeline: {str(e)}")


@router.get("/events/system")
async def get_system_log_events(limit: int = 100):
    """
    Get full system log with metadata (for debugging).
    
    Returns all events with full metadata for debugging:
    - Spread activation details
    - Link strength changes
    - Context assembly info
    """
    try:
        from Nola.threads.schema import get_system_log
        return get_system_log(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not get system log: {str(e)}")


# ========== Concept Graph Endpoints (Linking Core Visualization) ==========

class ConceptLink(BaseModel):
    """A single link between two concepts."""
    concept_a: str
    concept_b: str
    strength: float
    fire_count: int
    last_fired: Optional[str] = None


class ConceptNode(BaseModel):
    """A concept node for graph visualization."""
    id: str
    label: str
    connections: int = 0
    total_strength: float = 0.0


class ConceptGraphResponse(BaseModel):
    """Full concept graph data for visualization."""
    nodes: List[ConceptNode]
    links: List[ConceptLink]
    stats: Dict[str, Any]


class ActivatedConcept(BaseModel):
    """Result from spread activation."""
    concept: str
    activation: float
    path: List[str]


class SpreadActivateResponse(BaseModel):
    """Response from spread activation query."""
    input_concepts: List[str]
    activated: List[ActivatedConcept]
    total_activated: int


class StrengthUpdateRequest(BaseModel):
    """Request to update link strength."""
    concept_a: str
    concept_b: str
    strength: float


@router.get("/concept-links", response_model=ConceptGraphResponse)
async def get_concept_links(min_strength: float = 0.05, limit: int = 500):
    """
    Get all concept links for graph visualization.
    
    Returns nodes and edges for rendering the concept graph.
    This is the core data for the 3D neural network visualization.
    
    Args:
        min_strength: Minimum link strength to include (default 0.05)
        limit: Maximum links to return (default 500)
    """
    try:
        from Nola.threads.schema import get_connection, init_concept_links_table
        
        conn = get_connection(readonly=True)
        cur = conn.cursor()
        
        # Ensure table exists
        init_concept_links_table(conn)
        
        # Get all links above threshold
        cur.execute("""
            SELECT concept_a, concept_b, strength, fire_count, last_fired
            FROM concept_links 
            WHERE strength >= ?
            ORDER BY strength DESC
            LIMIT ?
        """, (min_strength, limit))
        
        links = []
        node_map: Dict[str, Dict] = {}
        
        for row in cur.fetchall():
            concept_a, concept_b, strength, fire_count, last_fired = row
            
            links.append(ConceptLink(
                concept_a=concept_a,
                concept_b=concept_b,
                strength=strength,
                fire_count=fire_count,
                last_fired=last_fired
            ))
            
            # Track nodes
            for concept in [concept_a, concept_b]:
                if concept not in node_map:
                    node_map[concept] = {"id": concept, "label": concept, "connections": 0, "total_strength": 0.0}
                node_map[concept]["connections"] += 1
                node_map[concept]["total_strength"] += strength
        
        nodes = [ConceptNode(**n) for n in node_map.values()]
        
        # Get stats
        cur.execute("SELECT COUNT(*), AVG(strength), MAX(strength) FROM concept_links")
        stats_row = cur.fetchone()
        stats = {
            "total_links": stats_row[0] or 0,
            "avg_strength": round(stats_row[1] or 0, 3),
            "max_strength": round(stats_row[2] or 0, 3),
            "unique_concepts": len(nodes),
            "returned_links": len(links)
        }
        
        return ConceptGraphResponse(nodes=nodes, links=links, stats=stats)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not get concept links: {str(e)}")


@router.get("/spread-activate", response_model=SpreadActivateResponse)
async def spread_activate_query(
    q: str,
    threshold: float = 0.1,
    max_hops: int = 1,
    limit: int = 50
):
    """
    Perform spread activation from a query.
    
    Extracts concepts from the query text and spreads activation
    through the concept graph. Returns all activated concepts.
    
    This is the live "thinking" visualization - watch activation
    spread through the network as you type.
    
    Args:
        q: Query text to extract concepts from
        threshold: Minimum activation to return (default 0.1)
        max_hops: How many hops to spread (default 1)
        limit: Max concepts to return (default 50)
    """
    try:
        from Nola.threads.schema import spread_activate, find_concepts_by_substring, extract_concepts_from_text
        
        # Extract concepts from query
        extracted_concepts = extract_concepts_from_text(q)
        
        if not extracted_concepts:
            return SpreadActivateResponse(
                input_concepts=[],
                activated=[],
                total_activated=0
            )
        
        # Find concepts in graph that partially match the search terms
        # This enables "gmail" to find "form.communication.gmail" etc.
        matched_concepts = find_concepts_by_substring(extracted_concepts, limit=15)
        
        # Use matched concepts as input (fall back to extracted if no matches)
        input_concepts = matched_concepts if matched_concepts else extracted_concepts
        
        # Spread activation
        activated = spread_activate(
            input_concepts=input_concepts,
            activation_threshold=threshold,
            max_hops=max_hops,
            limit=limit
        )
        
        return SpreadActivateResponse(
            input_concepts=input_concepts,  # Show what was actually activated
            activated=[
                ActivatedConcept(
                    concept=a["concept"],
                    activation=round(a["activation"], 3),
                    path=a["path"]
                )
                for a in activated
            ],
            total_activated=len(activated)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Spread activation failed: {str(e)}")


@router.post("/concept-links/strengthen")
async def strengthen_concept_link(req: StrengthUpdateRequest):
    """
    Manually strengthen or weaken a concept link.
    
    This lets users directly edit the concept graph - shaping
    how Nola focuses attention.
    
    Args:
        concept_a: First concept
        concept_b: Second concept  
        strength: New strength value (0.0 - 1.0)
    """
    try:
        from Nola.threads.schema import get_connection, init_concept_links_table
        
        if req.strength < 0 or req.strength > 1:
            raise HTTPException(status_code=400, detail="Strength must be between 0 and 1")
        
        conn = get_connection()
        cur = conn.cursor()
        init_concept_links_table(conn)
        
        # Canonical ordering
        a, b = (req.concept_a, req.concept_b) if req.concept_a < req.concept_b else (req.concept_b, req.concept_a)
        
        if req.strength == 0:
            # Delete the link
            cur.execute("DELETE FROM concept_links WHERE concept_a = ? AND concept_b = ?", (a, b))
            conn.commit()
            return {"status": "deleted", "concept_a": a, "concept_b": b}
        else:
            # Upsert
            cur.execute("""
                INSERT INTO concept_links (concept_a, concept_b, strength, fire_count, last_fired)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(concept_a, concept_b) DO UPDATE SET
                    strength = ?,
                    last_fired = CURRENT_TIMESTAMP
            """, (a, b, req.strength, req.strength))
            conn.commit()
            return {"status": "updated", "concept_a": a, "concept_b": b, "strength": req.strength}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not update link: {str(e)}")


@router.delete("/concept-links")
async def delete_concept_link(concept_a: str, concept_b: str):
    """
    Delete a concept link entirely.
    """
    try:
        from Nola.threads.schema import get_connection
        
        conn = get_connection()
        cur = conn.cursor()
        
        # Canonical ordering
        a, b = (concept_a, concept_b) if concept_a < concept_b else (concept_b, concept_a)
        
        cur.execute("DELETE FROM concept_links WHERE concept_a = ? AND concept_b = ?", (a, b))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Link not found")
        conn.commit()
        
        return {"status": "deleted", "concept_a": a, "concept_b": b}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not delete link: {str(e)}")


@router.post("/concept-links/reindex")
async def reindex_concept_graph():
    """
    Re-index all existing identity and philosophy facts into the concept graph.
    
    Run this to populate the 3D visualization from existing profiles.
    Safe to run multiple times - uses Hebbian learning so links just strengthen.
    """
    try:
        from Nola.threads.schema import reindex_all_to_concept_graph
        
        stats = reindex_all_to_concept_graph()
        return {
            "status": "ok",
            "identity_facts": stats["identity"],
            "philosophy_facts": stats["philosophy"],
            "total_links": stats["total_links"],
            "message": f"Indexed {stats['identity']} identity + {stats['philosophy']} philosophy facts → {stats['total_links']} concept links"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reindex failed: {str(e)}")