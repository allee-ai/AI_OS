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
├── loops.py        # Background maintenance loops (MemoryLoop, ConsolidationLoop)
├── triggers.py     # Event-driven hooks
├── contract.py     # API definitions for adapters
└── temp_memory/    # Short-term fact storage before consolidation
    ├── store.py    # add_fact(), get_facts(), status management
    └── README.md   # Module documentation
```

#### Memory Pipeline

```
Conversation → MemoryLoop (extracts facts) → temp_memory (stores)
                                                    ↓
                              ConsolidationLoop (scores, triages)
                                                    ↓
                                    Identity/Philosophy (permanent)
```

### agent/threads/ — The Cognitive Modules

Each thread is now a self-contained module with a standard interface:
- `adapter.py`: Implements `ThreadInterface` (introspect/health)
- `api.py`: FastAPI router for thread-specific endpoints
- `schema.py`: Database models (SQLAlchemy/Pydantic)
- `train.py`: Thread-specific learning logic

#### 1. Identity Thread (`agent/threads/identity/`)

**Purpose**: WHO am I? WHO are you? WHO do we know?

<!-- INCLUDE:identity:ARCHITECTURE -->
_Source: [agent/threads/identity/README.md](agent/threads/identity/README.md)_

### Database Schema

| Table | Purpose |
|-------|---------|
| `profile_types` | Categories with trust levels (user, machine, family, friend, etc.) |
| `profiles` | Individual identity profiles |
| `fact_types` | Types of facts (name, email, preference, relationship, etc.) |
| `profile_facts` | The actual facts with L1/L2/L3 values |

```sql
CREATE TABLE profile_facts (
    profile_id TEXT NOT NULL,
    key TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    l1_value TEXT,                   -- Brief (5-10 tokens)
    l2_value TEXT,                   -- Standard (20-50 tokens)
    l3_value TEXT,                   -- Detailed (100+ tokens)
    weight REAL DEFAULT 0.5,
    protected BOOLEAN DEFAULT FALSE,
    access_count INTEGER DEFAULT 0,
    PRIMARY KEY (profile_id, key)
)
```

### Adapter Methods

| Method | Purpose |
|--------|---------|
| `get_data(level, min_weight, limit)` | Get facts across all profiles |
| `set_fact(profile_id, key, l1, l2, l3, fact_type, weight)` | Create/update a fact |
| `introspect(context_level, query, threshold)` | Build STATE block contribution |
| `health()` | Health check with fact counts |

### Context Levels (HEA)

| Level | Content | Token Budget |
|-------|---------|--------------|
| **L1** | Core identifiers only (machine name, user name) | ~10 tokens |
| **L2** | L1 + top profiles with key facts | ~50 tokens |
| **L3** | L2 + detailed facts, relationships | ~200 tokens |

### Output Format

```
identity.machine.name: Nola - a personal AI
identity.primary_user.name: Jamie
identity.dad.relationship: Your father, retired engineer
```

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/identity/profiles` | List all profiles |
| GET | `/api/identity/profiles/{id}` | Get profile with facts |
| POST | `/api/identity/facts` | Create/update fact |
| DELETE | `/api/identity/profiles/{id}` | Delete (if not protected) |
<!-- /INCLUDE:identity:ARCHITECTURE -->

#### 2. Log Thread (`agent/threads/log/`)

**Purpose**: Maintains a strict, immutable history of *occurrences*. Answers "When did this happen?"

<!-- INCLUDE:log:ARCHITECTURE -->
_Source: [agent/threads/log/README.md](agent/threads/log/README.md)_

### Database Schema

| Table | Purpose |
|-------|---------|
| `unified_events` | Central event timeline |
| `log_events` | System events (errors, starts) |
| `log_sessions` | Conversation sessions |

```sql
CREATE TABLE unified_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,
    source TEXT DEFAULT 'system',
    data TEXT,
    metadata_json TEXT,
    session_id TEXT,
    related_key TEXT,
    related_table TEXT
)
```

### Adapter Methods

| Method | Purpose |
|--------|---------|
| `get_data(level, limit)` | Get events by recency level |
| `start_session()` | Start a new conversation session |
| `log_event(event_type, source, message, weight)` | Log a system event |
| `record_message()` | Increment message count |
| `get_session_duration()` | Current session duration |
| `introspect(context_level, query, threshold)` | Build STATE block contribution |
| `health()` | Health check with event counts |

### Context Levels (Recency-Based)

| Level | Events | Use Case |
|-------|--------|----------|
| **L1** | 10 most recent | Quick glance |
| **L2** | 100 most recent | Conversation-scale |
| **L3** | 1000 most recent | Full timeline |

### Event Types

