"""
Reflex Thread API
=================

CRUD endpoints for managing reflexes (greetings, shortcuts, system triggers).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path
import sys

# Add Nola to path
nola_path = Path(__file__).resolve().parent.parent.parent.parent
if str(nola_path) not in sys.path:
    sys.path.insert(0, str(nola_path))

router = APIRouter(prefix="/api/reflex", tags=["reflex"])


# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────

class ReflexBase(BaseModel):
    """Base reflex model."""
    key: str
    pattern: str  # What triggers this reflex
    response: str  # What to respond with
    description: Optional[str] = ""
    weight: float = 0.5
    enabled: bool = True


class GreetingCreate(BaseModel):
    """Create a greeting reflex."""
    key: str
    pattern: str
    response: str
    description: Optional[str] = ""
    weight: float = 0.8


class ShortcutCreate(BaseModel):
    """Create a shortcut."""
    trigger: str  # e.g., "/help", "/status"
    response: str
    description: Optional[str] = ""


class SystemReflexCreate(BaseModel):
    """Create a system reflex."""
    key: str
    trigger_type: str  # e.g., "error", "timeout", "resource"
    action: str  # e.g., "log_and_notify", "retry", "escalate"
    description: Optional[str] = ""
    weight: float = 0.9


class ReflexUpdate(BaseModel):
    """Update a reflex."""
    pattern: Optional[str] = None
    response: Optional[str] = None
    description: Optional[str] = None
    weight: Optional[float] = None
    enabled: Optional[bool] = None


# ─────────────────────────────────────────────────────────────
# Helper to get adapter
# ─────────────────────────────────────────────────────────────

def get_reflex_adapter():
    """Get reflex thread adapter."""
    try:
        from Nola.threads.reflex.adapter import ReflexThreadAdapter
        return ReflexThreadAdapter()
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Failed to import adapter: {e}")


# ─────────────────────────────────────────────────────────────
# Greetings Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/greetings")
async def list_greetings():
    """List all greeting reflexes."""
    adapter = get_reflex_adapter()
    greetings = adapter.get_greetings(level=3)
    
    result = []
    for g in greetings:
        result.append({
            "key": g.get("key", ""),
            "pattern": g.get("key", ""),  # Pattern is the key for greetings
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
    adapter = get_reflex_adapter()
    
    try:
        adapter.add_greeting(
            key=greeting.key,
            response=greeting.response,
            weight=greeting.weight
        )
        return {"status": "created", "key": greeting.key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/greetings/{key}")
async def delete_greeting(key: str):
    """Delete a greeting reflex."""
    try:
        from Nola.threads.schema import delete_from_module
        deleted = delete_from_module("reflex", "greetings", key)
        if deleted:
            return {"status": "deleted", "key": key}
        else:
            raise HTTPException(status_code=404, detail=f"Greeting '{key}' not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Shortcuts Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/shortcuts")
async def list_shortcuts():
    """List all shortcuts."""
    adapter = get_reflex_adapter()
    shortcuts = adapter.get_shortcuts(level=3)
    
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
    adapter = get_reflex_adapter()
    
    try:
        adapter.add_shortcut(
            trigger=shortcut.trigger,
            response=shortcut.response,
            description=shortcut.description or ""
        )
        return {"status": "created", "trigger": shortcut.trigger}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/shortcuts/{key}")
async def delete_shortcut(key: str):
    """Delete a shortcut."""
    try:
        from Nola.threads.schema import delete_from_module
        deleted = delete_from_module("reflex", "shortcuts", key)
        if deleted:
            return {"status": "deleted", "key": key}
        else:
            raise HTTPException(status_code=404, detail=f"Shortcut '{key}' not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# System Reflexes Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/system")
async def list_system_reflexes():
    """List all system reflexes."""
    adapter = get_reflex_adapter()
    system = adapter.get_system_reflexes(level=3)
    
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
    adapter = get_reflex_adapter()
    
    try:
        adapter.push(
            module="system",
            key=reflex.key,
            metadata={"type": "system", "description": reflex.description or f"System: {reflex.key}"},
            data={"trigger_type": reflex.trigger_type, "action": reflex.action},
            level=1,
            weight=reflex.weight
        )
        return {"status": "created", "key": reflex.key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/system/{key}")
async def delete_system_reflex(key: str):
    """Delete a system reflex."""
    try:
        from Nola.threads.schema import delete_from_module
        deleted = delete_from_module("reflex", "system", key)
        if deleted:
            return {"status": "deleted", "key": key}
        else:
            raise HTTPException(status_code=404, detail=f"System reflex '{key}' not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Combined Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/all")
async def list_all_reflexes():
    """List all reflexes across all modules."""
    adapter = get_reflex_adapter()
    
    greetings = adapter.get_greetings(level=3)
    shortcuts = adapter.get_shortcuts(level=3)
    system = adapter.get_system_reflexes(level=3)
    
    all_reflexes = []
    
    # Format greetings
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
    
    # Format shortcuts
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
    
    # Format system
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
    
    # Sort by weight (highest first)
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
    adapter = get_reflex_adapter()
    
    response = adapter.try_quick_response(text)
    
    if response:
        return {
            "matched": True,
            "response": response,
            "input": text
        }
    else:
        return {
            "matched": False,
            "response": None,
            "input": text
        }


@router.get("/stats")
async def get_reflex_stats():
    """Get reflex statistics."""
    adapter = get_reflex_adapter()
    
    greetings = adapter.get_greetings(level=3)
    shortcuts = adapter.get_shortcuts(level=3)
    system = adapter.get_system_reflexes(level=3)
    
    total = len(greetings) + len(shortcuts) + len(system)
    
    # Calculate average weights
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
