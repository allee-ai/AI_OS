# Identity Thread Agent

**Read `stack.md` first for universal patterns.**

## Purpose

Identity stores facts about self and user. This is the most important thread — user identity takes highest priority.

**Key question:** "Who am I? Who are you?"

## Contract: metadata vs data

Your adapter MUST implement:

```python
def get_metadata(self) -> dict:
    """Thread structure - thinking about thinking."""
    return {
        "files": ["adapter.py", "README.md"],
        "tables": ["identity_flat"],
        "modules": ["core", "beliefs", "preferences"],
        "schema": {"key": "TEXT", "data_json": "TEXT", "level": "INT", "weight": "REAL"},
        "db_path": "/data/db/state.db"
    }

def get_data(self, level: int = 2) -> list:
    """Thread content - actual stored facts."""
    return [{"key": "name", "data": "Nola", "level": 1, "weight": 1.0}, ...]
```

## Level System: L1/L2/L3 Per Key

Each key has three detail levels:
```
key: "user_name"
L1: "Jordan"
L2: "Jordan, software developer"
L3: "Jordan, software developer building AI_OS, prefers morning work"
```

## Database

### Primary Table: `identity_flat`

```sql
CREATE TABLE identity_flat (
    key TEXT PRIMARY KEY,
    metadata_type TEXT,      -- "user" | "nola" | "machine" | "relationship"
    metadata_desc TEXT,
    l1 TEXT,                 -- Quick (~10 tokens)
    l2 TEXT,                 -- Standard (~30 tokens)
    l3 TEXT,                 -- Full (~100 tokens)
    weight REAL DEFAULT 0.5,
    updated_at TIMESTAMP
);
```

### Sample Data
```sql
SELECT * FROM identity_flat LIMIT 5;
```

## Adapter

**Location:** `agent/threads/identity/adapter.py`

### Key Functions

```python
from agent.threads.identity.adapter import IdentityThreadAdapter

adapter = IdentityThreadAdapter()

# Get facts at level
facts = adapter.get_data(level=2, limit=10)

# Push new fact
adapter.push_identity(
    key="user_project",
    l1="AI_OS",
    l2="AI_OS, cognitive architecture",
    l3="AI_OS, cognitive architecture with 5 threads...",
    metadata_type="user",
    weight=0.8
)

# Health check
health = adapter.health()  # Returns HealthReport
```

## Code Map

### Backend (Python/FastAPI)

| File | Purpose |
|------|---------|
| `agent/threads/identity/adapter.py` | Core adapter - `get_data()`, `push_identity()`, `health()` |
| `agent/threads/identity/__init__.py` | Public API - `get_identity()`, `set_identity()` |
| `agent/threads/identity/README.md` | Documentation |
| `agent/services/api.py # introspection.py` | REST endpoints (lines 530-645) |
| `agent/threads/schema.py` | DB schema - `pull_from_module()`, `push_to_module()` |

### Backend Endpoints

| Endpoint | Method | Line | Purpose |
|----------|--------|------|---------|
| `/api/introspection/identity/table` | GET | 530 | All identity rows |
| `/api/introspection/identity/{key}` | PUT | 554 | Update row |
| `/api/introspection/identity` | POST | 596 | Create new row |
| `/api/introspection/identity/{key}` | DELETE | 622 | Delete row |

### Frontend (React/TypeScript)

| File | Purpose |
|------|---------|
| `frontend/src/pages/ThreadsPage.tsx` | Main UI - identity table, editing |
| `frontend/src/pages/ThreadsPage.css` | Styles |
| `frontend/src/services/introspectionService.ts` | API client - `getIdentityFacts()` |

### Frontend Functions (ThreadsPage.tsx)

| Function | Line | Purpose |
|----------|------|---------|
| `fetchIdentityData()` | ~180 | Load identity table |
| `handleSaveIdentity()` | ~220 | Save edited row |
| `handleDeleteIdentity()` | ~250 | Delete row |
| `renderIdentityView()` | ~350 | Render identity table with L1/L2/L3 tabs |

### CSS Classes

```css
.identity-table-container
.level-tabs, .level-tab, .level-tab.active
.identity-table
.editing-row, .edit-panel
.type-badge.user, .type-badge.nola, .type-badge.machine
```

## Conflicts to Watch

| If you're changing... | Check with... |
|----------------------|---------------|
| User preferences | Log (might be temporal pattern) |
| Mood/emotional state | Log (temporal) or Philosophy (values) |
| Relationship data | Log (history) |
| Skills/capabilities | Form (what can do vs who I am) |

## README

Full documentation: `agent/threads/identity/README.md`
