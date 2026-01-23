# Subconscious

The central nervous system — builds the agent's awareness before each response.

---

## For Users

The subconscious is like the agent's "background thinking." Before she responds to you, it:

1. **Gathers** what she knows about you (identity)
2. **Recalls** recent facts from memory
3. **Checks** what's been happening (events)
4. **Assembles** all this into her current awareness

You don't interact with this directly — it works automatically to make the agent's responses more personalized.

---

## For Developers

### Core Insight

> "Subconscious builds state, agent just reads it."

The agent is stateless. Before each response, `agent_service` calls `get_consciousness_context()` to assemble context from all registered threads.

### Quick Start

```python
from agent.subconscious import wake, get_consciousness_context

# At startup
wake()

# Before each agent.generate() call
context = get_consciousness_context(level=2)
response = agent.generate(user_input, convo, consciousness_context=context)
```

### Context Levels (HEA)

| Level | Tokens | Use Case |
|-------|--------|----------|
| L1 | ~10 | Quick, casual responses |
| L2 | ~50 | Default conversational |
| L3 | ~200 | Deep analytical, full history |

### Architecture

```
subconscious/
├── __init__.py         # Public API: wake(), sleep(), get_consciousness_context()
├── core.py             # ThreadRegistry, SubconsciousCore singleton
├── contract.py         # Metadata protocol for sync decisions
├── loops.py            # Background: ConsolidationLoop, SyncLoop, HealthLoop
└── triggers.py         # Event-driven: TimeTrigger, EventTrigger, ThresholdTrigger
```

### API Reference

#### `wake(start_loops: bool = True)`
Initialize the subconscious. Registers all thread adapters. Optionally starts background loops.

#### `sleep()`
Gracefully shut down. Stops all background loops.

#### `get_consciousness_context(level: int = 2) -> str`
Assemble context from all threads at the specified HEA level. Returns a formatted string for the agent's system prompt.

#### `get_status() -> dict`
Get health status of all registered threads and background loops.

## Thread Interface

All adapters implement the `ThreadInterface` protocol:

```python
class ThreadInterface(Protocol):
    name: str
    description: str
    
    def health(self) -> HealthReport: ...
    def introspect(self, context_level: int) -> IntrospectionResult: ...
```

## Data Flow

```
User Message
    ↓
agent_service.py
    ↓
get_consciousness_context(level=2)
    ↓
┌─────────────────────────────────────┐
│         SubconsciousCore            │
│  ┌─────────┐ ┌─────────┐ ┌───────┐  │
│  │identity │ │ memory  │ │  log  │  │
│  │ adapter │ │ adapter │ │adapter│  │
│  └────┬────┘ └────┬────┘ └───┬───┘  │
│       ↓           ↓          ↓      │
│   introspect() for each thread      │
└─────────────────────────────────────┘
    ↓
Assembled Context String
    ↓
agent.generate(consciousness_context=...)
    ↓
Response (uses learned facts, identity, etc.)
```

## Background Loops

| Loop | Interval | Purpose |
|------|----------|---------|
| ConsolidationLoop | 300s | Score and promote temp facts to permanent storage |
| SyncLoop | 600s | Sync identity sections across threads |
| HealthLoop | 60s | Check thread health, log issues |

## Adding a New Thread

1. Create adapter in `threads/` implementing `ThreadInterface`
2. Register in `core.py` `_register_default_threads()`
3. Return appropriate data in `introspect()` based on context level

```python
# threads/my_adapter.py
from .base import ThreadInterface, HealthReport, IntrospectionResult

class MyThreadAdapter(ThreadInterface):
    name = "my_thread"
    description = "Does something useful"
    
    def health(self) -> HealthReport:
        return HealthReport(status="ok", message="All good")
    
    def introspect(self, context_level: int) -> IntrospectionResult:
        data = self._get_data(context_level)
        return IntrospectionResult(
            thread_name=self.name,
            context_level=context_level,
            data=data,
            summary=f"Found {len(data)} items"
        )
```

## Integration Points

- **agent.py**: Accepts `consciousness_context` param, builds `== CURRENT AWARENESS ==` section
- **agent_service.py**: Calls `wake()` on import, `get_consciousness_context()` before generate
- **contract.py**: Metadata protocol shared with other modules for sync decisions
