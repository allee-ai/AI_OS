# 📐 Plan — Architecture-Aware Planning
**Role**: Plan changes before writing code. Classify, locate, scope, estimate.  
**Scope**: Any modification to AI_OS — features, fixes, refactors, new modules  
**Rule**: Read before you write. Every plan starts with what already exists.

---

## Read First

Before planning anything, read the files that define the boundaries:

| What you're changing | Read these first |
|---------------------|-----------------|
| Any thread | `agent/threads/base.py`, the thread's `adapter.py`, `schema.py`, `api.py` |
| Orchestrator / STATE | `agent/subconscious/orchestrator.py`, `agent/agent.py` |
| Any top-level module | `{module}/api.py`, `{module}/schema.py`, `scripts/server.py` |
| Frontend module | `frontend/src/App.tsx`, the module's `pages/`, `services/` |
| Database | `data/db/__init__.py`, the relevant `schema.py` |
| Training data | `finetune/auto_generated/`, the thread's `train.py` |
| Architecture context | `docs/ARCHITECTURE.md` |

---

## Planning Sequence

### 1. Classify

What kind of change is this?

| Type | Touches | Example |
|------|---------|---------|
| **Thread feature** | adapter + schema + api + frontend | Add "mood" to identity |
| **Top-level module** | schema + api + server + frontend | New "goals" module |
| **Orchestrator change** | orchestrator.py + possibly base.py | Change scoring thresholds |
| **Frontend-only** | pages/ + components/ + services/ | New visualization |
| **Schema migration** | schema.py + possibly adapter | Add column to existing table |
| **Training data** | train.py + auto_generated/ | New reasoning examples |
| **Bug fix** | Usually 1–2 files | Fix broken query |

### 2. Locate

List every file that will be touched. Use this mental model:

```
Change flows DOWN:
  schema.py  →  adapter.py  →  api.py  →  frontend service  →  frontend page
  (tables)      (logic)        (HTTP)     (fetch)              (render)
```

If a change touches schema.py, everything downstream may need updating.  
If a change touches only a frontend page, nothing upstream changes.

### 3. Boundary Check

Before proceeding, verify:

- [ ] Does this module already exist? (Don't reinvent)
- [ ] Does an adjacent module already handle this? (Don't duplicate)
- [ ] Does this cross a thread boundary? (Threads never import each other)
- [ ] Does this require a new table? (Must have `init_*_tables()`)
- [ ] Does this change the adapter interface? (Must update `base.py` if so)
- [ ] Does this affect STATE assembly? (Orchestrator is the only conductor)

### 4. Define the Shape

For each file that changes, describe:

```
FILE: {path}
CHANGE: {what changes}
CONTRACT: {inputs → outputs}
DEPENDS ON: {what must exist first}
```

### 5. Estimate Blast Radius

| Blast Radius | Meaning | Example |
|-------------|---------|---------|
| **Local** | 1 file, no downstream effects | Fix a typo in a query |
| **Module** | 2–5 files within one module | Add a column + expose via API |
| **Cross-module** | Touches orchestrator or base | Change introspect() signature |
| **System** | Touches server.py startup or DB init | New connection pool strategy |

If blast radius is **Cross-module** or **System**, write explicitly what regression risks exist.

### 6. Order of Operations

Write files in dependency order — upstream first:

1. **schema.py** — tables exist before anything queries them
2. **adapter.py** — logic exists before API exposes it
3. **api.py** — endpoints exist before frontend calls them
4. **__init__.py** — exports exist before server imports them
5. **server.py** — registration happens before frontend fetches
6. **frontend service** — fetch wrappers exist before pages use them
7. **frontend page** — UI renders last

Never skip ahead. If step 3 depends on step 1, finish step 1 first.

---

## Planning Anti-Patterns

- ❌ **Planning in your head** — Write it down. If the plan isn't written, it doesn't exist.
- ❌ **Starting with frontend** — Frontend is always last. It consumes; it doesn't define.
- ❌ **Combining schema + adapter + API in one step** — Three files = three steps.
- ❌ **Assuming a table exists** — Check `schema.py`. Run `init_*_tables()`.
- ❌ **Planning across threads** — Each thread is a separate plan. No shared state.
- ❌ **Skipping the read phase** — The codebase already solves half the problems. Find those solutions first.
- ❌ **No verification step** — Every plan ends with "how do I know this worked?"

---

## Frontend Addendum

When the plan includes frontend work:

```
frontend/src/modules/{module}/
├── pages/{Module}Page.tsx     # Route entry point
├── components/                # Reusable UI pieces
├── hooks/                     # Data fetching hooks
├── services/                  # fetch() → /api/{module}
└── types.ts                   # TypeScript interfaces matching Pydantic models
```

- Types mirror Pydantic models from the backend
- Services use raw `fetch()` — no axios
- Pages are registered in `App.tsx` with `<Route path="/{module}" element={<ModulePage />} />`
- Dev-links go in `Dashboard.tsx` during development

---

## Plan Template

Use this when presenting a plan:

```
## Plan: {title}

**Type**: {thread feature | top-level module | orchestrator | frontend | schema | training | fix}
**Blast Radius**: {local | module | cross-module | system}

### Files
1. `{path}` — {what changes}
2. `{path}` — {what changes}
...

### Dependencies
- {what must exist before this plan starts}

### Verification
- {how to confirm each step worked}
- {curl command, frontend test, query check}

### Risks
- {what could break, and how you'd know}
```
