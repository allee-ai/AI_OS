"""
Reflex Thread API
=================
CRUD endpoints for managing reflexes (greetings, shortcuts, system triggers).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# Import from local schema and adapter
from .schema import (
    get_greetings, get_shortcuts, get_system_reflexes,
    add_greeting, add_shortcut, add_system_reflex,
    delete_greeting, delete_shortcut, delete_system_reflex,
    # SQLite trigger functions
    create_trigger, get_triggers, get_trigger,
    update_trigger, delete_trigger, toggle_trigger,
    record_trigger_execution,
)
from .adapter import ReflexThreadAdapter

router = APIRouter(prefix="/api/reflex", tags=["reflex"])


# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────

class GreetingCreate(BaseModel):
    key: str
    pattern: str
    response: str
    description: Optional[str] = ""
    weight: float = 0.8


class ShortcutCreate(BaseModel):
    trigger: str
    response: str
    description: Optional[str] = ""


class SystemReflexCreate(BaseModel):
    key: str
    trigger_type: str
    action: str
    description: Optional[str] = ""
    weight: float = 0.9


class TriggerCreate(BaseModel):
    """Create a feed → tool trigger automation."""
    name: str
    feed_name: str  # e.g., "gmail", "discord"
    event_type: str  # e.g., "email_received", "message_received"
    tool_name: str  # e.g., "file_reader", "web_search"
    tool_action: str  # e.g., "read", "search"
    description: Optional[str] = ""
    trigger_type: str = "webhook"  # webhook, poll, schedule
    condition: Optional[Dict[str, Any]] = None  # Optional filter
    tool_params: Optional[Dict[str, Any]] = None  # Params to pass to tool
    poll_interval: Optional[int] = None  # For poll triggers (seconds)
    cron_expression: Optional[str] = None  # For schedule triggers
    priority: int = 5


class TriggerUpdate(BaseModel):
    """Update trigger fields."""
    name: Optional[str] = None
    description: Optional[str] = None
    condition: Optional[Dict[str, Any]] = None
    tool_params: Optional[Dict[str, Any]] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None
    poll_interval: Optional[int] = None
    cron_expression: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# Greetings Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/greetings")
async def list_greetings():
    """List all greeting reflexes."""
    greetings = get_greetings(level=3)
    
    result = []
    for g in greetings:
        result.append({
            "key": g.get("key", ""),
            "pattern": g.get("key", ""),
            "response": g.get("data", {}).get("value", ""),
            "description": g.get("metadata", {}).get("description", ""),
            "weight": g.get("weight", 0.5),
            "level": g.get("level", 1),
            "module": "greetings"
        })
    
    return {"greetings": result, "count": len(result)}


@router.post("/greetings")
async def create_greeting(greeting: GreetingCreate):
    """Create a new greeting reflex."""
    try:
        add_greeting(
            key=greeting.key,
            response=greeting.response,
            weight=greeting.weight
        )
        return {"status": "created", "key": greeting.key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/greetings/{key}")
async def remove_greeting(key: str):
    """Delete a greeting reflex."""
    if delete_greeting(key):
        return {"status": "deleted", "key": key}
    raise HTTPException(status_code=404, detail=f"Greeting '{key}' not found")


# ─────────────────────────────────────────────────────────────
# Shortcuts Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/shortcuts")
async def list_shortcuts():
    """List all shortcuts."""
    shortcuts = get_shortcuts(level=3)
    
    result = []
    for s in shortcuts:
        data = s.get("data", {})
        result.append({
            "key": s.get("key", ""),
            "trigger": data.get("trigger", ""),
            "response": data.get("response", ""),
            "description": s.get("metadata", {}).get("description", ""),
            "weight": s.get("weight", 0.5),
            "level": s.get("level", 1),
            "module": "shortcuts"
        })
    
    return {"shortcuts": result, "count": len(result)}


@router.post("/shortcuts")
async def create_shortcut(shortcut: ShortcutCreate):
    """Create a new shortcut."""
    try:
        add_shortcut(
            trigger=shortcut.trigger,
            response=shortcut.response,
            description=shortcut.description or ""
        )
        return {"status": "created", "trigger": shortcut.trigger}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/shortcuts/{key}")
async def remove_shortcut(key: str):
    """Delete a shortcut."""
    if delete_shortcut(key):
        return {"status": "deleted", "key": key}
    raise HTTPException(status_code=404, detail=f"Shortcut '{key}' not found")


# ─────────────────────────────────────────────────────────────
# System Reflexes Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/system")
async def list_system_reflexes():
    """List all system reflexes."""
    system = get_system_reflexes(level=3)
    
    result = []
    for s in system:
        data = s.get("data", {})
        result.append({
            "key": s.get("key", ""),
            "trigger_type": data.get("trigger_type", ""),
            "action": data.get("action", ""),
            "description": s.get("metadata", {}).get("description", ""),
            "weight": s.get("weight", 0.5),
            "level": s.get("level", 1),
            "module": "system"
        })
    
    return {"system": result, "count": len(result)}


@router.post("/system")
async def create_system_reflex(reflex: SystemReflexCreate):
    """Create a new system reflex."""
    try:
        add_system_reflex(
            key=reflex.key,
            trigger_type=reflex.trigger_type,
            action=reflex.action,
            description=reflex.description or "",
            weight=reflex.weight
        )
        return {"status": "created", "key": reflex.key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/system/{key}")
async def remove_system_reflex(key: str):
    """Delete a system reflex."""
    if delete_system_reflex(key):
        return {"status": "deleted", "key": key}
    raise HTTPException(status_code=404, detail=f"System reflex '{key}' not found")


# ─────────────────────────────────────────────────────────────
# Combined Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/all")
async def list_all_reflexes():
    """List all reflexes across all modules."""
    greetings = get_greetings(level=3)
    shortcuts = get_shortcuts(level=3)
    system = get_system_reflexes(level=3)
    
    all_reflexes = []
    
    for g in greetings:
        all_reflexes.append({
            "key": g.get("key", ""),
            "module": "greetings",
            "pattern": g.get("key", ""),
            "response": g.get("data", {}).get("value", ""),
            "description": g.get("metadata", {}).get("description", ""),
            "weight": g.get("weight", 0.5),
            "icon": "👋"
        })
    
    for s in shortcuts:
        data = s.get("data", {})
        all_reflexes.append({
            "key": s.get("key", ""),
            "module": "shortcuts",
            "pattern": data.get("trigger", ""),
            "response": data.get("response", ""),
            "description": s.get("metadata", {}).get("description", ""),
            "weight": s.get("weight", 0.5),
            "icon": "⚡"
        })
    
    for s in system:
        data = s.get("data", {})
        all_reflexes.append({
            "key": s.get("key", ""),
            "module": "system",
            "pattern": data.get("trigger_type", ""),
            "response": data.get("action", ""),
            "description": s.get("metadata", {}).get("description", ""),
            "weight": s.get("weight", 0.5),
            "icon": "🔧"
        })
    
    all_reflexes.sort(key=lambda x: x.get("weight", 0), reverse=True)
    
    return {
        "reflexes": all_reflexes,
        "count": len(all_reflexes),
        "by_module": {
            "greetings": len(greetings),
            "shortcuts": len(shortcuts),
            "system": len(system)
        }
    }


@router.post("/test")
async def test_reflex(text: str):
    """Test if text triggers a reflex."""
    adapter = ReflexThreadAdapter()
    response = adapter.try_quick_response(text)
    
    return {
        "matched": response is not None,
        "response": response,
        "input": text
    }


@router.get("/stats")
async def get_reflex_stats():
    """Get reflex statistics."""
    greetings = get_greetings(level=3)
    shortcuts = get_shortcuts(level=3)
    system = get_system_reflexes(level=3)
    
    total = len(greetings) + len(shortcuts) + len(system)
    
    all_weights = (
        [g.get("weight", 0.5) for g in greetings] +
        [s.get("weight", 0.5) for s in shortcuts] +
        [s.get("weight", 0.5) for s in system]
    )
    avg_weight = sum(all_weights) / len(all_weights) if all_weights else 0
    
    return {
        "total": total,
        "by_module": {
            "greetings": len(greetings),
            "shortcuts": len(shortcuts),
            "system": len(system)
        },
        "average_weight": round(avg_weight, 2),
        "modules": ["greetings", "shortcuts", "system"]
    }


# ─────────────────────────────────────────────────────────────
# Introspection (Thread owns its state block)
# ─────────────────────────────────────────────────────────────

@router.get("/introspect")
async def introspect_reflex(level: int = 2, query: Optional[str] = None):
    """
    Get reflex thread's contribution to STATE block.
    
    Each thread is responsible for building its own state.
    If query provided, filters to relevant reflexes via LinkingCore.
    """
    adapter = ReflexThreadAdapter()
    result = adapter.introspect(context_level=level, query=query)
    return result.to_dict()


@router.get("/health")
async def get_reflex_health():
    """Get reflex thread health status."""
    adapter = ReflexThreadAdapter()
    return adapter.health().to_dict()


# ─────────────────────────────────────────────────────────────
# Feed Triggers (Feed Event → Tool Action automations)
# ─────────────────────────────────────────────────────────────

@router.get("/triggers")
async def list_triggers(
    feed_name: Optional[str] = None,
    event_type: Optional[str] = None,
    enabled_only: bool = False,
):
    """
    List all triggers, optionally filtered by feed/event.
    
    These are feed event → tool action automations.
    """
    triggers = get_triggers(
        feed_name=feed_name,
        event_type=event_type,
        enabled_only=enabled_only,
    )
    return {
        "triggers": triggers,
        "count": len(triggers),
        "filters": {
            "feed_name": feed_name,
            "event_type": event_type,
            "enabled_only": enabled_only,
        }
    }


@router.get("/triggers/{trigger_id}")
async def get_trigger_detail(trigger_id: int):
    """Get a single trigger by ID."""
    trigger = get_trigger(trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")
    return trigger


@router.post("/triggers")
async def create_new_trigger(trigger: TriggerCreate):
    """
    Create a new feed → tool trigger automation.
    
    Example:
    - When email_received from gmail, execute web_search tool
    - When mention_received from discord, execute send_notification tool
    """
    try:
        trigger_id = create_trigger(
            name=trigger.name,
            feed_name=trigger.feed_name,
            event_type=trigger.event_type,
            tool_name=trigger.tool_name,
            tool_action=trigger.tool_action,
            description=trigger.description or "",
            trigger_type=trigger.trigger_type,
            condition=trigger.condition,
            tool_params=trigger.tool_params,
            poll_interval=trigger.poll_interval,
            cron_expression=trigger.cron_expression,
            priority=trigger.priority,
        )
        return {
            "status": "created",
            "trigger_id": trigger_id,
            "name": trigger.name,
            "automation": f"{trigger.feed_name}/{trigger.event_type} → {trigger.tool_name}/{trigger.tool_action}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/triggers/{trigger_id}")
async def update_existing_trigger(trigger_id: int, update: TriggerUpdate):
    """Update trigger fields."""
    existing = get_trigger(trigger_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")
    
    updates = {k: v for k, v in update.model_dump().items() if v is not None}
    if not updates:
        return {"status": "no_changes", "trigger_id": trigger_id}
    
    success = update_trigger(trigger_id, **updates)
    if success:
        return {"status": "updated", "trigger_id": trigger_id, "updated_fields": list(updates.keys())}
    raise HTTPException(status_code=500, detail="Failed to update trigger")


@router.delete("/triggers/{trigger_id}")
async def delete_existing_trigger(trigger_id: int):
    """Delete a trigger."""
    if delete_trigger(trigger_id):
        return {"status": "deleted", "trigger_id": trigger_id}
    raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")


@router.post("/triggers/{trigger_id}/toggle")
async def toggle_existing_trigger(trigger_id: int):
    """Toggle a trigger's enabled state."""
    new_state = toggle_trigger(trigger_id)
    if new_state is None:
        raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")
    return {
        "status": "toggled",
        "trigger_id": trigger_id,
        "enabled": new_state,
    }


