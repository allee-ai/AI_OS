# AI_OS Stack Reference

All thread agents share this context. Read this first.

## Tech Stack

| Layer | Technology | Location |
|-------|------------|----------|
| **Backend** | FastAPI + Uvicorn | `Nola/react-chat-app/backend/` |
| **Frontend** | React + Vite + React Router | `Nola/react-chat-app/frontend/` |
| **Database** | SQLite | `data/db/state.db` |
| **LLM** | Ollama (local) | System service |
| **Embeddings** | nomic-embed-text | Via Ollama |
| **Agent Core** | Python 3.11+ | `Nola/agent.py` |

## Architecture: 5 Data Threads + 1 Algorithm Thread

```
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ IDENTITY │ │   LOG    │ │   FORM   │ │PHILOSOPHY│ │  REFLEX  │
│  L1/L2/L3│ │ recency  │ │caps/state│ │  L1/L2/L3│ │ triggers │
└────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
     └────────────┴────────────┴────────────┴────────────┘
                              ↓
                    ┌─────────────────┐
                    │  LINKING CORE   │
                    │  (algorithms)   │
                    └─────────────────┘
```

## Universal Database Schema

Every thread module uses this table structure:

```sql
CREATE TABLE {thread}_{module} (
    key TEXT PRIMARY KEY,
    metadata_json TEXT NOT NULL,
    data_json TEXT NOT NULL,
    level INTEGER DEFAULT 2,
    weight REAL DEFAULT 0.5,
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## Universal Adapter Interface

Every thread adapter implements:

```python
class XxxThreadAdapter(BaseThreadAdapter):
    _name = "xxx"
    _description = "..."
    
    def get_data(self, level: int = 2, limit: int = 50) -> List[Dict]
    def health(self) -> HealthReport
    def introspect(self, context_level: int = 2) -> IntrospectionResult
    def push(self, module, key, metadata, data, level, weight)
```

## Key Files

| Purpose | Location |
|---------|----------|
| Thread schema | `Nola/threads/schema.py` |
| Base adapter | `Nola/threads/base.py` |
| API introspection | `Nola/react-chat-app/backend/api/introspection.py` |
| Frontend threads page | `Nola/react-chat-app/frontend/src/pages/ThreadsPage.tsx` |
| Frontend styles | `Nola/react-chat-app/frontend/src/pages/ThreadsPage.css` |

## Context Levels (HEA)

| Level | Tokens | Identity/Philosophy | Log |
|-------|--------|---------------------|-----|
| L1 | ~10/key | Brief fact | Last 10 events |
| L2 | ~30/key | Standard detail | Last 100 events |
| L3 | ~100/key | Full context | Last 1000 events |

## Before Making Changes

1. Check which thread owns this data
2. Read that thread's README at `Nola/threads/{thread}/README.md`
3. Verify no conflicts with other threads
4. Test with: `curl http://localhost:8000/api/introspection/threads/health`

## Running the System

```bash
# Start backend
cd Nola/react-chat-app/backend && python -m uvicorn main:app --reload --port 8000

# Start frontend
cd Nola/react-chat-app/frontend && npm run dev

# Check health
curl http://localhost:8000/api/introspection/threads/health
```
