# Subconscious

The central nervous system — builds the agent's awareness before each response.

---

## Description

The subconscious is the agent's background thinking layer. Before each response, it:

1. **Scores** every thread and module against the user's query (via LinkingCore)
2. **Ranks** sources into L1/L2/L3 detail levels based on relevance
3. **Assembles** `== STATE ==` from all sources within per-source token budgets
4. **Runs** 10+ background loops (memory, goals, self-improvement, training gen, etc.)

The agent is stateless. Before each response, the orchestrator calls `build_state()` to assemble context from 6 threads + 2 modules, ordered by relevance score.

---

## Architecture

<!-- ARCHITECTURE:subconscious -->
### Directory Structure

```
subconscious/
├── __init__.py         # Public API: wake(), sleep(), get_consciousness_context()
├── core.py             # ThreadRegistry, SubconsciousCore singleton
├── orchestrator.py     # Subconscious class — score(), build_state(), STATE assembly
├── api.py              # FastAPI router — 51 endpoints (/loops, /goals, /tasks, etc.)
├── cli.py              # CLI interface
├── contract.py         # Metadata protocol for sync decisions
├── triggers.py         # Event-driven triggers (time/event/threshold)
├── loops/
│   ├── base.py             # BackgroundLoop ABC, LoopConfig
│   ├── manager.py          # LoopManager — unified lifecycle
│   ├── memory.py           # MemoryLoop — periodic memory maintenance
│   ├── consolidation.py    # ConsolidationLoop — promote SHORT→LONG links
│   ├── sync.py             # SyncLoop — cross-thread state sync
│   ├── health.py           # HealthLoop — periodic health checks
│   ├── thought.py          # ThoughtLoop — LLM-driven introspection
│   ├── custom.py           # CustomLoop — user-defined from config
│   ├── task_planner.py     # TaskPlanner — plan and queue agent tasks
│   ├── goals.py            # GoalLoop — propose high-level goals
│   ├── self_improve.py     # SelfImprovementLoop — reads thoughts, proposes code edits
│   ├── training_gen.py     # TrainingGenLoop — kimi-k2 teacher, 17 modules, 105+ files
│   └── convo_concepts.py   # ConvoConceptLoop — backfill concept graph from convos
└── temp_memory/        # Short-term fact storage pending consolidation
```

### Orchestrator (orchestrator.py)

The brain of STATE assembly:

| Step | Action |
|------|--------|
| 1 | `score(query)` — LinkingCore scores each thread/module 0–10 |
| 2 | Score maps to L1 (0–3.5), L2 (3.5–7.0), L3 (7.0–10) |
| 3 | Each adapter's `introspect()` runs at chosen level |
| 4 | Facts concatenate into `== STATE ==` within per-source token budgets |
| 5 | STATE injects into system prompt |

Sources: `identity`, `log`, `form`, `philosophy`, `reflex`, `linking_core` (threads) + `chat`, `workspace` (modules).

### Context Levels

| Level | Score | Tokens | When |
|-------|-------|--------|------|
| L1 | 0–3.5 | ~150 | Low relevance |
| L2 | 3.5–7.0 | ~400 | Default conversational |
| L3 | 7.0–10 | ~800 | High relevance / deep queries |

### Background Loops (14 total)

| Loop | Interval | Purpose |
|------|----------|---------|
| MemoryLoop | varies | Periodic memory maintenance |
| ConsolidationLoop | 300s | Promote SHORT→LONG links, compact temp facts |
| SyncLoop | 600s | Cross-thread state synchronization |
| HealthLoop | 60s | Health checks on all threads |
| ThoughtLoop | varies | LLM-driven introspection cycles |
| CustomLoop(s) | user-defined | User-created loops with multi-step COT |
| TaskPlanner | varies | Plans and queues agent tasks |
| GoalLoop | varies | Proposes high-level goals for human review |
| SelfImprovementLoop | varies | Reads thoughts → proposes code edits (never auto-applied) |
| TrainingGenLoop | 7200s | kimi-k2 generates training data across 17 modules |
| ConvoConceptLoop | varies | Backfills concept graph from imported conversations |

### API Endpoints (51 routes at `/api/subconscious/`)

Key groups:
- **State**: `build_state`, `state`, `context`, `preview`, `health`
- **Loops**: CRUD, pause/resume, interval adjust, prompt editing, custom loops
- **Facts**: temp facts CRUD, approve/reject (bulk + individual), consolidate
- **Thoughts**: list, think-now, act on thought
- **Tasks**: CRUD, execute, cancel
- **Goals**: list, resolve
- **Notifications**: list, read, dismiss, respond
- **Improvements**: list, resolve, apply
- **Backfill**: status, trigger run

### Thread Interface

```python
class ThreadInterface(Protocol):
    name: str
    def health(self) -> HealthReport: ...
    def introspect(self, context_level: int) -> IntrospectionResult: ...
```
<!-- /ARCHITECTURE:subconscious -->

---

## Roadmap

<!-- ROADMAP:subconscious -->
### Done
- [x] **Loop Editor Dashboard** — Visual editor with status indicators, interval editing, live logs
- [x] **Context compression** — Token budgeting per thread via `_budget_fill()`
- [x] **Loop status indicators + configurable intervals**
- [x] **CustomLoop multi-step COT** — Iterative LLM calls with previous output as context (up to 20 iterations)

### Loop intelligence
- [ ] **COT convergence detection** — CustomLoop runs N iterations blindly. Add quality signal between iterations: embedding similarity to target, structured output validation, or LLM-as-judge step. Stop when confident, not when counter expires
- [ ] **Loop-to-loop communication** — ThoughtLoop insights should trigger MemoryLoop. Currently all loops run independently with no cross-loop data flow
- [ ] **Thought actionability** — ThoughtLoop writes to `thought_log` but nothing reads it. High-priority thoughts should surface in STATE or trigger reflexes
- [ ] **Context pressure testing** — What happens when all 6 threads are active, workspace has 100 files, and conversation is 40 messages deep? Budget overflow is the real failure mode

### Research
- [ ] **Self-evaluation within iterations** — Can a loop determine if iteration 3 was better than iteration 2? Requires an internal quality signal that doesn't exist yet
- [ ] **Idle-time background reasoning** — Agent processes accumulated context during quiet periods ("dream mode"). Requires: idle detection, priority queue for what to process, and quality measurement of outputs

### Starter tasks
- [ ] Loop execution history view
- [ ] Attention visualization — show what's currently in STATE and why
<!-- /ROADMAP:subconscious -->

---

## Changelog

<!-- CHANGELOG:subconscious -->
### 2026-01-31
- SubconsciousDashboard frontend component
- `/subconscious` standalone route
- API: `/loops`, `/temp-facts`, `/potentiation`, `/consolidate` endpoints
- Light theme CSS with proper variables

### 2026-01-27
- Three background loops: Consolidation, Sync, Health
- HEA context levels (L1/L2/L3)

### 2026-01-20
- ThreadRegistry with adapter protocol
- `get_consciousness_context()` assembles state
<!-- /CHANGELOG:subconscious -->