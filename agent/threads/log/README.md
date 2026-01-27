# Log Thread

**Cognitive Question**: WHEN did it happen? WHERE did it come from?  
**Resolution Order**: 5th (after patterns checked, establish timeline)  
**Brain Mapping**: Hippocampus (episodic memory, timeline formation)

---

## Necessity

Log provides temporal awareness — a timeline of events, sessions, and patterns. Unlike other threads that store "what is true", Log stores "what has occurred". This is how Agent knows "we talked about this yesterday" or "you've been working for 2 hours."

---

## Backend

### Database Tables

| Table | Location | Purpose |
|-------|----------|---------|
| `unified_events` | `schema.py:86` | Central event timeline |
| `log_events` | Module table | System events (errors, starts) |
| `log_sessions` | Module table | Conversation sessions |
| `log_temporal` | Module table | Time-based patterns |

### Schema: unified_events

```sql
CREATE TABLE unified_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,
    source TEXT DEFAULT 'system',
    data TEXT,
    metadata_json TEXT,
    session_id TEXT,
    related_key TEXT,
    related_table TEXT
)
```

### Core Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `log_event()` | `schema.py:111` | Log event to unified timeline |
| `get_events()` | `schema.py:172` | Query events with filters |
| `pull_log_events()` | `schema.py:1278` | Pull by recency + weight |
| `init_event_log_table()` | `schema.py:76` | Initialize tables |

### Adapter

| Method | Location | Purpose |
|--------|----------|---------|
| `get_data()` | `adapter.py:62` | Get events by recency level |
| `start_session()` | `adapter.py:80` | Start conversation session |
| `end_session()` | `adapter.py:99` | End conversation session |
| `log_message()` | `adapter.py:120` | Log a conversation message |
| `get_session_duration()` | `adapter.py:140` | Get time since session start |

---

## Context Levels (Recency-Based)

Log uses **recency**, not depth:

| Level | Events | Use Case |
|-------|--------|----------|
| **L1** | 10 most recent | Quick glance at activity |
| **L2** | 100 most recent | Conversation-scale history |
| **L3** | 1000 most recent | Full timeline |

```python
LOG_LIMITS = {1: 10, 2: 100, 3: 1000}
```

---

## Event Types

| Type | Relevance Score | Purpose |
|------|-----------------|---------|
| `convo` | 8 | Conversation events (direct interaction) |
| `memory` | 7 | Memory/reflection events (cognitive) |
| `user_action` | 6 | User actions in UI |
| `file` | 4 | File operations |
| `system` | 2 | System events (background) |
| `activation` | 1 | Spread activation (technical) |

Defined in `adapter.py:35`:
```python
EVENT_TYPE_RELEVANCE = {
    "convo": 8,
    "memory": 7,
    "user_action": 6,
    "file": 4,
    "system": 2,
    "activation": 1
}
```

---

## Frontend

| Component | Location | Status |
|-----------|----------|--------|
| Log events table | `ThreadsPage.tsx` | 🌀 Done |
| Session viewer | `ThreadsPage.tsx` | 🌀 Done |

**Features**:
- 🌀 View event timeline
- 🌀 Filter by event type
- 🌀 Session tracking
- ⬜ Timeline visualization
- ⬜ Pattern detection UI

---

## Weight Semantics

Weight represents **significance**, not permanence:

- **0.7+**: Important events (user corrections, errors, milestones)
- **0.3-0.6**: Normal events (messages, tool uses)
- **0.1-0.2**: Routine events (system wakes, heartbeats)

---

## Integration Points

| Thread | Integration |
|--------|-------------|
| **Identity** | Log records when identity facts change |
| **Form** | Action history tracked with timestamps |
| **Philosophy** | Log can track ethical decisions over time |
| **Reflex** | Track pattern frequency for 10x promotion |
| **Linking Core** | Temporal proximity affects relevance scoring |

---

## Usage Examples

```python
from agent.threads.schema import log_event, get_events

# Log a conversation start
log_event("convo", "Conversation started with Jordan",
          {"context_level": 2}, source="local", session_id="abc123")

# Log a memory extraction
log_event("memory", "Learned: Sarah likes coffee",
          {"hier_key": "sarah.likes.coffee", "score": 0.72},
          related_key="sarah.likes.coffee")

# Log an activation event
log_event("activation", "Spread activation fired",
          {"query": "coffee", "activated": ["sarah"], "links": 2})

# Query recent events
events = get_events(event_type="convo", limit=50)
```

---

## Temporal Reasoning

Log enables temporal awareness in responses:

| Pattern | How |
|---------|-----|
| "We talked about this yesterday" | Query events with Sarah in data, check timestamp |
| "You've been working for 2 hours" | Get session start, calculate duration |
| "Last time you mentioned X..." | Search events for X, return context |

Linking Core uses temporal proximity — recent mentions boost related concepts.
history = adapter.get_data(level=2)

# Log a new event
adapter.log_event(
    event_type="user_action",
    source="chat",
    message="User asked about weather",
    weight=0.3
)

# Start a session
session_id = adapter.start_session()
```

## Temporal Patterns

The Log thread enables temporal reasoning:

- "We talked about this yesterday"
- "You've been working for 2 hours"
- "Last time you mentioned Sarah..."

Linking Core can activate concepts based on temporal proximity — recent mentions of "Sarah" boost related facts.

## Integration with Other Threads

- **Identity**: Log records when identity facts change
- **Linking Core**: Temporal proximity affects relevance scoring
- **Form**: Action history lives in Form, but Log timestamps everything
- **Philosophy**: Log can track ethical decisions over time

## Implementation (canonical)

## Implementation (full)

The following content is the full implementation plan for the Log Thread (transferred from `docs/implementation/log_thread_implementation_plan.md`).

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
agent/
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
└── identity.json
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

- **Now (file appender)**: Single append-only file at `agent/log_thread/master.log` with pipe-delimited lines. This is the source of truth.
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
2. Add an `ingest` job later that reads `MASTER_LOG`, parses lines, and inserts rows into `events`.
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
log_thread/logger.py - Flat event logging for Agent

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


### `log_thread/__init__.py`

```python
"""
log_thread - Flat event logging for Agent

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

