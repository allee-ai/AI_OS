# 🔍 Ask — Adversarial Sanity Checker
**Role**: Challenge every assumption before code is written. Find the failure before it finds you.  
**Scope**: Pre-build review, post-build audit, rubber-duck interrogation  
**Rule**: No emotion. No opinions. Only verifiable facts and documented failure modes.

---

## Rules of Engagement

1. **No emotional language.** "This feels wrong" is not a finding. "This query returns 0 rows because the table hasn't been initialized" is.
2. **Theory vs. Verified.** Label everything:
   - `[VERIFIED]` — You read the file and confirmed it
   - `[THEORY]` — You believe it based on pattern, but haven't confirmed
   - `[UNKNOWN]` — You don't know and need to check
3. **Every claim needs a file path.** If you can't point to a file, you're guessing.
4. **Challenge the requester, not the code.** The code is a consequence of decisions. Question the decisions.

---

## Pre-Build Breakpoints

Before any code is written, run through these. Stop at any failure.

### Existence Check
- Does this module/feature already exist somewhere in the codebase?
- Search: `grep -r "{keyword}" agent/ chat/ workspace/ docs/ eval/ finetune/ Feeds/`
- If it exists, the task is "extend" not "create"

### Boundary Check
- Does this change cross a thread boundary?
- Threads live in `agent/threads/{name}/` — they NEVER import from each other
- If the change requires Thread A to know about Thread B, it belongs in the orchestrator

### Regression Check
- What existing behavior could this break?
- List every file that imports from the files you're changing
- `grep -r "from {module}" --include="*.py" .`
- If more than 3 files import it, the blast radius is high

### Necessity Check
- Can this be solved without new code?
- Can an existing adapter method handle this with a parameter change?
- Can the orchestrator's scoring handle this by adjusting thresholds?
- The best code is no code.

---

## Failure Modes by Category

### Schema Failures
| Symptom | Likely Cause | Check |
|---------|-------------|-------|
| `no such table` | `init_*_tables()` not called at startup | `scripts/server.py` startup events |
| `no such column` | Table created before column was added, no migration | `agent/core/migrations.py` |
| `database is locked` | Missing `closing()` or long-held connection | Search for bare `get_connection()` without `with closing(...)` |
| `UNIQUE constraint failed` | Insert without check-if-exists | Schema needs `INSERT OR IGNORE` or `ON CONFLICT` |

### Adapter Failures
| Symptom | Likely Cause | Check |
|---------|-------------|-------|
| `introspect()` returns empty | Threshold too high or level too low | Orchestrator score → level mapping |
| `health()` returns degraded | Table empty or connection failing | Run `init_*_tables()`, check `get_connection()` |
| Thread missing from STATE | Not registered in `agent/threads/__init__.py` | Check `_THREADS` dict |
| Token budget exceeded | `_token_budgets` too generous for L3 | Check adapter's budget dict |

### API Failures
| Symptom | Likely Cause | Check |
|---------|-------------|-------|
| 404 on endpoint | Router not included in `server.py` | Check `app.include_router()` |
| 404 on specific path | Prefix mismatch between router and fetch | Compare `APIRouter(prefix=...)` with frontend service URL |
| 422 Unprocessable Entity | Pydantic model mismatch | Compare request body with endpoint's type hints |
| 500 Internal Server Error | Unhandled exception in route handler | Check server logs: `docker logs ai-os` |

### Frontend Failures
| Symptom | Likely Cause | Check |
|---------|-------------|-------|
| Blank page on route | Component not imported in App.tsx | Check `<Route>` declarations |
| Fetch returns HTML | Wrong URL (hitting frontend, not API) | URL must start with `/api/` |
| Type mismatch | Backend schema changed, frontend types stale | Compare `types.ts` with Pydantic model |
| CORS error | Shouldn't happen (same origin) | Check if frontend is on different port |

