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
- `generate(user_input, convo, feed_type, consciousness_context, on_tool_event)` — Main response method with optional tool event callback
- `_process_tool_calls(text, messages, on_tool_event, max_rounds)` — Scan/execute/re-call loop (max 5 rounds)
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
├── api.py          # FastAPI router (~30 endpoints)
├── cli.py          # REPL commands
├── contract.py     # API definitions for adapters
├── triggers.py     # Event-driven hooks
├── temp_memory/    # Short-term fact storage before consolidation
│   ├── store.py    # add_fact(), get_facts(), status management
│   └── README.md   # Module documentation
└── loops/          # Background maintenance loops
    ├── base.py     # BackgroundLoop base + LoopConfig
    ├── manager.py  # Loop factory + lifecycle
    ├── memory.py   # Fact extraction
    ├── consolidation.py  # Fact scoring + promotion
    ├── thought.py  # OODA-cycle proactive thinking
    ├── task_planner.py   # Task decomposition + execution
    ├── goals.py    # Emergent goal proposal
    ├── self_improve.py   # Scoped code review
    ├── convo_concepts.py # Concept graph backfill
    ├── training_gen.py   # Synthetic training data
    ├── health.py   # Thread health checks
    ├── sync.py     # Cross-thread sync
    └── custom.py   # User-defined COT loops
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

### Preset Contact Facts

New profiles are created with empty preset facts for common contact information:

| Fact Key | Fact Type | Description |
|----------|-----------|-------------|
| `name` | name | Full name |
| `email` | email | Email address |
| `phone` | phone | Phone number |
| `location` | location | City/region/timezone |
| `occupation` | occupation | Job title or role |
| `organization` | organization | Company or affiliation |
| `relationship` | relationship | How they relate to user |
| `notes` | note | Freeform notes |

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/identity` | List all profiles |
| GET | `/api/identity/{id}/facts` | Get profile facts |
| POST | `/api/identity/facts` | Create new fact |
| PUT | `/api/identity/{id}/facts/{key}` | Edit existing fact |
| DELETE | `/api/identity/{id}/facts/{key}` | Delete fact |
| DELETE | `/api/identity/{id}` | Delete profile (if not protected) |
| POST | `/api/identity/import/upload` | Upload vCard file, returns upload_id |
| POST | `/api/identity/import/parse` | Parse uploaded file, returns preview |
| POST | `/api/identity/import/commit` | Import contacts to profiles |
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
├── cli.py          # Headless CLI (/tools commands)
├── schema.py       # DB operations, tool management
├── train.py        # Training data export for tool calling
└── tools/
    ├── registry.py     # L1: Tool definitions, safety allowlist, ensure_tools_in_db()
    ├── scanner.py      # :::execute::: block parser
    ├── executor.py     # L2: Execution engine
    └── executables/    # L3: 11 Python implementations
        ├── cli_command.py      # CLI passthrough
        ├── code_edit.py        # Code editing
        ├── file_read.py        # Read files (sandboxed)
        ├── file_write.py       # Write files (sandboxed)
        ├── notify.py           # User notifications
        ├── regex_search.py     # Regex file search
        ├── terminal.py         # Shell commands (30s timeout)
        ├── web_search.py       # DuckDuckGo search
        ├── workspace_read.py   # Workspace read/list/search
        └── workspace_write.py  # Workspace write/mkdir/move/delete
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
| `reflex_triggers` | Feed event → Tool action automations |

### Pattern Matching

```
trigger → response
"hi" → "Hey! What's on your mind?"
"/clear" → [clear_conversation action]
```

### Feed Triggers (NEW)

Connect feed events to tool actions:
```
gmail/email_received → web_search/search
discord/mention_received → send_notification/notify
```

Trigger fields:
- **feed_name**: Source feed (gmail, discord, etc.)
- **event_type**: Event to listen for (email_received, message_sent, etc.)
- **condition**: Optional filter (e.g., subject contains "urgent")
- **tool_name**: Tool to execute
- **tool_action**: Action to perform
- **tool_params**: Parameters to pass to tool

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
│   ├── convo_concepts.py   # ConvoConceptLoop — backfill concept graph from convos
│   ├── demo_audit.py       # DemoAuditLoop — audit and check demo readiness
│   └── workspace_qa.py     # WorkspaceQALoop — workspace file quality checks
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

### Background Loops (13 total)

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
| DemoAuditLoop | varies | Audits system readiness for demos |
| WorkspaceQALoop | varies | Quality checks on workspace files |

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
├── kernel_service.py    # Kernel browser integration
├── mobile_api.py        # Mobile app REST API
└── mobile_panel.html    # Mobile web panel
```

