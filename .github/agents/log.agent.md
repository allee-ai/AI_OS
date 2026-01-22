# Log Thread Agent

**Read `stack.md` first for universal patterns.**

## Purpose

Log provides temporal awareness — timeline of events, sessions, and patterns. Unlike other threads that store "what is true", Log stores "what has occurred".

**Key question:** "What happened? When? How long have we been talking?"

## Contract: metadata vs data

Your adapter MUST implement:

```python
def get_metadata(self) -> dict:
    """Thread structure - thinking about thinking."""
    return {
        "files": ["adapter.py", "README.md"],
        "tables": ["log_events"],
        "modules": list(LOG_LIMITS.keys()),  # event types
        "limits": LOG_LIMITS,  # {1: 10, 2: 100, 3: 1000}
        "schema": {"key": "TEXT", "data_json": "TEXT", "weight": "REAL", "created_at": "TEXT"},
        "db_path": "/data/db/state.db"
    }

def get_data(self, level: int = 2) -> list:
    """Thread content - recent events (recency-based)."""
    limit = LOG_LIMITS.get(level, 100)
    return [{"key": "conv:123", "data": "User asked about...", "weight": 0.8}, ...]
```

## Level System: Recency-Based

Levels determine **how far back** to look:
```
L1 = Last 10 events    (quick glance)
L2 = Last 100 events   (conversation history)
L3 = Last 1000 events  (full timeline)
```

## Database

### Tables

**`log_events`** - System events
```sql
key TEXT PRIMARY KEY,           -- "evt_20260108_143022_123456"
metadata_json TEXT,             -- {"type": "system:wake", "source": "subconscious"}
data_json TEXT,                 -- {"message": "...", "timestamp": "..."}
weight REAL,                    -- Event importance
created_at TIMESTAMP
```

**`log_sessions`** - Conversation sessions
```sql
key TEXT PRIMARY KEY,           -- "session_20260108_143022"
data_json TEXT,                 -- {"start_time": "...", "status": "active"}
weight REAL
```

**`unified_events`** - Combined event log
```sql
event_type TEXT,                -- "convo" | "system" | "memory" | "activation"
data TEXT,                      -- User-facing (what happened)
metadata_json TEXT,             -- Program-facing (why/how)
source TEXT,                    -- "local" | "web_public" | "daemon"
session_id TEXT
```

## Adapter

**Location:** `Nola/threads/log/adapter.py`

### Key Functions

```python
from Nola.threads.log.adapter import LogThreadAdapter

adapter = LogThreadAdapter()

# Get events by recency level
events = adapter.get_data(level=2)  # Last 100

# Log new event
adapter.log_event(
    event_type="user_action",
    source="chat",
    message="User asked about weather",
    weight=0.3
)

# Start session
session_id = adapter.start_session()

# Get recent events
recent = adapter.get_recent_events(limit=10)
```

### Special: `pull_log_events()`
```python
from Nola.threads.schema import pull_log_events

# Query by recency, not level
events = pull_log_events(module_name="events", limit=100, min_weight=0.0)
```

## Code Map

### Backend (Python/FastAPI)

| File | Purpose |
|------|---------|
| `Nola/threads/log/adapter.py` | Core adapter - `log_event()`, `get_recent_events()`, `start_session()` |
| `Nola/threads/log/__init__.py` | Public API - `log_event()`, `log_error()`, `read_log()` |
| `Nola/threads/log/README.md` | Documentation |
| `Nola/services/api.py # introspection.py` | REST endpoints (lines 413, 780-850) |
| `Nola/threads/schema.py` | DB helpers - `pull_log_events()` (line 1228) |

### Backend Endpoints

| Endpoint | Method | Line | Purpose |
|----------|--------|------|---------|
| `/api/introspection/events` | GET | 413 | Recent events (old, uses `_get_recent_events`) |
| `/api/introspection/events` | GET | 780 | Events with filters (new, `get_event_log`) |
| `/api/introspection/events` | POST | 804 | Add manual event |
| `/api/introspection/events/timeline` | GET | 826 | User-facing timeline |
| `/api/introspection/events/system` | GET | 843 | System debug log |

### Backend Helper Functions

| Function | Line | Purpose |
|----------|------|---------|
| `_get_recent_events()` | 203 | Fetch from `Nola.threads.log.read_log()` |
| `AddEventRequest` | 800 | Pydantic model for POST /events |

### Frontend (React/TypeScript)

| File | Purpose |
|------|---------|
| `frontend/src/pages/ThreadsPage.tsx` | Log viewer UI |
| `frontend/src/pages/ThreadsPage.css` | Log styles (`.log-view`, `.log-event`) |
| `frontend/src/services/introspectionService.ts` | API - `getRecentEvents()`, `addEvent()` |

### Frontend Functions (ThreadsPage.tsx)

| Function | Line | Purpose |
|----------|------|---------|
| `fetchLogEvents()` | ~290 | Load events with filters |
| `handleAddEvent()` | ~320 | Submit manual event |
| `renderLogView()` | ~450 | Render log viewer with controls |

### Frontend State Variables

```typescript
logEvents: LogEvent[]           // Fetched events
logLimit: number                // 20, 50, 100
logSortOrder: 'desc' | 'asc'    // Sort direction
logFilterType: string           // Filter by event_type
logFilterSource: string         // Filter by source
newEventType: string            // Add event form
newEventSource: string
newEventMessage: string
```

### CSS Classes

```css
.log-view, .log-controls, .log-events-list
.log-event, .log-event-header, .log-event-data
.log-event-type, .log-event-source, .log-event-time
.add-event-section, .add-event-form
```

## Event Types

```
system:wake      - Startup
system:shutdown  - Shutdown
convo:start      - Conversation began
convo:end        - Conversation ended
memory:extract   - Fact extracted
memory:consolidate - Facts consolidated
identity:update  - Identity changed
activation:spread - Concept activated
error:*          - Errors
```

## Conflicts to Watch

| If you're changing... | Check with... |
|----------------------|---------------|
| Persistent user data | Identity (if it should persist) |
| Action records | Form (action_history) |
| Timestamps on any data | Log owns temporal metadata |

## README

Full documentation: `Nola/threads/log/README.md`
