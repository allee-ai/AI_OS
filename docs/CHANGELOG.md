
# Changelog

All notable changes to this repository are documented below. Entries are grouped by date and describe features added, architecture changes, and notable fixes.

---

## 2026-02-01 — Feeds Architecture & Daemon Setup

### Infrastructure: Production-Ready Daemon
- **LaunchAgent**: `com.aios.server.plist` for auto-start on login, auto-restart on crash
- **Install Script**: `install_daemon.sh` with status, logs, restart commands
- **HTTP Logging**: Middleware logs all requests to `log_server` table with timing, client info
- **Server Monitoring**: `/api/log/server/stats` endpoint for error rates, avg duration, top paths

### Feeds: YAML → Python Module Migration  
- **Architecture**: Converted all feed configs from YAML to Python modules with adapters
- **Email Module**: Multi-provider support (Gmail, Outlook, Proton) with unified OAuth flow
- **GitHub Module**: 6 event types (issues, PRs, mentions, pushes) with OAuth integration  
- **Discord Module**: Converted from YAML, added OAuth and bot adapter
- **Viewers**: Native React components (EmailViewer with provider tabs, GithubViewer, DiscordViewer)
- **API**: Updated OAuth endpoints with provider parameter support
- **Events**: Centralized event emission system connecting to Reflex triggers

### Reflex: Executor Foundation
- **ReflexExecutor**: Core class for trigger → tool execution pipeline
- **Feed Integration**: Triggers now respond to Feed event emissions
- **Tool Registry**: Foundation for executable tools in `tools/executables/`
- **Form Integration**: Connected to Form Thread for standardized tool execution

### Log: Database Logging System
- **New Tables**: `log_system` (daemon logs) and `log_server` (HTTP logs)
- **Helper Functions**: `log_system_event()`, `log_server_request()`, query functions
- **API Endpoints**: `/api/log/daemon`, `/api/log/server`, server statistics
- **Monitoring**: Agent can now query server health and performance metrics

---

## 2026-01-31 — DMG Installer + Cleanup + Attribution

### Installer: Proper DMG Download Flow
- **Created**: `scripts/create_installer_app.sh` — Builds "Install AI OS.app"
- **Updated**: `scripts/create_dmg_installer.sh` — Now creates downloader-based DMG
- **Flow**: User opens DMG → runs installer → clones repo to `~/AI_OS` → creates `/Applications/AIOS.app`
- **Features**: 
  - Checks/installs dependencies (Python, Node, Ollama)
  - Handles existing installations (update prompt)
  - Creates absolute-path launcher in Applications
  - First-run model download with visible progress

### Fix: Model Download Progress
- **Problem**: `start.sh` hid model download with `>/dev/null`, users saw frozen terminal
- **Fix**: Now shows download progress and checks if models exist before pulling
- **File**: `scripts/start.sh`

### Documentation: Honesty Audit
- **README**: Reframed "Architecture Partners" → "Development Partners" (Claude/GPT as pair programming tools, not co-architects)
- **README**: Added "Nothing here is new" disclaimer to Theoretical Foundations
- **README**: Added "The pain point we solve" — all pieces in one integrated package
- **ROADMAP**: Changed "Structure beats scale" claim → "The hypothesis we're testing"
- **VISION.agent.md**: Removed "first local AI with genuine episodic memory" overclaim

### Documentation: Attribution Section
- **Added**: Comprehensive "Built With & Thanks To" section to README
- **Categories**: Runtime & Models, Development Partners, Development Environment, Infrastructure, Community & Research, Theoretical Foundations
- **Credits**: Ollama, Llama, Qwen, Mistral, Phi, nomic-embed, Claude, GPT, Gemini, VS Code, Copilot, Cursor, FastAPI, React, Three.js, SQLite, uv, Hugging Face, r/LocalLLaMA

### Cleanup: Scripts Directory
- **Deleted**: Built artifacts (`AIOS.app`, `Install AI OS.app`, `AIOS-Installer.dmg`, `.aios_installed`)
- **Deleted**: Superseded scripts (`create_desktop_shortcut.sh`, `create_icon.sh`, `setup_spiral_icon.sh`)
- **Deleted**: VM scripts (`connect_vm_aios.sh`, `create_vm_desktop_app.sh`, `install-vm.sh`, `test_install_loop.sh`)
- **Deleted**: Unused utilities (`scripts/utils/` — bench_state.py, import_vscode_conversations.py, populate_from_profile.py, stringify/, test_consolidation.py)
- **Deleted**: `seed_demo.sql` (demo DB is git-tracked)
- **Moved**: `runtests.sh`, `reset_demo.sh` → `tests/`
- **Result**: `scripts/` reduced from 31 to 10 items

### Files Changed
- `scripts/start.sh` — Model download progress fix
- `scripts/create_installer_app.sh` — New
- `scripts/create_dmg_installer.sh` — Rewritten for download flow
- `README.md` — Attribution section, honesty edits, pain point framing
- `docs/ROADMAP.md` — Hypothesis framing
- `.github/agents/VISION.agent.md` — Removed overclaim
- `assets/AIOS-Installer.dmg` — New proper installer

---

## 2026-01-31 — Roadmap Expansion + Docs Agent Profile

### Documentation: Module Roadmap Updates
- **Workspace**: Added file rendering (JSON/PY/DOCX), in-browser editing, auto L1/L2 summarization
- **Chat**: Added import pipeline repair, smart import helper, archiving, directory organization (`imported/claude/`, `imported/gpt/`)
- **Eval**: Added Battle Arena UI spec (three-panel: STATE+prompt | judge settings | cloud opponent config), auto-battle mode
- **Subconscious**: Added Loop Editor Dashboard, implicit COT loops with iteration/token/cutoff settings
- **Linking Core**: Added universal `create_link(row, row)` for cross-entity linking, graph density improvements (smaller nodes, hover info)

### Documentation: Program-Wide Features (New Section)
- **Onboarding wizard** — Guided first-run setup
- **Module helper chat** — Context-aware mini chat that resets per page, loads module docs, uses fast cloud model

### Documentation: GitHub & Community Management (New Section)
- **LLM issue creation** — Natural language to formatted issues
- **Vision agent integration** — Continuous improvement loop via Discussions
- **Multi-model discussions** — Claude/GPT collaboration bridge (AI "skin in the game")

### Agent Profile: docs.agent.md
- **Created**: `.github/agents/docs.agent.md` — Documentation orchestrator profile
- **Purpose**: Multi-doc sync for roadmap, changelog, and module README updates
- **Pipeline**: Source (module READMEs) → Aggregate (ROADMAP.md) → History (CHANGELOG.md)
- **Include markers**: Documents the `<!-- INCLUDE:{module}:ROADMAP -->` system

### Files Changed
- `workspace/README.md` — 3 new roadmap items
- `chat/README.md` — 5 new roadmap items  
- `eval/README.md` — 2 new roadmap items
- `agent/subconscious/README.md` — 2 new roadmap items
- `agent/threads/linking_core/README.md` — 2 new roadmap items
- `docs/ROADMAP.md` — 2 new sections (Program-Wide, GitHub Management)
- `.github/agents/docs.agent.md` — New agent profile

---

## 2026-01-31 — Frontend Restructure + Database Lock Fix + log_event Fix

### Fix: log_event() Signature Mismatch in temp_memory
- **Bug**: `add_fact()` called `log_event()` with incorrect parameters (`fact_id`, `fact_source`, `hier_key` as kwargs)
- **Fix**: Changed to use named parameters matching actual signature, moved extra data into `metadata` dict
- **Files Fixed**: `agent/subconscious/temp_memory/store.py`
- **Test Added**: `tests/test_consolidation.py::TestAddFact` — Regression test ensures correct log_event signature

### Refactor: Frontend Module Reorganization
- **Module-Based Structure**: Reorganized frontend to mirror backend structure
- **New Directory Layout**: `frontend/src/modules/` now contains:
  - `chat/` — Chat components, hooks, services, types (mirrors `chat/`)
  - `threads/` — Thread UIs with sub-modules: `identity/`, `philosophy/`, `reflex/`, `form/`, `linking_core/`, `log/` (mirrors `agent/threads/`)
  - `services/` — Service dashboards (mirrors `agent/services/`)
  - `feeds/` — Feeds page (mirrors `Feeds/`)
  - `workspace/` — Workspace components (mirrors `workspace/`)
  - `docs/` — Documentation viewer (mirrors `docs/`)
  - `finetune/` — Training UI (mirrors `finetune/`)
  - `eval/` — Battle Arena placeholder (mirrors `eval/`)
  - `subconscious/` — Orchestrator UI placeholder (mirrors `agent/subconscious/`)
