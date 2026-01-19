# AI Model Handoff Guide

**For: Any AI model continuing work on this project**

This document exists because context windows reset. Here's everything you need to pick up where the last model left off.

---

## What Is This Project?

**Nola** is a local-first personal AI with hierarchical memory. The key innovations:

> "Subconscious builds state, agent just reads it."
> "Structure beats scale" — 7B + architecture outperforms 100B flat context

The agent is stateless. Before each response, the subconscious assembles context from identity, memory, and logs using **spread activation** for associative recall.

---

## Current State (Updated: 2026-01-08)

### Completed ✅
- **Thread System Migration** - Old idv2/log_thread replaced with unified `Nola/threads/`
- New thread schema: `{thread}_{module}` tables (e.g., `identity_user_profile`, `log_events`)
- 5 threads operational: identity, log, reflex, philosophy, form, linking_core
- Subconscious module (`Nola/subconscious/`)
- LinkingCore for relevance scoring (`Nola/threads/linking_core/`)
- Agent integration (stateless with `consciousness_context` param)
- 23 tests passing

**React Router Frontend** (Jan 8, 2026)
- OS-like navigation: Dashboard, Chat, Threads, Docs, Contact pages
- Identity table with L1/L2/L3 CRUD (view, edit, delete)
- Docs viewer with nested directory tree
- Light theme throughout

**Spread Activation System** (Jan 8, 2026)
- `concept_links` table with Hebbian learning (strength + decay)
- `spread_activate()` for associative memory retrieval
- `generate_hierarchical_key()` — facts become `sarah.likes.blue`
- `extract_concepts_from_text()` — extracts queryable concepts
- `activate_memories()` in LinkingCore — combines embeddings + spread activation

### In Progress 🔄
- Focus System implementation (sequence learning, key prediction)
- Acquaintance tracking (web endpoint → acquaintance namespace)

### Not Started ❌
- Dream state / background reflection
- Matrix/email integration
- Multi-model routing
- Cloud sync (optional)

---

## Key Architecture Change (Jan 2026)

**Old System:**
```
identity_sections table → data_l1_json, data_l2_json, data_l3_json columns
log_thread/logger.py → separate logging system
```

**New System:**
```
threads_registry table → lists all threads and modules
{thread}_{module} tables → identity_user_profile, identity_nola_self, etc.
Nola/threads/__init__.py → unified thread interface
```

Each row now has: `key`, `context_level`, `data`, `metadata`, `weight`, `updated_at`

---

## Key Patterns

### 1. Message Flow
```
User Message
    → agent_service.classify_stimuli() → "realtime"/"conversational"/"analytical"
    → get_consciousness_context(level=1/2/3)
    → agent.generate(consciousness_context=context)
    → Response
```

### 2. Context Levels (HEA)
```
L1 (~10 tokens):  Name, role - for quick exchanges
L2 (~50 tokens):  + Projects, preferences - default
L3 (~200 tokens): + Full history - for analysis
```

### 3. Thread Interface
All state modules implement:
```python
class ThreadInterface(Protocol):
    name: str
    description: str
    def health(self) -> HealthReport
    def introspect(self, context_level: int) -> IntrospectionResult
```

---

## Where Things Live

```
Nola/
├── agent.py              # LLM interface, generate()
├── threads/              # Unified thread system
│   ├── __init__.py       # get_thread(), ThreadManager
│   ├── schema.py         # DB schema + spread activation
│   │   ├── concept_links table
│   │   ├── fact_relevance table
│   │   ├── spread_activate()
│   │   └── generate_hierarchical_key()
│   ├── linking_core/     # Relevance scoring + associative memory
│   │   └── adapter.py    # activate_memories(), get_associative_context()
│   └── [identity|log|reflex|philosophy|form]/
├── subconscious/         # Context assembly
│   ├── orchestrator.py   # SubconsciousOrchestrator
│   └── adapters/         # Thread adapters
├── services/
│   ├── agent_service.py  # Main entry, HEA routing
│   ├── memory_service.py # Fact extraction + hierarchical keys
│   └── consolidation_daemon.py # Background fact promotion
├── temp_memory/
│   └── store.py          # Short-term facts (now with hier_key)
└── react-chat-app/       # Web UI
    ├── backend/          # FastAPI
    │   └── api/          # introspection.py, database.py
    └── frontend/         # React + Vite + React Router
        └── src/pages/    # Dashboard, Chat, Threads, Docs, Contact
```

**Database:** `data/db/state.db`
- `threads_registry` - All registered threads/modules
- `identity_*`, `log_*`, `reflex_*`, `philosophy_*`, `form_*` - Thread tables
- `concept_links` - Spread activation network (concept_a ↔ concept_b, strength)
- `fact_relevance` - Multi-dimensional fact scoring (identity/log/form scores)
- `key_cooccurrence` - Hebbian co-occurrence tracking
- `temp_facts` - Short-term memory with hierarchical keys

---

## Common Tasks

### Run the app
```bash
./start.sh
```

### Run tests
```bash
pytest tests/ -v
```

### Test subconscious
```python
from Nola.subconscious import wake, get_consciousness_context
wake()
print(get_consciousness_context(level=2))
```

### Query the database
```bash
# List all threads
sqlite3 data/db/state.db "SELECT * FROM threads_registry"

# Get identity data
sqlite3 data/db/state.db "SELECT key, context_level, data FROM identity_user_profile"

# Check all tables
sqlite3 data/db/state.db ".tables"
```

---

## If You're Adding a Feature

### New Thread Adapter
1. Create `Nola/subconscious/threads/my_adapter.py`
2. Implement `ThreadInterface`
3. Register in `core.py` `_register_default_threads()`

### New API Endpoint
1. Add to `Nola/react-chat-app/backend/api/`
2. Register router in `main.py`

### New Stimuli Channel
1. Create handler in `Nola/Stimuli/comms/`
2. Call `agent_service.send_message()`

---

## Documentation Map

| Need | Read |
|------|------|
| User-friendly intro | [README.md](README.md) |
| Developer guide | [DEVELOPERS.md](DEVELOPERS.md) |
| Architecture deep-dive | [Nola/ARCHITECTURE.md](Nola/ARCHITECTURE.md) |
| Theory behind HEA | [docs/concept_attention_theory.md](docs/concept_attention_theory.md) |
| Module specifics | Each module has a README.md |

---

## Recent Decisions

1. **Agent is stateless** - Subconscious owns all state
2. **3-level context** - L1/L2/L3 based on stimuli type
3. **SQLite over JSON** - For identity and facts storage
4. **Thread adapters** - Pluggable modules via protocol

---

## If Something Breaks

1. Check `Nola/LOG.txt`
2. Run `pytest tests/ -v`
3. Check subconscious status:
   ```python
   from Nola.subconscious import get_status
   print(get_status())
   ```
4. Read the module's README.md

---

*This file should be updated whenever major architectural changes are made.*
