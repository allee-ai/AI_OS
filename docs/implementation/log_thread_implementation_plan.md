# Log Thread Implementation Plan

**Status**: ⚠️ PARTIAL (core implemented, advanced features pending)  
**Author**: Backend Developer Profile  
**Date**: 2025-12-19  
**Updated**: 2026-01-09

> **Note:** Core logging is implemented with `log_events` table in SQLite, log thread adapter, and frontend viewer. Advanced features (session rotation, embeddings, storage abstraction) are planned for future release.

---

## Overview

The `log_thread/` module sits adjacent to `identity_thread/` and provides a **flat, factual event log** of all program actions. Unlike identity threads which store interpretive state (who/what/why), log_thread maintains the **physical where/when timeline** — raw events with timestamps, no interpretation.

### Core Principles

1. **One line per event** — flat, append-only
2. **No interpretation** — just `event:type description`
3. **Relevance-scorable** — compatible with `relevance.py` for L-system integration
4. **Error capture** — all exceptions log here
5. **Timeline truth** — actual physical when/where, not interpreted context
6. **No per-turn logs by default** — only `conversation:start` and `conversation:end`

---

## Directory Structure

```
Nola/
├── identity_thread/       # WHO/WHAT/WHY (interpretive)
│   ├── identity.json
│   ├── identity.py
│   ├── machineID/
│   └── userID/
│
├── log_thread/            # WHEN/WHERE (factual) ← NEW
│   ├── __init__.py
│   ├── logger.py          # Core logging functions
│   ├── master.log         # Master event log (append-only)
│   ├── sessions/          # Per-session logs (optional rotation)
│   │   └── 2024-12-19_001.log
│   └── log_index.json     # Cached embeddings for relevance scoring
│
├── agent.py
├── relevance.py
└── Nola.json
```

---

## Log Format Specification

### Event Line Format

```
{ISO8601_TIMESTAMP}|{EVENT_TYPE}|{SOURCE}|{MESSAGE}
```

**Example lines:**
```
2024-12-19T14:32:01.123Z|conversation:start|agent_service|session_id=abc123 user_msg_len=45
2024-12-19T14:32:01.456Z|llm:request|agent|model=llama3.2 tokens_in=512
2024-12-19T14:32:03.789Z|llm:response|agent|tokens_out=128 latency_ms=2333
2024-12-19T14:32:03.801Z|state:write|agent|section=ConversationContext keys_updated=3
2024-12-19T14:32:03.812Z|error:runtime|websockets|ConnectionResetError: client disconnected
2024-12-19T14:32:04.001Z|conversation:end|agent_service|turns=5 duration_ms=3000
```

### Event Types (Taxonomy)

| Category | Event Type | Description |
|----------|------------|-------------|
| **Lifecycle** | `app:start` | Application startup |
| | `app:shutdown` | Clean shutdown |
| | `session:create` | New user session |
| | `session:end` | Session terminated |
| **Conversation** | `conversation:start` | New conversation begun |
| | `conversation:turn` (optional, default: off) | User/assistant turn |
| | `conversation:end` | Conversation closed |
| **LLM** | `llm:request` | Request sent to model |
| | `llm:response` | Response received |
| | `llm:error` | Model error |
| **State** | `state:read` | State section accessed |
| | `state:write` | State section modified |
| | `state:bootstrap` | Identity bootstrap triggered |
| **Relevance** | `relevance:score` | Relevance scoring run |
| | `relevance:cache_hit` | Index loaded from cache |
| **Error** | `error:runtime` | Uncaught exception |
| | `error:validation` | Input validation failed |
| | `error:io` | File/network I/O error |
| **System** | `system:memory` | Memory threshold event |
| | `system:disk` | Disk space event |

---

## Defaults and Config

- **Default policy**: Per-turn conversation logging is disabled. Only `conversation:start` and `conversation:end` are recorded.
- **Optional override**: Set environment variable `LOG_CONVERSATION_TURNS=1` to enable `conversation:turn` events if needed later.

---

## Storage Design (File → DB)

- **Now (file appender)**: Single append-only file at `Nola/log_thread/master.log` with pipe-delimited lines. This is the source of truth.
- **Later (DB-backed)**: Swap storage to SQLite while keeping the same public API (`log_event`, `log_error`).
- **Abstraction**: Introduce a minimal storage interface so callers never change:

