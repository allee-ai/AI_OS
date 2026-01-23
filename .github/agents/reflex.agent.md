# Reflex Thread Agent

**Read `stack.md` first for universal patterns.**

## Purpose

Reflex stores quick patterns that bypass full context assembly — "muscle memory" responses like greetings, shortcuts, and triggers.

**Key question:** "What's my instant response?"

## Contract: metadata vs data

Your adapter MUST implement:

```python
def get_metadata(self) -> dict:
    """Thread structure - thinking about thinking."""
    return {
        "files": ["adapter.py", "README.md"],
        "tables": ["reflex_patterns"],
        "modules": ["greetings", "errors", "shortcuts"],
        "schema": {"pattern": "TEXT", "response": "TEXT", "weight": "REAL"},
        "db_path": "/data/db/state.db"
    }

def get_data(self, level: int = 2) -> list:
    """Thread content - actual pattern→response pairs."""
    return [{"pattern": "^(hi|hello)", "response": "Hey!", "weight": 1.0}, ...]
```

## Level System: Pattern Matching

Reflex doesn't use L1/L2/L3 depth. It stores:
```
trigger → response
"hi" → "Hey! What's on your mind?"
"/clear" → [clear conversation action]
```

## Database

### Tables

**`reflex_greetings`** - Social responses
```sql
key TEXT PRIMARY KEY,           -- "greeting_hi"
metadata_json TEXT,             -- {"type": "greeting", "triggers": ["hi", "hello"]}
data_json TEXT,                 -- {"responses": ["Hey!", "Hello!"]}
weight REAL                     -- Priority when multiple match
```

**`reflex_shortcuts`** - User commands
```sql
key TEXT PRIMARY KEY,           -- "shortcut_clear"
metadata_json TEXT,             -- {"type": "shortcut", "trigger": "/clear"}
data_json TEXT,                 -- {"action": "clear_conversation", "confirm": false}
weight REAL
```

**`reflex_system`** - System-level
```sql
key TEXT PRIMARY KEY,           -- "error_handler"
metadata_json TEXT,             -- {"type": "system", "trigger": "error_detected"}
data_json TEXT                  -- {"action": "log_and_notify"}
```

## Adapter

**Location:** `agent/threads/reflex/adapter.py`

### Key Functions

```python
from agent.threads.reflex.adapter import ReflexThreadAdapter

adapter = ReflexThreadAdapter()

# Check if input matches a reflex
match = adapter.match_pattern("hi there")
if match:
    return match.response  # Skip full context assembly

# Get all reflexes
reflexes = adapter.get_data(level=2)

# Register new shortcut
adapter.register_shortcut(
    trigger="/weather",
    action="get_weather",
    description="Quick weather check"
)
```

## Code Map

### Backend (Python/FastAPI)

| File | Purpose |
|------|---------|
| `agent/threads/reflex/adapter.py` | Core adapter - `match_pattern()`, `get_data()`, `register_shortcut()` |
| `agent/threads/reflex/__init__.py` | Public API |
| `agent/threads/reflex/README.md` | Documentation |
| `agent/services/api.py # introspection.py` | REST endpoints (lines 647-710) |
| `agent/threads/schema.py` | DB schema - `pull_from_module()` |

### Backend Endpoints

| Endpoint | Method | Line | Purpose |
|----------|--------|------|---------|
| `/api/introspection/threads/reflex` | GET | 668 | All reflex data |
| `/api/introspection/threads/reflex/readme` | GET | 647 | README content |
| `/api/introspection/threads/reflex/{module}` | GET | 707 | Module data (greetings, shortcuts) |

### Frontend (React/TypeScript)

| File | Purpose |
|------|---------|
| `frontend/src/pages/ThreadsPage.tsx` | Thread viewer (generic module view) |
| `frontend/src/pages/ThreadsPage.css` | Styles |
| `frontend/src/services/introspectionService.ts` | API client |

### Frontend Functions (ThreadsPage.tsx)

| Function | Line | Purpose |
|----------|------|---------|
| `fetchThreadData()` | ~150 | Load thread modules |
| `renderModuleView()` | ~400 | Generic module table |

### Database Tables

```
reflex_greetings   - Social responses (hi → Hey!)
reflex_shortcuts   - User commands (/clear, /help)
reflex_system      - System-level triggers (error_handler)
```

### Future UI (TODO)

- **Create Reflex button** - Add new triggers from UI
- Time-based triggers ("every morning at 9am")
- Stimuli triggers (file uploaded → sort it)
- 10x rule automation (pattern repeats → promote to reflex)

## Reflex Cascade (Priority Order)

1. **System reflexes** (safety, errors) — weight 0.9+
2. **User shortcuts** (/commands) — weight 0.6-0.8
3. **Social reflexes** (greetings) — weight 0.3-0.5

First match wins.

## Future: Stimuli Triggers

```python
# When file is uploaded
stimuli_trigger = {
    "type": "file_upload",
    "action": "sort_by_weighted_facts",
    "description": "Compare file to identity, sort accordingly"
}

# When time matches
time_trigger = {
    "type": "time",
    "cron": "0 9 * * *",  # 9am daily
    "action": "morning_checkin"
}
```

## Conflicts to Watch

| If you're changing... | Check with... |
|----------------------|---------------|
| Value-based responses | Philosophy (principles vs patterns) |
| Tool shortcuts | Form (capability registration) |
| Event triggers | Log (temporal patterns) |

## README

Full documentation: `agent/threads/reflex/README.md`
