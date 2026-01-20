# Nola Architecture

Technical deep-dive into Nola's internal systems.

---

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    STIMULI CHANNELS                     │
│         (React Chat, CLI, Matrix, Email, etc.)          │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    agent_service.py                     │
│  • Classifies stimuli type (realtime/conversational/    │
│    analytical)                                          │
│  • Maps to context level (L1/L2/L3)                     │
│  • Calls subconscious for context assembly              │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                     SUBCONSCIOUS                        │
│  wake() → registers thread adapters                     │
│  get_consciousness_context(level) → assembles context   │
├─────────────────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌───────────┐           │
│  │ Identity  │  │  Memory   │  │    Log    │           │
│  │  Adapter  │  │  Adapter  │  │  Adapter  │           │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘           │
│        │              │              │                  │
│        ▼              ▼              ▼                  │
│  introspect()   introspect()   introspect()            │
│  at level N     at level N     at level N              │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                      agent.py                           │
│  • Receives assembled consciousness_context             │
│  • Builds system prompt with == CURRENT AWARENESS ==    │
│  • Calls Ollama for response                            │
└─────────────────────────────────────────────────────────┘
```

---

## Module Reference

### agent.py — The Voice

Thread-safe singleton that interfaces with the LLM.

```python
from agent import get_agent

agent = get_agent()  # Auto-bootstraps on first call
response = agent.generate(
    user_input="Hello",
    convo="previous conversation...",
    stimuli_type="conversational",
    consciousness_context="assembled context..."
)
```

**Key Methods:**
- `get_agent()` — Returns singleton instance
- `generate(user_input, convo, stimuli_type, consciousness_context)` — Main response method
- `introspect()` — Returns agent status and identity

### subconscious/ — The Mind

Assembles context from all registered threads before each response.

```python
from Nola.subconscious import wake, get_consciousness_context

wake()  # Initialize, register adapters
context = get_consciousness_context(level=2)  # Assemble L2 context
```

**Key Functions:**
- `wake(start_loops=True)` — Initialize subconscious
- `sleep()` — Graceful shutdown
- `get_consciousness_context(level)` — Main context assembly
- `get_status()` — Health check all threads

See [subconscious/README.md](subconscious/README.md) for details.

### threads/identity/ — Identity Database

SQLite-backed identity with level-aware storage.

**Location:** `Nola/threads/identity`

**Tables:**
- `identity_sections` — machineID, userID with L1/L2/L3 variants
- `identity_meta` — Sync metadata

### temp_memory/ — Session Facts

Temporary fact storage before consolidation.

```python
from temp_memory.store import add_fact, get_all_pending

add_fact("User prefers dark mode", source="conversation")
pending = get_all_pending()  # Facts awaiting consolidation
```

### log_thread/ — Event Timeline

Lightweight event logging.

```python
from log_thread import log_event, read_events

log_event("conversation:start", {"session_id": "abc123"})
events = read_events(event_type="conversation:*", limit=50)
```

### services/agent_service.py — The Router

FastAPI integration and HEA (context level) routing.

```python
# Main entry point for all channels
response = await agent_service.send_message(
    content="User message",
    session_id="session_123"
)
```

**HEA Classification:**
```python
"realtime"      → L1 (~10 tokens)   # Greetings, quick exchanges
"conversational" → L2 (~50 tokens)  # Default
"analytical"    → L3 (~200 tokens)  # Complex questions
```

---

## Data Flow

### Message → Response

```
1. User types "What's my project status?"
   
2. agent_service.classify_stimuli()
   → Returns "conversational" (L2)
   
3. get_consciousness_context(level=2)
   → Identity adapter: pulls user's projects
   → Memory adapter: recent facts about projects
   → Log adapter: recent project-related events
   → Returns assembled context string
   
4. agent.generate(consciousness_context=context)
   → System prompt includes:
      == CURRENT AWARENESS ==
      - User is working on TaskMaster project
      - User prefers Python
      ...
   → LLM generates personalized response
   
5. Response returned to user
```

### Fact → Memory

```
1. User says "I just started learning Rust"
   
2. Memory service extracts fact
   → add_fact("User is learning Rust", source="conversation")
   
3. consolidation_daemon runs (every 5 min)
   → Scores fact: permanence=3, relevance=4, identity=3
   → Total: 3.3 → Promotes to L3
   
4. Next conversation
   → L3 context includes "User is learning Rust"
```

---

## Context Levels (HEA)

| Level | Budget | Contents | Trigger |
|-------|--------|----------|---------|
| L1 | ~10 tokens | Name, role | Quick exchanges |
| L2 | ~50 tokens | + Projects, preferences | Default |
| L3 | ~200 tokens | + Full history, all facts | Deep analysis |

### Escalation Rules

```python
# In agent_service.py
def classify_stimuli(message: str) -> str:
    # Greeting patterns → L1
    if re.match(r"^(hi|hello|hey|sup)\b", message, re.I):
        return "realtime"
    
    # Deep questions → L3
    if any(w in message.lower() for w in ["analyze", "explain", "why"]):
        return "analytical"
    
    # Default → L2
    return "conversational"
```

---

## File Locations

| File | Purpose |
|------|---------|
| `Nola.json` | Runtime identity state |
| `identity_thread/identity.json` | Aggregated identity |
| `identity_thread/machineID/machineID.json` | Machine context |
| `identity_thread/userID/user.json` | User context |
| `Stimuli/conversations/*.json` | Chat history |
| `data/db/state.db` | SQLite database |

---

## Adding a New Thread

1. Create adapter in `subconscious/threads/`:

```python
# my_adapter.py
from .base import ThreadInterface, HealthReport, IntrospectionResult

class MyAdapter(ThreadInterface):
    name = "my_thread"
    description = "Provides X context"
    
    def health(self) -> HealthReport:
        return HealthReport(status="ok", message="Ready")
    
    def introspect(self, context_level: int) -> IntrospectionResult:
        if context_level == 1:
            data = self._get_minimal()
        elif context_level == 2:
            data = self._get_moderate()
        else:
            data = self._get_full()
        return IntrospectionResult(
            thread_name=self.name,
            context_level=context_level,
            data=data,
            summary=f"{len(data)} items"
        )
```

2. Register in `subconscious/core.py`:

```python
def _register_default_threads(self):
    # ... existing ...
    from .threads.my_adapter import MyAdapter
    self.register(MyAdapter())
```

---

## Testing

```bash
# All tests
pytest tests/ -v

# Specific
pytest tests/test_agent.py -v      # Agent singleton
pytest tests/test_hea.py -v        # Context levels
```

---

## Related Docs

- [Subconscious README](subconscious/README.md)
- [HEA Theory](../docs/concept_attention_theory.md)
- [Main Developer Guide](../DEVELOPERS.md)
