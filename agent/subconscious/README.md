# Subconscious

The central nervous system — builds the agent's awareness before each response.

---

## Description

The subconscious is like the agent's "background thinking." Before she responds to you, it:

1. **Gathers** what she knows about you (identity)
2. **Recalls** recent facts from memory
3. **Checks** what's been happening (events)
4. **Assembles** all this into her current awareness

The agent is stateless. Before each response, `agent_service` calls `get_consciousness_context()` to assemble context from all registered threads.

---

## Architecture

<!-- ARCHITECTURE:subconscious -->
### Directory Structure

```
subconscious/
├── __init__.py         # Public API: wake(), sleep(), get_consciousness_context()
├── core.py             # ThreadRegistry, SubconsciousCore singleton
├── contract.py         # Metadata protocol for sync decisions
├── loops.py            # Background: ConsolidationLoop, SyncLoop, HealthLoop
├── triggers.py         # Event-driven triggers
└── temp_memory/        # Short-term fact storage
```

### Context Levels (HEA)

| Level | Tokens | Use Case |
|-------|--------|----------|
| L1 | ~10 | Quick, casual responses |
| L2 | ~50 | Default conversational |
| L3 | ~200 | Deep analytical |

### API

| Function | Purpose |
|----------|---------|
| `wake(start_loops)` | Initialize subconscious, register adapters |
| `sleep()` | Gracefully shut down loops |
| `get_consciousness_context(level)` | Assemble context from all threads |
| `get_status()` | Health status of threads and loops |

### Background Loops

| Loop | Interval | Purpose |
|------|----------|---------|
| ConsolidationLoop | 300s | Score and promote temp facts |
| SyncLoop | 600s | Sync identity across threads |
| HealthLoop | 60s | Check thread health |

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