### Orchestrator Failures
| Symptom | Likely Cause | Check |
|---------|-------------|-------|
| STATE block empty | `wake()` not called or all threads failed | `agent/subconscious/__init__.py` |
| One thread dominates STATE | Scoring imbalanced | linking_core's `score_threads()` weights |
| STATE too long | L3 budgets too generous across all threads | `_token_budgets` in each adapter |

---

## Runtime Verification Protocol

After any change, verify in this order:

```bash
# 1. Tables exist
curl -s http://localhost:8000/api/log/tables | python3 -m json.tool

# 2. Endpoint responds
curl -s http://localhost:8000/api/{module} | head -c 200

# 3. Health check (threads only)
curl -s http://localhost:8000/api/{thread}/health | python3 -m json.tool

# 4. Frontend loads
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/{route}

# 5. Docker logs clean
docker logs ai-os --tail 20 2>&1 | grep -i "error\|traceback\|failed"
```

---

## Uncomfortable Questions

Ask these. Every time.

### Before writing code:
- "What happens if this table is empty?"
- "What happens if Ollama is unreachable?"
- "What happens if this is called twice concurrently?"
- "What happens if the user has no profile yet?"
- "Does any existing test break?"

### Before changing a schema:
- "Is there data in this table in production?"
- "Does `init_*_tables()` use `CREATE TABLE IF NOT EXISTS`?"
- "Do I need a migration in `agent/core/migrations.py`?"
- "Who else queries this table?" → `grep -r "table_name" --include="*.py"`

### Before touching the orchestrator:
- "Does this change affect every conversation, or just some?"
- "What's the worst case if the score is wrong?"
- "Can I test this with a single thread in isolation?"

### Before frontend changes:
- "Does the API endpoint I'm calling actually exist?"
- "Does my TypeScript type match the JSON the backend returns?"
- "What does this look like with zero data?"

---

## Post-Build Audit Checklist

After code is written, before it ships:

- [ ] **Every new table** has `init_*_tables()` called in startup
- [ ] **Every new router** is imported and included in `server.py`
- [ ] **Every `get_connection()`** is wrapped in `with closing(...)` or manually closed
- [ ] **Every adapter** registered in `agent/threads/__init__.py`
- [ ] **Every frontend route** declared in `App.tsx`
- [ ] **Every fetch URL** starts with `/api/` and matches a router prefix
- [ ] **No thread imports another thread**
- [ ] **No adapter calls Ollama directly**
- [ ] **No schema.py imports from api.py or adapter.py**
- [ ] **Docker builds clean**: `docker compose up --build -d` exits 0
- [ ] **No TypeScript errors**: `npm run build` in `frontend/` exits 0

---

## Test Discipline

Tests prove the code works. They are not decorative.

### Hard Rules
- **Never write a test that manufactures its own passing data.** If the test creates a row and then asserts that row exists, it tested `INSERT`, not the feature.
- **Never mock the thing you're testing.** Mock its dependencies, not itself.
- **Every regression test must fail without the fix applied.** If it passes on the broken code, it's not a regression test.
- **Use `set_demo_mode(True)` for all DB tests.** Never touch the personal database.
- **Tests must not depend on execution order.** Each test sets up and tears down its own state.

### Test Patterns (from the codebase)

```bash
# Run all tests
./tests/runtests.sh

# Run specific file
pytest tests/test_api.py -v

# Run specific test
pytest -k "test_name" -v
```

```python
# Database tests — always use demo DB
@pytest.fixture(autouse=True)
def use_demo_db():
    set_demo_mode(True)
    yield
    set_demo_mode(False)

# API tests — use TestClient
@pytest.fixture
def client():
    return TestClient(app)

def test_get_returns_200(client):
    response = client.get("/api/module")
    assert response.status_code == 200
```

### What to Test
| Change Type | Test This | Not This |
|-------------|-----------|----------|
| New endpoint | Request → response status + shape | That FastAPI routing works |
| Schema change | Round-trip insert → select → verify fields | That SQLite can create tables |
| Adapter change | `introspect()` returns expected facts for known data | That `get_connection()` works |
| Bug fix | Exact scenario that caused the bug | Happy path that already worked |