@router.post("/triggers/{trigger_id}/test")
async def test_trigger_execution(trigger_id: int, test_payload: Optional[Dict[str, Any]] = None):
    """
    Test execute a trigger with optional test payload.
    
    This simulates receiving a feed event and executing the tool action.
    """
    from .executor import execute_tool_action
    
    trigger = get_trigger(trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")
    
    # Parse tool params if stored as JSON string
    tool_params = trigger.get("tool_params") or trigger.get("tool_params_json")
    if isinstance(tool_params, str):
        import json
        try:
            tool_params = json.loads(tool_params)
        except json.JSONDecodeError:
            tool_params = {}
    
    # Execute the tool
    try:
        result = await execute_tool_action(
            tool_name=trigger["tool_name"],
            tool_action=trigger["tool_action"],
            tool_params=tool_params,
            event_payload=test_payload or {},
        )
        
        if result.get("success"):
            record_trigger_execution(trigger_id, success=True)
        else:
            record_trigger_execution(trigger_id, success=False, error=result.get("error"))
        
        return {
            "status": "executed" if result.get("success") else "failed",
            "trigger_id": trigger_id,
            "trigger_name": trigger.get("name"),
            "tool_result": result,
            "test_payload": test_payload,
        }
    except Exception as e:
        record_trigger_execution(trigger_id, success=False, error=str(e))
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")


@router.get("/triggers/stats/summary")
async def get_trigger_stats():
    """Get trigger statistics and summary."""
    all_triggers = get_triggers()
    enabled = [t for t in all_triggers if t.get("enabled")]
    
    by_feed = {}
    by_tool = {}
    total_executions = 0
    
    for t in all_triggers:
        feed = t.get("feed_name", "unknown")
        tool = t.get("tool_name", "unknown")
        by_feed[feed] = by_feed.get(feed, 0) + 1
        by_tool[tool] = by_tool.get(tool, 0) + 1
        total_executions += t.get("execution_count", 0)
    
    return {
        "total": len(all_triggers),
        "enabled": len(enabled),
        "disabled": len(all_triggers) - len(enabled),
        "by_feed": by_feed,
        "by_tool": by_tool,
        "total_executions": total_executions,
    }
