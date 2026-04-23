"""
AI OS Server - Main FastAPI Application
=======================================
Central entry point for the AI OS. All routes are imported from 
self-contained modules (agent, chat, workspace, Feeds, etc.).

Run with:
    uvicorn scripts.server:app --reload
    # or
    python -m scripts.server
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, APIRouter, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import json
import os
import sys
import time
from pathlib import Path
import uuid

# Ensure project root is on path
_project_root = Path(__file__).resolve().parents[1]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Auth
from agent.core.auth import require_auth, require_ws_auth, get_or_create_token

# Database mode functions
from data.db import is_demo_mode, set_demo_mode, get_db_path

# Core settings
from agent.core import settings, models_router
from agent.core.settings_api import router as settings_router
from agent.core.mcp_api import router as mcp_router

# Self-contained the agent modules with routers
from chat import router as chat_router, websocket_manager
from workspace import router as workspace_router
from agent.services import router as services_router
from agent.services.mobile_api import router as mobile_router
from agent.services.mobile_voice_api import router as mobile_voice_router
from Feeds import api_router as feeds_router
from agent.subconscious import subconscious_router
from voice import router as voice_router
from sensory import router as sensory_router, init_sensory_tables, init_salience_tables, init_consent_tables, seed_consent_from_taxonomy
from agent.threads.field import router as field_router, init_field_tables

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
from eval import router as eval_router
from experiments import router as experiments_router


# =============================================================================
# HTTP Logging Middleware
# =============================================================================

class HTTPLoggingMiddleware(BaseHTTPMiddleware):
    """Log all HTTP requests to the log_server table."""
    
    # Skip logging for high-frequency endpoints
    SKIP_PATHS = {"/health", "/api/log/events", "/api/log/server", "/api/log/system"}
    
    async def dispatch(self, request: Request, call_next):
        # Skip certain paths to avoid log spam
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)
        
        start_time = time.time()
        error_msg = None
        status_code = 500  # Default if something goes wrong
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            error_msg = str(e)
            raise
        finally:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Extract client info
            client_ip = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent", "")[:500]  # Truncate long UAs
            
            # Log to database (async-safe via sync call)
            try:
                from agent.threads.log.schema import log_server_request
                log_server_request(
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    duration_ms=round(duration_ms, 2),
                    client_ip=client_ip,
                    user_agent=user_agent,
                    error=error_msg,
                    metadata={"query": str(request.url.query)} if request.url.query else None
                )
            except Exception:
                # Don't let logging failures break requests
                pass


# =============================================================================
# Create FastAPI App
# =============================================================================

app = FastAPI(
    title=settings.app_name,
    description="AI OS - Backend API",
    version="1.0.0",
    debug=settings.debug,
    dependencies=[Depends(require_auth)],
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(HTTPLoggingMiddleware)


# =============================================================================
# Read-Only Middleware (demo deployments)
# =============================================================================
# When AIOS_READ_ONLY=1, reject mutating requests to /api/* with 403.
# Used by the public demo service so visitors can browse but not modify state.
# Whitelist: chat WS messages and a handful of demo-safe POSTs (sensory record,
# notify dismissal) that don't touch identity / philosophy / goals / loops.

if os.getenv("AIOS_READ_ONLY", "").lower() in ("1", "true", "yes"):
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse as _JSONResponse

    _RO_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    # Paths we explicitly allow to mutate even in read-only mode.
    # Each visitor session needs to be able to chat (canned LLM reply) and
    # have its UI pings dismiss without errors. Nothing in this list can
    # write to identity, philosophy, goals, loops, or workspace.
    _RO_WRITE_ALLOWLIST = (
        "/api/chat/",                # chat send (LLM is killswitched separately)
        "/api/sensory/record",       # let visitors trigger demo events
        "/api/notify/",              # ack/dismiss in-app pings
    )

    class ReadOnlyMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.method in _RO_WRITE_METHODS and request.url.path.startswith("/api/"):
                if not any(request.url.path.startswith(p) for p in _RO_WRITE_ALLOWLIST):
                    return _JSONResponse(
                        status_code=403,
                        content={
                            "error": "demo is read-only",
                            "detail": (
                                f"{request.method} {request.url.path} is not allowed "
                                "in the public demo. Run AI_OS locally to write state: "
                                "https://github.com/allee-ai/AI_OS"
                            ),
                        },
                    )
            return await call_next(request)

    app.add_middleware(ReadOnlyMiddleware)
    print("[Startup] AIOS_READ_ONLY=1 — mutating /api/* requests will return 403 (allowlist applies)")


# =============================================================================
# Include Routers
# =============================================================================

# the agent modules
app.include_router(chat_router)
app.include_router(workspace_router)
app.include_router(services_router)
app.include_router(feeds_router)
app.include_router(models_router)
app.include_router(settings_router)
app.include_router(mcp_router)

# Thread routers
app.include_router(philosophy_router)
app.include_router(identity_router)
app.include_router(reflex_router)
app.include_router(form_router)
app.include_router(linking_router)
app.include_router(log_router)
app.include_router(voice_router)
app.include_router(subconscious_router)

# Sensory bus
app.include_router(sensory_router)

# Field thread (situational awareness)
app.include_router(field_router)

# Mobile remote-control API
app.include_router(mobile_voice_router)
app.include_router(mobile_router)

# Project-level routers
app.include_router(docs_router)
app.include_router(finetune_router)
app.include_router(eval_router)
app.include_router(experiments_router)


# =============================================================================
# Database Mode Router (demo/personal toggle)
# =============================================================================

db_mode_router = APIRouter(prefix="/api/db-mode", tags=["db-mode"])

@db_mode_router.get("/mode")
async def get_mode():
    """Get current database mode + whether LLM calls are blocked."""
    import os
    no_llm = os.getenv("AIOS_NO_LLM", "").lower() in ("1", "true", "yes")
    allow = os.getenv("AIOS_DEMO_ALLOW_LLM", "").lower() in ("1", "true", "yes")
    demo = is_demo_mode()
    llm_blocked = no_llm or (demo and not allow)
    return {
        "mode": "demo" if demo else "personal",
        "database": str(get_db_path().name),
        "llm_blocked": llm_blocked,
        "reason": (
            "AIOS_NO_LLM env override" if no_llm
            else "demo DB + AIOS_DEMO_ALLOW_LLM not set" if llm_blocked
            else None
        ),
    }

@db_mode_router.post("/mode/{new_mode}")
async def switch_mode(new_mode: str):
    """Switch database mode (demo or personal)."""
    if new_mode not in ("demo", "personal"):
        return JSONResponse(status_code=400, content={"error": "Mode must be 'demo' or 'personal'"})
    
    set_demo_mode(new_mode == "demo")
    return {"mode": new_mode, "database": str(get_db_path().name), "message": "Mode switched. Reload page to see changes."}

app.include_router(db_mode_router)


# =============================================================================
# Static File Serving (Production/Docker)
# =============================================================================
# Serve built frontend from frontend/dist if it exists

_frontend_dist = _project_root / "frontend" / "dist"
if _frontend_dist.exists():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from starlette.exceptions import HTTPException as StarletteHTTPException
    
    # Serve static assets
    app.mount("/assets", StaticFiles(directory=_frontend_dist / "assets"), name="assets")
    
    # Serve index.html at root
    @app.get("/")
    async def serve_index():
        """Serve the SPA index."""
        return FileResponse(_frontend_dist / "index.html")
    
    # Use 404 handler to serve SPA for client-side routes
    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        """Serve SPA for unknown routes (client-side routing)."""
        # Don't serve SPA for API routes
        if request.url.path.startswith(("/api/", "/ws/", "/docs", "/openapi")):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        # Serve index.html for SPA routing
        return FileResponse(_frontend_dist / "index.html")


# =============================================================================
# Lifecycle Events
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize subconscious core on startup."""
    try:
        # Generate/display API token
        token = get_or_create_token()
        print(f"[Startup] API token: {token}")
        print(f"[Startup] Set Authorization: Bearer <token> for API access")
        
        # Verify database path
        from data.db import get_db_path, DB_PATH
        print(f"[Startup] DB_PATH: {DB_PATH}")
        print(f"[Startup] DB exists: {DB_PATH.exists()}")
        
        # Ensure all tables + columns exist in both DBs
        from agent.core.migrations import ensure_all_schemas
        ensure_all_schemas()
        print("[Startup] Schema synced")

        # Sensory bus tables (events + salience dropped log)
        try:
            init_sensory_tables()
            init_salience_tables()
            init_consent_tables()
            added = seed_consent_from_taxonomy()
            print(f"[Startup] Sensory bus initialized (consent: +{added} seeded, all disabled)")
        except Exception as e:
            print(f"[Startup] Sensory init skipped: {e}")

        # Field thread tables (situational awareness)
        try:
            init_field_tables()
            print("[Startup] Field thread initialized")
        except Exception as e:
            print(f"[Startup] Field init skipped: {e}")

        # Check Ollama connectivity
        import os
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        try:
            import urllib.request
            urllib.request.urlopen(f"{ollama_host}/api/tags", timeout=3)
            print(f"[Startup] Ollama reachable at {ollama_host}")
        except Exception:
            print(f"[Startup] WARNING: Ollama not reachable at {ollama_host}")
            print(f"[Startup] LLM calls will fail until Ollama is running with a model pulled")
            print(f"[Startup] Install: https://ollama.com  |  Pull: ollama pull qwen2.5:7b")

        # Wake subconscious
        from agent.subconscious import wake
        start_loops = os.getenv("AIOS_LOOPS", "").lower() in ("1", "true", "yes")
        wake(start_loops=start_loops)
        if not start_loops:
            print("[Startup] Loops inactive (set AIOS_LOOPS=1 to auto-start)")
        from agent.subconscious import get_core
        core = get_core()
        print(f"[Startup] Subconscious awakened with {core.registry.count()} threads")
        
        # Verify identity data
        from agent.threads.identity.schema import pull_profile_facts
        try:
            rows = pull_profile_facts(limit=3)
            print(f"[Startup] identity check: {len(rows)} rows")
        except Exception as e:
            print(f"[Startup] identity ERROR: {e}")

        # Start feed polling + bridge + schedule loop
        try:
            from Feeds.polling import start_polling
            from Feeds.bridge import start_bridge
            start_bridge()   # register event handler (respects AIOS_FEED_BRIDGE env)
            start_polling()  # start background poll loop (checks .enabled.json)
            print("[Startup] Feed polling & bridge initialized")
        except Exception as e:
            print(f"[Startup] Feed polling/bridge skipped: {e}")

        try:
            from agent.threads.reflex.schedule import start_schedule_loop
            start_schedule_loop()  # 60s tick — evaluates cron triggers
            print("[Startup] Reflex schedule loop initialized")
        except Exception as e:
            print(f"[Startup] Schedule loop skipped: {e}")

    except Exception as e:
        import traceback
        print(f"[Startup] Failed to wake subconscious: {e}")
        traceback.print_exc()


