from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.responses import JSONResponse
from api.chat import router as chat_router
from api.database import router as database_router
from api.workspace import router as workspace_router
from api.models import router as models_router
from api.introspection import router as introspection_router
from api.docs import router as docs_router
from api.conversations import router as conversations_router
from api.ratings import router as ratings_router
from api.stimuli import router as stimuli_router
from api.form import router as form_router
from api.reflex import router as reflex_router
from api.services import router as services_router
from api.finetune import router as finetune_router
from api.profiles import router as profiles_router
from api.import_routes import router as import_router
from api.websockets import websocket_manager
from core.config import settings
import json
import uuid
from pathlib import Path
import sys

# Ensure project root is on path before importing Nola.*
project_root_bootstrap = Path(__file__).resolve().parents[4]
if str(project_root_bootstrap) not in sys.path:
    sys.path.insert(0, str(project_root_bootstrap))

from Nola.path_utils import ensure_project_root_on_path, ensure_nola_root_on_path, warn_if_not_venv

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Backend API for React Chat App with Demo Agent Integration",
    version="1.0.0",
    debug=settings.debug
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include routers
app.include_router(chat_router)
app.include_router(database_router)
app.include_router(workspace_router)
app.include_router(models_router)
app.include_router(introspection_router)
app.include_router(docs_router)
app.include_router(conversations_router)
app.include_router(ratings_router)
app.include_router(stimuli_router)
app.include_router(form_router, prefix="/api/form", tags=["form"])
app.include_router(reflex_router)
app.include_router(services_router)
app.include_router(finetune_router, prefix="/api/finetune", tags=["finetune"])
app.include_router(profiles_router)
app.include_router(import_router)


@app.on_event("startup")
async def startup_event():
    """Initialize subconscious core on startup."""
    try:
        ai_os_root = ensure_project_root_on_path(Path(__file__).resolve())
        ensure_nola_root_on_path(Path(__file__).resolve())
        venv_warning = warn_if_not_venv(ai_os_root)
        if venv_warning:
            print(f"⚠️  {venv_warning}")
        
        # Verify database path before waking
        from Nola.threads.schema import DB_PATH
        print(f"[Startup] DB_PATH: {DB_PATH}")
        print(f"[Startup] DB exists: {DB_PATH.exists()}")
        
        from Nola.subconscious import get_core
        core = get_core()
        core.wake()
        print(f"[Startup] Subconscious awakened with {core.registry.count()} threads")
        
        # Verify identity_flat is accessible
        from Nola.threads.schema import pull_identity_flat
        try:
            rows = pull_identity_flat(level=2, limit=3)
            print(f"[Startup] identity_flat check: {len(rows)} rows")
        except Exception as e:
            print(f"[Startup] identity_flat ERROR: {e}")
            
    except Exception as e:
        import traceback
        print(f"[Startup] Failed to wake subconscious: {e}")
        traceback.print_exc()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": settings.app_name}

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "React Chat Backend API", "docs": "/docs"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time chat"""
    client_id = str(uuid.uuid4())
    
    try:
        await websocket_manager.connect(websocket, client_id)
        
        while True:
            # Receive message from client
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning"
    )