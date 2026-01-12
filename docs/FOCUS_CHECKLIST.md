# Focus System Implementation Checklist

**Quick reference for implementing the focus-based architecture.**

See [`implementation/FOCUS_IMPLEMENTATION.md`](implementation/FOCUS_IMPLEMENTATION.md) for detailed plan.

---

## 🎯 Core Concept

**Focus > Attention**
- DB learns which keys come after which keys
- Prompt contains only focused keys (not everything)
- LLM generates from pre-selected space
- System learns from every query

---

## ✅ Week 1: Foundation (Jan 2-8) — COMPLETE

### Schema Migration
- [x] Add weight columns to identity tables (via `fact_relevance` table)
- [x] Create indexes on weight columns
- [x] Create `key_cooccurrence` table (key_a, key_b, count)
- [x] Create `concept_links` table (concept_a, concept_b, strength, fire_count)
- [x] Create `fact_relevance` table (multi-dimensional scoring)
- [x] Test migration on dev database

**Implemented in:** `Nola/threads/schema.py`

### Create Focus Module (Partial)
- [x] `spread_activate()` - Activation spreading through concept graph
- [x] `link_concepts()` - Hebbian learning (strength += (1-strength) * rate)
- [x] `decay_concept_links()` - Time-based decay
- [x] `generate_hierarchical_key()` - Convert facts to dot-notation
- [x] `extract_concepts_from_text()` - Pull concepts from messages
- [x] `get_keys_for_concepts()` - Retrieve facts for activated concepts

**Implemented in:** `Nola/threads/schema.py`, `Nola/threads/linking_core/adapter.py`

### LinkingCore Integration
- [x] `activate_memories(input_text)` - Uses spread activation
- [x] `get_associative_context()` - Combines embeddings + spread activation
- [x] `_get_cooccurrence_boost()` - Co-occurrence scoring

**Test:** Spread activation returns linked concepts ✅

---

## 🧠 Week 2: Memory Logic (Jan 9-15) — IN PROGRESS

### Memory Permanence
- [ ] `memory_filter.py` - Conflict detection
- [ ] `check_memory_exists()` - Exact match check
- [ ] `check_memory_conflicts()` - Conflict detection
- [ ] `get_memory_variations()` - Count variations
- [ ] `should_save_memory()` - Decision logic

### Tomorrow Queue
- [ ] Create `memory_queue` table
- [ ] Queue system for deferred decisions
- [ ] Daily summary generation
- [ ] Auto-expire after 7 days

**File:** `Nola/temp_memory/permanence.py`

**Test:** Memory saves only when unique, queues conflicts

---

## 🔌 Week 3: Integration (Jan 16-22)

### Subconscious Core
- [ ] Replace `get_consciousness_context()` with focus version
- [ ] Call `focus.get_focused_context(query, level)`
- [ ] Record accessed keys after response
- [ ] Trigger weight updates every 5 turns

**Files:** `Nola/subconscious/core.py`, `Nola/subconscious/__init__.py`

### Agent Service
- [ ] Pass query to subconscious for focus
- [ ] Receive focused context (not full dumps)
- [ ] Pass accessed_keys back to learner
- [ ] Add feedback mechanism (`helpful=True/False`)

**File:** `Nola/services/agent_service.py`

### Background Loops
- [ ] FocusMaintenanceLoop (runs every 30 min)
- [ ] Decay old weights (weight *= 0.95)
- [ ] Normalize weights per table
- [ ] Prune sequences with weight < 0.1

**File:** `Nola/subconscious/loops.py`

---

## 📊 Week 4: Validation (Jan 23-29)

### Evaluation Metrics
- [ ] Precision: % of returned keys used
- [ ] Recall: Did we miss critical keys?
- [ ] Latency: Query time with/without focus
- [ ] Learning rate: Weight convergence speed

**Files:** `eval/focus_quality.py`, `eval/focus_comparison.py`

### Profile Integration
- [ ] Update `.github/agents/*.agent.md` with focus sections
- [ ] Add "Focus Areas" to agent profiles
- [ ] Handoff passes focus state
- [ ] Test with multiple agent workflows