```python
class LogStorage:
    def append(self, line: str) -> None: ...
    def tail(self, n: int = 1000) -> list[str]: ...

class FileStorage(LogStorage):
    # default implementation writing to master.log
    ...

# logger.py holds a module-level `_storage: LogStorage = FileStorage(...)`
# Future: `_storage = SQLiteStorage(conn)` without changing call sites
```

### Future DB Schema (SQLite example)

Table: `events`
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `ts` TEXT NOT NULL  -- ISO8601 UTC (same value as in file)
- `event_type` TEXT NOT NULL  -- e.g. "conversation:start"
- `source` TEXT NOT NULL  -- module name
- `message` TEXT NOT NULL  -- flat message string
- `session_id` TEXT NULL  -- parsed from message if present
- `kv_json` TEXT NULL  -- optional JSON of parsed key=value pairs
- `raw_line` TEXT NOT NULL  -- the exact original line for audit

Indexes:
- `idx_events_ts` on (`ts`)
- `idx_events_type_ts` on (`event_type`, `ts`)
- `idx_events_session_ts` on (`session_id`, `ts`)

### Migration Path

1. Keep writing the file today.
2. Add an `ingest` job later that reads `master.log`, parses lines, and inserts rows into `events`.
3. Flip a config (`LOG_STORAGE=sqlite`) to route new writes to DB; keep file mirroring optional for audit.
4. Existing `log_event/log_error` callers remain unchanged.

### Compatibility Rules

- The file line format is the canonical interchange; DB rows must be lossless relative to `raw_line`.
- Timestamps stay in UTC ISO8601 with milliseconds.
- No schema-enforced interpretations; `kv_json` is optional and best-effort parsing of `key=value` tokens.

## Core API Design

### `log_thread/logger.py`

```python
"""
log_thread/logger.py - Flat event logging for Nola

Usage:
    from log_thread import log_event, log_error
    
    log_event("conversation:start", "agent_service", session_id="abc123")
    log_error("websockets", exception)
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional
import traceback

# Paths
LOG_DIR = Path(__file__).parent
MASTER_LOG = LOG_DIR / "master.log"
SESSIONS_DIR = LOG_DIR / "sessions"

# Thread safety
_log_lock = Lock()

# Current session ID (set on app start)
_current_session: Optional[str] = None


def _timestamp() -> str:
    """ISO8601 timestamp with milliseconds, UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _format_event(
    event_type: str,
    source: str,
    message: str = "",
    **kwargs
) -> str:
    """Format a single log line.
    
    Args:
        event_type: Category:action (e.g., "conversation:start")
        source: Module/function name
        message: Optional description
        **kwargs: Key=value pairs appended to message
    
    Returns:
        Formatted log line (no newline)
    """
    # Build message with kwargs
    parts = [message] if message else []
    for k, v in kwargs.items():
        parts.append(f"{k}={v}")
    full_message = " ".join(parts)
    
    return f"{_timestamp()}|{event_type}|{source}|{full_message}"


def log_event(
    event_type: str,
    source: str,
    message: str = "",
    **kwargs
) -> str:
    """Log an event to master.log.
    
    Thread-safe, append-only.
    
    Args:
        event_type: Category:action (e.g., "llm:request")
        source: Module name (e.g., "agent", "websockets")
        message: Optional description
        **kwargs: Structured data (session_id=X, tokens=Y)
    
    Returns:
        The formatted log line
    
    Example:
        log_event("conversation:start", "agent_service", session_id="abc123")
        # → 2024-12-19T14:32:01.123Z|conversation:start|agent_service|session_id=abc123
    """
    line = _format_event(event_type, source, message, **kwargs)
    
    with _log_lock:
        MASTER_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(MASTER_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    
    return line


def log_error(
    source: str,
    exception: Exception,
    context: str = ""
) -> str:
    """Log an error with traceback summary.
    
    Args:
        source: Module where error occurred
        exception: The caught exception
        context: Optional context about what was happening
    
    Returns:
        The formatted log line
    """
    # Get exception type and message (single line)
    exc_type = type(exception).__name__
    exc_msg = str(exception).replace("\n", " ").replace("|", "/")[:200]
    
    message = f"{exc_type}: {exc_msg}"
    if context:
        message = f"{context} - {message}"
    
    return log_event("error:runtime", source, message)


def set_session(session_id: str) -> None:
    """Set current session ID for log correlation."""
    global _current_session
    _current_session = session_id
    log_event("session:create", "logger", session_id=session_id)


def get_session() -> Optional[str]:
    """Get current session ID."""
    return _current_session


# -----------------------------------------------------------------------------
# Log Reading (for relevance scoring)
# -----------------------------------------------------------------------------

def read_log(
    since: Optional[datetime] = None,
    event_types: Optional[list[str]] = None,
    limit: int = 1000
) -> list[dict]:
    """Read log entries as structured dicts.
    
    Args:
        since: Only entries after this timestamp
        event_types: Filter to these types (e.g., ["conversation:*"])
        limit: Max entries to return
    
    Returns:
        List of parsed log entries
    """
    if not MASTER_LOG.exists():
        return []
    
    entries = []
    
    with open(MASTER_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split("|", 3)
            if len(parts) < 4:
                continue
            
            timestamp_str, event_type, source, message = parts
            
            # Parse timestamp
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            
            # Filter by time
            if since and timestamp < since:
                continue
            
            # Filter by event type
            if event_types:
                matched = False
                for pattern in event_types:
                    if pattern.endswith("*"):
                        if event_type.startswith(pattern[:-1]):
                            matched = True
                            break
                    elif event_type == pattern:
                        matched = True
                        break
                if not matched:
                    continue
            
            entries.append({
                "timestamp": timestamp,
                "event_type": event_type,
                "source": source,
                "message": message
            })
            
            if len(entries) >= limit:
                break
    
    return entries


def get_log_text(since: Optional[datetime] = None) -> str:
    """Get log as plain text for relevance scoring.
    
    Returns concatenated log lines (embeddable by relevance.py).
    """
    entries = read_log(since=since)
    return "\n".join(
        f"{e['event_type']} {e['source']} {e['message']}"
        for e in entries
    )
```

