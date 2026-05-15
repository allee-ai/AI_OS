"""FastAPI application — mounts static files + includes all routers."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from backend.database import init_db
from backend.routers import dashboard, tenant, pdf, sales
from backend.routers import auth_router

APP_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(APP_DIR, "..", "frontend")
DIST_DIR = os.path.join(FRONTEND_DIR, "dist")

app = FastAPI(title="Jake Property Manager")


@app.on_event("startup")
def startup():
    init_db()


# --- Routers ---
app.include_router(auth_router.router, prefix="/api/auth")
app.include_router(dashboard.router, prefix="/api")
app.include_router(tenant.router, prefix="/api/tenant")
app.include_router(pdf.router, prefix="/api")
app.include_router(sales.router, prefix="/api/sales")

# --- Page routes ---
@app.get("/")
def serve_index():
    index = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    # Fallback to legacy
    legacy = os.path.join(APP_DIR, "..", "legacy", "dashboard.html")
    return FileResponse(legacy)


@app.get("/tenant")
def serve_tenant_page():
    index = os.path.join(DIST_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return FileResponse(os.path.join(APP_DIR, "..", "legacy", "tenant.html"))


@app.get("/login")
def serve_login():
    return FileResponse(os.path.join(DIST_DIR, "index.html"))


@app.get("/sales")
def serve_sales():
    return FileResponse(os.path.join(FRONTEND_DIR, "sales.html"))


# --- Sync (push to VM) ---
@app.post("/api/sync")
def sync_to_vm():
    import subprocess
    deploy_script = os.path.join(APP_DIR, "..", "deploy.sh")
    if not os.path.exists(deploy_script):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": "deploy.sh not found"})
    try:
        result = subprocess.run(
            ["bash", deploy_script],
            capture_output=True, text=True, timeout=60,
            cwd=os.path.join(APP_DIR, "..")
        )
        return {"ok": result.returncode == 0, "output": result.stdout + result.stderr}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "Deploy timed out after 60s"}


# Static files — serve built React assets first, then legacy
if os.path.exists(os.path.join(DIST_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