### VS Code Bridge
- [ ] Export focus state to `.vscode/agents/*.json`
- [ ] Import feedback from VS Code usage
- [ ] Bidirectional learning loop

**Files:** `Nola/workspace/export_focus.py`, `Nola/workspace/import_feedback.py`

---

## 📸 Checkpoint System (Jan 7+)

### Database Changes
- [ ] Add `log_checkpoints` module (via existing schema)
- [ ] `create_checkpoint()` - snapshot all thread tables
- [ ] `get_checkpoints()` - list available (last 10)
- [ ] `restore_checkpoint()` - revert to state
- [ ] `_prune_checkpoints()` - keep only MAX_CHECKPOINTS

**File:** `Nola/threads/schema.py`

### Log Thread Integration
- [ ] Add checkpoint methods to `LogThreadAdapter`
- [ ] Log `checkpoint:created` and `checkpoint:restored` events
- [ ] Auto-checkpoint before consolidation (if > 1 hour since last)

**File:** `Nola/threads/log/adapter.py`

### API Endpoints
- [ ] GET `/api/introspection/checkpoints` - list checkpoints
- [ ] POST `/api/introspection/checkpoints` - create new
- [ ] POST `/api/introspection/checkpoints/{key}/restore` - restore

**File:** `Nola/react-chat-app/backend/api/introspection.py`

### Frontend UI
- [ ] "Checkpoints" section in RightSidebar
- [ ] List last 5 checkpoints with timestamps
- [ ] "New Checkpoint" button
- [ ] "⏪ Restore" button per checkpoint

**Files:** `RightSidebar.tsx`, `introspectionService.ts`, `RightSidebar.css`

---

## 🗂️ Thread Browser UI (Jan 8+) — ✅ COMPLETE

### Implementation

Live in `Nola/react-chat-app/frontend/src/pages/ThreadsPage.tsx`:

- [x] Thread tabs (identity, log, philosophy, reflex, form, linking_core)
- [x] Thread health display with status indicators
- [x] Identity flat table with L1/L2/L3 columns
- [x] Philosophy flat table (same schema as identity)
- [x] Edit/Delete actions on rows
- [x] Add Row form for identity and philosophy
- [x] Level selector (L1/L2/L3)
- [x] Log event viewer with filters and sorting
- [x] Add Event form for log thread

### Architecture Reference
Original mockup (implemented as ThreadsPage):

