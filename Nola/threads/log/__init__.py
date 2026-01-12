"""
Log Thread - temporal awareness and history.

Public API (replaces old log_thread module):
    from Nola.threads.log import log_event, log_error, set_session, get_session
"""
from .adapter import LogThreadAdapter

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


def log_event(event_type: str, source: str, message: str = "", **kwargs) -> None:
    """Log a structured event."""
    _get_adapter().log_event(event_type, source, message)


def log_error(source: str, error: Exception, message: str = "") -> None:
    """Log an error event."""
    error_msg = message or str(error)
    _get_adapter().log_event("error", source, f"{error_msg}: {type(error).__name__}", level=1)


def read_log(limit: int = 100):
    """Read recent log entries."""
    return _get_adapter().get_recent_events(limit)


def read_events(event_type: str = None, source: str = None, limit: int = 100):
    """Read events, optionally filtered."""
    events = _get_adapter().get_recent_events(limit)
    if event_type:
        events = [e for e in events if e.get("metadata", {}).get("type") == event_type]
    if source:
        events = [e for e in events if e.get("metadata", {}).get("source") == source]
    return events


__all__ = [
    "LogThreadAdapter",
    "log_event",
    "log_error", 
    "set_session",
    "get_session",
    "read_log",
    "read_events",
]
