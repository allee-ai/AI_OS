# Agent Architecture

Technical deep-dive into the Agent's internal systems.

---

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    FEED CHANNELS                     │
│         (React Chat, CLI, Matrix, Email, etc.)          │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    agent_service.py                     │
│  • Classifies feeds type (realtime/conversational/    │
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
    feed_type="conversational",
    consciousness_context="assembled context..."
)
```

**Key Methods:**
- `get_agent()` — Returns singleton instance
- `generate(user_input, convo, feed_type, consciousness_context)` — Main response method
- `introspect()` — Returns agent status and identity

### agent/core/ — System Primitives

Low-level utilities and types.

```python
agent/core/
├── config.py       # Pydantic settings loading (.env)
├── locks.py        # Async concurrency primitives
└── models_api.py   # Shared data models (ContextLevel, etc.)
```

### agent/subconscious/ — The Orchestrator

The "Operating System" kernel that manages threads and assembles context.

```python
agent/subconscious/
├── core.py         # Subconscious singleton
├── orchestrator.py # Thread lifecycle management
├── loops.py        # Background maintenance loops
├── triggers.py     # Event-driven hooks
└── contract.py     # API definitions for adapters
```

### agent/threads/ — The Cognitive Modules

Each thread is now a self-contained module with a standard interface:
- `adapter.py`: Implements `ThreadInterface` (introspect/health)
- `api.py`: FastAPI router for thread-specific endpoints
- `schema.py`: Database models (SQLAlchemy/Pydantic)
- `train.py`: Thread-specific learning logic

#### 1. Identity Thread (`agent/threads/identity/`)

**Purpose**: Relational Identity System. No longer a static JSON file. It is a fully relational system stored in SQLite (`data/db/state.db`), allowing for multiple profiles (Self, User, Admin, Guests) with granular fact storage.

**Schema (`schema.py`):**
- **`profile_types`**: Defines roles and permissions (e.g., `self`, `admin`, `guest`).
- **`profiles`**: Instances of identities.
- **`profile_facts`**: Atomic units of identity with L1/L2/L3 values.

**API (`api.py`):** Push/Pull facts via `/api/identity/facts`.

#### 2. Log Thread (`agent/threads/log/`)

**Purpose**: Maintains a strict, immutable history of *occurrences*. Answers "When did this happen?"

**Schema (`schema.py`):**
- **`unified_events`**: Central timeline for all system events.

**Context Strategy (Recency):**
- **L1 (Reflex):** Last 10 events.
- **L2 (Routine):** Last 100 events.
- **L3 (Deep):** Last 1000 events.

#### 3. Form Thread (`agent/threads/form/`)

**Purpose**: Embodiment & Capabilities. Answers "WHAT can I do?". Manages tools and actions.

**Architecture**: L1/L2/L3 pattern
- **L1 (Registry)**: Tool definitions, metadata (`tools/registry.py`)
- **L2 (Executor)**: Execution engine, error handling (`tools/executor.py`)
- **L3 (Executables)**: Actual Python implementations (`tools/executables/*.py`)

**API (`api.py`):**
- `GET /api/form/tools` — List all tools
- `POST /api/form/tools/{name}/execute` — Execute a tool action
- `GET /api/form/tools/{name}/code` — Get executable source

**Executable Interface**: Each tool implements `run(action: str, params: dict) -> Any`

#### 4. Philosophy Thread (`agent/threads/philosophy/`)

**Purpose**: Values & Alignment. Answers "WHY should I do this?".

**Schema (`schema.py`):**
- **`philosophy_flat`**: Values with L1/L2/L3 descriptions.
- **`philosophy_ethical_bounds`**: Hard constraints.

#### 5. Reflex Thread (`agent/threads/reflex/`)

**Purpose**: Pattern Automata (Basal Ganglia). Answers "HOW do I respond (automatically)?".

**Schema (`schema.py`):**
- **`reflex_greetings`**: Fast-path responses.
- **`reflex_shortcuts`**: User aliases.

#### 6. Linking Core Thread (`agent/threads/linking_core/`)

**Purpose**: Relevance Engine (Thalamus). Answers "WHICH concepts matter NOW?".

**Key Features**: Spread Activation, Hebbian Learning. Not a content store — an *index* and *relevance calculator*.

### agent/services/ — Integration Layer

Bridges external inputs (chat, kernel) with internal systems.

```python
agent/services/
├── agent_service.py    # Main LLM interface & HEA routing
├── kernel_service.py   # Experimental browser automation (Lazy loaded)
└── api.py              # Router aggregation
```

### External Modules

Non-cognitive modules that support the OS.

#### 1. Feeds (`Feeds/`) — Input & Awareness

**Purpose**: Pipeline for external inputs (Chat, Email, Slack, etc.). Config-driven integration layer.

**Design**:
- **Router (`router.py`)**: Universal adapter that normalizes inputs.
- **Sources (`sources/*.yaml`)**: Zero-code integration configs.
- **Conversations (`conversations/`)**: Raw log storage.

**Data Flow**:
Input Source → Normalizer → `NormalizedMessage` → Agent Service → Response

#### 2. Chat (`chat/`) — Interface API

**Purpose**: Real-time chat + conversation lifecycle management.

**Design (`api.py` & `schema.py`):**
- **Session Management**: Create, rename, archive, delete sessions.
- **Message Handling**: HTTP/WebSocket endpoints for frontend.
- **Persistence**: Saves conversation state (`data/db/state.db`).
- **Ratings**: Thumbs up/down feedback collection.

#### 3. Eval (`eval/`) — The Battle Arena

**Purpose**: Testing ground for models. Compare Managed AI (stateful) vs Raw Models (stateless).

**Features**:
- **Battle Configurations**: Identity, Coherence, Wisdom, Custom.
- **Judges**: LLM-based scoring of battle outcomes.
- **Leaderboard**: Track performance over time.

#### 4. Finetune (`finetune/`) — Training Studio

**Purpose**: Tools for teaching models "State Obedience" — respecting the OS context over prompt injection.

**Contents**:
- **Data**: JSONL files (`state_obedience.jsonl`, `identity_defense.jsonl`).
- **Scripts**: Training runners for MLX (Mac) and Axolotl (Cloud).

#### 5. Documentation (`docs/`)

**Purpose**: Documentation engine and specs.

- `specs/`: Technical specifications.
- `guides/`: User guides.
- `vision/`: Long-term roadmap documents.

---

## Data Flow

### Message → Response

```
1. User types "What's my project status?"
   
2. agent_service.classify_feed()
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
def classify_feed(message: str) -> str:
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

## File Locations (Runtime)

| File | Purpose |
|------|---------|
| `data/db/state.db` | Primary SQLite database (Identity, Threads, Logs, Links) |
| `data/vscode_import_log.json` | VS Code import history |
| `Feeds/conversations/*.json` | Raw conversation logs |
| `~/.aios/tokens/` | OAuth tokens for external integrations |

---

## Adding a New Thread

1. Create a dictionary in `agent/threads/new_thread/`:
   - `__init__.py`
   - `adapter.py`
   - `schema.py`
   - `api.py`

2. Implement the Adapter:

```python
# agent/threads/new_thread/adapter.py
from agent.threads.base import ThreadInterface, HealthReport, IntrospectionResult

class NewThreadAdapter(ThreadInterface):
    name = "new_thread"
    description = "Provides specialized context"
    
    def health(self) -> HealthReport:
        # Check database/service health
        return HealthReport(status="ok", message="Ready")
    
    def introspect(self, context_level: int) -> IntrospectionResult:
        # Retrieve context based on L1/L2/L3 budget
        data = self._get_data(limit=context_level * 5)
        return IntrospectionResult(
            thread_name=self.name,
            context_level=context_level,
            data=data,
            summary=f"Found {len(data)} items"
        )
```

3. Register in `agent/subconscious/core.py`.

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