### Components

| File | Purpose |
|------|---------|
| `agent_service.py` | Message pipeline, context assembly |
| `kernel_service.py` | Kernel browser automation |
| `api.py` | Agent control endpoints |
| `mobile_api.py` | Mobile-optimized REST API with bearer token auth |
| `mobile_panel.html` | Mobile web interface |

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
├── router.py              # Main message bus
├── api.py                 # FastAPI endpoints (secrets, OAuth, events)
├── events.py              # Event registry and emission system
├── bridge.py              # Feed↔Agent bridge for message routing
├── cli.py                 # Headless CLI (/feeds commands)
├── intelligence.py        # Feed content analysis / scoring
├── polling.py             # Background feed polling scheduler
└── sources/               # Modular feed directories
    ├── calendar/
    │   └── __init__.py    # Calendar integration
    ├── discord/
    │   └── __init__.py    # Bot adapter, event types
    ├── email/
    │   └── __init__.py    # Multi-provider (Gmail, Outlook, Proton)
    ├── github/
    │   └── __init__.py    # Issues, PRs, mentions, pushes
    └── website/
        └── __init__.py    # RSS/web scraping adapter
```

### Feed Modules

Each feed module defines:
- **Event types**: What events it can emit (email_received, message_sent, etc.)
- **OAuth config**: How to authenticate (Google OAuth2, bot tokens, etc.)
- **Adapter**: API wrapper for fetching/sending data

### Event System

```python
from Feeds.events import emit_event, EventPriority

# Emit an event (auto-logged, triggers reflexes)
emit_event(
    feed_name="gmail",
    event_type="email_received",
    payload={"from": "user@example.com", "subject": "Hello"},
    priority=EventPriority.HIGH,
)
```

### Secrets Management

Encrypted credential storage for API keys and OAuth tokens:
```python
from agent.core.secrets import store_secret, get_oauth_tokens

# Store API key
store_secret("discord", "bot_token", "MTEx...")

# Get OAuth tokens
tokens = get_oauth_tokens("gmail")
```

### Status

| Feature | Status |
|---------|--------|
| Router Logic | ✅ |
| API Endpoints | ✅ |
| Event System | ✅ |
| Secrets Storage | ✅ |
| Gmail OAuth | 🔧 Config only |
| Discord Adapter | 🔧 Config only |
| Reflex Triggers | ✅ |
<!-- /INCLUDE:feeds:ARCHITECTURE -->

#### 2. Chat (`chat/`) — Interface API

<!-- INCLUDE:chat:ARCHITECTURE -->
_Source: [chat/README.md](chat/README.md)_

### Directory Structure

```
chat/
├── api.py              # FastAPI endpoints
├── schema.py           # SQLite tables
├── cli.py              # Headless CLI (/chat commands)
├── import_convos.py    # Import from other providers
├── train.py            # Training data export from chat history
└── parsers/            # Format-specific parsers
    ├── export_parser_base.py     # Base class for all parsers
    ├── chatgpt_export_parser.py  # ChatGPT conversations.json
    ├── claude_export_parser.py   # Claude export format
    ├── gemini_export_parser.py   # Gemini JSON export
    └── vscode_export_parser.py   # VS Code Copilot export
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
├── api.py               # FastAPI endpoints (upload, move, delete, search, etc.)
├── schema.py            # SQLite tables, CRUD, FTS5 indexing
├── cli.py               # Headless CLI (/files commands)
├── summarizer.py        # LLM-powered file summarization
├── __init__.py
├── aios-demo/           # Demo website (community hub)
└── allee-ai.github.io/  # Project documentation site
```

### Database Tables

| Table | Purpose |
|-------|---------|
| `workspace_files` | File metadata, content, parent paths, MIME types |
| `workspace_fts` | FTS5 full-text search index on file content |

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/workspace/files` | List files (with parent_path filter) |
| POST | `/api/workspace/upload` | Upload a file |
| DELETE | `/api/workspace/files/{id}` | Delete a file |
| POST | `/api/workspace/folders` | Create folder |
| PUT | `/api/workspace/move` | Move/rename files |
| GET | `/api/workspace/files/{id}/content` | Download file content |
| GET | `/api/workspace/files/{id}/meta` | Get file metadata |
| PUT | `/api/workspace/files/{id}/edit` | Edit file content in-place |
| GET | `/api/workspace/search` | FTS5 search within file contents |
| GET | `/api/workspace/recent` | Recently modified files |
| POST | `/api/workspace/pin/{id}` | Pin a file |
| GET | `/api/workspace/pinned` | List pinned files |
| POST | `/api/workspace/notes` | Create a quick note |
| GET | `/api/workspace/notes` | List notes |
| POST | `/api/workspace/summarize/{id}` | Generate LLM summary |