- **Shared Components**: `frontend/src/shared/` for reusable components (Sidebar, SelectWithAdd, Dashboard, ContactPage)
- **Barrel Exports**: Each module has `index.ts` for clean imports
- **App.tsx Updated**: All imports now use new module paths
- **Internal Imports Fixed**: ChatContainer, ModelSelector, MessageInput, etc. use correct relative paths

### Files Created
- `frontend/RESTRUCTURE_PLAN.md` — Migration plan and file mapping reference
- `frontend/src/modules/*/index.ts` — Module barrel exports
- `frontend/src/modules/services/components/index.ts` — Services components barrel
- `frontend/src/shared/index.ts` — Shared component exports
- `frontend/src/shared/utils/constants.ts` — Shared constants

### Fix: SQLite Database Lock Errors
- **Connection Leak Fix**: Added `contextlib.closing()` to ensure connections close after use
- **Files Fixed**:
  - `agent/threads/identity/schema.py` — `push_profile_fact()` now uses context manager
  - `agent/threads/philosophy/schema.py` — `push_philosophy_profile_fact()` now uses context manager  
  - `agent/subconscious/temp_memory/store.py` — `mark_consolidated()` now uses context manager
- **Foreign Key Fix**: Changed `profile_id="user"` to `profile_id="primary_user"` in `loops.py` to match existing profiles

### Documentation: Module READMEs
- `chat/README.md` — Chat module overview (API, schema, imports)
- `eval/README.md` — Simplified to focus on eval module status
- `Feeds/README.md` — Simplified to focus on feeds module status
- `finetune/README.md` — Simplified to focus on finetune module status

---

## 2026-01-27 — Consolidation Loop with Hybrid Approval

### Feature: Fact Consolidation Pipeline
- **Hybrid Approval**: Facts scored for confidence; high confidence (≥0.7) auto-approves, low confidence requires human review
- **Duplicate Detection**: Embedding-based similarity check rejects duplicates (≥0.85 similarity)
- **Fact Classification**: Routes facts to appropriate thread:
  - **Identity Thread**: Personal facts (name, preferences, location, work, hobbies)
  - **Philosophy Thread**: Beliefs, values, principles, ethics, worldview

### Feature: Temp Memory Status Tracking
- **Status Column**: Facts now track status: `pending`, `approved`, `pending_review`, `consolidated`, `rejected`
- **Confidence Score**: Each fact stores its calculated confidence (0.0-1.0)
- **New Functions**: `get_pending_review()`, `update_fact_status()`, `approve_fact()`, `reject_fact()`, `get_approved_pending()`
- **Enhanced Stats**: `get_stats()` now includes `pending_review` and `approved` counts

### Feature: Smart Key Generation
- **Category Detection**: Auto-detects fact category (identity, preferences, professional, beliefs, values, ethics)
- **Hierarchical Keys**: Generates keys like `user.preferences.python` or `philosophy.values.honesty`
- **Stop Word Filtering**: Removes common words to create meaningful keys

### Tests: 28 New Consolidation Tests
- Fact classification (identity vs philosophy)
- Key generation for both threads
- Confidence scoring behavior
- Status validation and exports

### Files Changed
- `agent/subconscious/loops.py` — Implemented `_consolidate()`, `_score_and_triage_pending()`, `_promote_approved_facts()`, `_classify_fact_destination()`, `_generate_key()`
- `agent/subconscious/temp_memory/store.py` — Added `status`, `confidence_score` columns; new status functions
- `agent/subconscious/temp_memory/__init__.py` — Export new functions
- `tests/test_consolidation.py` — New test file with 28 tests

---

## 2026-01-27 — Linking Core UI + Conversation Context Scoring

### Feature: Linking Core Thread in UI
- **Thread Visibility**: `linking_core` now appears in Threads page with 3D graph visualization
- **Summary Facts**: Introspect returns explanatory facts for agent understanding:
  - `linking_core.function: Scores facts by relevance using spread activation`
  - `linking_core.mechanism: Extracts concepts from query, finds connected concepts in graph`
  - `linking_core.concepts`, `linking_core.links`, `linking_core.activated` at higher levels
- **STATE Block Integration**: Linking core facts included in STATE assembly

### Feature: Conversation Context for Scoring
- **Assess Block**: Chat now passes last 5 turns of conversation (not just last message) to scoring
- **Pronoun Resolution**: "What else does he enjoy?" after discussing dad now keeps family facts activated
- **Topic Continuity**: Relevance scoring sees full conversation context for better fact selection
- **Implementation**: `agent_service.py` builds assess block from `convo_context + user_message`

### Documentation: Thread README Updates
- **Identity README**: Complete rewrite with accurate schema, adapter methods, output format
- **Log README**: Updated adapter methods table, added output format section
- **Philosophy README**: Updated to profile-based schema, added `_filter_by_relevance` docs

### Files Changed
- `agent/subconscious/orchestrator.py` — Added `linking_core` to THREADS list, removed skip in build_state
- `agent/threads/linking_core/adapter.py` — Updated `introspect()` and `get_context()` for summary facts
- `agent/services/agent_service.py` — Pass conversation context as assess block for scoring
- `agent/threads/identity/README.md` — Complete documentation rewrite
- `agent/threads/log/README.md` — Updated with accurate methods
- `agent/threads/philosophy/README.md` — Updated with profile-based schema

---

## 2026-01-26 — STATE + ASSESS Architecture & Embedding-Based Scoring

### Architecture: STATE + ASSESS Model
- **Core Equation**: `state_t+1 = f(state_t, assess)` — one architecture, different assess sources
- **Three-Step Flow**: `score(query) → build_state(scores, query) → agent.generate(state, query)`
- **Unified Pattern**: Same STATE building for conversation, file processing, memory loops, self-reflection
- **Clean Separation**: Subconscious builds STATE, agent.generate() IS the assess step (LLM evaluates query against state)

### Feature: Separated Scoring & State Building
- **`score(query)`**: Returns thread relevance scores `{identity: 9.0, log: 5.0, ...}`
- **`build_state(scores, query)`**: Builds STATE block from scores with dot notation
- **`get_state(query)`**: Convenience method combining both
- **Score Thresholds**: 0-3.5 = L1 (lean), 3.5-7 = L2 (medium), 7-10 = L3 (full)

### Feature: Chat Summary for Query Building
- **New Column**: `summary` column added to `convos` table
- **`update_summary(session_id, summary)`**: Store conversation summary at session close
- **`build_query(session_id, recent_turns=3)`**: Builds query string from summary + recent turns
- **Query Flow**: `chat.build_query() → subconscious.score() → subconscious.build_state() → agent.generate()`

### Feature: Embedding-Based Thread Scoring
- **Thread Summaries**: ConsolidationLoop generates summaries from each thread's introspection
- **Pre-computed Embeddings**: Summaries embedded via nomic-embed-text during consolidation
- **Hybrid Scoring**: 70% embedding similarity + 30% keyword matching for thread relevance
- **On Wake/Sleep**: Summaries updated during consolidation, cached for fast scoring

### Architecture: ConsolidationLoop Implementation
- **`_update_thread_summaries()`**: Generates thread summaries and caches embeddings (~850ms)
- **`_consolidate()`**: Runs summary updates + stub for temp_memory promotion
- **Scoring Infrastructure**: `set_thread_summary()`, `get_thread_summary()`, `score_threads_by_embedding()`

### Performance: State Building Latency
- **`score()`**: ~0ms (dict lookups)
- **`build_state()`**: ~13ms (DB reads + string formatting)
- **Full pipeline**: ~12ms for ~3.8KB of state
- **Embedding scoring**: ~15ms per query after summaries cached

### Files Changed
- `agent/subconscious/orchestrator.py` — Added `score()`, refactored `build_state()`, added `get_state()`
- `agent/subconscious/loops.py` — Implemented ConsolidationLoop with thread summary generation
- `agent/threads/linking_core/scoring.py` — Added thread summary storage and embedding-based scoring
- `agent/threads/linking_core/adapter.py` — Updated `score_threads()` to use embedding scoring
- `chat/schema.py` — Added `summary` column, `update_summary()`, `get_summary()`, `build_query()`
- `agent/threads/*/adapter.py` — All adapters support threshold param and dot notation output

### Scripts Added
- `scripts/utils/bench_state.py` — Benchmark state building latency
- `scripts/utils/test_consolidation.py` — Test thread summary generation and embedding scoring

---

## 2026-01-23 — Architecture Hardening + Doc Consolidation

