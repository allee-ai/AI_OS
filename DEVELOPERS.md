# Nola Developer Guide

Technical documentation for building features and understanding the codebase.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Node](https://img.shields.io/badge/node-18+-green.svg)
![TypeScript](https://img.shields.io/badge/typescript-5.0+-blue.svg)

---

## 🆕 Latest: Focus System Architecture (Jan 2026)

**"Attention is all you need" → "Focus is all you need"**

AI_OS now uses a **focus-based architecture** where the database learns key sequences and pre-selects relevant context before the LLM sees anything.

- **DB (Control Plane):** Learns "after key A comes key B" patterns
- **LLM (Data Plane):** Generates from pre-focused space only
- **Learning Loop:** Every query updates weights and sequence predictions

📖 **Read the plan:** [docs/implementation/FOCUS_IMPLEMENTATION.md](docs/implementation/FOCUS_IMPLEMENTATION.md)  
✅ **Quick checklist:** [docs/FOCUS_CHECKLIST.md](docs/FOCUS_CHECKLIST.md)  
📝 **Discovery notes:** [docs/DEV_NOTES.md](docs/DEV_NOTES.md) - Focus System Discovery section

---

## Quick Navigation

| I want to... | Go to |
|--------------|-------|
| Understand the architecture | [Architecture Overview](#architecture-overview) |
| Add a new feature | [Adding Features](#adding-features) |
| Add a new thread/adapter | [New Thread Adapter](#new-thread-adapter) |
| Add an API endpoint | [New API Endpoint](#new-api-endpoint) |
| Run tests | [Testing](#testing) |
| Debug context assembly | [Debugging](#debugging) |

### Module READMEs

| Module | What it does | README |
|--------|--------------|--------|
| **subconscious** | Builds context before each response | [Nola/subconscious/README.md](Nola/subconscious/README.md) |
| **idv2** | SQLite identity storage | [Nola/idv2/README.md](Nola/idv2/README.md) |
| **temp_memory** | Session facts before consolidation | [Nola/temp_memory/README.md](Nola/temp_memory/README.md) |
| **log_thread** | Event timeline | [Nola/log_thread/README.md](Nola/log_thread/README.md) |
| **services** | FastAPI integration, HEA routing | [Nola/services/README.md](Nola/services/README.md) |
| **react-chat-app** | Web UI | [Nola/react-chat-app/README.md](Nola/react-chat-app/README.md) |
| **Stimuli** | Input channels | [Nola/Stimuli/readme.md](Nola/Stimuli/readme.md) |

### Key Files (When You Need to Change Something)

| Change | File | Line to find |
|--------|------|--------------|
| How context is assembled | `Nola/subconscious/core.py` | `get_consciousness_context` |
| How stimuli are classified | `Nola/services/agent_service.py` | `classify_stimuli` |
| How agent generates responses | `Nola/agent.py` | `def generate` |
| How facts are scored | `Nola/services/consolidation_daemon.py` | `score_fact` |
| Context level token budgets | `Nola/services/agent_service.py` | `L1_TOKENS`, `L2_TOKENS` |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    STIMULI CHANNELS                     │
├──────────────┬──────────────┬──────────────┬───────────┤
│  React Chat  │    Matrix    │    Email     │   CLI     │
│  (primary)   │   (future)   │   (future)   │ (exists)  │
└──────┬───────┴──────────────┴──────────────┴───────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│                 AGENT SERVICE (HEA)                     │
│  Classifies stimuli → selects context level → routes    │
└──────┬──────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│                    SUBCONSCIOUS                         │
│  Builds context from all threads before each response   │
├─────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────────┐  │
│  │Identity │  │ Memory  │  │   Log   │  │  Future   │  │
│  │ Thread  │  │  Store  │  │ Thread  │  │ Threads   │  │
│  └────┬────┘  └────┬────┘  └────┬────┘  └───────────┘  │
└───────┼────────────┼────────────┼───────────────────────┘
        │            │            │
        ▼            ▼            ▼
┌─────────────────────────────────────────────────────────┐
│                   SQLite (state.db)                     │
└─────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│              AGENT (Stateless Singleton)                │
│  Receives assembled context, generates response         │
└──────┬──────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│                 Ollama (Local LLM)                      │
└─────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
AI_OS/
├── start.sh                 # Entry point - Local/Docker mode chooser
├── DEVELOPERS.md            # ← You are here
│
├── Nola/                    # 🧠 Core AI system
│   ├── agent.py             # Thread-safe singleton, LLM calls
│   ├── contract.py          # Metadata protocol (re-exports from subconscious)
│   ├── Nola.json            # Runtime identity state
│   │
│   ├── subconscious/        # Central nervous system
│   │   ├── __init__.py      # API: wake(), sleep(), get_consciousness_context()
│   │   ├── core.py          # ThreadRegistry, SubconsciousCore
│   │   ├── contract.py      # Metadata protocol for sync
│   │   ├── loops.py         # Background: Consolidation, Sync, Health
│   │   ├── triggers.py      # Event-driven execution
│   │   └── threads/         # Pluggable adapters
│   │       ├── base.py      # ThreadInterface protocol
│   │       ├── identity_adapter.py
│   │       ├── memory_adapter.py
│   │       └── log_adapter.py
│   │
│   ├── idv2/                # SQLite-backed identity
│   │   └── idv2.py          # push/pull sections, level filtering
│   │
│   ├── identity_thread/     # JSON-based identity (legacy, still used)
│   │   ├── identity.py      # Aggregator
│   │   ├── machineID/       # Machine context
│   │   └── userID/          # User context
│   │
│   ├── temp_memory/         # Session-scoped fact storage
│   │   └── store.py         # add_fact(), get_pending(), consolidate
│   │
│   ├── log_thread/          # Event timeline
│   │   ├── logger.py        # log_event(), read_events()
│   │   └── config.py        # Rotation, persistence settings
│   │
│   ├── services/            # Service layer
│   │   ├── agent_service.py # FastAPI integration, HEA routing
│   │   ├── memory_service.py
│   │   └── consolidation_daemon.py  # Fact scorer, promotion
│   │
│   └── Stimuli/             # External stimuli
│       ├── conversations/   # JSON chat logs
│       └── comms/           # Future: Matrix, email
│
├── Nola/react-chat-app/     # 💻 Web UI
│   ├── backend/             # FastAPI server
│   │   ├── main.py          # App entry, WebSocket handler
│   │   └── api/
│   │       ├── chat.py      # REST: /api/chat/*
│   │       ├── database.py  # REST: /api/database/*
│   │       └── websockets.py
│   └── frontend/            # React + Vite + TypeScript
│       └── src/
│           ├── components/  # UI components
│           ├── hooks/       # React hooks
│           └── services/    # API client
│
├── tests/                   # 🧪 pytest suite
│   ├── test_agent.py        # Singleton, thread safety
│   ├── test_idv2.py         # DB operations
│   └── test_hea.py          # Context levels
│
├── eval/                    # 📊 Evaluation harness
│   ├── duel.py              # Adversarial benchmark CLI
│   ├── judges.py            # Judge model integrations
│   └── metrics.py           # Scoring functions
│
├── data/db/                 # SQLite databases
│   └── state.db             # Identity, facts, events
│
└── docs/                    # 📚 Documentation
    ├── concept_attention_theory.md
    └── evaluation_framework.md
```

---

## Core Concepts

### Hierarchical Experiential Attention (HEA)

Context levels control how much information flows to the LLM:

| Level | Tokens | Trigger | Use Case |
|-------|--------|---------|----------|
| L1 | ~10 | Quick exchanges, greetings | Minimal latency |
| L2 | ~50 | Default conversation | Balanced |
| L3 | ~200 | Complex questions, analysis | Full context |

**Escalation Logic** (in `agent_service.py`):
```python
def classify_stimuli(message: str) -> str:
    if is_greeting(message):
        return "realtime"      # → L1
    if needs_deep_context(message):
        return "analytical"    # → L3
    return "conversational"    # → L2
```

### Subconscious Pattern

> "Subconscious builds state, agent just reads it."

Before each `agent.generate()` call:
1. `agent_service` calls `get_consciousness_context(level=X)`
2. Subconscious introspects all registered threads
3. Returns assembled context string
4. Agent receives context as `consciousness_context` param

```python
# In agent_service.py
consciousness_context = get_consciousness_context(level=context_level)
response = agent.generate(
    user_input=message,
    consciousness_context=consciousness_context
)
```

### Thread Interface

All state modules implement `ThreadInterface`:

```python
class ThreadInterface(Protocol):
    name: str
    description: str
    
    def health(self) -> HealthReport: ...
    def introspect(self, context_level: int) -> IntrospectionResult: ...
```

---

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Ollama

### Local Development

```bash
# Backend (terminal 1)
cd Nola/react-chat-app/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (terminal 2)
cd Nola/react-chat-app/frontend
npm install
npm run dev

# Run tests
pytest tests/ -v
```

### API Documentation

With backend running: http://localhost:8000/docs

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat/message` | POST | Send message, get response |
| `/api/chat/history` | GET | Retrieve conversation history |
| `/api/database/identity` | GET | Get identity by level |
| `/api/database/events` | GET | Query event log |
| `/ws` | WebSocket | Real-time chat |

---

## Adding Features

### New Thread Adapter

1. Create `Nola/subconscious/threads/my_adapter.py`:

```python
from .base import ThreadInterface, HealthReport, IntrospectionResult

class MyAdapter(ThreadInterface):
    name = "my_thread"
    description = "Does something useful"
    
    def health(self) -> HealthReport:
        return HealthReport(status="ok", message="Operational")
    
    def introspect(self, context_level: int) -> IntrospectionResult:
        data = self._get_data_for_level(context_level)
        return IntrospectionResult(
            thread_name=self.name,
            context_level=context_level,
            data=data,
            summary=f"Found {len(data)} items"
        )
```

2. Register in `Nola/subconscious/core.py`:

```python
def _register_default_threads(self):
    # ... existing threads ...
    from .threads.my_adapter import MyAdapter
    self.register(MyAdapter())
```

### New Stimuli Channel

1. Create handler in `Nola/Stimuli/comms/`
2. Map to existing `agent_service.py` interface:

```python
# Your channel just needs to call:
response = await agent_service.send_message(
    content="User message",
    session_id="channel_session_123"
)
```

### New API Endpoint

Add to `Nola/react-chat-app/backend/api/`:

```python
# api/my_feature.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/my-feature", tags=["my-feature"])

@router.get("/")
async def get_data():
    return {"data": "..."}
```

Register in `main.py`:
```python
from api.my_feature import router as my_feature_router
app.include_router(my_feature_router)
```

---

## Testing

```bash
# All tests
pytest tests/ -v

# Specific module
pytest tests/test_agent.py -v

# With coverage
pytest tests/ --cov=Nola --cov-report=html
```

### Test Files

- `test_agent.py` — Singleton pattern, thread safety, provider toggle
- `test_idv2.py` — Database operations, level filtering, migration
- `test_hea.py` — Stimuli classification, context budgets

---

## Debugging

### Check Subconscious Status

```python
from Nola.subconscious import get_status
print(get_status())
```

### View Context Assembly

```python
from Nola.subconscious import wake, get_consciousness_context
wake()
print(get_consciousness_context(level=2))
```

### Query Event Log

```python
from Nola.log_thread import read_events
events = read_events(event_type="conversation:start", limit=10)
```

### Database Inspection

```bash
sqlite3 data/db/state.db ".schema"
sqlite3 data/db/state.db "SELECT * FROM identity_sections"
```

---

## Code Style

- **Python**: Black formatter, type hints required
- **TypeScript**: ESLint + Prettier
- **Commits**: Conventional commits (`feat:`, `fix:`, `docs:`)

---

## Related Documentation

- [Subconscious README](Nola/subconscious/README.md) — Thread system details
- [HEA Theory](docs/theory/concept_attention_theory.md) — Context attention theory
- [All Documentation](docs/README.md) — Full documentation index
- [Contributing Guide](CONTRIBUTING.md) — PR process
