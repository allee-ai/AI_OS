
# Changelog

All notable changes to this repository are documented below. Entries are grouped by date and describe features added, architecture changes, and notable fixes.

---

## 2026-01-20 — Legacy Code Removal & Database Path Consolidation

### Refactoring: Remove IDv2 Legacy System
- **Deleted Module References**: Removed all `idv2` references from codebase (already deleted in Phase 7, now cleaned docs)
- **Updated Documentation**: Fixed `Nola/threads/linking_core/README.md` and `Nola/threads/REBUILD_CHECKLIST.md` to reference new `schema.py` instead of deleted `idv2.py`
- **Code Archaeology**: Confirmed no functional code imports or uses `idv2` — only historical comments remain

### Architecture: Centralized Database Path Logic
- **Single Source of Truth**: Refactored `Nola/threads/schema.py` to expose `get_db_path()` as public function
- **Dynamic Mode Switching**: `get_db_path()` reads `NOLA_MODE` env var or `.nola_mode` file at runtime to select `state.db` vs `state_demo.db`
- **Agent Integration**: Updated `Nola/agent.py` to import `get_db_path()` instead of hardcoding `DEFAULT_STATE_DB`
- **Eliminated Scatter**: No more hardcoded DB paths — all modules now reference central function

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
- **SSH Tunnel Connection**: `connect_vm_nola.sh` script for seamless local access via port forwarding
- **Desktop Shortcuts**: `Connect to Nola VM.command` for one-click VM access + browser launch
- **App Bundle**: `Nola VM.app` macOS application for desktop integration

### Technical Implementation
- **Static File Serving**: Modified FastAPI backend to serve React frontend from `../frontend/dist/`
- **Frontend Build**: npm build process on VM with Node.js v18 compatibility  
- **Database Migration**: Production mode using `state.db` instead of demo database
- **Network Architecture**: Local port 8000 → SSH tunnel → VM port 8000 → Nola interface

### Cloud-First Architecture Benefits
- ✅ **True 24/7 Operation**: No local machine dependency
- ✅ **Universal Access**: SSH tunnel from any device with SSH key
- ✅ **Consolidated Service**: Single VM runs all Nola components
- ✅ **Auto-Recovery**: Systemd ensures service restoration after VM restarts
- ✅ **Scalable Foundation**: Ready for multi-tenant Nola-as-a-Service expansion

---

## 2026-01-19 (Evening) — Linking Core 3D Visualization & Concept Graph Engine

### Feature: 3D Concept Graph Visualization
- **ConceptGraph3D.tsx**: Full 3D visualization of Nola's concept graph using Three.js + React Three Fiber
- **Purple Nebula Containment**: Swirling particle shell (4000 outer + 1200 inner particles) representing the cognitive boundary
- **Circular Particle Sprites**: Replaced square pixels with soft radial gradient dots
- **Density-Aware Gas Layer**: 2000 gas particles cluster near high-connection nodes, visualizing information density in real-time
- **Identity-Anchored Origin**: `name.nola` or identity node positioned at (0,0,0) — all other concepts positioned relative to self
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
- **Portable App Bundle**: Rebuilt `Nola AI OS.app` to use relative paths. The entire OS folder can now be moved anywhere, and the app will auto-locate `run.command`.
- **Fast Dependency Management**: Integrated `uv` for 10-100x faster package installation, with robust fallbacks to standard `pip` and `venv`.
- **Cross-Platform Launchers**: Unification of `start.sh` and `install.sh` to handle macOS (bundle), Linux (script), and environment checks automatically.

### Feature: Demo vs Personal Mode
- **Database Separation**: Implemented strictly isolated database paths (`state.db` for Personal, `state_demo.db` for Demo).
- **Mode Selection UI**: Added native dialog prompts at startup to choose between "Demo Mode" (safe for showing off) and "Personal Mode" (private data).

### Stability & Performance
- **Concurrency Safety**: Implemented global `RLock` system (`Nola/core/locks.py`) to prevent SQLite "database is locked" errors during background subconscious ops.
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
- **score_threads(stimuli)**: Thread-level relevance (0-10 scale)
  - Keyword-based scoring for each thread
  - Returns scores pushed to threads for context retrieval
  - Can be called anytime by reflex or subconscious