### `log_thread/__init__.py`

```python
"""
log_thread - Flat event logging for Nola

The log_thread maintains the physical where/when timeline.
No interpretation, just facts: event:type, timestamp, source.

Usage:
    from log_thread import log_event, log_error
    
    log_event("conversation:start", "my_module", session_id="abc")
    log_error("my_module", some_exception)
"""

from .logger import (
    log_event,
    log_error,
    set_session,
    get_session,
    read_log,
    get_log_text,
    MASTER_LOG,
)

__all__ = [
    "log_event",
    "log_error", 
    "set_session",
    "get_session",
    "read_log",
    "get_log_text",
    "MASTER_LOG",
]
```

---

## Integration Points

### 1. Agent Bootstrap (`agent.py`)

```python
from log_thread import log_event

class Agent:
    def bootstrap(self, context_level: int = 2, force: bool = False) -> dict:
        log_event("state:bootstrap", "agent", context_level=context_level, force=force)
        # ... existing code ...
        log_event("state:bootstrap_complete", "agent", sections_loaded=len(result))
```

### 2. Chat Service (`services/agent_service.py`)

```python
from log_thread import log_event, log_error

# No per-turn logging; only start/end of conversation.
async def handle_conversation_start(session_id: str):
    log_event("conversation:start", "agent_service", session_id=session_id)

async def handle_conversation_end(session_id: str, turns: int | None = None, duration_ms: int | None = None):
    log_event("conversation:end", "agent_service", session_id=session_id, turns=turns, duration_ms=duration_ms)

async def process_message(message: str, session_id: str):
    try:
        response = await generate_response(message)
        return response
    except Exception as e:
        log_error("agent_service", e, context=f"processing message for {session_id}")
        raise
```

### 3. WebSocket Handlers (`react-chat-app/backend/api/websockets.py`)

```python
from log_thread import log_event, log_error, set_session

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    log_event("session:create", "websockets", session_id=session_id)
    try:
        await websocket.accept()
        log_event("websocket:connect", "websockets", session_id=session_id)
        # ... existing code ...
    except WebSocketDisconnect:
        log_event("websocket:disconnect", "websockets", session_id=session_id)
    except Exception as e:
        log_error("websockets", e, context=f"session {session_id}")
```

### 4. Error Handler Decorator

