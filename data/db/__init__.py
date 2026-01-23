"""
Database Connection Manager
===========================

The single source of truth for database connections.
Lives right next to the databases it manages.

Usage:
    from data.db import get_connection, get_db_path, set_demo_mode
    
    conn = get_connection()  # Read/write
    conn = get_connection(readonly=True)  # Read-only
    
    # Switch modes at runtime
    set_demo_mode(True)   # Use state_demo.db
    set_demo_mode(False)  # Use state.db

Files:
    data/db/state.db      - Personal/production database
    data/db/state_demo.db - Demo database (safe to reset)
    data/.aios_mode       - Current mode file ("demo" or "personal")
"""

import sqlite3
import os
from pathlib import Path

# Paths
_DB_DIR = Path(__file__).parent.resolve()  # data/db/
_DATA_DIR = _DB_DIR.parent                  # data/
_MODE_FILE = _DATA_DIR / ".aios_mode"

# Database files
STATE_DB = _DB_DIR / "state.db"
DEMO_DB = _DB_DIR / "state_demo.db"


def _get_current_mode() -> str:
    """
    Get current mode - checks file first (for runtime switching), then env var.
    
    Returns: "demo" or "personal"
    """
    if _MODE_FILE.exists():
        return _MODE_FILE.read_text().strip().lower()
    return os.getenv("AIOS_MODE", "personal").lower()


def is_demo_mode() -> bool:
    """Check if running in demo mode."""
    return _get_current_mode() == "demo"


def set_demo_mode(demo: bool) -> None:
    """
    Switch database mode at runtime.
    
    Args:
        demo: True for demo mode (state_demo.db), False for personal (state.db)
    """
    mode = "demo" if demo else "personal"
    _MODE_FILE.write_text(mode)


def get_db_path() -> Path:
    """
    Get database path based on current mode.
    
    Called dynamically to support runtime switching.
    """
    mode = _get_current_mode()
    db_path = DEMO_DB if mode == "demo" else STATE_DB
    return Path(os.getenv("STATE_DB_PATH", str(db_path)))


def get_connection(readonly: bool = False) -> sqlite3.Connection:
    """
    Get a SQLite connection.
    
    Uses dynamic DB path to support runtime mode switching.
    
    Args:
        readonly: If True, opens in read-only mode (faster, allows concurrent reads)
    
    Returns:
        sqlite3.Connection with row_factory set to sqlite3.Row
    """
    db_path = get_db_path()
    
    if not readonly:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
    else:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# For backwards compatibility
DB_PATH = get_db_path()

# Print mode on startup (only if demo)
if is_demo_mode():
    print("🎮 RUNNING IN DEMO MODE (state_demo.db)")


__all__ = [
    "get_connection",
    "get_db_path",
    "is_demo_mode",
    "set_demo_mode",
    "STATE_DB",
    "DEMO_DB",
    "DB_PATH",
]
