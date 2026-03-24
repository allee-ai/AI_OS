# Agent Core Threads

5 data-producing threads + 1 relevance engine, orchestrated by the Subconscious.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    5 DATA THREADS                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│
│  │ IDENTITY │ │   LOG    │ │   FORM   │ │PHILOSOPHY│ │ REFLEX ││
│  │          │ │          │ │          │ │          │ │        ││
│  │ L1/L2/L3 │ │ recency  │ │meta=caps │ │ L1/L2/L3 │ │patterns││
│  │ per key  │ │ 10/100/  │ │data=now  │ │ per key  │ │        ││
│  │          │ │ 1000     │ │          │ │          │ │        ││
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘│
│       └────────────┴────────────┴────────────┴───────────┘     │
└─────────────────────────────────┬───────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────┐
│                       LINKING CORE                              │
│  The relevance engine — equations for what's important NOW      │
│  ├─ Spread activation: concept → linked concepts                │
│  ├─ Hebbian learning: co-occurrence strengthens links           │
│  ├─ Decay: unused links fade over time                          │
│  └─ Not a data store — a scoring algorithm                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Thread Architecture

| Thread | Level System | metadata_json | data_json |
|--------|--------------|---------------|-----------|
| **Identity** | L1/L2/L3 per key | type, description | fact content at depth |
| **Philosophy** | L1/L2/L3 per key | type, description | value/belief at depth |
| **Log** | Recency (L1=10, L2=100, L3=1000) | event type, source | message, timestamp |
| **Form** | L1/L2/L3 | **capabilities** (static) | **current state** (dynamic) |
| **Reflex** | Quick patterns | trigger type | response pattern |
| **Linking Core** | N/A (not data) | See [linking_core/README.md](linking_core/README.md) | Equations only |

---

## Level Systems Explained

### Identity & Philosophy: Depth-Based
Each key has L1/L2/L3 variants — more detail at higher levels.

```
key: "user_name"
L1: "Jordan"
L2: "Jordan, prefers morning work sessions"  
L3: "Jordan, software developer, prefers morning sessions, building AI_OS project"
```

### Log: Recency-Based
Levels determine how far back in time to look:
- **L1** = Last 10 events (quick glance)
- **L2** = Last 100 events (conversation history)
- **L3** = Last 1000 events (full timeline)

### Form: Capability vs State
- **metadata** = What CAN happen (tool definitions, capabilities)
- **data** = What IS happening (current browser URL, active sessions)

```
key: "tool_browser"
metadata: { "name": "browser", "actions": ["navigate", "screenshot"] }
data: { "url": "github.com", "session_id": "abc123" }
```

---

## Thread Summary

| Thread | Purpose | Key Question |
|--------|---------|--------------|
| **Identity** | Self + user awareness | "Who am I? Who are you?" |
| **Log** | Temporal awareness | "What happened? When?" |
| **Form** | Capabilities + current state | "What can I do? What's active?" |
| **Philosophy** | Values, reasoning style | "What do I believe? How should I think?" |
| **Reflex** | Quick patterns | "What's my instant response?" |
| **Linking Core** | Relevance scoring | "What's important right now?" |

---

## Current Status & Future Ideas

### Identity Thread
| Aspect | Status |
|--------|--------|
| **Current** | 🌀 SQLite backend working, pulls facts by level, user/machine separation |
| **Future** | Memory permanence logic, weight decay, consolidation daemon, "tomorrow queue" for deferred decisions |

### Log Thread  
| Aspect | Status |
|--------|--------|
| **Current** | 🌀 Event logging to master.log, session tracking, basic temporal facts |
| **Future** | File→DB migration, relevance integration, pattern detection for reflex promotion |

### Form Thread
| Aspect | Status |
|--------|--------|
| **Current** | 🌀 L1/L2/L3 tools architecture (registry → executor → executables), tool execution API, browser integration |
| **Future** | Email/calendar integration, sandbox environment, plugin architecture |

### Philosophy Thread
| Aspect | Status |
|--------|--------|
| **Current** | 🌀 SQLite adapter, L1/L2/L3 depth levels, values and beliefs stored per key |
| **Future** | Ethics/awareness/curiosity/resolve modules (from Elaris), dream state for personality development |

### Reflex Thread
| Aspect | Status |
|--------|--------|
| **Current** | 🌀 SQLite adapter, pattern matching, trigger→response pairs |
| **Future** | 10x rule pattern detection, reflex promotion, user macros, system reflexes for resource management |

### LinkingCore (Utility)
| Aspect | Status |
|--------|--------|
| **Current** | 🌀 Basic relevance.py with embedding similarity |
| **Future** | Key sequence learning, attention scoring, prompt builder, focus system integration |

---

## Directory Structure