### Documentation: Consolidation (9 files → 4 active)
- **Created**: `docs/RESEARCH_PAPER.md` - Single canonical research paper merging best of `write_up.md` and `AI_OS_RESEARCH_PAPER.md`
- **Archived**: 5 redundant vision docs moved to `_archive/docs_old/`:
  - `AI_OS_RESEARCH_PAPER.md` (superseded by new RESEARCH_PAPER.md)
  - `CONCEPT_ATTENTION.md` (merged into paper)
  - `CORE_CONTRIBUTIONS.md` (merged into paper)
  - `LIVING_BODY.md` (merged into paper)
  - `NEUROSCIENCE_VALIDATION.md` (preserved in archive for reference)
- **Updated**: `Agent/ARCHITECTURE.md` - Current implementation with protected profiles, fault isolation
- **Kept Active**: `docs/vision/AUTHOR_NOTE.md` - Human voice, stays separate

### Architecture: Agent Singleton Pattern
- **Minimal agent.py**: Stripped from ~400 lines to ~150 lines - now just LLM interface
- **State Delegation**: All state management delegated to subconscious → threads → state.db
- **Module Singleton**: `get_agent()` returns same instance everywhere - one identity, one history
- **Clean Separation**: "Subconscious builds state, agent just reads and talks"

### Architecture: Fault-Isolated Threads
- **Independent Thread Loading**: Each thread adapter loads in its own try/catch - one failure doesn't crash others
- **Resilient Health Checks**: `get_all_health()` catches errors per-thread, returns partial results
- **Bulletproof API**: `/api/subconscious/threads` endpoint always returns valid response even if subconscious fails
- **Graceful Degradation**: Broken threads show "error" status in UI, others continue working

### Feature: Protected Core Profiles
- **Core Profiles in Schema**: `self.agent` and `user.primary` created on DB init (no seed files)
- **Protected Flag**: `protected` column on `profiles` and `profile_facts` tables
- **Deletion Protection**: Cannot delete protected profiles or fact keys from UI (backend enforced)
- **Empty by Default**: Core structure exists but values are blank - user fills them in
- **Quick Accessors**: New functions `get_agent_name()`, `get_user_name()`, `get_core_identity()`

### Removed: Seed Data Anti-Pattern
- **Deleted**: `agent/threads/seed_data.py` - no more seeding scripts
- **Schema-Driven**: Core profiles and fact keys defined in `init_profiles()` and `init_profile_facts()`
- **Values vs Structure**: Structure is permanent, values are user-controlled

### API: Identity Quick Access
```python
from agent.threads.identity import get_agent_name, get_user_name, get_core_identity

# Direct DB read - perfect for reflexes
name = get_agent_name()  # Returns L1 value or "Agent"
user = get_user_name()   # Returns L1 value or "User"
core = get_core_identity()  # {'agent_name': '...', 'agent_role': '...', 'user_name': '...'}
```

### Documentation: Stale Reference Audit
- **Completed**: All active docs now reference generic patterns, not "Agent" hardcoding
- **Pattern**: `{identity.name}` instead of "Agent", `state.db` instead of `*.json`, `Agent/` for module path
- **Archive**: Original verbose docs preserved in `_archive/` for reference

---

## 2026-01-20 (Evening) — Thread Architecture: Self-Contained APIs & Frontend Migration

### Architecture: Per-Thread API Consolidation
- **Self-Contained Threads**: Each thread now owns its own `/api/{thread}/` router with introspect, health, and table endpoints
- **Subconscious Aggregator**: `/api/subconscious/` endpoints aggregate all thread introspections at runtime
- **Deprecated Legacy**: `introspection.py` scheduled for deletion — all threads now use new per-thread APIs

### API Fixes
- **`/api/subconscious/threads`**: Fixed response format — returns object with `status` (was `health`), `message`, `has_data` fields
- **`/api/linking_core/`**: Changed router prefix from `/api/linking/` to match thread name
- **`/api/linking_core/graph`**: Fixed `get_graph_data()` to return `links` array (was `edges`) with `concept_a/concept_b/strength/fire_count` format and `stats` object
- **`/api/form/table`**: Added new endpoint returning 21 tools with column metadata

### Frontend Fixes
- **ConceptGraph3D.tsx**: Updated all fetch URLs to use `/api/linking_core/` prefix — graph now loads with 100 links, 50 nodes
- **ThreadsPage.tsx**: Added `form`, `reflex`, `linking_core` to skip generic introspect fetch (they have custom dashboards)
- **ThreadsPage.tsx**: Fixed "No data" condition — added `form` and `reflex` to exclusion list so ToolDashboard renders
- **ToolDashboard.css**: Added `min-height: 500px` to ensure visibility

### Thread Status (All 6 Working)
- 🌀 **Identity**: ProfilesPage with L1/L2/L3 facts
- 🌀 **Philosophy**: ProfilesPage (mode="philosophy")  
- 🌀 **Log**: Custom log viewer with filtering
- 🌀 **Form**: ToolDashboard with 21 tools, 6 categories
- 🌀 **Reflex**: ReflexDashboard
- 🌀 **Linking Core**: ConceptGraph3D with spread activation

---

## 2026-01-20 — Legacy Cleanup, Security Audit, Conversation DB Migration

### Refactoring: Remove IDv2 Legacy System
- **Deleted Module References**: Removed all `idv2` references from codebase (already deleted in Phase 7, now cleaned docs)
- **Updated Documentation**: Fixed `agent/threads/linking_core/README.md` and `agent/threads/REBUILD_CHECKLIST.md` to reference new `schema.py` instead of deleted `idv2.py`
- **Code Archaeology**: Confirmed no functional code imports or uses `idv2` — only historical comments remain

### Architecture: Centralized Database Path Logic
- **Single Source of Truth**: Refactored `agent/threads/schema.py` to expose `get_db_path()` as public function
- **Dynamic Mode Switching**: `get_db_path()` reads `AIOS_MODE` env var or `.aios_mode` file at runtime to select `state.db` vs `state_demo.db`
- **Agent Integration**: Updated `agent/agent.py` to import `get_db_path()` instead of hardcoding `DEFAULT_STATE_DB`
- **Eliminated Scatter**: No more hardcoded DB paths — all modules now reference central function

### Security: Pre-Public Audit
- **API Keys**: Cleared Kernel API key from `.env` file
- **Personal Identifiers**: Replaced "allee Roden" with "Allee" in all tracked files
- **VM IP Addresses**: Replaced hardcoded 159.203.95.51 with `YOUR_VM_IP` placeholder in docs
- **Local Paths**: Converted `/Users/allee/Desktop` to relative paths throughout codebase

### Architecture: Conversation Storage Migration (JSON → SQLite)
- **New Module**: Created `agent/react-chat-app/backend/api/chatschema.py` with:
  - `convos` table: session_id, name, channel, weight (0.0-1.0), indexed flag, timestamps
  - `convo_turns` table: FK to convos, user/assistant messages, feed_type, context_level
  - Full CRUD: `save_conversation()`, `add_turn()`, `get_conversation()`, `list_conversations()`
  - Weight system: `increment_conversation_weight()` for linking_core integration prep
  - Auto-index tracking: `get_unindexed_high_weight_convos()` for future semantic indexing
- **Refactored**: `agent/react-chat-app/backend/api/conversations.py` now uses chatschema instead of JSON files
- **Refactored**: `agent/services/agent_service.py` uses `add_turn()` instead of writing to `Feeds/conversations/*.json`
- **Backward Compatible**: API endpoints unchanged — frontend works without modification

### Testing
- **Test Suite Validation**: All 17 tests pass after refactoring (Agent singleton, thread safety, identity, HEA context levels)
- **No Regressions**: Agent initialization, state loading, and DB connection work correctly with new path system

### GitHub Issues
- Created 3 new issues for UI/UX improvements:
  - **#10**: Cannot add facts from Thread Browser UI (bug, frontend)
  - **#11**: UI cleanup - weight sliders positioned weirdly, color mismatches (frontend)
  - **#12**: Philosophy thread has no demo data (backend)

---

## 2026-01-19 (Late Night) — Database Toggle & Profile Seeding

### Feature: Database Mode Toggle
- **Runtime Database Switching**: Frontend toggle to switch between `state.db` (personal) and `state_demo.db` (demo) without restart
- **Visual Indicator**: Shows current database mode in top-right corner
- **Seamless Transition**: All profile/identity/philosophy data switches instantly