- **score_relevance(stimuli, facts)**: Comprehensive fact-level scoring
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
  - `profiles`: Instances like `admin.cade`, `family.mom`.
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
  - Nola is the active system; Elaris references remain in docs for historical context

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
- **`Nola/Nola.json`**: Fixed hardcoded `/Users/cade/...` path → relative `./identity_thread/identity.json`
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
- **Form Thread Tool System** (`Nola/threads/form/`)
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

## 2026-01-10 — Stimuli System & Universal API Router

### Added
- **Stimuli Router Architecture** (`Nola/Stimuli/router.py`)
  - **Universal API Adapter**: Config-driven integrations via YAML files
  - **Core Data Classes**:
    - `NormalizedMessage`: Converts any platform → standardized format
    - `ResponseTemplate`: Deterministic fields + LLM slots
    - `SourceConfig`: Parses YAML configs with auth, pull, push sections
  - **JSONPath Extraction**: Maps nested API responses to normalized fields
  - **Template Rendering**: `{{slot}}` placeholders filled by LLM
- **20+ YAML Source Configs** (`Nola/Stimuli/sources/*.yaml`)
  - Communication: Gmail, Slack, SMS (Twilio), Discord, Telegram, Twitter/X, WhatsApp, Microsoft Teams
  - Project Management: GitHub, Linear, Jira, Todoist
  - Databases: Notion, Airtable
  - Productivity: Google Calendar
  - Customer Support: Zendesk, Intercom
  - Commerce: Shopify, HubSpot
  - Generic: Webhook, Template
- **Stimuli Frontend Dashboard** (`StimuliPage.tsx`)
  - Source List with enable/disable toggles and status indicators
  - Source Detail View with full config display
  - Editable Config Sections with JSON editor
  - Add Source Modal with template cards
  - Test Connection and Delete Confirmation
- **Stimuli Backend API** (`api/stimuli.py`)
  - `GET /api/stimuli/sources` — List all configured sources
  - `GET/PUT /api/stimuli/sources/{name}` — Get/Update source config
  - `POST /api/stimuli/sources` — Add new source from template
  - `DELETE /api/stimuli/sources/{name}` — Remove source
  - `POST /api/stimuli/sources/{name}/toggle` — Enable/disable
  - `POST /api/stimuli/sources/{name}/test` — Test connection
  - `GET /api/stimuli/templates` — List available templates
- **LLM Fact Extraction** (`Nola/services/fact_extractor.py`)
  - Replaces regex parsing with LLM-based extraction
  - LLM generates: key, L3 (full), L2 (summary), L1 (essence)
  - Uses `llama3.2:3b` by default, configurable via `NOLA_EXTRACT_MODEL`

### Changed
- `main.py`: Added stimuli router import and `/api/stimuli` route prefix
- Phase 3 (Reflex Thread) documented as visual automation builder
- Phase 6 (Beyond Chat) marked as ✅ FOUNDATION COMPLETE

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
  - **StimuliPage** (`/stimuli`): Stimuli management
  - **WorkspacePage** (`/workspace`): File browser
- **Identity CRUD API**
  - `GET /api/introspection/identity/table` — All identity keys with L1/L2/L3 values
  - `PUT /api/introspection/identity/{key}` — Update identity values
  - `DELETE /api/introspection/identity/{key}` — Delete identity entries
  - `GET /api/introspection/threads/health` — Health status for all threads
- **Spread Activation System** (`Nola/threads/schema.py`)
  - `concept_links` table: Hebbian strength/decay between concepts
  - `link_concepts(a, b)`: Strengthens association when concepts co-occur
  - `decay_concept_links()`: Daily decay (0.95×) with pruning
  - `spread_activate(concepts)`: Associative memory retrieval
  - `generate_hierarchical_key(fact)`: Converts facts to dot-notation keys
  - `extract_concepts_from_text(text)`: Pulls concepts from messages
- **Memory Service Updates** (`Nola/services/memory_service.py`)
  - `_add_to_temp_memory()` generates hierarchical keys and links concepts
  - Facts pre-populate `fact_relevance` table
