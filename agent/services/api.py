"""
Services API - Manage the agent's background services, loops, and imports

Architecture:
- Background Loops (subconscious/loops.py):
  - MemoryLoop: Extracts facts from conversations → temp_memory
  - ConsolidationLoop: Promotes approved facts → identity/philosophy
  - SyncLoop: Keeps threads in sync
  - HealthLoop: Monitors thread health

- Standalone Services:
  - FactExtractor: LLM-based fact extraction
  - KernelService: Browser automation
  - AgentService: Core chat agent
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from pathlib import Path
import tempfile
import shutil
import zipfile
import json
import os

router = APIRouter(prefix="/api/services", tags=["services"])

# Temp directory for imports
UPLOAD_TEMP_DIR = Path(tempfile.gettempdir()) / "aios_imports"
UPLOAD_TEMP_DIR.mkdir(exist_ok=True)


# =============================================================================
# Service Definitions
# =============================================================================

SERVICE_DEFINITIONS = {
    "fact-extractor": {
        "name": "Fact Extractor",
        "description": "LLM-based fact extraction with detail levels",
        "module": "agent.services.fact_extractor",
        "class": "FactExtractor",
        "icon": "🔍"
    },
    "kernel": {
        "name": "Kernel Service",
        "description": "Browser automation through Kernel API",
        "module": "agent.services.kernel_service",
        "class": "KernelService",
        "icon": "🌐"
    },
    "agent": {
        "name": "Agent Service",
        "description": "Core agent connecting chat to HEA system",
        "module": "agent.services.agent_service",
        "class": "AgentService",
        "icon": "🤖"
    }
}


# =============================================================================
# Pydantic Models
# =============================================================================

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


# =============================================================================
# Helper Functions
# =============================================================================

def _get_service_status(service_id: str, definition: dict) -> ServiceStatus:
    """Check if a service module is loadable and get its status."""
    try:
        module = __import__(definition["module"], fromlist=[definition["class"]])
        status = "running"
        message = "Service module loaded successfully"
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


# =============================================================================
# Mode Management
# =============================================================================

def _is_mode_set() -> bool:
    """Check if mode was set (via start.sh dialogs or POST)."""
    return bool(os.getenv("AIOS_MODE"))


def get_aios_mode() -> str:
    """Get current the agent mode from environment."""
    return os.getenv("AIOS_MODE", "personal")


def is_demo_mode() -> bool:
    """Check if running in demo mode."""
    return os.getenv("AIOS_MODE", "personal").lower() == "demo"


def is_dev_mode() -> bool:
    """Check if dev mode is enabled."""
    return os.getenv("DEV_MODE", "false").lower() == "true"


@router.get("/mode")
async def get_mode():
    """Get current the agent mode for frontend."""
    try:
        return {
            "mode": get_aios_mode(),
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
    
    os.environ["AIOS_MODE"] = mode
    os.environ["DEV_MODE"] = str(dev_mode).lower()
    os.environ["BUILD_METHOD"] = build_method
    
    return {
        "success": True,
        "mode": mode,
        "dev_mode": dev_mode,
        "build_method": build_method,
        "message": f"Mode set to {mode}" + (" + dev" if dev_mode else "") + f" ({build_method})"
    }


# =============================================================================
# Service Endpoints
# =============================================================================

@router.get("/", response_model=List[ServiceStatus])
async def list_services():
    """List all services with their current status."""
    services = []
    for service_id, definition in SERVICE_DEFINITIONS.items():
        services.append(_get_service_status(service_id, definition))
    return services


@router.get("/loops/status")
async def get_loops_status():
    """Get status of all background loops."""
    try:
        from agent.subconscious.core import get_core
        core = get_core()
        
        if hasattr(core, '_loops') and core._loops:
            return {
                "loops": core._loops.get_stats(),
                "count": len(core._loops._loops)
            }
        return {"loops": [], "count": 0, "message": "Loop manager not initialized"}
    except Exception as e:
        return {"loops": [], "count": 0, "error": str(e)}


@router.get("/{service_id}", response_model=ServiceStatus)
async def get_service(service_id: str):
    """Get status of a specific service."""
    if service_id not in SERVICE_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    return _get_service_status(service_id, SERVICE_DEFINITIONS[service_id])


@router.get("/{service_id}/config", response_model=Dict[str, Any])
async def get_service_config_endpoint(service_id: str):
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
        from agent.subconscious import get_core
        core = get_core()
        core.sleep()
        core.wake()
        
        return RestartResponse(
            success=True,
            message="All services restarted successfully",
            services_restarted=list(SERVICE_DEFINITIONS.keys())
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restart services: {e}")


# =============================================================================
# Memory Service Endpoints
# =============================================================================

@router.get("/memory/stats")
async def get_memory_stats():
    """Get memory service statistics."""
    try:
        from agent.subconscious.temp_memory import get_stats
        stats = get_stats()
        return {
            "pending": stats.get("pending", 0),
            "total": stats.get("total", 0),
            "consolidated": stats.get("consolidated", 0)
        }
    except Exception as e:
        return {"pending": 0, "total": 0, "error": str(e)}


@router.get("/consolidation/pending")
async def get_pending_facts():
    """Get list of facts pending consolidation."""
    try:
        from agent.subconscious.temp_memory import get_all_pending
        pending = get_all_pending()
        return {
            "facts": [
                {"id": f.id, "text": f.text, "source": f.source, "timestamp": f.timestamp}
                for f in pending[:50]
            ]
        }
    except Exception as e:
        return {"facts": [], "error": str(e)}


@router.post("/consolidation/run")
async def run_consolidation():
    """Manually trigger consolidation."""
    return {
        "success": False,
        "message": "Consolidation moved to subconscious orchestrator - not yet implemented",
        "facts_processed": 0
    }


# =============================================================================
# Kernel Service Endpoints
# =============================================================================

@router.get("/kernel/status")
async def get_kernel_status():
    """Get Kernel service status including API key check."""
    api_key = os.getenv("KERNEL_API_KEY")
    return {
        "api_key_set": bool(api_key),
        "api_key_preview": f"{api_key[:8]}..." if api_key and len(api_key) > 8 else None
    }


# =============================================================================
# Import Endpoints
# =============================================================================

@router.post("/import/upload")
async def upload_export(file: UploadFile = File(...), platform: Optional[str] = Form(None)):
    """Upload an export file or folder (as zip)."""
    upload_id = f"upload_{file.filename}_{os.urandom(8).hex()}"
    upload_path = UPLOAD_TEMP_DIR / upload_id
    upload_path.mkdir(parents=True, exist_ok=True)
    
    try:
        file_path = upload_path / file.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        if file.filename.endswith('.zip'):
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(upload_path)
            file_path.unlink()
            extracted_folders = [p for p in upload_path.iterdir() if p.is_dir()]
            actual_path = extracted_folders[0] if extracted_folders else upload_path
        else:
            actual_path = file_path
        
        return JSONResponse({
            "upload_id": upload_id,
            "filename": file.filename,
            "path": str(actual_path),
            "platform": platform
        })
        
    except Exception as e:
        if upload_path.exists():
            shutil.rmtree(upload_path)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/import/parse")
async def parse_export(upload_id: str = Form(...), platform: Optional[str] = Form(None)):
    """Parse uploaded export and return preview."""
    upload_path = UPLOAD_TEMP_DIR / upload_id
    
    if not upload_path.exists():
        raise HTTPException(status_code=404, detail="Upload not found")
    
    export_path = next(upload_path.iterdir(), None)
    if not export_path:
        raise HTTPException(status_code=400, detail="No files found in upload")
    
    try:
        from chat.import_convos import ImportConvos
        
        project_root = Path(__file__).resolve().parents[2]
        workspace_path = project_root / "workspace"
        feeds_path = project_root / "Feeds"
        
        import_convos = ImportConvos(workspace_path, feeds_path)
        
        if not platform:
            parser = import_convos.detect_platform(export_path)
            if not parser:
                raise HTTPException(status_code=400, detail="Could not detect platform")
            platform = parser.get_platform_name()
        
        parser = next(p for p in import_convos.parsers if p.get_platform_name().lower() == platform.lower())
        conversations = await parser.parse(export_path)
        
        preview = {
            "platform": platform,
            "total_conversations": len(conversations),
            "conversations": [
                {
                    "id": conv.id,
                    "title": conv.title,
                    "message_count": len(conv.messages),
                    "created_at": conv.created_at.isoformat(),
                    "has_attachments": bool(conv.attachments)
                }
                for conv in conversations[:10]
            ]
        }
        
        return JSONResponse(preview)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parse failed: {str(e)}")


@router.post("/import/commit")
async def commit_import(
    upload_id: str = Form(...),
    platform: Optional[str] = Form(None),
    organize_by_project: bool = Form(True)
):
    """Commit the import - convert and save conversations."""
    upload_path = UPLOAD_TEMP_DIR / upload_id
    
    if not upload_path.exists():
        raise HTTPException(status_code=404, detail="Upload not found")
    
    export_path = next(upload_path.iterdir(), None)
    if not export_path:
        raise HTTPException(status_code=400, detail="No files found in upload")
    
    try:
        from chat.import_convos import ImportConvos
        
        project_root = Path(__file__).resolve().parents[2]
        workspace_path = project_root / "workspace"
        feeds_path = project_root / "Feeds"
        
        import_convos = ImportConvos(workspace_path, feeds_path)
        result = await import_convos.import_conversations(
            export_path=export_path,
            platform=platform,
            organize_by_project=organize_by_project
        )
        
        shutil.rmtree(upload_path)
        return JSONResponse(result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/import/status/{upload_id}")
async def get_import_status(upload_id: str):
    """Check status of an upload."""
    upload_path = UPLOAD_TEMP_DIR / upload_id
    
    if not upload_path.exists():
        return JSONResponse({"status": "not_found"})
    
    return JSONResponse({"status": "ready", "upload_id": upload_id})