@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown - stop loops, checkpoint SQLite WAL."""
    # Stop feed polling
    try:
        from Feeds.polling import stop_polling
        stop_polling()
    except Exception:
        pass

    # Stop schedule loop
    try:
        from agent.threads.reflex.schedule import stop_schedule_loop
        stop_schedule_loop()
    except Exception:
        pass

    try:
        from contextlib import closing
        from data.db import get_connection
        with closing(get_connection()) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        print("[Shutdown] Database checkpointed")
    except Exception as e:
        print(f"[Shutdown] Checkpoint failed: {e}")


# =============================================================================
# Core Endpoints
# =============================================================================

@app.get("/health")
@app.get("/api/health")
async def health_check():
    """Health check endpoint (aliased at /api/health so the dashboard's
    standard /api/* probing succeeds). Kept /health for legacy clients."""
    return {"status": "healthy", "service": settings.app_name}


@app.get("/api/morning-brief")
async def morning_brief():
    """JARVIS-style morning briefing composed from STATE threads."""
    try:
        from scripts.morning_brief import compose_brief
        return compose_brief()
    except Exception as e:
        return {"error": str(e), "text": "Morning brief unavailable."}


# Root endpoint only when frontend not built (dev mode uses Vite proxy)
if not _frontend_dist.exists():
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
