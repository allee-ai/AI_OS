"""
Services API - Manage Nola's background services
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import json
import os

router = APIRouter(prefix="/api/services", tags=["services"])


# Service definitions with their module paths
SERVICE_DEFINITIONS = {
    "memory": {
        "name": "Memory Service",
        "description": "Extracts and manages facts from conversations",
        "module": "Nola.services.memory_service",
        "class": "MemoryService",
        "icon": "🧠"
    },
    "consolidation": {
        "name": "Consolidation Daemon",
        "description": "Promotes facts from short-term to long-term memory",
        "module": "Nola.services.consolidation_daemon",
        "class": "ConsolidationDaemon",
        "icon": "📦"
    },
    "fact-extractor": {
        "name": "Fact Extractor",
        "description": "LLM-based fact extraction with detail levels",
        "module": "Nola.services.fact_extractor",
        "class": "FactExtractor",
        "icon": "🔍"
    },
    "kernel": {
        "name": "Kernel Service",
        "description": "Browser automation through Kernel API",
        "module": "Nola.services.kernel_service",
        "class": "KernelService",
        "icon": "🌐"
    },
    "agent": {
        "name": "Agent Service",
        "description": "Core agent connecting chat to HEA system",
        "module": "Nola.services.agent_service",
        "class": "AgentService",
        "icon": "🤖"
    }
}


class ServiceStatus(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    status: str  # "running", "stopped", "error"
    message: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class ServiceConfig(BaseModel):
    enabled: bool = True
    settings: Dict[str, Any] = {}


class RestartResponse(BaseModel):
    success: bool
    message: str
    services_restarted: List[str]


def _get_service_status(service_id: str, definition: dict) -> ServiceStatus:
    """Check if a service module is loadable and get its status."""
    try:
        # Try to import the module
        module = __import__(definition["module"], fromlist=[definition["class"]])
        
        # Check if it has a status method or is functional
        status = "running"
        message = "Service module loaded successfully"
        
        # Try to get config from database
        config = _get_service_config(service_id)
        
        return ServiceStatus(
            id=service_id,
            name=definition["name"],
            description=definition["description"],
            icon=definition["icon"],
            status=status,
            message=message,
            config=config
        )
    except ImportError as e:
        return ServiceStatus(
            id=service_id,
            name=definition["name"],
            description=definition["description"],
            icon=definition["icon"],
            status="error",
            message=f"Module not found: {e}",
            config=None
        )
    except Exception as e:
        return ServiceStatus(
            id=service_id,
            name=definition["name"],
            description=definition["description"],
            icon=definition["icon"],
            status="error",
            message=str(e),
            config=None
        )


def _get_service_config(service_id: str) -> Optional[Dict[str, Any]]:
    """Get service config from database."""
    try:
        from data.db import get_connection
        conn = get_connection(readonly=True)
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_config (
                service_id TEXT PRIMARY KEY,
                enabled INTEGER DEFAULT 1,
                settings_json TEXT DEFAULT '{}',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute(
            "SELECT enabled, settings_json FROM service_config WHERE service_id = ?",
            (service_id,)
        )
        row = cursor.fetchone()
        
        if row:
            return {
                "enabled": bool(row[0]),
                "settings": json.loads(row[1]) if row[1] else {}
            }
        return {"enabled": True, "settings": {}}
    except Exception:
        return {"enabled": True, "settings": {}}


def _save_service_config(service_id: str, config: ServiceConfig) -> bool:
    """Save service config to database."""
    try:
        from data.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_config (
                service_id TEXT PRIMARY KEY,
                enabled INTEGER DEFAULT 1,
                settings_json TEXT DEFAULT '{}',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            INSERT INTO service_config (service_id, enabled, settings_json, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(service_id) DO UPDATE SET
                enabled = excluded.enabled,
                settings_json = excluded.settings_json,
                updated_at = CURRENT_TIMESTAMP
        """, (service_id, int(config.enabled), json.dumps(config.settings)))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving service config: {e}")
        return False


# === Mode Management Endpoints (MUST BE BEFORE /{service_id} routes) ===

# Mode is set if NOLA_MODE env var was passed from start.sh
# (start.sh now shows dialogs BEFORE launching services)
def _is_mode_set() -> bool:
    """Check if mode was set (via start.sh dialogs or POST)."""
    # If NOLA_MODE env var exists and isn't empty, mode was set by start.sh
    return bool(os.getenv("NOLA_MODE"))

def get_nola_mode() -> str:
    """Get current Nola mode from environment."""
    return os.getenv("NOLA_MODE", "personal")

def is_demo_mode() -> bool:
    """Check if running in demo mode."""
    return os.getenv("NOLA_MODE", "personal").lower() == "demo"

def is_dev_mode() -> bool:
    """Check if dev mode is enabled."""
    return os.getenv("DEV_MODE", "false").lower() == "true"

@router.get("/mode")
async def get_mode():
    """Get current Nola mode for frontend."""
    try:
        return {
            "mode": get_nola_mode(),
            "mode_set": _is_mode_set(),
            "dev_mode": is_dev_mode(),
            "is_demo": is_demo_mode(),
            "is_dev": is_dev_mode(),
            "build_method": os.getenv("BUILD_METHOD", "local")
        }
    except Exception as e:
        return {
            "mode": "personal",
            "mode_set": False,
            "dev_mode": False,
            "is_demo": False,
            "is_dev": False,
            "build_method": "local",
            "error": str(e)
        }

