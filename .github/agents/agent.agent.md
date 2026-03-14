# 🧠 Agent — Behavioral & Structural Guide
**Role**: Build, extend, or modify AI_OS modules using verified codebase patterns  
**Scope**: Backend threads, top-level modules, adapters, schemas, routers, frontend modules  
**Rule**: Every change follows the patterns already in the codebase. No invention.

---

## Naming

- **"Agent"** is the boilerplate — the generic, unnamed instance before the user configures it. All code references use `agent` (class `Agent`, `get_agent()`, `agent.generate()`).
- **"Nola"** is the demo database identity — the pre-configured agent that ships with `state_demo.db`. Her machine profile is `identity.machine.name: Nola`. Training data and gold examples reference Nola because they're generated from demo state.
- **The user's agent** gets its name from `identity.machine.name` in `state.db` (personal database). It could be anything — Atlas, Vega, whatever. The name is a stored fact, not a constant.
- **Never hardcode "Nola" in runtime code.** The name comes from the identity thread at introspection time. Hardcoding it in training data and documentation is fine — that's demo context.

---

## File Responsibilities

| File | Does | Never Does |
|------|------|------------|
| `schema.py` | Tables, CRUD, `init_*_tables()` | Import adapters or routers |
| `api.py` | FastAPI router, HTTP boundary | Raw SQL, business logic |
| `adapter.py` | `introspect()`, `health()`, `get_data()` | HTTP, table creation |
| `__init__.py` | Export `router` (+ `init_*` for threads) | Contain logic |
| `train.py` | Generate JSONL training pairs | Touch the database |

---

## Database Pattern

Every schema uses the central connection from `data/db`:

```python
from data.db import get_connection
from contextlib import closing

def init_example_tables(conn=None):
    own_conn = conn is None
    conn = conn or get_connection()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS example (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ...
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    if own_conn:
        conn.commit()
        conn.close()
```

`get_connection()` already sets: `row_factory = sqlite3.Row`, `PRAGMA foreign_keys = ON`, `PRAGMA busy_timeout = 30000`, `PRAGMA journal_mode = WAL`. Never set these yourself.

Always use `with closing(get_connection()) as conn:` for short-lived queries.

---

## Router Pattern

```python
from fastapi import APIRouter
router = APIRouter(prefix="/api/{module_name}", tags=["{module_name}"])
```

Every router follows the same CRUD skeleton:

```
GET  /api/{module}          → list / overview
GET  /api/{module}/{id}     → single item
POST /api/{module}          → create
PUT  /api/{module}/{id}     → update
DELETE /api/{module}/{id}   → remove
```

Registration in `scripts/server.py`:
```python
from {package} import router as {name}_router
app.include_router({name}_router)
```

No prefix override at `include_router`. The prefix lives on the router itself.

---

## Adapter Pattern (Threads Only)

Every thread adapter extends `BaseThreadAdapter` from `agent/threads/base.py`:

```python
class ExampleThreadAdapter(BaseThreadAdapter):
    _name = "example"
    _description = "One-line purpose"
    _token_budgets = {1: 150, 2: 400, 3: 800}

    def introspect(self, context_level=2, query=None, threshold=0.0) -> IntrospectionResult:
        ...
    def health(self) -> HealthReport:
        ...
    def get_data(self, level=2, limit=50) -> List[Dict]:
        ...
```

**L1/L2/L3 levels** — controlled by the orchestrator's score:
| Level | Score Range | Tokens | When |
|-------|------------|--------|------|
| L1 | 0–3.5 | ~150 | Quick / low relevance |
| L2 | 3.5–7.0 | ~400 | Default conversational |
| L3 | 7.0–10 | ~800 | Deep / high relevance |

Registration in `agent/threads/__init__.py`:
```python
_THREADS["example"] = ExampleThreadAdapter()
```

---

## Orchestrator — How STATE Is Built

`agent/subconscious/orchestrator.py` drives everything:

1. `score(query)` → linking_core scores each thread 0–10
2. Score maps to L1/L2/L3
3. Each adapter's `introspect()` runs at that level
4. Facts concatenate into `== STATE ==` block
5. STATE injects into the system prompt via `agent.py`

