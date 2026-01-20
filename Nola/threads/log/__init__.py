"""
Log Thread - Temporal Awareness and History
===========================================

Provides event logging, session tracking, and timeline functionality.

Usage:
    from Nola.threads.log import log_event, get_events, get_user_timeline
    
    # Log an event
    log_event("convo", "Started conversation with Jordan", source="local")
    
    # Get timeline
    timeline = get_user_timeline(limit=50)
"""

# API router
from .api import router

# Adapter for subconscious integration
from .adapter import LogThreadAdapter

# Schema functions (self-contained in this thread)
from .schema import (
    # Table init
    init_event_log_table,
    init_log_module_table,
    # Event operations
    log_event,
    get_events,
    delete_event,
    clear_events,
    get_user_timeline,
    get_system_log,
    search_events,
    # Log module operations
    pull_log_events,
    push_log_entry,
    get_log_entry,
    delete_log_entry,
    # Session operations
    create_session,
    end_session,
    get_active_sessions,
    # Stats and metadata
    get_log_stats,
    get_event_types,
    get_sources,
)

# Singleton instance for module-level functions
_adapter = None

def _get_adapter() -> LogThreadAdapter:
    global _adapter
    if _adapter is None:
        _adapter = LogThreadAdapter()
    return _adapter


def set_session(session_id: str) -> None:
    """Start a session with the given ID."""
    _get_adapter().start_session()


def get_session() -> str:
    """Get current session info."""
    adapter = _get_adapter()
    if adapter._session_start:
        return adapter._session_start.strftime("%Y%m%d_%H%M%S")
    return ""


def log_error(source: str, error: Exception, message: str = "") -> None:
    """Log an error event."""
    error_msg = message or str(error)
    log_event("system", f"Error from {source}: {error_msg}", 
              metadata={"error_type": type(error).__name__}, source=source)


def read_log(limit: int = 100):
    """Read recent log entries."""
    return get_events(limit=limit)


def read_events(event_type: str = None, source: str = None, limit: int = 100):
    """Read events, optionally filtered."""
    return get_events(event_type=event_type, source=source, limit=limit)


__all__ = [
    # Adapter
    "LogThreadAdapter",
    # API
    "router",
    # Legacy helpers
    "set_session", "get_session", "log_error", "read_log", "read_events",
    # Schema - table init
    "init_event_log_table", "init_log_module_table",
    # Schema - event operations
    "log_event", "get_events", "delete_event", "clear_events",
    "get_user_timeline", "get_system_log", "search_events",
    # Schema - log module operations
    "pull_log_events", "push_log_entry", "get_log_entry", "delete_log_entry",
    # Schema - session operations
    "create_session", "end_session", "get_active_sessions",
    # Schema - stats
    "get_log_stats", "get_event_types", "get_sources",
]