```
┌─────────────────────────────────────┐
│ 🧵 Thread Browser                    │
├─────────────────────────────────────┤
│ [identity] [log] [form] [phil] [ref]│  ← Thread tabs
├─────────────────────────────────────┤
│ identity                             │
│ ├── user_profile (5 items)          │  ← Module list
│ ├── machine_context (2 items)       │
│ └── nola_self (4 items)             │
├─────────────────────────────────────┤
│ 📋 user_profile                      │
│ ┌─────────────────────────────────┐ │
│ │ user_name          L1  w:0.95   │ │  ← Key/value rows
│ │ "Jordan Rivera"                 │ │
│ ├─────────────────────────────────┤ │
│ │ projects           L2  w:0.80   │ │
│ │ ["Nola AI", "AI_OS"]           │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

### Components (Implemented in ThreadsPage.tsx)
- [x] Thread tabs with icons and health indicators
- [x] Flat table renderer (shared for identity/philosophy)
- [x] Log event table with sorting/filtering
- [x] Add row/event forms
- [x] Edit modal for rows

**File:** `Nola/react-chat-app/frontend/src/pages/ThreadsPage.tsx`

### API Endpoints ✅ COMPLETE
- [x] GET `/api/introspection/threads/summary` - all threads overview
- [x] GET `/api/introspection/threads/{thread}` - thread data
- [x] GET `/api/introspection/threads/{thread}/{module}` - module data
- [x] GET `/api/introspection/identity/table` - identity flat table
- [x] PUT `/api/introspection/identity/{key}` - update identity row
- [x] POST `/api/introspection/identity` - add identity row
- [x] DELETE `/api/introspection/identity/{key}` - delete identity row
- [x] GET `/api/introspection/philosophy/table` - philosophy flat table
- [x] PUT `/api/introspection/philosophy/{key}` - update philosophy row
- [x] POST `/api/introspection/philosophy` - add philosophy row
- [x] DELETE `/api/introspection/philosophy/{key}` - delete philosophy row
- [x] GET `/api/introspection/events` - log events with filters

### State Management ✅
- [x] `activeThread` - current thread tab
- [x] `identityRows` / `philosophyRows` - flat table data
- [x] `logEvents` - log thread data with filters
- [x] `activeLevel` - L1/L2/L3 selector
- [x] `editingKey` / `editForm` - inline editing state
- [x] Add row form state (key, type, desc, L1/L2/L3, weight)

**File:** `pages/ThreadsPage.tsx`

### Features
- [x] Click thread tab → show its data
- [x] Show L1/L2/L3 columns for identity/philosophy
- [x] Show weight column
- [x] Edit/Delete actions
- [x] Add Row form
- [x] Log event filtering by type/source
- [x] Log event sorting (timestamp, type, source)
- [x] Add Event form for log thread

### Future Enhancements (Nice to Have)
- [ ] Search/filter within identity/philosophy
- [ ] Promote/Demote weight actions
- [ ] Bulk edit/delete

### Layout
- [x] ThreadsPage as dedicated route (`/threads`)
- [x] Accessible from sidebar navigation

---

## 📡 Stimuli System (Jan 10) — ✅ COMPLETE

### Core Architecture
- [x] `Nola/Stimuli/router.py` — Universal API adapter
- [x] `NormalizedMessage` dataclass — Any source → same format
- [x] `ResponseTemplate` dataclass — Deterministic fields + LLM slots
- [x] `SourceConfig` dataclass — Parsed YAML configs
- [x] JSONPath extraction for response mapping
- [x] Template rendering with `{{slot}}` placeholders

### YAML Source Configs (20+)
- [x] **Communication:** Gmail, Slack, SMS (Twilio), Discord, Telegram, Twitter/X, WhatsApp, Teams
- [x] **Project Management:** GitHub, Linear, Jira, Todoist
- [x] **Databases:** Notion, Airtable
- [x] **Productivity:** Google Calendar
- [x] **Support:** Zendesk, Intercom
- [x] **Commerce:** Shopify, HubSpot
- [x] **Generic:** Webhook, Template

**File:** `Nola/Stimuli/sources/*.yaml`

### Frontend Dashboard
- [x] Source list with enable/disable toggles
- [x] Source detail view with config sections
- [x] **Editable** Auth/Pull/Push configs (JSON editor)
- [x] Add source modal with template cards
- [x] Test connection button
- [x] Delete source confirmation

**File:** `Nola/react-chat-app/frontend/src/pages/StimuliPage.tsx`

### Backend API
- [x] GET `/api/stimuli/sources` — List all sources
- [x] GET `/api/stimuli/sources/{name}` — Source details
- [x] PUT `/api/stimuli/sources/{name}` — Update source config
- [x] POST `/api/stimuli/sources` — Add new source
- [x] DELETE `/api/stimuli/sources/{name}` — Remove source
- [x] POST `/api/stimuli/sources/{name}/toggle` — Enable/disable
- [x] POST `/api/stimuli/sources/{name}/test` — Test connection
- [x] GET `/api/stimuli/templates` — List source templates

**File:** `Nola/react-chat-app/backend/api/stimuli.py`

### Key Innovation: Slot-Based Architecture
```
DETERMINISTIC (code handles):     PROBABILISTIC (LLM handles):
- Authentication                  - subject: "___"
- Routing (to/from)               - body: "___"  
- Thread IDs                      
- Timestamps                      
- Draft vs send (ALWAYS draft)    
```

LLM cannot make routing errors. Only prose errors.

---

## 💬 Chat Enhancements (Jan 9-10) — ✅ COMPLETE

### Markdown Rendering
- [x] `react-markdown` + `remark-gfm` for assistant messages
- [x] Code blocks with dark theme
- [x] Tables, lists, headers, bold/italic
- [x] Links, blockquotes

**File:** `Nola/react-chat-app/frontend/src/components/Chat/MessageList.tsx`

### Conversation Sidebar
- [x] List all conversations with auto-generated names
- [x] Click to load conversation history
- [x] Rename conversations inline
- [x] Delete with confirmation
- [x] "New Chat" button
- [x] Auto-naming via LLM after first message

**Files:** `ConversationSidebar.tsx`, `api/conversations.py`

### System Prompt Viewer (Right Sidebar)
- [x] Display current consciousness context
- [x] Toggle between "Context Only" and "Full Prompt"
- [x] L1/L2/L3 level selector
- [x] Auto-refreshes every 5 seconds
- [x] Collapsible sidebar

**File:** `Nola/react-chat-app/frontend/src/components/Chat/SystemPromptSidebar.tsx`

### Feedback System
- [x] 👍/👎 buttons on assistant messages
- [x] Thumbs up → saves to `finetune/user_approved.jsonl`
- [x] Thumbs down → opens feedback form with reason
- [x] Feedback saved to `finetune/negative_feedback.jsonl`

**Files:** `MessageList.tsx`, `api/ratings.py`

---

## 🧠 LLM Fact Extraction (Jan 10) — ✅ COMPLETE

### New Approach (Replaces Regex Parsing)
- [x] LLM generates key directly (no regex)
- [x] LLM generates L3 (full detail)
- [x] LLM summarizes to L2 (half length)
- [x] LLM summarizes to L1 (half again)
- [x] LLM classifies thread (identity vs philosophy)
- [x] LLM classifies type (user, nola, value, etc.)

**File:** `Nola/services/fact_extractor.py`

### Model Choice
- Default: `llama3.2:3b` — 2GB, fast, reliable
- Configurable via `NOLA_EXTRACT_MODEL` env var

---

## 📊 Training Data Pipeline (Jan 9-10) — ✅ COMPLETE

### Auto-Generated Training Data
- [x] `Nola/training/logger.py` — Core logging module
- [x] Log identity decisions (confident retrievals)
- [x] Log linking activations (spread activation)
- [x] Log conversation examples
- [x] Confidence thresholding
- [x] Thread-safe writes

### Output Files
- [x] `finetune/auto_generated/identity_retrieval.jsonl`
- [x] `finetune/auto_generated/identity_boundary.jsonl`
- [x] `finetune/auto_generated/linking_activation.jsonl`
- [x] `finetune/auto_generated/conversations.jsonl`
- [x] `finetune/user_approved.jsonl` — Thumbs-up responses
- [x] `finetune/negative_feedback.jsonl` — Thumbs-down with reasons

---

## 🎪 Success Criteria

- [ ] **30% faster** context assembly
- [ ] **7 keys average** returned (vs 50+ before)
- [ ] **<15ms latency** at 10K memories
- [ ] **<10% redundant** memory saves
- [ ] **Weights converge** after 100 queries
- [ ] **VS Code integration** works
- [ ] **Checkpoints** - can restore to any of last 10 states
- [x] **Thread Browser** - can view/edit identity/philosophy/log threads

---

## 🚨 Quick Commands

### Run Migration
```bash
cd Nola/idv2
python migrations/001_add_weights.py
```

### Test Sequence Learner
```bash
pytest tests/test_focus.py -v
```

### Export Focus State
```bash
python -m Nola.workspace.export_focus --output comparison/workspace/.vscode/agents/
```

### Check Focus Health
```bash
python -m Nola.subconscious.focus.health_check
```

---

## 📝 Notes

- **No vocab expansion:** Just better focus on existing keys
- **Learning loop:** Query → Focus → Generate → Record → Update
- **Control vs Data:** DB decides what, LLM decides how
- **Parallel evolution:** AI_OS + VS Code workspace agents = same pattern

---

## 🔗 References

- Full Plan: [`docs/FOCUS_IMPLEMENTATION.md`](docs/FOCUS_IMPLEMENTATION.md)
- Architecture Notes: [`notes.txt`](notes.txt) - Focus System Discovery section
- Changelog: [`CHANGELOG.md`](CHANGELOG.md) - 2026-01-02 entry
- Comparison: [`comparison/workspace/`](comparison/workspace/) - VS Code agent orchestrator