**Never call the orchestrator from a thread.** Threads are passive — they return data when asked.

---

## Frontend Pattern

```
frontend/src/modules/{module}/
├── pages/{Module}Page.tsx     # Route-level component
├── components/                # UI pieces
├── hooks/                     # useFetch*, useModule*
├── services/                  # fetch() wrappers → /api/{module}
└── types.ts                   # TypeScript interfaces
```

Service files call `fetch("/api/{module}/...")` — no axios, no external HTTP libs.

---

## Adding a New Thread Module (Checklist)

1. `agent/threads/{name}/schema.py` — tables + `init_*_tables()`
2. `agent/threads/{name}/adapter.py` — extends `BaseThreadAdapter`
3. `agent/threads/{name}/api.py` — `router = APIRouter(prefix="/api/{name}")`
4. `agent/threads/{name}/__init__.py` — export `router`
5. `agent/threads/__init__.py` — register in `_THREADS`
6. `scripts/server.py` — import + `app.include_router()`
7. `frontend/src/modules/{name}/` — page, service, types
8. `frontend/src/App.tsx` — add route

## Adding a Top-Level Module (Checklist)

1. `{name}/schema.py` — tables + `init_*_tables()`
2. `{name}/api.py` — `router = APIRouter(prefix="/api/{name}")`
3. `{name}/__init__.py` — export `router`
4. `scripts/server.py` — import + `app.include_router()`
5. `frontend/src/modules/{name}/` — page, service, types
6. `frontend/src/App.tsx` — add route

---

## Behavioral Boundaries

| Principle | Do | Don't |
|-----------|----|-------|
| **Scope** | One module at a time | Cross-module imports between threads |
| **Data flow** | Thread → orchestrator → agent → prompt | Thread → thread directly |
| **DB access** | `get_connection()` from `data/db` | `sqlite3.connect()` with a raw path |
| **Error handling** | Validate at API boundary | Try/except deep in adapters |
| **State** | Stateless adapters, stateless routers | Module-level globals or caches |
| **Naming** | `snake_case` files, `PascalCase` classes | Abbreviations or acronyms in names |

---

## Step Sizing for Smaller Models

If you're working with a ≤7B model, break every task into steps that touch **one file at a time**:

1. Write schema.py → test with `init_*_tables()`
2. Write adapter.py → test with `health()`
3. Write api.py → test with `curl`
4. Write __init__.py → test import
5. Register in server.py → test endpoint
6. Frontend service → test fetch
7. Frontend page → test render

Never combine steps. If a step fails, fix it before moving on.

---

## Anti-Patterns

- ❌ Importing one thread's schema from another thread
- ❌ Adding a new table without `init_*_tables()` that's callable from startup
- ❌ Using `conn.execute()` without `closing()` or manual close
- ❌ Adding router prefix at `include_router()` instead of on the router
- ❌ Storing computed state in a thread — threads store raw facts only
- ❌ Calling Ollama directly from a thread adapter — only the agent calls the model
- ❌ Writing a test that passes by constructing its own expected result
- ❌ Running `rm -rf` or `--force` on anything without confirming scope
- ❌ Using `--no-verify` to skip git hooks

---

## CLI & Debug Boundaries

When working from the command line or fixing errors:

| Do | Don't |
|----|-------|
| `docker logs ai-os --tail 30` to read errors | Guess what the error might be |
| `curl -s http://localhost:8000/api/{mod}` to verify | Assume the endpoint works because the code looks right |
| `grep -r "from {module}" --include="*.py" .` to check imports | Manually trace imports in your head |
| `pytest -k "test_name" -v` to run one test | Run the full suite when debugging a single failure |
| `with closing(get_connection()) as conn:` always | Bare `get_connection()` without cleanup |
| Read the traceback bottom-up (last frame = real cause) | Read top-down and get lost in framework internals |

### Fix Protocol

1. **Reproduce** — get the exact error message
2. **Read** — open the file at the line number in the traceback
3. **Trace** — follow the call stack: `api.py → schema.py → db`
4. **Fix** — change the minimum code to resolve the root cause
5. **Verify** — `curl` or `pytest` to confirm
6. **Check blast radius** — `grep` for other callers of the function you changed