### Feature: Profile Data Population
- **Allee.json Import**: Script to seed personal database from structured JSON profile
- **Identity Extraction**: Cognitive profile, superpowers, working principles imported as L1/L2/L3 facts
- **Philosophy Mapping**: Mission, ethics, design principles converted to philosophy profiles
- **Relationship Data**: Partner, children, family bonds as identity facts

### Documentation
- **VM_DEPLOYMENT.md**: Complete step-by-step guide for cloud deployment
- **Deployment Workflow**: Streamlined to single-click deploy + connect

---

## 2026-01-19 (Night) — Production VM Deployment & 24/7 Cloud Infrastructure

### Infrastructure: Always-On VM Deployment  
- **DigitalOcean VM**: Ubuntu 22.04, 8GB RAM, 4 vCPU, 160GB SSD ($40/month) at 159.203.95.51
- **Production Architecture**: Full frontend + backend deployment on VM serving static files
- **Systemd Service**: Auto-restart configuration ensuring 24/7 uptime with production environment
- **Ollama Models**: qwen2:1.5b (934MB) for fast local responses + llama2:7b backup
- **VM Installer**: `install-vm.sh` script for Linux deployment (removes Mac-specific dependencies)

### Desktop Integration
- **SSH Tunnel Connection**: `connect_vm_aios.sh` script for seamless local access via port forwarding
- **Desktop Shortcuts**: `Connect to Agent VM.command` for one-click VM access + browser launch
- **App Bundle**: `AI OS VM.app` macOS application for desktop integration

### Technical Implementation
- **Static File Serving**: Modified FastAPI backend to serve React frontend from `../frontend/dist/`
- **Frontend Build**: npm build process on VM with Node.js v18 compatibility  
- **Database Migration**: Production mode using `state.db` instead of demo database
- **Network Architecture**: Local port 8000 → SSH tunnel → VM port 8000 → Agent interface

### Cloud-First Architecture Benefits
- 🌀 **True 24/7 Operation**: No local machine dependency
- 🌀 **Universal Access**: SSH tunnel from any device with SSH key
- 🌀 **Consolidated Service**: Single VM runs all Agent components
- 🌀 **Auto-Recovery**: Systemd ensures service restoration after VM restarts
- 🌀 **Scalable Foundation**: Ready for multi-tenant AI-OS-as-a-Service expansion

---

## 2026-01-19 (Evening) — Linking Core 3D Visualization & Concept Graph Engine

### Feature: 3D Concept Graph Visualization
- **ConceptGraph3D.tsx**: Full 3D visualization of the agent's concept graph using Three.js + React Three Fiber
- **Purple Nebula Containment**: Swirling particle shell (4000 outer + 1200 inner particles) representing the cognitive boundary
- **Circular Particle Sprites**: Replaced square pixels with soft radial gradient dots
- **Density-Aware Gas Layer**: 2000 gas particles cluster near high-connection nodes, visualizing information density in real-time
- **Identity-Anchored Origin**: `name.agent` or identity node positioned at (0,0,0) — all other concepts positioned relative to self
- **Graph-Distance Positioning**: BFS calculates conceptual distance from identity; closer = nearer to center
- **Temporal Coloring**: Node color reflects age (oldest = deep purple, newest = silver/white) from `last_fired` timestamps
- **Resonance Point Detection**: Algorithm finds curve intersections in 3D space — emergent structure where unrelated concept-arcs cross

### Backend: Concept Graph Auto-Population
- **`index_key_in_concept_graph(key, value)`**: New function indexes every key:value write into concept graph
  - Links parent↔child along dot-notation hierarchy (`form.communication` ↔ `gmail`)
  - Extracts concepts from values and cross-links them
  - Links sibling concepts from same value together
- **`find_concepts_by_substring(terms)`**: Fuzzy search for concepts containing search terms (enables "gmail" to find "form.communication.gmail")
- **Auto-indexing in `push_identity_row()` and `push_philosophy_row()`**: Graph automatically builds as data is written
- **`reindex_all_to_concept_graph()`**: Batch reindex all existing data into graph

### API: New Introspection Endpoints
- `GET /api/introspection/concept-links` — Returns nodes, links, and stats for visualization
- `GET /api/introspection/spread-activate?q=` — Spread activation with fuzzy matching
- `POST /api/introspection/concept-links/reindex` — Trigger full reindex from profiles

### Architecture: Semantic Position = Meaning
- Position in 3D space IS the semantics — not projected from embeddings
- `form.communication.gmail` is positioned near `form.communication` because that's what it IS
- The topology is interpretable: you can look at any node and know WHY it's there
- Online Hebbian learning on human-readable concept hierarchies with visible topology

### Discovery: Temporal-Identity Convergence
- **Emergent property**: As graph grows, temporal origin and self converge
- Decay removes non-identity-relevant links → what survives at temporal origin = identity core
- System becomes more coherent over time through natural dynamics (not explicit optimization)
- Persistence = identity-relevance; age + centrality = core self

---

## 2026-01-19 (Morning) — Readiness: Installers, Demo Mode & Stability

### Installer & Infrastructure Overhaul
- **Portable App Bundle**: Rebuilt `AI OS.app` to use relative paths. The entire OS folder can now be moved anywhere, and the app will auto-locate `run.command`.
- **Fast Dependency Management**: Integrated `uv` for 10-100x faster package installation, with robust fallbacks to standard `pip` and `venv`.
- **Cross-Platform Launchers**: Unification of `start.sh` and `install.sh` to handle macOS (bundle), Linux (script), and environment checks automatically.

### Feature: Demo vs Personal Mode
- **Database Separation**: Implemented strictly isolated database paths (`state.db` for Personal, `state_demo.db` for Demo).
- **Mode Selection UI**: Added native dialog prompts at startup to choose between "Demo Mode" (safe for showing off) and "Personal Mode" (private data).

### Stability & Performance
- **Concurrency Safety**: Implemented global `RLock` system (`agent/core/locks.py`) to prevent SQLite "database is locked" errors during background subconscious ops.
- **Frontend Fixes**: Corrected API endpoint mismatches (`/agent-status`) and fixed missing dependency crashing the React app.
- **Disk Optimization**: Cleaned up massive redundant model caches (~50GB) and added checks for embedding model availability (`nomic-embed-text`) during startup.

## 2026-01-13 — L3→L2→L1 Compression Pipeline & Consolidation Modernization

### Consolidation Daemon Modernization
- **L3→L2→L1 Compression Pipeline**: Facts now compressed based on relevance scores:
  - High score (≥0.8): Keep L1+L2+L3, weight=0.9 (full context preserved)
  - Medium score (0.5-0.8): Keep L1+L2 only, weight=0.6 (drop verbose L3)
  - Low score (0.3-0.5): Keep L1 only, weight=0.3 (minimal footprint)
  - Very low (<0.3): Discard entirely (not worth keeping)
- **Linking Core Integration**: Replaced old `MemoryService.score_fact()` with modern `linking_core.score_relevance()`:
  - Multi-dimensional scoring (identity/log/form/philosophy/reflex/cooccurrence)
  - 4-method weighting: embeddings (50%), co-occurrence (30%), spread activation (20%), keywords (10%)
  - Score range normalized to 0.0-1.0 for consistent threshold comparison
- **Concept Link Updates**: Consolidation now extracts concepts and updates graph:
  - `extract_concepts_from_text()`: Maps session summary to concept keys
  - `record_concept_cooccurrence()`: Strengthens Hebbian links between co-occurring concepts
  - Enables spread activation to work across consolidated memories
- **Dimensional Score Tracking**: Consolidation writes per-dimension scores to `fact_relevance` table:
  - `identity_score`, `log_score`, `form_score`, `philosophy_score`, `reflex_score`, `cooccurrence_score`, `final_score`
  - Enables future analysis of which dimensions contribute most to memory retention
- **Batch Scoring**: All facts scored together with session summary for context:
  - More accurate relevance assessment using full session context
  - Efficient single-pass scoring of entire temp_memory batch
- **Updated Stats Output**: Result dict now tracks compression tiers:
  - `high_score`: Facts with L1+L2+L3 (comprehensive)
  - `medium_score`: Facts with L1+L2 (standard)
  - `low_score`: Facts with L1 only (minimal)
  - `discarded`: Facts below threshold
  - `concept_links_updated`: Number of concept pairs strengthened

### Architecture: Fact Lifecycle Design
1. **Creation**: New facts enter temp_memory at full detail (L3)
2. **Consolidation**: After N turns or session end, score all pending facts
3. **Compression**: Based on score, keep L1+L2+L3 / L1+L2 / L1 / discard
4. **Graph Update**: Extract concepts and strengthen `concept_links` for spread activation
5. **Dimensional Tracking**: Write scores to `fact_relevance` for learning
6. **Subconscious Loops** (planned):
   - Decay: Daily/weekly temporal decay of concept link strengths
   - Reinforcement: Per-access Hebbian strengthening of retrieved facts
   - Deduplication: Check for similar facts on creation

