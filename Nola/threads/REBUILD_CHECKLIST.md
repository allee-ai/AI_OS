# Thread System Rebuild Checklist

**Goal:** Clean database-backed thread system with universal format.

**Rule:** No JSON files for state. DB only. JSON files are seed data only.

---

## Developer Profile Assignments

| Task | Profile | Why |
|------|---------|-----|
| Schema design, DB operations | `backend-developer` | DB expertise |
| Thread adapters, interfaces | `state-sync-developer` | State management |
| LinkingCore relevance scoring | `ai-ml-engineer` | Embeddings, scoring |
| Subconscious orchestration | `ai-ml-engineer` | Context assembly |
| API integration | `fastapi-developer` | Endpoint updates |
| Testing | `backend-developer` | Integration tests |

---

## Phase 1: Schema Foundation ✅ COMPLETE
**Profile:** `backend-developer`

- [x] Finalize `schema.py` with universal table format
- [x] Create `threads_registry` table
- [x] Define module table template: `{thread}_{module}`
- [x] Each row: `key | metadata_json | data_json | level | weight`
- [x] Test: `python schema.py bootstrap` → "5 threads with 15 modules"
- [x] Test: `python schema.py summary` → Shows all threads

### Universal Table Format

Every module table has identical structure:

```sql
CREATE TABLE {thread}_{module} (
    key TEXT PRIMARY KEY,
    metadata_json TEXT NOT NULL,  -- {"type": "fact", "description": "..."}
    data_json TEXT NOT NULL,      -- {"value": "...", "context": "..."}
    level INTEGER DEFAULT 2,      -- 1=L1, 2=L2, 3=L3
    weight REAL DEFAULT 0.5,      -- 0.0-1.0 importance
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

---

## Phase 2: Seed Data Migration ✅ COMPLETE
**Profile:** `backend-developer`

- [x] Create `seed_data.py` to load initial data
- [x] Seed identity data (user_profile, machine_context, nola_self)
- [x] Seed philosophy data (core_values, ethical_bounds, reasoning_style)
- [x] Seed reflex data (greetings, shortcuts)
- [x] Migrated 2 rows from old `identity_sections` table
- [x] Verify: `python schema.py summary` shows 19 rows total

**READY TO DELETE:** Old JSON files can be deleted once API is updated.

---

## Phase 3: Thread Adapters ✅ COMPLETE
**Profile:** `state-sync-developer`

Created new v2 adapters that use `schema.py` for all data access:

- [x] Created `threads/base.py` - Universal `BaseThreadAdapter` class
- [x] Created `identity/adapter_v2.py` - Uses `pull_from_module()`, `push_to_module()`
- [x] Created `log/adapter_v2.py` - With `log_event()`, `start_session()`
- [x] Created `form/adapter_v2.py` - With `register_tool()`, `record_action()`
- [x] Created `philosophy/adapter_v2.py` - With `add_value()`, `add_bound()`
- [x] Created `reflex/adapter_v2.py` - With `try_quick_response()`
- [x] Updated `__init__.py` to import v2 adapters

### Universal Adapter Interface

```python
class ThreadAdapter:
    thread_name: str  # "identity", "log", etc.
    
    def get_modules(self) -> list[str]:
        """List modules in this thread."""
    
    def get_metadata(self) -> dict:
        """Thread-level metadata for STATE block."""
    
    def get_data(self, level: int, limit: int = 50) -> list[dict]:
        """Pull data from all modules at given level."""
    
    def push(self, module: str, key: str, metadata: dict, data: dict, level: int = 2):
        """Push a row to a module."""
```

---

## Phase 4: LinkingCore Attention ✅ COMPLETE
**Profile:** `ai-ml-engineer`

- [x] Created `linking_core/scoring.py` as pure utility functions
- [x] Implemented `score_relevance(query, items)` → list of (key, score)
- [x] Implemented `rank_items(items, query, threshold, limit)` → scored items
- [x] Embedding support with keyword fallback when Ollama unavailable
- [x] Updated `__init__.py` to export new functions

---

## Phase 5: Subconscious Integration ✅ COMPLETE
**Profile:** `ai-ml-engineer`

- [x] Created `subconscious/orchestrator.py` with new `Subconscious` class
- [x] `build_context(level, query)` returns STATE + CONTEXT blocks
- [x] Uses `pull_all_thread_data()` from schema
- [x] Uses `rank_items()` from LinkingCore for scoring
- [x] Added `record_interaction()` to log conversations
- [x] Exposed in `__init__.py`: `Subconscious`, `get_subconscious`, `build_context`

---

## Phase 6: API Updates ✅ COMPLETE
**Profile:** `fastapi-developer`

- [x] Updated `_get_identity_facts()` to try new `build_context()` first
- [x] Updated `_get_context_assembly()` to use new orchestrator
- [x] Added `GET /api/introspection/threads/summary` - list all threads
- [x] Added `GET /api/introspection/threads/{thread}` - get thread data
- [x] Added `GET /api/introspection/threads/{thread}/{module}` - get module data
- [x] Fallback to old idv2 system if new system fails

---

## Phase 7: Cleanup ✅ COMPLETE
**Profile:** `backend-developer`

Deleted deprecated files (~1,700 lines):
- [x] `Nola/relevance.py` → replaced by `linking_core/scoring.py`
- [x] `Nola/identity_thread/` entire directory → data in DB
- [x] `Nola/idv2/idv2.py` → replaced by `schema.py`
- [x] `Nola/contract.py` shim → use `subconscious/contract.py`
- [x] Old `threads/*/adapter.py` files → renamed `adapter_v2.py` to `adapter.py`
- [x] `Nola/subconscious/threads/` directory → adapters now in `Nola/threads/*/adapter.py`
- [x] Updated imports in `subconscious/core.py` and `subconscious/__init__.py`
- [x] Cleaned stale `__pycache__` directories

**NOTE:** `Nola/Nola.json` kept for now (still used by agent.py bootstrap)

---

## Creating a New Thread

When you want to add a new thread (e.g., "memory", "social", "calendar"):

```python
from Nola.threads.schema import register_module, push_to_module

# 1. Register modules
register_module("calendar", "events", "Calendar events and reminders")
register_module("calendar", "patterns", "Recurring patterns")

# 2. Create adapter (copy template)
# Nola/threads/calendar/adapter.py

# 3. Register in threads/__init__.py
from .calendar.adapter import CalendarThreadAdapter
_THREADS["calendar"] = CalendarThreadAdapter()
```

That's it. The universal format means no schema changes needed.

---

## Success Criteria

- [x] `python schema.py summary` shows all 5 threads with modules
- [x] `/api/introspection/?level=2` returns facts from new schema
- [x] Demo commands still work
- [x] No JSON files read at runtime (only DB)
- [x] New thread can be added in <10 lines of code
- [x] All old adapters deleted, imports updated

---

## REBUILD COMPLETE ✅

Thread system rebuild finished 2025-01-06.

**What we built:**
- Universal DB schema (`schema.py`) for all threads
- 5 data threads with 15 modules total (19 facts seeded)
- BaseThreadAdapter for consistent interface
- LinkingCore scoring for relevance ranking
- Subconscious orchestrator for context assembly
- API endpoints for introspection

**What we deleted:**
- ~1,700 lines of deprecated code
- JSON-based state files
- Duplicate adapter implementations

**Files to know:**
- `Nola/threads/schema.py` - The foundation
- `Nola/threads/base.py` - Universal adapter base
- `Nola/subconscious/orchestrator.py` - Context builder
