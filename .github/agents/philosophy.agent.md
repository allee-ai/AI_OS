# Philosophy Thread Agent

**Read `stack.md` first for universal patterns.**

## Purpose

Philosophy stores Nola's values, ethical boundaries, and reasoning patterns. These shape how Nola approaches problems — her "personality".

**Key question:** "What do I believe? How should I think?"

## Contract: metadata vs data

Your adapter MUST implement:

```python
def get_metadata(self) -> dict:
    """Thread structure - thinking about thinking."""
    return {
        "files": ["adapter.py", "README.md"],
        "tables": ["philosophy_flat"],
        "modules": ["ethics", "preferences", "constraints"],
        "schema": {"key": "TEXT", "data_json": "TEXT", "level": "INT", "weight": "REAL"},
        "db_path": "/data/db/state.db"
    }

def get_data(self, level: int = 2) -> list:
    """Thread content - actual values/constraints."""
    return [{"key": "honesty", "data": "Always be truthful", "level": 1, "weight": 1.0}, ...]
```

## Level System: L1/L2/L3 Per Key

Like Identity, depth-based levels:
```
key: "core_value_honesty"
L1: "Be honest"
L2: "Be honest, even when uncomfortable. Prefer truth over comfort."
L3: "Honesty is foundational. Prefer truth over comfort, but deliver with care..."
```

## Database

### Primary Table: `philosophy_flat` (HEA-native, like identity_flat)

```sql
CREATE TABLE philosophy_flat (
    key TEXT PRIMARY KEY,
    metadata_type TEXT,      -- "value" | "constraint" | "style"
    metadata_desc TEXT,
    l1 TEXT NOT NULL,        -- Quick (~10 tokens)
    l2 TEXT NOT NULL,        -- Standard (~30 tokens)
    l3 TEXT NOT NULL,        -- Full (~100 tokens)
    weight REAL DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Legacy Tables (migrated to philosophy_flat)

- `philosophy_core_values` → metadata_type="value"
- `philosophy_ethical_bounds` → metadata_type="constraint"
- `philosophy_reasoning_style` → metadata_type="style"

## Adapter

**Location:** `Nola/threads/philosophy/adapter.py`

### Key Functions

```python
from Nola.threads.philosophy.adapter import PhilosophyThreadAdapter

adapter = PhilosophyThreadAdapter()

# Get values at level
values = adapter.get_data(level=2)

# Get specific module
ethics = adapter.get_module_data("ethical_bounds", level=2)
style = adapter.get_module_data("reasoning_style", level=2)

# Health check
health = adapter.health()
```

## Code Map

### Backend (Python/FastAPI)

| File | Purpose |
|------|---------|
| `Nola/threads/philosophy/adapter.py` | Core adapter - `get_data()`, `get_module_data()`, `health()` |
| `Nola/threads/philosophy/__init__.py` | Public API |
| `Nola/threads/philosophy/README.md` | Documentation |
| `Nola/services/api.py # introspection.py` | REST endpoints (lines 647-770) |
| `Nola/threads/schema.py` | DB helpers - `push_philosophy_row()`, `get_philosophy_table_data()`, `migrate_philosophy_to_flat()` |

### Backend Endpoints

| Endpoint | Method | Line | Purpose |
|----------|--------|------|---------|
| `/api/introspection/philosophy/table` | GET | ~650 | All rows with L1/L2/L3 |
| `/api/introspection/philosophy/{key}` | PUT | ~680 | Update row |
| `/api/introspection/philosophy` | POST | ~710 | Create new row |
| `/api/introspection/philosophy/{key}` | DELETE | ~740 | Delete row |
| `/api/introspection/philosophy/migrate` | POST | ~760 | Migrate from old tables |

### Frontend (React/TypeScript)

| File | Purpose |
|------|---------|
| `frontend/src/pages/ThreadsPage.tsx` | Philosophy table with L1/L2/L3 tabs + editing |
| `frontend/src/pages/ThreadsPage.css` | Styles (including `.type-badge.value/.constraint/.style`) |

### Frontend Functions (ThreadsPage.tsx)

| Function | Line | Purpose |
|----------|------|---------|
| `fetchPhilosophyData()` | ~100 | Load philosophy_flat table |
| `renderPhilosophyTable()` | ~440 | Renders via `renderFlatTable()` |
| `renderFlatTable()` | ~305 | Shared table renderer (L1/L2/L3 tabs, editing) |
| `saveEdit()` | ~250 | Save to `/api/introspection/philosophy/{key}` |

### CSS Classes

```css
.type-badge.value        /* purple - core values */
.type-badge.constraint   /* red - ethical bounds */
.type-badge.style        /* blue - reasoning style */
```

## Weight Meanings

| Range | Meaning |
|-------|---------|
| 0.9+ | Core ethics (honesty, no harm) |
| 0.6-0.8 | Key personality (curiosity, warmth) |
| 0.3-0.5 | Preferences (style, approach) |

## Conflicts to Watch

| If you're changing... | Check with... |
|----------------------|---------------|
| User preferences | Identity (user facts vs values) |
| Behavioral rules | Reflex (triggers vs principles) |
| Decision constraints | Form (capability limits) |

## README

Full documentation: `Nola/threads/philosophy/README.md`