```python
# Can be added to utils.py or log_thread/logger.py

from functools import wraps
from log_thread import log_error

def logged(source: str):
    """Decorator to auto-log exceptions."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_error(source, e, context=func.__name__)
                raise
        return wrapper
    return decorator

# Usage:
@logged("agent_service")
def risky_operation():
    ...
```

---

## Relevance Integration

The log_thread can be scored by `relevance.py` just like any other thread:

```python
from relevance import RelevanceIndex
from log_thread import get_log_text, MASTER_LOG

# Build index from Nola.json (or identity.json)
index = RelevanceIndex.from_json_file("Nola.json")

# Score recent log activity against identity
log_content = get_log_text(since=datetime.now() - timedelta(hours=1))
scores = index.score_text(log_content)

# Find which identity keys are most relevant to recent activity
top_keys = sorted(scores.items(), key=lambda x: -x[1])[:5]
```

This enables:
- **Behavioral pattern detection**: "User always triggers errors after midnight"
- **Activity correlation**: "High LLM latency correlates with state:write events"
- **Timeline reconstruction**: Exact physical ordering of events

---

## Log Rotation (Optional)

For long-running deployments, add rotation:

```python
# log_thread/rotation.py

from pathlib import Path
from datetime import datetime
import shutil

def rotate_log(max_size_mb: float = 10.0):
    """Rotate master.log when it exceeds max_size_mb."""
    if not MASTER_LOG.exists():
        return
    
    size_mb = MASTER_LOG.stat().st_size / (1024 * 1024)
    if size_mb < max_size_mb:
        return
    
    # Move to sessions/
    SESSIONS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = SESSIONS_DIR / f"{timestamp}.log"
    
    shutil.move(MASTER_LOG, archive_path)
    
    log_event("system:log_rotated", "rotation", 
              old_size_mb=f"{size_mb:.2f}", archive=str(archive_path))
```

---

## Implementation Checklist

### Phase 1: Core Logger (Est. 30 min)
- [ ] Create `Nola/log_thread/` directory
- [ ] Implement `log.py` with `log_event()`, `log_error()`
- [ ] Create `__init__.py` with exports
- [ ] Manual test: verify log lines written to `master.log`

### Phase 2: Integration (Est. 1 hour)
- [ ] Add logging to `agent.py` bootstrap
- [ ] Add conversation start/end logging in `services/agent_service.py`
- [ ] Add logging to WebSocket handlers
- [ ] Add logging to `relevance.py` scoring calls

### Phase 3: Error Capture (Est. 30 min)
- [ ] Create `@logged` decorator
- [ ] Wrap critical functions in try/except with `log_error()`
- [ ] Add global exception handler to FastAPI

### Phase 4: Relevance Scoring (Est. 30 min)
- [ ] Add `get_log_text()` for embedding
- [ ] Test scoring log against identity keys
- [ ] Document correlation patterns

### Phase 5: Polish (Est. 30 min)
- [ ] Add log rotation
- [ ] Add CLI for log inspection: `python -m log_thread tail`
- [ ] Update README with log format docs

---

## Example Output

After implementation, `master.log` will contain:

```
2024-12-19T14:30:00.001Z|app:start|main|version=0.1.0
2024-12-19T14:30:00.123Z|state:bootstrap|agent|context_level=2 force=False
2024-12-19T14:30:01.456Z|state:bootstrap_complete|agent|sections_loaded=3
2024-12-19T14:32:01.001Z|session:create|websockets|session_id=abc123
2024-12-19T14:32:01.015Z|websocket:connect|websockets|session_id=abc123
2024-12-19T14:32:01.200Z|llm:request|agent|model=llama3.2 tokens_in=512
2024-12-19T14:32:03.533Z|llm:response|agent|tokens_out=128 latency_ms=2333
2024-12-19T14:32:10.001Z|websocket:disconnect|websockets|session_id=abc123
```

---

## Notes

- **No interpretation**: Log thread doesn't decide if an event is "important" — that's relevance.py's job
- **Append-only**: Never modify past entries
- **Pipe-delimited**: Easy to grep, parse, import to database
- **UTC timestamps**: No timezone ambiguity
- **Thread-safe**: Lock on writes, safe for async/threaded code

This gives you the raw timeline for the physical where/when, while identity_thread handles the interpretive who/what/why.
