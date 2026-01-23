# Form Thread Agent

**Read `stack.md` first for universal patterns.**

## Purpose

Form manages capabilities and current state — what tools exist (static) and what's actively happening (dynamic).

## Contract: metadata vs data

Your adapter MUST implement:

```python
def get_metadata(self) -> dict:
    """Thread structure - thinking about thinking."""
    return {
        "files": ["adapter.py", "README.md"],
        "tables": ["form_tool_registry", "form_action_history", "form_browser"],
        "modules": ["tools", "actions", "browser"],
        "capabilities": ["browser", "file_ops", "memory"],  # what CAN happen
        "schema": {"key": "TEXT", "metadata_json": "TEXT", "data_json": "TEXT"},
        "db_path": "/data/db/state.db"
    }

def get_data(self, level: int = 2) -> list:
    """Thread content - current state (what IS happening)."""
    return [{"key": "browser", "available": True, "session_id": "abc123"}, ...]
```

**Key question:** "What can I do? What's happening right now?"

## Level System: Metadata vs Data Split

Form uses a unique architecture:
```
metadata_json = CAPABILITIES (what CAN happen) - static
data_json = CURRENT STATE (what IS happening) - dynamic
```

### Example
```json
{
  "key": "tool_browser",
  "metadata": {
    "name": "browser",
    "actions": ["navigate", "screenshot", "interact"]
  },
  "data": {
    "available": true,
    "session_id": "abc123",
    "current_url": "https://github.com"
  }
}
```

## Database

### Tables

**`form_tool_registry`** - Available tools
```sql
key TEXT PRIMARY KEY,           -- "tool_browser"
metadata_json TEXT,             -- {"name": "browser", "actions": [...], "requires": [...]}
data_json TEXT,                 -- {"available": true, "last_used": "..."}
weight REAL                     -- Tool priority
```

**`form_action_history`** - What's been done
```sql
key TEXT PRIMARY KEY,           -- "action_20260108_143022"
metadata_json TEXT,             -- {"type": "action", "tool": "browser", "action": "navigate"}
data_json TEXT,                 -- {"success": true, "duration_ms": 1200}
weight REAL
```

**`form_browser`** - Browser/Kernel state
```sql
key TEXT PRIMARY KEY,           -- "current_browser"
metadata_json TEXT,             -- {"type": "browser_state", "capabilities": [...]}
data_json TEXT                  -- {"url": "...", "title": "...", "session_id": "..."}
```

## Adapter

**Location:** `agent/threads/form/adapter.py`

### Key Functions

```python
from agent.threads.form.adapter import FormThreadAdapter

adapter = FormThreadAdapter()

# Get available tools
tools = adapter.get_tools(level=2)

# Register a tool
adapter.register_tool(
    name="email",
    description="Send and read emails",
    actions=["send", "read", "search"],
    available=False
)

# Update browser state
adapter.update_browser_state(
    url="https://github.com",
    title="GitHub",
    session_id="abc123"
)

# Record action
adapter.record_action(
    tool="browser",
    action="navigate",
    success=True,
    details="Loaded GitHub"
)
```

## Code Map

### Backend (Python/FastAPI)

| File | Purpose |
|------|---------|
| `agent/threads/form/adapter.py` | Core adapter - `get_tools()`, `register_tool()`, `record_action()` |
| `agent/threads/form/__init__.py` | Public API |
| `agent/threads/form/README.md` | Documentation |
| `agent/services/api.py # introspection.py` | REST endpoints (lines 647-710) |
| `agent/services/kernel_service.py` | Browser/Kernel integration |
| `agent/threads/schema.py` | DB schema - `pull_from_module()` |

### Backend Endpoints

| Endpoint | Method | Line | Purpose |
|----------|--------|------|---------|
| `/api/introspection/threads/form` | GET | 668 | All form data |
| `/api/introspection/threads/form/readme` | GET | 647 | README content |
| `/api/introspection/threads/form/{module}` | GET | 707 | Module data (tools, actions, browser) |

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
form_tool_registry   - Available tools (browser, file_ops, memory)
form_action_history  - What's been done (action log)
form_browser         - Browser/Kernel state (url, session_id)
```

### Related Services

| File | Purpose |
|------|---------|
| `agent/services/kernel_service.py` | Browser automation via Kernel |
| `agent/agent.py` | Tool execution via `_execute_tool()` |

### Future UI (TODO)

- **File sorting** - Upload file, compare to weighted facts, sort
- **PC scan on first run** - Dig through files, sort, report
- **Permission system** - Grant/revoke tool access
- **Capability discovery** - "What can I do?" query

## Future: File Operations

```python
# Reflexive file sort
def on_file_upload(file_path):
    # 1. Extract content
    content = extract_file_content(file_path)
    
    # 2. Compare to weighted identity facts
    relevance = linking_core.score_relevance(content, identity_facts)
    
    # 3. Sort to appropriate folder
    destination = categorize_by_relevance(relevance)
    move_file(file_path, destination)
    
    # 4. Log action
    log.log_event("file:sorted", f"Sorted {file_path} to {destination}")
```

## Future: First-Run PC Scan

```python
def first_run_scan():
    """On first launch, scan user's files and organize."""
    for file in scan_user_documents():
        # Compare to identity (what does user care about?)
        # Sort files by relevance
        # Build initial understanding of user's world
    
    # Report what was done
    return "I organized your files based on what you work on..."
```

## Conflicts to Watch

| If you're changing... | Check with... |
|----------------------|---------------|
| User skills/abilities | Identity (who vs what can do) |
| Action timestamps | Log (temporal records) |
| Tool constraints | Philosophy (ethical limits) |
| Quick tool commands | Reflex (shortcuts) |

## README

Full documentation: `agent/threads/form/README.md`
