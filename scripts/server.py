"""
AI OS Server - Main FastAPI Application
=======================================
Central entry point for the AI OS. All routes are imported from 
self-contained modules (agent, chat, workspace, Stimuli, etc.).

Run with:
    uvicorn scripts.server:app --reload
    # or
    python -m scripts.server
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.responses import JSONResponse
import json
import sys
from pathlib import Path
import uuid

# Ensure project root is on path
_project_root = Path(__file__).resolve().parents[1]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Database mode functions
from data.db import is_demo_mode, set_demo_mode, get_db_path

# Core settings
from agent.core import settings, models_router

# Self-contained the agent modules with routers
from chat import router as chat_router, websocket_manager
from workspace import router as workspace_router
from agent.services import router as services_router
from Stimuli import api_router as stimuli_router
from agent.subconscious import subconscious_router

# Thread routers
from agent.threads.philosophy import router as philosophy_router
from agent.threads.identity import router as identity_router
from agent.threads.reflex import router as reflex_router
from agent.threads.form import router as form_router
from agent.threads.linking_core import router as linking_router
from agent.threads.log import router as log_router

# Project-level modules with routers
from docs import router as docs_router
from finetune import router as finetune_router


# =============================================================================
# Create FastAPI App
# =============================================================================

app = FastAPI(
    title=settings.app_name,
    description="AI OS - Backend API",
    version="1.0.0",
    debug=settings.debug
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# =============================================================================
# Include Routers
# =============================================================================

# the agent modules
app.include_router(chat_router)
app.include_router(workspace_router)
app.include_router(services_router)
app.include_router(stimuli_router)
app.include_router(models_router)

# Thread routers
app.include_router(philosophy_router)
app.include_router(identity_router)
app.include_router(reflex_router)
app.include_router(form_router)
app.include_router(linking_router)
app.include_router(log_router)
app.include_router(subconscious_router)

# Project-level routers
app.include_router(docs_router)
app.include_router(finetune_router)


# =============================================================================
# Database Mode Router (demo/personal toggle)
# =============================================================================

db_mode_router = APIRouter(prefix="/api/db-mode", tags=["db-mode"])

@db_mode_router.get("/mode")
async def get_mode():
    """Get current database mode."""
    mode = "demo" if is_demo_mode() else "personal"
    return {"mode": mode, "database": str(get_db_path().name)}

@db_mode_router.post("/mode/{new_mode}")
async def switch_mode(new_mode: str):
    """Switch database mode (demo or personal)."""
    if new_mode not in ("demo", "personal"):
        return JSONResponse(status_code=400, content={"error": "Mode must be 'demo' or 'personal'"})
    
    set_demo_mode(new_mode == "demo")
    return {"mode": new_mode, "database": str(get_db_path().name), "message": "Mode switched. Reload page to see changes."}

app.include_router(db_mode_router)


# =============================================================================
# Lifecycle Events
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize subconscious core on startup."""
    try:
        # Verify database path
        from data.db import get_db_path, DB_PATH
        print(f"[Startup] DB_PATH: {DB_PATH}")
        print(f"[Startup] DB exists: {DB_PATH.exists()}")
        
        # Wake subconscious
        from agent.subconscious import get_core
        core = get_core()
        core.wake()
        print(f"[Startup] Subconscious awakened with {core.registry.count()} threads")
        
        # Verify identity data
        from agent.threads.identity.schema import pull_profile_facts
        try:
            rows = pull_profile_facts(limit=3)
            print(f"[Startup] identity check: {len(rows)} rows")
        except Exception as e:
            print(f"[Startup] identity ERROR: {e}")
            
    except Exception as e:
        import traceback
        print(f"[Startup] Failed to wake subconscious: {e}")
        traceback.print_exc()


# =============================================================================
# Core Endpoints
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": settings.app_name}


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "AI OS API", "docs": "/docs"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time chat"""
    client_id = str(uuid.uuid4())
    
    try:
        await websocket_manager.connect(websocket, client_id)
        
        while True:
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
                await websocket_manager.handle_message(websocket, client_id, message_data)
            except json.JSONDecodeError:
                await websocket_manager.send_personal_message({
                    "type": "error",
                    "content": "Invalid message format"
                }, client_id)
                
    except WebSocketDisconnect:
        websocket_manager.disconnect(client_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        websocket_manager.disconnect(client_id)


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Global exception handler"""
    print(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "scripts.server:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning"
    )