| Type | Relevance | Purpose |
|------|-----------|---------|
| `convo` | 8 | Conversation events |
| `memory` | 7 | Memory/reflection |
| `user_action` | 6 | UI actions |
| `file` | 4 | File operations |
| `system` | 2 | System events |

### Output Format

```
log.session.duration: 15 minutes
log.session.messages: 8
log.events.0: discussed architecture [conversation]
```
<!-- /INCLUDE:log:ARCHITECTURE -->

#### 3. Form Thread (`agent/threads/form/`)

**Purpose**: Embodiment & Capabilities. Answers "WHAT can I do?". Manages tools and actions.

<!-- INCLUDE:form:ARCHITECTURE -->
_Source: [agent/threads/form/README.md](agent/threads/form/README.md)_

Form follows the L1/L2/L3 pattern:

```
L1: Registry   (what tools exist, metadata)
L2: Executor   (how to run them, orchestration)
L3: Executables (actual implementations)
```

### Directory Structure

```
form/
├── adapter.py      # Thread adapter (introspection, state)
├── api.py          # FastAPI routes (/api/form/*)
├── schema.py       # DB operations, tool management
└── tools/
    ├── registry.py     # L1: Tool definitions
    ├── executor.py     # L2: Execution engine
    └── executables/    # L3: Python implementations
```

### Tool Definition

```python
ToolDefinition(
    name="browser",
    description="Kernel browser automation",
    category=ToolCategory.BROWSER,
    actions=["navigate", "click", "screenshot"],
    run_file="browser.py",
    requires_env=["KERNEL_API_KEY"],
)
```

### Context Levels

| Level | Content |
|-------|---------|
| **L1** | Tool names, current action |
| **L2** | L1 + available tools with descriptions |
| **L3** | L2 + executable source code |

### Tool Categories

| Category | Tools |
|----------|-------|
| Communication | gmail, slack, sms, discord |
| Browser | browser, web_search |
| Memory | identity, philosophy, log, linking |
| Files | file_read, file_write |
| Automation | terminal, scheduler |
<!-- /INCLUDE:form:ARCHITECTURE -->

#### 4. Philosophy Thread (`agent/threads/philosophy/`)

**Purpose**: Values & Alignment. Answers "WHY should I do this?".

<!-- INCLUDE:philosophy:ARCHITECTURE -->
_Source: [agent/threads/philosophy/README.md](agent/threads/philosophy/README.md)_

### Database Schema

| Table | Purpose |
|-------|---------|
| `philosophy_profile_types` | Category definitions |
| `philosophy_profiles` | Profile instances (agent.core, agent.ethics, etc.) |
| `philosophy_profile_facts` | Individual facts with L1/L2/L3 values |

```sql
CREATE TABLE philosophy_profile_facts (
    profile_id TEXT NOT NULL,
    key TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    l1_value TEXT,
    l2_value TEXT,
    l3_value TEXT,
    weight REAL DEFAULT 0.5,
    PRIMARY KEY (profile_id, key)
)
```

### Adapter Methods

| Method | Purpose |
|--------|---------|
| `get_data(level, min_weight, limit)` | Get philosophy facts at HEA level |
| `get_core_values(level)` | Get facts with 'value' in fact_type |
| `get_ethical_bounds(level)` | Get facts with 'bound' or 'constraint' in fact_type |
| `introspect(context_level, query, threshold)` | Build STATE block contribution |
| `health()` | Health check with principle counts |

### Context Levels

| Level | Token Budget | Content |
|-------|--------------|---------|
| **L1** | ~10 tokens | Core value names only |
| **L2** | ~50 tokens | L1 + relevant constraints with brief descriptions |
| **L3** | ~200 tokens | L2 + full reasoning/examples |

### Output Format

```
philosophy.value.honesty: always direct
philosophy.value.curiosity: stay curious
philosophy.bound.harm_reduction: minimize harm
```
<!-- /INCLUDE:philosophy:ARCHITECTURE -->

#### 5. Reflex Thread (`agent/threads/reflex/`)

**Purpose**: Pattern Automata (Basal Ganglia). Answers "HOW do I respond (automatically)?".

<!-- INCLUDE:reflex:ARCHITECTURE -->
_Source: [agent/threads/reflex/README.md](agent/threads/reflex/README.md)_

### Database Tables

| Table | Purpose |
|-------|---------|
| `reflex_greetings` | Quick greeting patterns |
| `reflex_shortcuts` | User-defined commands |
| `reflex_system` | System-level reflexes |

### Pattern Matching

```
trigger → response
"hi" → "Hey! What's on your mind?"
"/clear" → [clear_conversation action]
```

### Reflex Cascade