- **LinkingCore Adapter** (`Nola/threads/linking_core/adapter.py`)
  - `activate_memories(input_text)`: Uses spread activation
  - `get_associative_context()`: Combines embedding + spread activation

### Changed
- **Light Theme**: Entire frontend switched from dark to light
- **Layout**: Dashboard uses CSS Grid 3×2, Chat fills full viewport
- **DocsPage**: Tree view hides root "docs" node

---

## 2026-01-06 — Thread System Migration Complete

### Changed
- **Thread System Architecture**: Migrated from old idv2/log_thread to unified `Nola/threads/`
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
- **Nola Core Dead Code**: Unused imports across 8 files
- **Cache Cleanup**: Cleared 15 `__pycache__` directories (84 .pyc files)

---

## 2025-12-27 — Evaluation Harness, Identity Anchors & Subconscious Integration

### Added
- **AI Battle Evaluation** (`eval/ai_battle.py`): AI vs AI identity persistence battle
- **Coherence Test** (`eval/coherence_test.py`): Nola vs raw LLM comparison
  - **Result:** Nola (7B+HEA) beat raw 20B model 16.75 vs 14.88
- **Identity Anchor** in agent.py: "You are ALWAYS Nola" — prevents name changes
- **Reality Anchor** in agent.py: "If information is not in context, it does not exist"
- **Chinese README** (`README.zh.md`): Full translation
- **Subconscious Module** (`Nola/subconscious/`)
  - `__init__.py`: Main API — `wake()`, `sleep()`, `get_consciousness_context()`
  - `core.py`: `ThreadRegistry`, `SubconsciousCore` singleton
  - `contract.py`: Metadata protocol for sync
  - `loops.py`: `ConsolidationLoop`, `SyncLoop`, `HealthLoop`
  - `triggers.py`: `TimeTrigger`, `EventTrigger`, `ThresholdTrigger`
- **Log Thread Module** (`Nola/log_thread/`): Lightweight event tracking
- **Temp Memory Store** (`Nola/temp_memory/`): Session-scoped fact extraction
- **Consolidation Daemon** (`Nola/services/consolidation_daemon.py`)
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
  - `test_hea.py` (10): Stimuli classification, context levels, token budgets
  - `conftest.py` fixtures: temp_db, sample_identity, mock_agent_config
- **Eval harness** (`eval/`): Adversarial coherence benchmarks
  - `duel.py`: CLI runner for Nola vs baselines
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
- SQLite-backed identity pipeline (`Nola/idv2/idv2.py`) with level-scoped storage
- Sync mapping: `sync_for_stimuli` translates stimuli types → context levels
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

## 2025-12-15 — React Chat Stimuli Channel Integration

### Added
- **React UI as stimuli channel**: Chat app acts as external stimuli source
- **Backend integration**: `agent_service.py` routes through Nola agent
- **Conversation persistence**: Persists to `Stimuli/conversations/react_*.json`
- **Context management**: HEA to classify stimuli and manage L1/L2/L3 levels
- **Onboarding script**: Root-level `start.sh` for one-click local setup

---

## 2025-12-13 — Architecture Overhaul

### Added
- **Contracts & metadata protocol** (`contract.py`): `create_metadata()`, `should_sync()`, `is_stale()`, `mark_synced()`
- **Hierarchical state sync**: `machineID.json` → `identity.json` → `Nola.json`
- **Context levels**: 1 = minimal, 2 = moderate, 3 = full

### Changed
- **Agent refactor**: Thread-safe singleton with atomic file writes
- **Auto-bootstrap**: `get_agent()` triggers full sync chain on first call
- **JSON layout**: Files now `{ "metadata": {...}, "data": {...} }`
- **Removed bootstrap.py**: Moved into `Agent.bootstrap()`

---

## 2025-12-07 — Initial Setup & Housekeeping

### Added
- Renamed agent `alex` → `nola`
- Created `Stimuli/` folder for external stimuli control
- Thread system: `personal` → `machineID`, `work` → `userID`
- Conversation file handling with chat IDs and names



