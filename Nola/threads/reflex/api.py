"""
Reflex Thread API
=================
CRUD endpoints for managing reflexes (greetings, shortcuts, system triggers).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

# Import from local schema and adapter
from .schema import (
    get_greetings, get_shortcuts, get_system_reflexes,
    add_greeting, add_shortcut, add_system_reflex,
    delete_greeting, delete_shortcut, delete_system_reflex,
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