Checked in order (first match wins):
1. **System reflexes** (safety, errors) — 0.9+ weight
2. **User shortcuts** (commands) — 0.6-0.8 weight
3. **Social reflexes** (greetings) — 0.3-0.5 weight

If no match → proceed to full context assembly.

### Context Levels

| Level | Content |
|-------|---------|
| **L1** | Active reflex triggers (metadata) |
| **L2** | L1 + matching patterns with responses |
| **L3** | L2 + full tool chains for complex reflexes |
<!-- /INCLUDE:reflex:ARCHITECTURE -->

#### 6. Linking Core Thread (`agent/threads/linking_core/`)

**Purpose**: Relevance Engine (Thalamus). Answers "WHICH concepts matter NOW?".

<!-- INCLUDE:linking_core:ARCHITECTURE -->
_Source: [agent/threads/linking_core/README.md](agent/threads/linking_core/README.md)_

### Core Concept: Spread Activation

When a concept is activated, activation spreads to linked concepts:

```
[sarah] ──0.8──→ [sarah.likes.blue]
       ──0.6──→ [sarah.works.coffee_shop]  
```

### The Math

**1. Hebbian Learning** — "Neurons that fire together, wire together"
```
new_strength = old_strength + (1.0 - old_strength) × learning_rate
```

**2. Spread Activation** — Multi-hop through the graph
```
target_activation = source_activation × link_strength
```

**3. Temporal Decay** — Links that aren't reinforced fade
```
new_strength = old_strength × decay_rate^days
```

### Tables

| Table | Purpose |
|-------|---------|
| `concept_links` | Learned associations (the graph) |
| `concept_activations` | Current activation levels |
| `fact_relevance` | Multi-dimensional scores per fact |

### Multi-Dimensional Scoring

| Dimension | Source | Description |
|-----------|--------|-------------|
| identity_score | Identity | Goal/value alignment |
| log_score | Log | Recency |
| form_score | Form | Semantic similarity |
| philosophy_score | Philosophy | Emotional salience |
| reflex_score | Reflex | Access frequency |
| cooccurrence_score | LinkingCore | Co-occurrence |
<!-- /INCLUDE:linking_core:ARCHITECTURE -->

### agent/subconscious/ — The Orchestrator

<!-- INCLUDE:subconscious:ARCHITECTURE -->
_Source: [agent/subconscious/README.md](agent/subconscious/README.md)_

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
<!-- /INCLUDE:subconscious:ARCHITECTURE -->

### agent/subconscious/temp_memory/ — Working Memory

<!-- INCLUDE:temp_memory:ARCHITECTURE -->
_Source: [agent/subconscious/temp_memory/README.md](agent/subconscious/temp_memory/README.md)_

### Database Schema

```sql
CREATE TABLE temp_facts (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    timestamp TEXT,
    source TEXT DEFAULT 'conversation',
    session_id TEXT,
    consolidated INTEGER DEFAULT 0,
    score_json TEXT,
    hier_key TEXT,
    metadata_json TEXT,
    status TEXT DEFAULT 'pending',
    confidence_score REAL
)
```

### Fact Lifecycle

```
PENDING → PENDING_REVIEW → APPROVED → CONSOLIDATED
                ↓
            REJECTED
```

| Status | Meaning |
|--------|---------|
| pending | Awaiting scoring |
| pending_review | Low confidence, needs human approval |
| approved | Ready for consolidation |
| consolidated | Promoted to permanent storage |
| rejected | Discarded |

### Key Functions

| Function | Purpose |
|----------|---------|
| `add_fact()` | Store a new fact |
| `get_facts()` | Retrieve facts |
| `get_pending_review()` | Facts needing approval |
| `approve_fact()` / `reject_fact()` | Human triage |
| `mark_consolidated()` | Mark as promoted |
<!-- /INCLUDE:temp_memory:ARCHITECTURE -->

### agent/services/ — Integration Layer

<!-- INCLUDE:services:ARCHITECTURE -->
_Source: [agent/services/README.md](agent/services/README.md)_

### Directory Structure

```
agent/services/
├── agent_service.py     # Main runtime — message handling
├── api.py               # FastAPI endpoints
└── kernel_service.py    # Kernel browser integration
```

### Components

| File | Purpose |
|------|---------|
| `agent_service.py` | Message pipeline, context assembly |
| `kernel_service.py` | Kernel browser automation |
| `api.py` | Agent control endpoints |

### Data Flow

```
User Message → agent_service.py
    → get_consciousness_context()
    → agent.generate()
    → Response
```
<!-- /INCLUDE:services:ARCHITECTURE -->

### External Modules

Non-cognitive modules that support the OS.

#### 1. Feeds (`Feeds/`) — Input & Awareness