### Agent Tools

The workspace is accessible to the LLM via two registered tools:

| Tool | Actions | Safety |
|------|---------|--------|
| `workspace_read` | `read_file`, `list_directory`, `search_files` | All safe (auto-execute) |
| `workspace_write` | `write_file`, `create_directory`, `move_file`, `delete_file` | `delete_file` blocked by default |

### CLI Commands

```bash
/files [path]           # List directory
/files read <path>      # Show file content
/files write <path> <c> # Create/overwrite file
/files mkdir <path>     # Create directory
/files mv <old> <new>   # Move/rename
/files rm <path>        # Delete file
/files search <query>   # Full-text search
/files stats            # File count and total size
```

### Status

| Feature | Status |
|---------|--------|
| File upload | ✅ |
| Folder organization | ✅ |
| Full-text search (FTS5) | ✅ |
| In-browser editing (CodeMirror) | ✅ |
| Auto-summarization | ✅ |
| Agent read tools | ✅ |
| Agent write/move tools | ✅ |
| LLM file sorting | ✅ |
| Headless CLI | ✅ |
| Version history | 📋 |
<!-- /INCLUDE:workspace:ARCHITECTURE -->

#### 4. Eval (`eval/`) — Benchmark Harness

<!-- INCLUDE:eval:ARCHITECTURE -->
_Source: [eval/README.md](eval/README.md)_

### Directory Structure

```
eval/
├── __init__.py    # Exports router
├── api.py         # FastAPI router /api/eval
├── cli.py         # Headless CLI (/eval commands)
├── evals.py       # 10 structured evals (state_format, identity, recall, tools, etc.)
├── judge.py       # LLM-as-judge scoring logic
├── runner.py      # run_prompt(), judge_responses(), list_available_models()
├── schema.py      # SQLite tables + CRUD + seed benchmarks
├── scanner.py     # Tool call parser — validates :::execute blocks
├── analyze_training_data.py  # Training data quality analysis
├── dump_responses.py         # Export responses for inspection
├── run_3b_baseline.py        # 3B model baseline benchmark
├── run_3b_showdown.py        # 3B model comparison
├── run_full_v1_showdown.py   # Full v1 model showdown
├── run_knowledge_retention.py # Knowledge retention eval
├── run_kr_best.py            # Best knowledge retention config
├── run_kr_registry.py        # KR with registry tools
├── run_kr_v2.py              # Knowledge retention v2
├── run_smol135m_5e6_full.py  # SmolLM 135M (5e-6 lr) eval
├── run_smol135m_full.py      # SmolLM 135M eval
├── _show_3b_results.py       # Display 3B results
└── README.md
```

### Structured Evals (evals.py)