### Hierarchical Context System (L1/L2/L3) & Sparse Activation

### Linking Core as Central Scoring Engine
- **score_threads(feeds)**: Thread-level relevance (0-10 scale)
  - Keyword-based scoring for each thread
  - Returns scores pushed to threads for context retrieval
  - Can be called anytime by reflex or subconscious
- **score_relevance(feeds, facts)**: Comprehensive fact-level scoring
  - **Embedding similarity** (50% weight): Semantic matching via Ollama
  - **Co-occurrence scoring** (30% weight): Concepts appearing together in `key_cooccurrence` table
  - **Spread activation** (20% weight): Concept graph traversal via `concept_links` table
  - **Keyword matching** (10% weight / 100% fallback): Token overlap
  - Used by consolidation, context assembly, and memory retrieval
- **Infrastructure in schema.py**:
  - `key_cooccurrence` table: Tracks which concept keys appear together
  - `concept_links` table: Hebbian learning graph for spread activation
  - `extract_concepts_from_text()`: Maps input tokens to known concept keys
  - `spread_activate()`: Graph traversal with activation threshold and decay
  - `generate_hierarchical_key()`: Converts facts to dot-notation keys (e.g., "sarah.likes.coffee")
- **Three-Tier Gating**: Thread scores determine context depth:
  - 0-3.5: Tier 1 (metadata only)
  - 3.5-7: Tier 2 (profile metadata)
  - 7-10: Tier 3 (full facts with L1/L2/L3)

### Database Schema Updates
- **Profile Facts L1/L2/L3 Migration**: Replaced single `value` column with `l1_value`, `l2_value`, `l3_value` TEXT columns in `profile_facts` table for hierarchical verbosity levels:
  - L1: Brief (~10 tokens) - Quick/automatic retrieval
  - L2: Standard (~50 tokens) - Working memory/conversation
  - L3: Full (~200 tokens) - Deliberate recall/full context
- **Migration Script**: Created `migrate_profile_facts_to_l123.py` to automatically migrate existing profile facts from single value to three verbosity levels
- **Token Optimization**: Weight-based verbosity selection provides 66% token savings (680 vs 2000 tokens for 10 facts with mixed weights)

### Context Builder Functions
- **get_value_by_weight()**: New helper function in `schema.py` for weight-based verbosity selection:
  - Weight ≥0.7 → L3 (full detail ~200 tokens)
  - Weight 0.4-0.7 → L2 (standard ~50 tokens)
  - Weight <0.4 → L1 (brief ~10 tokens)
- **score_thread_relevance()**: New method in `base.py` for three-tier sparse activation gating:
  - Score 0-3.5 (Tier 1): Metadata only - thread description, row count
  - Score 3.5-7 (Tier 2): Profile metadata - profile list, fact counts, no values
  - Score 7-10 (Tier 3): Full facts with weight-based L1/L2/L3 verbosity selection
- **EVENT_TYPE_RELEVANCE**: Log thread mapping for query-based context filtering:
  - convo: 8 (high priority)
  - memory: 7 (high priority)
  - user_action: 6 (medium-high)
  - file: 4 (medium)
  - system: 2 (low)
  - activation: 1 (low)

### UI Updates
- **ProfilesPage L1/L2/L3 Editor**: Updated Profile Manager with level toggle interface:
  - Three-button toggle (L1/L2/L3) for selecting which verbosity level to edit
  - Add Fact form now shows single level at a time (not all three simultaneously)
  - Facts table displays selected level with visual indicators for missing values
  - Textarea for L3 (longer text), input for L1/L2
- **Level Toggle Component**: New reusable `.level-toggle` CSS component with active state styling
- **Backend API**: Updated `profiles.py` to accept `l1_value`, `l2_value`, `l3_value` in FactCreate model
- **Frontend Types**: Updated Fact interface to include l1_value, l2_value, l3_value fields

### Architecture Documentation
- **Hierarchical Attention Economics (HEA)**: Codified three-tier context fetching strategy:
  - Thread-level gating (L1): Which threads are relevant? (Tier 1/2/3 metadata vs full facts)
  - Profile-level filtering (L2): Which profiles matter? (trust_level, context_priority)
  - Fact-level verbosity (L3): How much detail? (weight-based L1/L2/L3 selection)
- **UI-Data Hierarchy Mapping**: Thread tabs → Profile sidebar → Fact table corresponds to cognitive L1 → L2 → L3 attention layers
- **Token Budget Optimization**: Sparse activation prevents unnecessary data loading, reducing context size by up to 66%

### Philosophy Thread
- **Structure Consistency**: Philosophy thread already uses `philosophy_flat` table with identical L1/L2/L3 structure to `identity_flat`
- **UI Parity**: Existing ThreadsPage implementation provides level toggle and weight editing for philosophy facts
- **Future Enhancement**: Philosophy could adopt profile-based system similar to identity for organizing philosophical stances by category

---

## 2026-01-13 — Profile Manager & Documentation Overhaul

### Profile Manager (New Feature)
- **Architecture**: Replaced monolithic `identity_flat` with extensible profile system.
- **Schema**: Added 4 new tables in `schema.py`:
  - `profile_types`: User-defined types (admin, family, friend) with trust levels.
  - `profiles`: Instances like `admin.allee`, `family.mom`.
  - `fact_types`: Categories (name, birthday, preference) with default weights.
  - `profile_facts`: Key-value facts with **visible, editable weights**.
- **API**: New `/api/profiles` endpoints for CRUD operations.
- **UI**: `/profiles` page with:
  - **Sidebar**: Type dropdown (+ Add New) → Profile list → Add button.
  - **Main view**: Fact table with weight sliders and visual bars.
  - **Modals**: Add profile, inline add fact/type.
- **Migration**: Added `migrate_identity_to_profiles()` for seamless transition.

### Documentation
- **Reorganization**: Restructured `docs/` into distinct categories:
  - `vision/`: Research papers and core theory (`CORE_CONTRIBUTIONS.md`).
  - `guides/`: User manuals and health checks (`FINETUNE_ON_MAC.md`).
  - `specs/`: Technical references and schemas.
  - `archive/`: Deprecated implementation plans.
- **Core Vision**: Created `CORE_CONTRIBUTIONS.md` detailing the 12 novel innovations (Learned Focus, HEA, Living Body, etc.).
- **Annotated Guides**: Added educational annotations to fine-tuning configs.

### Fine-tuning (Apple Silicon / M4 Air)
- **New Module**: Added `finetune/` directory with MLX framework support.
- **Optimization**: Configured `mlx_config.yaml` for 4-bit quantization and LoRA to run on 16GB unified memory.
- **Automation**: Created `train_mac.sh` for one-click environment setup and training.

### UI & Developer Experience
- **Dev Dashboard**: Added `/dev` page with FinetunePanel component.
- **Live Mode Switching**: Updated `start.sh` to allow selecting "Dev Mode", "Personal Mode", or "Demo Mode" from the GUI.
- **Safety**: Added "DEMO MODE" warning banner in Frontend when running with volatile data.
- **Dashboard**: Added 👥 Profiles card in main navigation.
- **Backend API**: Added `/api/finetune/start` to trigger subprocess training jobs securely.

### Clean up
- **Frontend**: Removed unused components `RightSidebar` and `SidePanel`.
- **Tests**: Removed `tests/test_idv2.py` as Identity V2 is deprecated.

---

## 2026-01-10 — Repository Portability & Elaris Removal

### Removed
- **Elaris Directory**: Removed entire `Elaris/` directory (legacy prototype)
  - Contained exposed OpenAI API key (`openai_key.txt`) — **key should be revoked**
  - Agent is the active system; Elaris references remain in docs for historical context

