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
### Ready for contributors
- [ ] **Loop Editor Dashboard** — Visual editor for background loops:
  - View running loops with status indicators
  - Edit loop parameters (interval, enabled/disabled)
  - Live logs per loop
- [ ] **Implicit COT Loops** — Chain-of-thought background reasoning:
  - Set max iterations per loop
  - Configure max tokens per iteration
  - Cutoff conditions (confidence threshold, diminishing returns)
- [ ] **Context compression** — Smarter token budgeting per thread
- [ ] **Priority queue** — Urgent facts surface first
- [ ] **Dream mode** — Background processing during idle
- [ ] **Attention visualization** — Show what's in context

### Starter tasks
- [ ] Add loop status indicators in UI
- [ ] Configurable loop intervals
- [ ] Loop execution history view
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