```
agent/threads/
├── __init__.py              # Thread registry and exports
├── README.md                # This file
│
├── identity/                # WHO AM I, WHO ARE YOU
│   ├── __init__.py
│   ├── adapter.py           # IdentityThreadAdapter
│   ├── README.md
│   └── modules/             # (future: user_profile, machine_id, aios_self)
│
├── log/                     # TEMPORAL AWARENESS
│   ├── __init__.py
│   ├── adapter.py           # LogThreadAdapter
│   ├── README.md
│   └── modules/             # (future: events, sessions, temporal)
│
├── linking_core/            # RELEVANCE SCORING
│   ├── __init__.py
│   ├── adapter.py           # LinkingCoreThreadAdapter
│   ├── README.md
│   └── modules/             # (future: relevance, embeddings, topic_graph)
│
├── form/                    # TOOL USE, ACTIONS
│   ├── __init__.py
│   ├── adapter.py           # FormThreadAdapter
│   ├── api.py               # FastAPI routes
│   ├── cli.py               # CLI /tools commands
│   ├── schema.py            # DB ops, tool CRUD
│   ├── train.py             # Tool training data export
│   ├── README.md
│   └── tools/               # L1/L2/L3 architecture
│       ├── registry.py      # L1: Tool definitions + ensure_tools_in_db()
│       ├── executor.py      # L2: Execution engine
│       ├── scanner.py       # Auto-discovers executables
│       └── executables/     # L3: 11 Python implementations
│           ├── cli_command.py
│           ├── code_edit.py
│           ├── file_read.py
│           ├── file_write.py
│           ├── notify.py
│           ├── regex_search.py
│           ├── terminal.py
│           ├── web_search.py
│           ├── workspace_read.py
│           └── workspace_write.py
│
├── philosophy/              # VALUES, REASONING
│   ├── __init__.py
│   ├── adapter.py           # PhilosophyThreadAdapter
│   ├── README.md
│   └── modules/             # (future: core_values, ethical_bounds)
│
├── vision/                  # VISUAL PROCESSING
│   └── (experimental)
│
└── reflex/                  # QUICK PATTERNS/PROGRAMMATIC REFLEXES
    ├── __init__.py
    ├── adapter.py           # ReflexThreadAdapter
    ├── README.md
    └── modules/             # (future: greetings, shortcuts, triggers)
```

---

## Migration Plan

### Phase 1: Thread Structure (COMPLETE 🌀)
- [x] Create 6 thread directories
- [x] Create adapter.py for each thread
- [x] Create README.md for each thread
- [x] Create threads/__init__.py registry

### Phase 2: Wire Up Subconscious (COMPLETE 🌀)
- [x] Update `subconscious/core.py` to import from `agent/threads/`
- [x] Deprecate `subconscious/threads/` adapters
- [x] Test all 6 threads register correctly

### Phase 3: Migrate Existing Code (COMPLETE 🌀)
All adapters now live in `agent/threads/<name>/adapter.py`.

### Phase 4: Update Imports (COMPLETE 🌀)
- [x] Update all imports in `services/agent_service.py`
- [x] Removed `react-chat-app/` (consolidated to `scripts/server.py`)
- [x] Tests pass

### Phase 5: Cleanup (IN PROGRESS)
- [x] Remove deprecated `subconscious/threads/` directory
- [ ] Remove remaining orphaned files
- [x] Update documentation

---

## Usage

```python
from agent.threads import get_all_threads, get_thread

# Get all threads
threads = get_all_threads()
for t in threads:
    print(f"{t.name}: {t.purpose}")

# Get specific thread
identity = get_thread("identity")
facts = identity.get_context(level=2)

# Check reflex pattern
reflex = get_thread("reflex")
match = reflex.match_pattern("hi there")
if match:
    pattern_type, response = match
    print(f"Quick response: {response}")
```

---

## Thread Interface

All threads implement this interface:

```python
class ThreadAdapter:
    name: str
    purpose: str
    
    def get_context(self, level: int) -> list[str]:
        """Return facts for the given HEA level (1-3)."""
    
    def get_metadata(self) -> dict:
        """Return thread health and status."""
    
    def health(self) -> HealthReport:
        """Check thread health."""
    
    def introspect(self, context_level: int) -> IntrospectionResult:
        """Full introspection for subconscious."""
```

---

## HEA Context Levels

| Level | Name | Tokens | Thread Behavior |
|-------|------|--------|-----------------|
| L1 | Realtime | ~50/thread | Minimal facts, Reflex dominant |
| L2 | Conversational | ~200/thread | Balanced facts, all threads contribute |
| L3 | Analytical | ~400/thread | Full facts, deep context |

---

## Status

| Thread | Adapter | README | Wired | Tested |
|--------|---------|--------|-------|--------|
| Identity | 🌀 | 🌀 | 🌀 | 🌀 |
| Log | 🌀 | 🌀 | 🌀 | 🌀 |
| LinkingCore | 🌀 | 🌀 | 🌀 | 🌀 |
| Form | 🌀 | 🌀 | 🌀 | 🌀 |
| Philosophy | 🌀 | 🌀 | 🌀 | 🌀 |
| Reflex | 🌀 | 🌀 | 🌀 | 🌀 |

---

## Frontend Module

Located at `frontend/src/modules/threads/`:

```
threads/
├── index.ts                          # Module exports
├── pages/
│   ├── ThreadsPage.tsx               # Main threads dashboard
│   ├── ThreadsPage.css
│   ├── ProfilesPage.tsx              # Identity/Philosophy profile editor
│   └── ProfilesPage.css
├── form/
│   ├── index.ts
│   └── components/
│       ├── ToolDashboard.tsx         # Form thread tools view
│       └── ToolDashboard.css
├── reflex/
│   ├── index.ts
│   └── components/
│       ├── ReflexDashboard.tsx       # Reflex patterns editor
│       └── ReflexDashboard.css
├── linking_core/
│   ├── index.ts
│   └── components/
│       └── ConceptGraph3D.tsx        # 3D concept visualization
├── hooks/
│   └── useIntrospection.ts           # Thread state polling
├── services/
│   └── introspectionService.ts       # API client
├── types/
│   └── introspection.ts              # TypeScript interfaces
└── utils/
    └── constants.ts                  # API config
```