@router.post("/mode")
async def set_mode(body: Dict[str, Any]):
    """Set mode for current session."""
    mode = body.get("mode", "personal")
    dev_mode = body.get("dev_mode", False)
    build_method = body.get("build_method", "local")
    
    # Set environment variables for current process
    os.environ["NOLA_MODE"] = mode
    os.environ["DEV_MODE"] = str(dev_mode).lower()
    os.environ["BUILD_METHOD"] = build_method
    
    return {
        "success": True,
        "mode": mode,
        "dev_mode": dev_mode,
        "build_method": build_method,
        "message": f"Mode set to {mode}" + (" + dev" if dev_mode else "") + f" ({build_method})"
    }


@router.get("/", response_model=List[ServiceStatus])
async def list_services():
    """List all services with their current status."""
    services = []
    for service_id, definition in SERVICE_DEFINITIONS.items():
        services.append(_get_service_status(service_id, definition))
    return services


@router.get("/{service_id}", response_model=ServiceStatus)
async def get_service(service_id: str):
    """Get status of a specific service."""
    if service_id not in SERVICE_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    
    return _get_service_status(service_id, SERVICE_DEFINITIONS[service_id])


@router.get("/{service_id}/config", response_model=Dict[str, Any])
async def get_service_config(service_id: str):
    """Get configuration for a specific service."""
    if service_id not in SERVICE_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    
    config = _get_service_config(service_id)
    return config or {"enabled": True, "settings": {}}


@router.put("/{service_id}/config")
async def update_service_config(service_id: str, config: ServiceConfig):
    """Update configuration for a specific service."""
    if service_id not in SERVICE_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    
    success = _save_service_config(service_id, config)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save config")
    
    return {
        "success": True,
        "message": "Config saved. Restart required to apply changes.",
        "requires_restart": True
    }


@router.post("/restart", response_model=RestartResponse)
async def restart_services():
    """Restart all services by cycling the subconscious."""
    try:
        from Nola.subconscious import get_core
        
        core = get_core()
        
        # Sleep (graceful shutdown)
        core.sleep()
        
        # Wake (reinitialize with new config)
        core.wake()
        
        return RestartResponse(
            success=True,
            message="All services restarted successfully",
            services_restarted=list(SERVICE_DEFINITIONS.keys())
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restart services: {e}")


# === Memory Service Endpoints ===

@router.get("/memory/stats")
async def get_memory_stats():
    """Get memory service statistics."""
    try:
        from Nola.temp_memory import get_stats
        stats = get_stats()
        return {
            "pending": stats.get("pending", 0),
            "total": stats.get("total", 0),
            "consolidated": stats.get("consolidated", 0)
        }
    except Exception as e:
        return {"pending": 0, "total": 0, "error": str(e)}


# === Consolidation Daemon Endpoints ===

@router.get("/consolidation/pending")
async def get_pending_facts():
    """Get list of facts pending consolidation."""
    try:
        from Nola.temp_memory import get_all_pending
        pending = get_all_pending()
        return {
            "facts": [
                {
                    "id": f.id,
                    "text": f.text,
                    "source": f.source,
                    "timestamp": f.timestamp
                }
                for f in pending[:50]  # Limit to 50
            ]
        }
    except Exception as e:
        return {"facts": [], "error": str(e)}


@router.post("/consolidation/run")
async def run_consolidation():
    """Manually trigger consolidation daemon."""
    try:
        from Nola.services.consolidation_daemon import ConsolidationDaemon
        
        daemon = ConsolidationDaemon()
        result = daemon.run()
        
        return {
            "success": True,
            "facts_processed": result.get("facts_processed", 0),
            "promoted_l2": result.get("promoted_l2", 0),
            "promoted_l3": result.get("promoted_l3", 0),
            "discarded": result.get("discarded", 0),
            "errors": result.get("errors", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Fact Extractor Endpoints ===

@router.post("/fact-extractor/test")
async def test_fact_extraction(body: Dict[str, Any]):
    """Test fact extraction without storing."""
    fact = body.get("fact", "")
    if not fact:
        raise HTTPException(status_code=400, detail="No fact provided")
    
    try:
        from Nola.services.fact_extractor import extract_key, extract_value_levels, classify_thread
        
        key = extract_key(fact)
        l1, l2, l3 = extract_value_levels(fact)
        thread, meta_type = classify_thread(fact)
        
        return {
            "key": key,
            "thread": thread,
            "meta_type": meta_type,
            "l1": l1,
            "l2": l2,
            "l3": l3
        }
    except Exception as e:
        return {"error": str(e)}


# === Kernel Service Endpoints ===

@router.get("/kernel/status")
async def get_kernel_status():
    """Get Kernel service status including API key check."""
    api_key = os.getenv("KERNEL_API_KEY")
    return {
        "api_key_set": bool(api_key),
        "api_key_preview": f"{api_key[:8]}..." if api_key and len(api_key) > 8 else None
    }