### Added
- **Root `requirements.txt`**: Consolidated Python dependencies for easier setup
- **`start.bat`**: Windows launcher (README referenced it but it didn't exist)
- **`.gitkeep` in `data/db/`**: Preserves directory structure while ignoring DB files

### Changed
- **`.gitignore` Security Hardening**:
  - Added `**/openai_key.txt`, `**/*_key.txt`, `**/*_secret.txt`
  - Added `**/*.pem`, `**/*.key` for credential files
  - Database files now use `data/db/*.db` pattern (keeps directory)
- **`.env.example` Expanded**: Now documents all optional API keys
  - `OPENAI_API_KEY` (for fallback/Elaris)
  - `KERNEL_API_KEY` (browser automation)
  - `LINEAR_API_KEY` (task management)
- **`agent/identity.json`**: Fixed hardcoded `/Users/allee/...` path → relative `./identity_thread/identity.json`
- **`README.md`**: Added Step 2 for copying `.env.example` before first run

### Clone & Run Instructions
```bash
git clone https://github.com/allee-ai/AI_OS.git
cd AI_OS
cp .env.example .env  # Optional: add API keys for extended features
./start.sh            # Mac/Linux
start.bat             # Windows
```

---

## 2026-01-10 — Thread Dashboards & Tool Registry

### Added
- **Form Thread Tool System** (`agent/threads/form/`)
  - **Tool Registry** (`tools.py`): 21 tool definitions across 6 categories
    - Communication: `send_email`, `send_sms`, `post_slack`, `send_discord`
    - Browser: `browse_url`, `search_web`, `take_screenshot`, `fill_form`
    - Memory: `memory_identity`, `memory_log`, `memory_search`, `memory_link`
    - Files: `read_file`, `write_file`, `list_directory`, `execute_script`
    - Automation: `schedule_task`, `run_workflow`, `trigger_webhook`
    - Internal: `introspect`, `ask_llm`, `notify`
  - **Tool Executor** (`executor.py`): Execution framework with `@register_handler` decorator
    - Built-in handlers: `memory_identity`, `memory_log`, `introspect`, `ask_llm`, `notify`
    - `ToolResult` dataclass for standardized outputs
  - **Adapter Integration**: `seed_tools()` populates registry on first introspection
- **Tool Dashboard UI** (`ToolDashboard.tsx`)
  - Embedded in ThreadsPage when Form thread is selected
  - Tool list grouped by category with icons
  - Detail panel: actions, description, weight, handler code
  - Edit mode for modifying tool definitions
  - Add modal for creating new tools
  - Category filtering and status indicators
- **Reflex Dashboard UI** (`ReflexDashboard.tsx`)
  - Embedded in ThreadsPage when Reflex thread is selected
  - Stats bar: total count, by-module breakdown
  - Grouped list: 👋 Greetings, ⚡ Shortcuts, 🔧 System
  - Detail panel: pattern, response, weight visualization
  - **Test Area**: Type any input to see if it triggers a reflex
  - Add modal with module-specific fields
- **Reflex API** (`api/reflex.py`)
  - `GET /api/reflex/all` — List all reflexes across modules
  - `GET /api/reflex/stats` — Stats by module
  - `GET/POST/DELETE /api/reflex/greetings` — Greeting CRUD
  - `GET/POST/DELETE /api/reflex/shortcuts` — Shortcut CRUD
  - `GET/POST/DELETE /api/reflex/system` — System reflex CRUD
  - `POST /api/reflex/test` — Test if text triggers a reflex
- **Form API** (`api/form.py`)
  - `GET /api/form/tools` — List all tools with metadata
  - `GET /api/form/tools/{name}` — Get tool details + handler code
  - `POST /api/form/tools` — Create new tool
  - `PUT /api/form/tools/{name}` — Update tool definition
  - `DELETE /api/form/tools/{name}` — Remove tool
  - `GET /api/form/categories` — List tool categories
  - `POST /api/form/tools/{name}/test` — Test tool execution
- **Schema Enhancement** (`schema.py`): Added `delete_from_module()` function for row deletion

### Changed
- ThreadsPage now renders custom dashboards for Form and Reflex threads
- Removed standalone `/form` route (tools now in Threads → Form)
- Removed Tools link from Dashboard navigation

---

## 2026-01-10 — Feeds System & Universal API Router

### Added
- **Feeds Router Architecture** (`agent/Feeds/router.py`)
  - **Universal API Adapter**: Config-driven integrations via YAML files
  - **Core Data Classes**:
    - `NormalizedMessage`: Converts any platform → standardized format
    - `ResponseTemplate`: Deterministic fields + LLM slots
    - `SourceConfig`: Parses YAML configs with auth, pull, push sections
  - **JSONPath Extraction**: Maps nested API responses to normalized fields
  - **Template Rendering**: `{{slot}}` placeholders filled by LLM
- **20+ YAML Source Configs** (`agent/Feeds/sources/*.yaml`)
  - Communication: Gmail, Slack, SMS (Twilio), Discord, Telegram, Twitter/X, WhatsApp, Microsoft Teams
  - Project Management: GitHub, Linear, Jira, Todoist
  - Databases: Notion, Airtable
  - Productivity: Google Calendar
  - Customer Support: Zendesk, Intercom
  - Commerce: Shopify, HubSpot
  - Generic: Webhook, Template
- **Feeds Frontend Dashboard** (`FeedsPage.tsx`)
  - Source List with enable/disable toggles and status indicators
  - Source Detail View with full config display
  - Editable Config Sections with JSON editor
  - Add Source Modal with template cards
  - Test Connection and Delete Confirmation
- **Feeds Backend API** (`api/feeds.py`)
  - `GET /api/feeds/sources` — List all configured sources
  - `GET/PUT /api/feeds/sources/{name}` — Get/Update source config
  - `POST /api/feeds/sources` — Add new source from template
  - `DELETE /api/feeds/sources/{name}` — Remove source
  - `POST /api/feeds/sources/{name}/toggle` — Enable/disable
  - `POST /api/feeds/sources/{name}/test` — Test connection
  - `GET /api/feeds/templates` — List available templates
- **LLM Fact Extraction** (`agent/services/fact_extractor.py`)
  - Replaces regex parsing with LLM-based extraction
  - LLM generates: key, L3 (full), L2 (summary), L1 (essence)
  - Uses `llama3.2:3b` by default, configurable via `AIOS_EXTRACT_MODEL`

### Changed
- `main.py`: Added feeds router import and `/api/feeds` route prefix
- Phase 3 (Reflex Thread) documented as visual automation builder
- Phase 6 (Beyond Chat) marked as 🌀 FOUNDATION COMPLETE

---

## 2026-01-09 — Training Feedback UI & System Prompt Viewer

### Added
- **Rating System for Training Data Collection**
  - 👍/👎 buttons on assistant messages (appear on hover)
  - Thumbs up saves exchange to `finetune/user_approved.jsonl`
  - Thumbs down opens feedback form, saves to `finetune/negative_feedback.jsonl`
  - `POST /api/ratings/rate` — Submit rating with optional reason
  - `GET /api/ratings/stats` — Get counts of approved/negative feedback
- **System Prompt Viewer Sidebar**
  - Right sidebar showing live system prompt state
  - Toggle between L1/L2/L3 context levels
  - "Context Only" vs "Full Prompt" view modes
  - Auto-refreshes every 5 seconds
  - `GET /api/introspection/system-prompt` — Returns full system prompt
- **Markdown Rendering in Chat**
  - Installed `react-markdown` + `remark-gfm`
  - Assistant messages render proper markdown (code blocks, bold, lists, tables)
  - Styled code blocks with dark theme, inline code with pink accent
- **Conversation Sidebar Improvements**
  - Auto-naming conversations using llama3.2:1b after first turn
  - Retroactively named all existing conversations

### Fixed
- **Duplicate Database**: Removed stale `backend/data/db/state.db`
- **Model Selector**: Cloud models now correctly route through ollama
- **Unused Import**: Removed `apiService` import causing TypeScript build error

### Changed
- Message footer now includes both timestamp and rating buttons
- System prompt sidebar starts collapsed (📋 icon to expand)

---

## 2026-01-08 — Spread Activation & React Router Overhaul

### Added
- **React Router Frontend Rewrite**
  - **Dashboard** (`/`): 3×2 grid with System Status, Identity Summary, Threads Overview, Recent Logs, Memory Stats, Quick Actions
  - **ChatPage** (`/chat`): Full-viewport chat interface with light theme
  - **ThreadsPage** (`/threads`): Thread navigation + Identity table with L1/L2/L3 columns
  - **DocsPage** (`/docs`): Markdown documentation viewer with nested directory tree
  - **ContactPage** (`/contact`): Project info and links
  - **FeedsPage** (`/feeds`): Feeds management
  - **WorkspacePage** (`/workspace`): File browser
- **Identity CRUD API**
  - `GET /api/introspection/identity/table` — All identity keys with L1/L2/L3 values
  - `PUT /api/introspection/identity/{key}` — Update identity values
  - `DELETE /api/introspection/identity/{key}` — Delete identity entries
  - `GET /api/introspection/threads/health` — Health status for all threads
- **Spread Activation System** (`agent/threads/schema.py`)
  - `concept_links` table: Hebbian strength/decay between concepts
  - `link_concepts(a, b)`: Strengthens association when concepts co-occur
  - `decay_concept_links()`: Daily decay (0.95×) with pruning
  - `spread_activate(concepts)`: Associative memory retrieval
  - `generate_hierarchical_key(fact)`: Converts facts to dot-notation keys
  - `extract_concepts_from_text(text)`: Pulls concepts from messages
- **Memory Service Updates** (`agent/services/memory_service.py`)
  - `_add_to_temp_memory()` generates hierarchical keys and links concepts
  - Facts pre-populate `fact_relevance` table
- **LinkingCore Adapter** (`agent/threads/linking_core/adapter.py`)
  - `activate_memories(input_text)`: Uses spread activation
  - `get_associative_context()`: Combines embedding + spread activation

### Changed
- **Light Theme**: Entire frontend switched from dark to light
- **Layout**: Dashboard uses CSS Grid 3×2, Chat fills full viewport
- **DocsPage**: Tree view hides root "docs" node

---

## 2026-01-06 — Thread System Migration Complete

### Changed
- **Thread System Architecture**: Migrated from old idv2/log_thread to unified `agent/threads/`
  - Old: `identity_sections` table with `data_l1_json`, `data_l2_json`, `data_l3_json` columns
  - New: `{thread}_{module}` tables (e.g., `identity_user_profile`, `log_events`)
  - Each row: `key`, `context_level`, `data`, `metadata`, `weight`, `updated_at`
- **Backend API Updates** (`backend/api/database.py`):
  - `/api/database/identity-hea` queries new thread tables
  - Added `/api/database/threads-summary` — all threads with modules and row counts
  - Added `/api/database/thread/{name}` — thread data at context level
- **Frontend Updates**:
  - `constants.ts`: Added trailing slash to introspection endpoint
  - `api.ts`: Added `getThreadsSummary()`, `getThreadData()` methods
  - `HEATable.tsx`: Updated interface for `key` and `weight` fields

### Fixed
- **RelevanceIndex Error**: Removed reference to deleted `RelevanceIndex` class
- **Introspection Polling**: Frontend correctly polls `/api/introspection/`

---

## 2026-01-02 — Focus System Architecture Discovery

### Added
- **Implementation Plan** (`docs/FOCUS_IMPLEMENTATION.md`): 7-phase rollout
- **Comparison Workspace** (`comparison/workspace/`): VS Code agent orchestrator

### Discovery
- **Architectural Breakthrough**: "Attention is all you need" → "Focus is all you need"
  - DB acts as control plane: Learns key sequences
  - LLM acts as data plane: Operates in pre-focused space
  - Two-stage processing: Deterministic focus → Probabilistic generation
- **DB as Semantic Tokenizer**:
  - Dynamic vocabulary (DB tables), learned importance (weights)
  - Key-value pairs ARE the semantic tokens
- **Memory Permanence Logic**:
  - Conflict detection: New value conflicts → Queue for tomorrow
  - Update detection: Modify existing key vs create redundant entry

---

## 2025-12-28 — Codebase Cleanup & Professionalization

### Added
- **Cleanup Directive** in agent profiles: 8 code builder profiles with cleanup-focused instructions
- **Resizable Sidebar Panels**: Drag handles between panels (180-450px range)

### Changed
- **Chat Positioning**: Messages align top-to-bottom, stable layout

### Removed
- **Backend Dead Code**: 6 unused imports from `websockets.py`, 3 from `database.py`, route count 30 → 28
- **AI OS Core Dead Code**: Unused imports across 8 files
- **Cache Cleanup**: Cleared 15 `__pycache__` directories (84 .pyc files)

---

## 2025-12-27 — Evaluation Harness, Identity Anchors & Subconscious Integration

### Added
- **AI Battle Evaluation** (`eval/ai_battle.py`): AI vs AI identity persistence battle
- **Coherence Test** (`eval/coherence_test.py`): Agent vs raw LLM comparison
  - **Result:** Agent (7B+HEA) beat raw 20B model 16.75 vs 14.88
- **Identity Anchor** in agent.py: "You are ALWAYS Agent" — prevents name changes
- **Reality Anchor** in agent.py: "If information is not in context, it does not exist"
- **Chinese README** (`README.zh.md`): Full translation
- **Subconscious Module** (`agent/subconscious/`)
  - `__init__.py`: Main API — `wake()`, `sleep()`, `get_consciousness_context()`
  - `core.py`: `ThreadRegistry`, `SubconsciousCore` singleton
  - `contract.py`: Metadata protocol for sync
  - `loops.py`: `ConsolidationLoop`, `SyncLoop`, `HealthLoop`
  - `triggers.py`: `TimeTrigger`, `EventTrigger`, `ThresholdTrigger`
- **Log Thread Module** (`agent/log_thread/`): Lightweight event tracking
- **Temp Memory Store** (`agent/temp_memory/`): Session-scoped fact extraction
- **Consolidation Daemon** (`agent/services/consolidation_daemon.py`)
- **Events API**: `GET /api/database/events`, `GET /api/database/events/stats`

### Changed
- **Agent Stateless Refactor**: `agent.py` accepts `consciousness_context` parameter
- **Memory Flow**: Facts flow Conversation → temp_memory → scorer → consolidation → DB

### Key Findings
- Structure beats scale: 7B+HEA matches or beats 120B on identity coherence
- HEA provides real context; instruction-only AI has no anchor

---

## 2025-12-23 — Test Suite & Evaluation Harness

### Added
- **Test suite** (`tests/`): 23 passing tests
  - `test_agent.py` (7): Singleton pattern, thread safety, provider toggle
  - `test_idv2.py` (6): DB init, push/pull sections, level filtering
  - `test_hea.py` (10): Feeds classification, context levels, token budgets
  - `conftest.py` fixtures: temp_db, sample_identity, mock_agent_config
- **Eval harness** (`eval/`): Adversarial coherence benchmarks
  - `duel.py`: CLI runner for Agent vs baselines
  - `judges.py`: Judge model integrations (OpenAI, Anthropic, Mock)
  - `metrics.py`: Scoring functions mapped to neural correlates
- **Evaluation framework** (`docs/evaluation_framework.md`)
- **pyproject.toml**: Added pytest configuration

---

## 2025-12-22 — Checklist & Launcher UX

### Added
- Evaluator checklist with progress tracking (`docs/checklist.md`)

### Changed
- `start.sh`: Run-mode chooser (Local vs Docker), `START_MODE` env override
- Docker Compose: Added Ollama service; `start-docker.sh` pulls configured model

---

## 2025-12-19 — Identity Thread v2 (DB Backend)

### Added
- SQLite-backed identity pipeline (`agent/idv2/idv2.py`) with level-scoped storage
- Sync mapping: `sync_for_feed` translates feeds types → context levels
- `pull_identity` returns level-filtered identity for prompts
- DatabaseAgent helper centralizes `state.db` connections

### Changed
- `agent.py` prefers DB-backed identity (with JSON fallback)
- Conversation snapshots capture minimal, level-scoped identity from DB

---

## 2025-12-18 — Licensing, Launcher & Backend Consolidation

### Changed
- Universal launcher: Consolidated run/start scripts into cross-platform `start.sh`
- Backend cleanup: Removed redundant relevancev2/chat_demo, centralized `agent_service.py`
- Docker/idv2 integration: Backend entrypoint migrates/health-checks identity DB

---

## 2025-12-17 — Repo Reorganization & Cleanup

### Changed
- **Portability fixes**: Changed `.venv/bin/uvicorn` shebang to `/usr/bin/env python3`
- Updated `start.sh` to invoke virtualenv explicitly with `"$VENV_DIR/bin/python" -m uvicorn`

---

## 2025-12-15 — React Chat Feeds Channel Integration

### Added
- **React UI as feed channel**: Chat app acts as external feed source
- **Backend integration**: `agent_service.py` routes through Agent agent
- **Conversation persistence**: Persists to `Feeds/conversations/react_*.json`
- **Context management**: HEA to classify feeds and manage L1/L2/L3 levels
- **Onboarding script**: Root-level `start.sh` for one-click local setup

---

## 2025-12-13 — Architecture Overhaul

### Added
- **Contracts & metadata protocol** (`contract.py`): `create_metadata()`, `should_sync()`, `is_stale()`, `mark_synced()`
- **Hierarchical state sync**: `machineID.json` → `identity.json` → `identity.json`
- **Context levels**: 1 = minimal, 2 = moderate, 3 = full

### Changed
- **Agent refactor**: Thread-safe singleton with atomic file writes
- **Auto-bootstrap**: `get_agent()` triggers full sync chain on first call
- **JSON layout**: Files now `{ "metadata": {...}, "data": {...} }`
- **Removed bootstrap.py**: Moved into `Agent.bootstrap()`

---

## 2025-12-07 — Initial Setup & Housekeeping

### Added
- Renamed agent `alex` → `agent`
- Created `Feeds/` folder for external feeds control
- Thread system: `personal` → `machineID`, `work` → `userID`
- Conversation file handling with chat IDs and names

---

<!-- MANAGED BELOW — Module changelogs auto-sync from module READMEs -->

## Module Changelogs

### Identity Thread
<!-- INCLUDE:identity:CHANGELOG -->
_Source: [agent/threads/identity/README.md](agent/threads/identity/README.md)_

### 2026-01-27
- Profile-based schema with L1/L2/L3 values
- Protected core profiles (machine, primary_user)
- Relevance filtering via LinkingCore

### 2026-01-23
- Protected profiles created in schema init (no seed files)
- Quick accessors: `get_agent_name()`, `get_user_name()`

### 2026-01-20
- Self-contained API router at `/api/identity/`
- Introspect returns dot-notation facts
<!-- /INCLUDE:identity:CHANGELOG -->

### Philosophy Thread
<!-- INCLUDE:philosophy:CHANGELOG -->
_Source: [agent/threads/philosophy/README.md](agent/threads/philosophy/README.md)_

### 2026-01-27
- Profile-based schema with L1/L2/L3 values
- Relevance filtering via LinkingCore

### 2026-01-20
- Self-contained API router at `/api/philosophy/`
- Introspect returns dot-notation facts
<!-- /INCLUDE:philosophy:CHANGELOG -->

### Log Thread
<!-- INCLUDE:log:CHANGELOG -->
_Source: [agent/threads/log/README.md](agent/threads/log/README.md)_

### 2026-02-01: Database Logging System
- **New Tables**: Added `log_system` (daemon logs) and `log_server` (HTTP logs) 
- **Helper Functions**: `log_system_event()`, `log_server_request()`, query functions
- **API Endpoints**: `/api/log/daemon`, `/api/log/server`, `/api/log/server/stats`
- **HTTP Middleware**: Auto-logging all requests with timing, client info, errors
- **Monitoring**: Server statistics endpoint for error rates, avg duration, top paths

### 2026-01-27
- Unified events table consolidates all event sources
- Recency-based context levels (L1=10, L2=100, L3=1000)

### 2026-01-20
- Session tracking with duration and message count
- Event relevance scoring by type
<!-- /INCLUDE:log:CHANGELOG -->

### Form Thread
<!-- INCLUDE:form:CHANGELOG -->
_Source: [agent/threads/form/README.md](agent/threads/form/README.md)_

### 2026-01-27
- L1/L2/L3 tool architecture
- Executable hot-reload support

### 2026-01-20
- Tool registry with categories
- API execution with result tracking
<!-- /INCLUDE:form:CHANGELOG -->

### Reflex Thread
<!-- INCLUDE:reflex:CHANGELOG -->
_Source: [agent/threads/reflex/README.md](agent/threads/reflex/README.md)_

### 2026-02-01: Executor Foundation & Feed Integration
- **Executor Class**: Created ReflexExecutor for trigger → tool execution pipeline
- **Feed Integration**: Triggers now respond to Feed event emissions (email, github, discord)
- **Tool Registry**: Foundation for executable tools in tools/executables/
- **Form Integration**: Connected to Form Thread for standardized tool execution
- **Schema Complete**: reflex_triggers table with conditions, actions, enabled status
- **API Endpoints**: Full CRUD operations for trigger management

### 2026-01-27
- Added `reflex_triggers` SQLite table for feed → tool automations
- New trigger CRUD endpoints (create, read, update, delete, toggle)
- Trigger executor integrates with Form tools
- Condition matching with operators (eq, contains, regex, etc.)
- Auto-execution when feed events are emitted
- Trigger test endpoint for manual testing

### 2026-01-20
- Greeting and shortcut tables
- Basic pattern matching
<!-- /INCLUDE:reflex:CHANGELOG -->

### Linking Core
<!-- INCLUDE:linking_core:CHANGELOG -->
_Source: [agent/threads/linking_core/README.md](agent/threads/linking_core/README.md)_

### 2026-01-31
- Potentiation column: SHORT/LONG memory stages
- `consolidate_links()` promotes high-fire links to LONG
- `get_potentiation_stats()` for dashboard
- `train.py` exports concept graph to JSONL

### 2026-01-27
- Hebbian learning with asymptotic strength growth
- Multi-dimensional fact scoring

### 2026-01-20
- Spread activation with max_hops parameter
- Temporal decay with configurable rate
<!-- /INCLUDE:linking_core:CHANGELOG -->

### Subconscious
<!-- INCLUDE:subconscious:CHANGELOG -->
_Source: [agent/subconscious/README.md](agent/subconscious/README.md)_

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
<!-- /INCLUDE:subconscious:CHANGELOG -->

### Temp Memory
<!-- INCLUDE:temp_memory:CHANGELOG -->
_Source: [agent/subconscious/temp_memory/README.md](agent/subconscious/temp_memory/README.md)_

### 2026-01-27
- Fixed log_event integration (correct parameter signature)
- Added regression tests in test_consolidation.py

### 2026-01-20
- Multi-status fact lifecycle
- Integration with unified_events timeline
<!-- /INCLUDE:temp_memory:CHANGELOG -->

### Services
<!-- INCLUDE:services:CHANGELOG -->
_Source: [agent/services/README.md](agent/services/README.md)_

### 2026-01-27
- Consciousness context assembly via subconscious
- Kernel browser integration

### 2026-01-20
- Agent runtime with message pipeline
- FastAPI endpoints for agent control
<!-- /INCLUDE:services:CHANGELOG -->

### Chat
<!-- INCLUDE:chat:CHANGELOG -->
_Source: [chat/README.md](chat/README.md)_

### 2026-01-27
- Multi-provider import system
- Message ratings for fine-tuning

### 2026-01-20
- Real-time WebSocket chat
- Conversation CRUD operations
<!-- /INCLUDE:chat:CHANGELOG -->

### Feeds
<!-- INCLUDE:feeds:CHANGELOG -->
_Source: [Feeds/README.md](Feeds/README.md)_

### 2026-02-01: Module System & Multi-Provider Support
- **YAML → Python**: Converted all feed configs to Python modules with adapters
- **Email Module**: Multi-provider support (Gmail, Outlook, Proton) with unified OAuth
- **GitHub Module**: 6 event types (issues, PRs, mentions, pushes) with OAuth integration
- **Discord Module**: Converted from YAML, added OAuth flow and bot adapter
- **Viewers**: Native viewer components (EmailViewer with provider tabs, GithubViewer, DiscordViewer)
- **API**: Updated OAuth endpoints with provider parameter support
- **Events**: Centralized event emission system with feed registry
- **Secrets**: Encrypted storage for OAuth tokens and API keys

### 2026-01-27
- YAML-driven source configuration
- Router message bus

### 2026-01-20
- Basic API endpoints for message CRUD
<!-- /INCLUDE:feeds:CHANGELOG -->

### Workspace
<!-- INCLUDE:workspace:CHANGELOG -->
_Source: [workspace/README.md](workspace/README.md)_

### 2026-01-27
- File upload and folder organization
- FastAPI endpoints for CRUD

### 2026-01-20
- SQLite schema for file metadata
<!-- /INCLUDE:workspace:CHANGELOG -->

### Finetune
<!-- INCLUDE:finetune:CHANGELOG -->
_Source: [finetune/README.md](finetune/README.md)_

### 2026-01-31
- Export pipeline: `/api/finetune/export` aggregates all threads
- Per-thread `train.py` pattern (identity, philosophy, log, reflex, form, linking_core)
- Combined JSONL output at `finetune/combined_train.jsonl`

### 2026-01-27
- MLX configuration for Apple Silicon
- JSONL data format defined

### 2026-01-20
- Initial fine-tuning concept
<!-- /INCLUDE:finetune:CHANGELOG -->

### Eval
<!-- INCLUDE:eval:CHANGELOG -->
_Source: [eval/README.md](eval/README.md)_

### 2026-01-27
- Battle types defined
- API endpoints planned

### 2026-01-20
- Initial eval concept
<!-- /INCLUDE:eval:CHANGELOG -->



