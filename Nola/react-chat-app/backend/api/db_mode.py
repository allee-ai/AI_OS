"""
Database mode switching API.
Changes NOLA_MODE and triggers hot reload.
"""

from fastapi import APIRouter
from pathlib import Path
import os

router = APIRouter(prefix="/api/db-mode", tags=["database-mode"])

# Mode file for persistence across reloads
MODE_FILE = Path(__file__).parent.parent.parent.parent.parent / "data" / ".nola_mode"

def get_current_mode() -> str:
    """Get current database mode - check file first, then env."""
    if MODE_FILE.exists():
        return MODE_FILE.read_text().strip()
    return os.getenv("NOLA_MODE", "personal").lower()

@router.get("/mode")
async def get_mode():
    """Get current database mode."""
    mode = get_current_mode()
    return {
        "mode": mode,
        "database": "state_demo.db" if mode == "demo" else "state.db"
    }

@router.post("/mode/{new_mode}")
async def set_mode(new_mode: str):
    """
    Switch database mode and trigger reload.
    Valid modes: 'personal', 'demo'
    
    WARNING: This will restart the server. Unsaved changes will be lost.
    """
    if new_mode not in ("personal", "demo"):
        return {"error": f"Invalid mode: {new_mode}. Use 'personal' or 'demo'"}
    
    current = get_current_mode()
    if current == new_mode:
        return {"status": "already_set", "mode": new_mode}
    
    # Write mode to file for persistence
    MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
    MODE_FILE.write_text(new_mode)
    
    # Also update env var for current process
    os.environ["NOLA_MODE"] = new_mode
    
    # Touch main.py to trigger uvicorn hot reload
    main_py = Path(__file__).parent.parent / "main.py"
    if main_py.exists():
        main_py.touch()
    
    return {
        "status": "switching",
        "from": current,
        "to": new_mode,
        "message": "Server reloading... refresh in 2-3 seconds"
    }