<!-- INCLUDE:feeds:ARCHITECTURE -->
_Source: [Feeds/README.md](Feeds/README.md)_

### Directory Structure

```
Feeds/
├── router.py          # Main message bus
├── api.py             # FastAPI endpoints
└── sources/           # YAML configurations
    └── _template.yaml # Structure for new sources
```

### Source Configuration

```yaml
# sources/slack.yaml
name: slack
type: rest
poll_interval: 60
auth:
  method: bearer
  token_env: SLACK_BOT_TOKEN
pull:
  endpoint: https://slack.com/api/conversations.history
```

### Status

| Feature | Status |
|---------|--------|
| Router Logic | ✅ |
| API Endpoints | ✅ |
| Auth Handlers | 🔜 |
| Polling | 🔜 |
| Draft Push | 🔜 |
<!-- /INCLUDE:feeds:ARCHITECTURE -->

#### 2. Chat (`chat/`) — Interface API

<!-- INCLUDE:chat:ARCHITECTURE -->
_Source: [chat/README.md](chat/README.md)_

### Directory Structure

```
chat/
├── api.py              # FastAPI endpoints
├── schema.py           # SQLite tables
├── import_convos.py    # Import from other providers
└── parsers/            # Format-specific parsers
```

### Database Schema

| Table | Purpose |
|-------|---------|
| `convos` | Session metadata |
| `convo_turns` | Message content |
| `message_ratings` | User feedback |

### Key Functions

| Function | Purpose |
|----------|---------|
| `save_conversation()` | Persist full conversation state |
| `add_turn()` | Append single interaction |
| `ImportConvos.import_conversations()` | Import pipeline |

### Supported Import Formats

- ChatGPT (`conversations.json`)
- Claude (`conversations.json`)
- Gemini (JSON export)
- VS Code Copilot (JSON export)
<!-- /INCLUDE:chat:ARCHITECTURE -->

#### 3. Workspace (`workspace/`) — File Management

<!-- INCLUDE:workspace:ARCHITECTURE -->
_Source: [workspace/README.md](workspace/README.md)_

### Directory Structure

```
workspace/
├── api.py               # FastAPI endpoints
└── schema.py            # SQLite tables for metadata
```

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/workspace/files` | List all files |
| POST | `/api/workspace/upload` | Upload a file |
| DELETE | `/api/workspace/files/{id}` | Delete a file |
| POST | `/api/workspace/folders` | Create folder |
| PUT | `/api/workspace/move` | Move/rename files |

### Status

| Feature | Status |
|---------|--------|
| File upload | ✅ |
| Folder organization | ✅ |
| Full-text search | 🔜 |
| Agent reference integration | 🔜 |
<!-- /INCLUDE:workspace:ARCHITECTURE -->

#### 4. Eval (`eval/`) — The Battle Arena

<!-- INCLUDE:eval:ARCHITECTURE -->
_Source: [eval/README.md](eval/README.md)_

### Directory Structure

```
eval/
├── api.py               # FastAPI router
├── schema.py            # SQLite tables
├── battle.py            # Battle orchestration
├── judge.py             # LLM-as-a-Judge
├── metrics.py           # Scoring functions
└── runners/             # Battle implementations
    ├── identity.py
    ├── coherence.py
    └── speed.py
```

### Battle Types

| Battle | Tests |
|--------|-------|
| Identity | Resists prompt injection |
| Memory | Remembers across sessions |
| Tool Use | Multi-step task execution |
| Connections | Links facts over time |
| Speed | Response latency |

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/eval/battle/start` | Start battle |
| GET | `/api/eval/battle/{id}` | Get results |
| GET | `/api/eval/leaderboard` | Win/loss stats |
<!-- /INCLUDE:eval:ARCHITECTURE -->

#### 5. Finetune (`finetune/`) — Training Studio

<!-- INCLUDE:finetune:ARCHITECTURE -->
_Source: [finetune/README.md](finetune/README.md)_

### Directory Structure

```
finetune/
├── api.py               # Endpoints to trigger training
├── mlx_config.yaml      # Apple MLX configuration
└── train_mac.sh         # Local fine-tuning script
```

### Dataset Strategy

| Dataset | Purpose |
|---------|---------|
| `aios_finetune_data.jsonl` | Core state obedience |
| `aios_finetune_adversarial.jsonl` | Identity protection |
| `aios_combined.jsonl` | All examples merged |

### Status

| Feature | Status |
|---------|--------|
| Data format | ✅ |
| MLX config | ✅ |
| Data generation scripts | 🔜 |
| Validation suite | 🔜 |
<!-- /INCLUDE:finetune:ARCHITECTURE -->

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