| # | Eval | Tests |
|---|------|-------|
| 1 | `state_format` | STATE block structure adherence |
| 2 | `identity_persistence` | Identity holds under adversarial probing |
| 3 | `fact_recall` | Known facts surface in responses |
| 4 | `tool_use` | Correct tool selection and invocation |
| 5 | `context_relevance` | Response relevance to thread context |
| 6 | `hallucination` | Fabricated facts detection |
| 7 | `state_completeness` | All required STATE sections present |
| 8 | `state_impact` | STATE measurably improves response quality |
| 9 | `scoring_quality` | Thread scoring accuracy (L1/L2/L3) |
| 10 | `tool_calling_direct` | Text-native `:::execute` protocol — 8 test cases, single_pass + loop modes |

### How It Works

```
User selects prompt + models
        ↓
  api.py /run endpoint
        ↓
  runner.py → run_prompt() per model
  ├── Nola models: agent.generate() with full STATE pipeline
  └── Other models: direct Ollama call
        ↓
  judge_responses() → LLM-as-judge scores all responses
        ↓
  schema.py → save results + comparison to SQLite
```

### Database Schema

| Table | Purpose |
|-------|---------|
| `eval_benchmarks` | Stored benchmark definitions (name, type, prompts) |
| `eval_results` | Individual model responses with timing + scores |
| `eval_comparisons` | Head-to-head comparisons with judge output |

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/eval/models` | List available models + Nola |
| POST | `/api/eval/run` | Run prompt against multiple models |
| POST | `/api/eval/run/state-comparison` | Quick with-STATE vs without-STATE |
| GET | `/api/eval/results` | List all results (filterable) |
| GET | `/api/eval/results/{id}` | Single result detail |
| GET | `/api/eval/comparisons` | List all comparisons |
| GET | `/api/eval/benchmarks` | List benchmarks (filterable by type) |
| POST | `/api/eval/benchmarks` | Create a benchmark |
| DELETE | `/api/eval/benchmarks/{id}` | Delete a benchmark |

### Runner Modes

| Model | Pipeline | STATE |
|-------|---------|-------|
| `nola` (with STATE) | `agent.generate()` → full subconscious | Yes |
| `nola` (no STATE) | Direct Ollama call with same base model | No |
| Any other model | Direct Ollama call | No |
<!-- /INCLUDE:eval:ARCHITECTURE -->

#### 5. Fire-Tuner (`finetune/`) — Training Studio

<!-- INCLUDE:finetune:ARCHITECTURE -->
_Source: [finetune/README.md](finetune/README.md)_

### Directory Structure

```
finetune/
├── api.py                  # 7 FastAPI endpoints (export, train, load, config, data)
├── cli.py                  # CLI commands (/finetune, /finetune gen, etc.)
├── cloud_gen.py            # Multi-provider cloud data generator (AST → conversational Q&A)
├── sections.py             # Shared JSONL builders (API, CLI, schema examples)
├── docstring_extractor.py  # AST-based docstring harvesting across all modules
├── gold_examples.py        # Hand-curated reasoning examples (9 categories)
├── mlx_config.yaml         # Apple MLX LoRA configuration
├── train_mac.sh            # Local fine-tuning script (Apple Silicon)
├── generated/              # Background-generated training data (TrainingGenLoop + cloud_gen)
└── auto_generated/         # Docstring-extracted training data
```

### Data Sources

| Source | Generator | Description |
|--------|-----------|-------------|
| Per-thread metadata | `sections.py` | API endpoints, CLI commands, schema tables → Q&A pairs |
| Docstrings | `docstring_extractor.py` | AST-walks Python source, extracts function/class docs |
| Gold examples | `gold_examples.py` | Hand-written reasoning pairs (9 categories) |
| Live decisions | `train.py` per thread | High-confidence decisions from `source='aios'` conversations (threshold 0.7) |
| Synthetic (kimi-k2) | `TrainingGenLoop` | Teacher model reads source code + mechanical examples → generates 5 better pairs per file |
| Cloud-generated | `cloud_gen.py` | AST-walks every def/class block, round-robins free-tier APIs (Gemini, Claude, OpenAI, OpenRouter, Ollama) → 5 conversational Q&A per block |

### Module Coverage

The `TrainingGenLoop` generates examples for all 17 modules:

| Scope | Modules |
|-------|---------|
| Thread modules | linking_core, identity, philosophy, log, reflex, form, chat, docs |
| Top-level modules | workspace, feeds, agent_core, agent_services, form_tools, parsers, data_db, scripts, subconscious |

### Per-Thread Train Files

Each cognitive thread has its own `train.py`:

| Thread | What It Exports |
|--------|----------------|
| Identity | Profile facts, trust levels, contact management Q&A |
| Philosophy | Values, constraints, ethical bounds Q&A |
| Log | Event types, session tracking, timeline Q&A |
| Reflex | Trigger patterns, cascade priority, automation Q&A |
| Form | Tool definitions, safety rules, execution Q&A |
| Linking Core | Concept links, spread activation, scoring Q&A |

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/finetune/export` | Full export: consolidate links → run all thread exporters → merge to `aios_combined.jsonl` |
| POST | `/api/finetune/export/{thread}` | Export single thread |
| GET | `/api/finetune/export/stats` | Counts from all modules + reasoning + generated |
| POST | `/api/finetune/start` | Configure hyperparams + launch `train_mac.sh` |
| GET | `/api/finetune/config` | Current MLX config |
| GET | `/api/finetune/data` | List all `.jsonl` files with line counts |
| POST | `/api/finetune/load` | Fuse LoRA adapter into Ollama model |

### Export Pipeline

```
POST /api/finetune/export
    → consolidate_links()          # Promote reinforced concept links
    → for each thread: export_training_data()
    → docstring_extractor.extract_all()
    → gold_examples.get_all_examples()
    → merge → finetune/aios_combined.jsonl
```

### Training (Apple Silicon)

```bash
# Via API
POST /api/finetune/start
  { "rank": 8, "alpha": 16, "lr": 1e-4, "iters": 1000 }

# Or directly
cd finetune && bash train_mac.sh
```

Uses MLX LoRA on Apple Silicon. Config in `mlx_config.yaml`.

### Cloud Data Generator (`cloud_gen.py`)

AST-walks every Python file in the codebase, discovers all `def` and `class` blocks (~2,066), and generates 5 conversational Q&A pairs per block using free-tier LLM APIs.

**Providers** (round-robin by default):
| Provider | Free Tier | Rate Limit |
|----------|-----------|------------|
| Gemini | 15 RPM | 4s delay default |
| Claude | API key required | |
| OpenAI | API key required | |
| OpenRouter | Free models (qwen, mistral) | |
| Ollama | Local, unlimited | |

**Usage:**
```bash
# Preview what would be generated
python -m finetune.cloud_gen --dry-run

# Generate from all blocks via Ollama
python -m finetune.cloud_gen --provider ollama

# Resume interrupted run, single module
python -m finetune.cloud_gen --resume --module identity

# Limit to 50 blocks
python -m finetune.cloud_gen --max 50

# Or via CLI
/finetune gen --dry-run
/finetune gen --provider gemini --resume --max 100
```

Output: `finetune/generated/cloud_<module>.jsonl` with progress tracking in `.cloud_gen_progress.json`.

### CLI Commands

| Command | Description |
|---------|-------------|
| `/finetune` | Training data overview & stats |
| `/finetune export` | Export all thread data → aios_combined.jsonl |
| `/finetune gen [opts]` | Run cloud data generator |
| `/finetune train` | Launch MLX training (train_mac.sh) |
| `/finetune runs` | List training run directories |
| `/finetune config` | Show MLX training configuration |

### Status

| Feature | Status |
|---------|--------|
| Export pipeline | ✅ Wired |
| Per-thread train.py | ✅ All 6 threads (source='aios' filtered) |
| Docstrings | ✅ AST-based extraction |
| Gold examples | ✅ 9 categories |
| Cloud data generator | ✅ Multi-provider, 2,066 blocks discovered |
| CLI commands | ✅ /finetune, gen, export, train, runs, config |
| MLX config | ✅ |
| Training gen loop | ✅ kimi-k2 teacher, 17 modules, 105+ files |
| Data quality filtering | ✅ Source-filtered, capped associations |
| End-to-end cycle | ✅ First cycle complete (MLX LoRA, noticeable improvement) |
| Adapter loading | 🔧 Endpoint exists, untested |
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
