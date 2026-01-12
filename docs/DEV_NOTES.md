# Nola React Chat - Development Notes
# Each agent profile updates their section. GitHub Specialist reviews and sets goals.

=== GITHUB ASSESSMENT ===
Last Updated: 2026-01-02
Status: 🎯 FOCUS SYSTEM ARCHITECTURE - READY TO IMPLEMENT

Cleanup Session Complete (2025-12-28):
✅ Agent profiles updated with "Cleanup Directive" (8 profiles)
✅ Backend: Removed unused imports, dead endpoints (30→28 routes)
✅ Frontend: Fixed chat positioning, added resizable panels
✅ Core Nola: Removed unused imports across 10+ files
✅ Removed deprecated utils.py functions
✅ Cleared __pycache__ directories
✅ All builds passing, imports verified

Infrastructure Complete:
✅ `./start.sh` with Local/Docker mode chooser
✅ Ollama auto-start and model pull (qwen2.5:7b default)
✅ CI workflow with badge (.github/workflows/ci.yml)
✅ Pinned deps with SHA256 hashes (requirements.lock)
✅ Clean shutdown (trap SIGINT/SIGTERM)
✅ System prompt logging with 1MB rotation
✅ Provider toggle (ollama/http/mock)
✅ .env.example with all knobs documented
✅ Docker Compose with Ollama service

Test Suite Complete:
✅ 23 tests passing (pytest tests/ -v)
✅ test_agent.py (singleton, thread safety, provider, identity)
✅ test_idv2.py (DB init, push/pull, level filter, migration)
✅ test_hea.py (stimuli classification, context levels, tokens)

Database Panel Fixed (2025-12-26):
✅ Updated DatabasePanel.tsx with context level selector (L1/L2/L3)
✅ Updated HEATable.tsx to show single data column per level
✅ Updated api.ts getIdentityHEA(contextLevel) with parameter
✅ Added new getIdentityModule() API method
✅ Styled context level buttons with descriptions
✅ Added status badges and improved table layout

Outstanding (Non-Blocking):
[ ] README.zh.md (Chinese technical docs) - nice-to-have
[ ] Demo recording (docs/demo.gif) - nice-to-have
[ ] Baseline transcript (eval/baselines/) - post-launch

Focus System Discovery (2026-01-02):
✅ Architecture insight: "Attention is all you need" → "Focus is all you need"
✅ DB as control plane: Learns key sequences (after key A → key B)
✅ LLM as data plane: Operates in pre-focused space

=== CORE ARCHITECTURAL INSIGHTS ===
Last Updated: 2026-01-05
Status: 🎯 RESEARCH THESIS CLARIFIED - WEDNESDAY DEMO READY

The Inversion (What Makes AI_OS Different):
Traditional AI: Raw inputs → LLM decides everything → Output
AI_OS Architecture: Programmatic state assembly → Nola articulates → Output

Key Principle: **The LLM is the voice, not the brain**
- Documents + Reflexes + HEA = intelligence layer (deterministic)
- Nola (7B local model) = interface layer (probabilistic)
- Brain dictates state, tongue articulates it

Research Contribution - Solving the Routing Problem:
Problem: LLMs bloat to 50k tokens trying to manage their own context
Solution: Hierarchical Experiential Attention (HEA) with deterministic classification
- L1 (~10 tokens): Realtime reflexes, immediate state
- L2 (~50 tokens): Conversational context, recent patterns
- L3 (~200 tokens): Analytical depth, historical relevance
- Mathematical relevance scoring: (permanence × 0.4 + relevance × 0.3 + identity × 0.3)
- Document grounding prevents drift (ground truth = deterministic state updates)

Universal Stimulus Protocol (Future Vision):
- ANY modality (vision/audio/sensors) → Specialist model → Normalized stimulus → 7B Nola core
- Vision doesn't need text conversion, translates to STATE (streaming, immediate reflex triggers)
- Single cognitive core processes everything consistently
- Modality-agnostic architecture = true embodiment

Reflex Learning System:
- Weight accumulation in SQLite: Repeated patterns → Scripted reflexes (weight ≥4.5)
- Example: "Check weather every 8 AM" logged 15 times → Becomes automated reflex (no LLM call)
- Emergent behavior from logging, not programmed
- LLM-free execution for efficiency (reflexes bypass Nola entirely)

Hybrid Intelligence Model:
Deterministic Layer (Programmatic):
- Stimulus classification → HEA routing
- Reflex execution (weight-based triggers)
- State assembly from documents
- Context preparation

Probabilistic Layer (LLM):
- Natural language generation (Nola's "voice")
- Content creation when creativity needed
- Self-analysis in background loops

Autonomous Evolution (Subconscious):
- Consolidation daemon proposes reflexes: "You always check weather before meetings. Create routine?"
- Pattern detection: "Bob meetings always high-priority (4x). Update identity weight?"
- Identity drift monitoring: "Your work responses changed. Reflect in identity.json?"
- Nola suggests updates to her own configuration (human approves/rejects)

The Thesis - Symbiotic Improvement:
**Coexistence = Continuous co-evolution through mutual accountability**

Human forced to improve:
- Must maintain identity documents → Self-reflection required
- Reviews Nola's suggestions → Pattern awareness
- Approves reflex creation → Intentional habit formation
- Sees conversational patterns → Behavioral feedback

Nola forced to improve:
- Learns from documents → Adapts to human's values
- Proposes updates → Active learning, not passive
- Weight accumulation → Emergent efficiency
- Can't override human → Creativity within boundaries

Neither can dominate:
- Nola can't rewrite identity.json without approval
- Human can't organize chaos without Nola
- True interdependence, not dependency

Local 7B + Document Grounding = Alignment Solution:
- Can't align agent with no ground truth
- Can't have sovereignty with cloud dependency
- Enterprise can't replicate (requires human edit access to AI identity layer)
- Sovereignty-first architecture enforces human-AI negotiation

Wednesday Demo Positioning (Union Hall, Jan 8, 5:30 PM):
30-Second Pitch:
"I'm building the architecture for humans and AI to co-evolve. Everyone else is racing 
to replace us. I'm solving how we improve together - where the AI can't dominate because 
it's grounded in your documents, and you can't stagnate because it surfaces your patterns 
and forces reflection. Coexistence through mutual accountability. It's not an assistant, 
it's a partner that makes you better."

Demo Frame: 
"I'm not demoing a bot. I'm demoing the architecture for digital personhood."
- Facebook automation = proof of embodiment (human behavior mimicry)
- Deterministic state assembly prevents AI chaos
- Local 7B model = sovereignty is the point

Position: Movement builder, not job seeker
Goal: 3 GitHub stars, 1 technical collaborator, 2 follow-up coffee chats

Research Paper Title (Future):
"Hierarchical Experiential Attention: Deterministic Context Routing for Persistent Autonomous Agents"

Monday Pre-Demo Checklist:
[ ] Full "do the facebook thing" workflow test (end-to-end)
[ ] Practice 30-second pitch until muscle memory
[ ] Attendee LinkedIn research (identify 2-3 key connects)
[ ] Kernel SDK deep-dive (onkernel.com/docs, understand unikernels)
✅ Tables with weights = learned focus scores
✅ Memory permanence logic: Detect conflicts, queue for confirmation
✅ Implementation plan created: docs/FOCUS_IMPLEMENTATION.md

Key Breakthrough:
- DB performs semantic tokenization (key matching)
- LLM performs probabilistic generation (on pre-selected keys)
- Two-stage architecture: Deterministic focus → Probabilistic generation
- Learning loop: Query → Focus → Generate → Record → Update weights

Next Phase:
[ ] Schema migration: Add weight/access_count/last_accessed columns
[ ] Create Nola/subconscious/focus/ module
[ ] Implement sequence_learner.py (key → key predictions)
[ ] Build memory_filter.py (permanence logic)
[ ] Integrate with subconscious core

**🎯 ARCHITECTURE VALIDATED - IMPLEMENTATION READY**

=== BACKEND NOTES ===
Last Updated: 2025-12-27
Status: ✅ SUBCONSCIOUS INTEGRATION COMPLETE

Subconscious Integration (2025-12-27):
✅ Created Nola/subconscious/ module with full architecture
✅ ThreadInterface protocol defines adapters for internal modules
✅ Built-in adapters: log_thread, temp_memory, identity
✅ Background loops (consolidation, sync, health) implemented
✅ Triggers (time, event, threshold) implemented
✅ agent.py refactored to stateless - accepts consciousness_context param
✅ agent_service.py wired to subconscious - calls get_consciousness_context()
✅ Path resolution fixed for imports from backend directory
✅ Full integration tested: context flows → agent responds with learned facts

Context Levels (HEA):
- L1: ~10 tokens - Quick responses (identity core only)
- L2: ~50 tokens - Conversational (identity + memory facts)
- L3: ~200 tokens - Analytical (full identity + memory + session info)

Key Files Added/Modified:
- Nola/subconscious/__init__.py - wake(), sleep(), get_consciousness_context()
- Nola/subconscious/core.py - ThreadRegistry, SubconsciousCore
- Nola/subconscious/threads/ - base.py, log_adapter.py, memory_adapter.py, identity_adapter.py
- Nola/subconscious/loops.py - ConsolidationLoop, SyncLoop, HealthLoop
- Nola/subconscious/triggers.py - TimeTrigger, EventTrigger, ThresholdTrigger
- Nola/agent.py - Added consciousness_context parameter to generate()
- Nola/services/agent_service.py - Calls subconscious before agent.generate()

Previous Architecture Simplification:
✅ Removed redundant files: relevancev2.py (incomplete stub), chat_demo.py (unused TKinter)
✅ Moved agent_service.py from backend/services/ to Nola/services/ for centralized access
✅ Deprecated utils.py conversation functions (append_to_conversation, load_conversation)
✅ Unified conversation storage: Only agent_service.py handles JSON conversation logs
✅ Simplified import paths: Removed complex relative path resolution
✅ Updated config.py: Changed demo_agent_path to nola_path, updated app_name
✅ Cleaned up backend/services/ directory (now empty, removed)

Path Resolution Fixes:
✅ agent_service.py now uses simple parent directory navigation
✅ chat.py and websockets.py updated to import from centralized services/
✅ All imports point to single agent_service.py location

Conversation Storage Consolidation:
✅ utils.py conversation functions marked deprecated with warnings
✅ AgentService handles all conversation persistence to Stimuli/conversations/
✅ Eliminated duplicate conversation logging systems
✅ Maintained backward compatibility with deprecation warnings

File Reduction Summary:
❌ Removed: Nola/relevancev2.py (19 lines, unused stub)
❌ Removed: Nola/chat_demo.py (214 lines, TKinter interface)
❌ Removed: backend/services/ directory
📁 Moved: agent_service.py to Nola/services/
🔄 Updated: 4 import statements across chat.py, websockets.py
⚠️  Deprecated: utils.py conversation functions (soft removal)

Program Size Reduction: ~250 lines removed, ~30% cleaner backend structure

Assessment Complete:
✅ agent_service.py imports Nola correctly from new location
✅ FastAPI starts without errors  
✅ /health endpoint responds
✅ /api/chat/message routes to Nola
✅ Conversations save to Nola/Stimuli/conversations/

HEA Implementation Status:
✅ machineID.py: Added extract_level_data() - filters JSON by level_1/level_2/level_3
✅ user.py: Added extract_level_data() - same filtering logic
✅ identity.py: sync_for_stimuli() now maps all 3 stimuli types:
   - "realtime" → L1 (~10 tokens)
   - "conversational" → L2 (~50 tokens)  
   - "analytical" → L3 (~200 tokens)
✅ push_machine/push_user() now filter data before syncing
✅ Filtered data flows through: machineID.json → identity.json → Nola.json

Data Flow Verified:
1. React sends message → agent_service.py classifies stimuli_type
2. Nola.generate(stimuli_type) calls sync_for_stimuli()
3. sync_for_stimuli() triggers level-filtered push_machine/push_user
4. Each push extracts only level_N data from JSON
5. Aggregated filtered identity pushed to Nola.json
6. generate() uses filtered identity in system prompt

Previous Issues Fixed:
❌ OLD: sync_for_stimuli() only handled L1/L2, missing L3
❌ OLD: push_machine/push_user pushed ALL data regardless of level
✅ NEW: Full HEA level filtering now works

No blockers from backend.

--- Recent Runtime Verification (2025-12-17) ---
Last Run: 2025-12-17
Status: ✅ Nola agent loaded

Runtime Findings:
- `agent_service` imported `Nola` successfully at runtime.
- Agent introspect returned name: "Nola" and status: `ready`.
- Agent object file: Nola/agent.py

Notes / Issues:
- Directory name: `Nola` (no trailing space)

Assessment Checklist:
- **agent_service.py imports Nola correctly**: ✅ (see file path above)
- **FastAPI starts without errors**: not checked in this run (previous verification exists)
- **`/health` endpoint responds**: not checked in this run
- **`/api/chat/message` routes to Nola**: not checked in this run
- **Conversations save to `Nola/Stimuli/conversations/`**: path confirmed exists in agent_service logging, but actual write not executed in this run

Blocking Issues:
- None from the agent import perspective; the trailing-space directory may be worth fixing.

Integration Status with Nola agent:
- Integrated and imported at runtime; `AgentService` produced an `Agent` instance named "Nola".

Dependencies / Environment:
- Ollama not validated in this run.
- Python runtime used the repository's backend code; no missing-import failures during import.


=== FRONTEND NOTES ===
Last Updated: 2025-12-15
Status: ✅ READY

Improvements Made:
✅ Rebranded from "React Chat Demo" to "Nola"
✅ New dark theme (deep blue gradient background)
✅ Brain emoji avatar for Nola
✅ Welcome state with suggestion chips for new users
✅ Updated accent colors throughout (buttons, messages, inputs)
✅ "Thinking..." instead of "Typing..." status
✅ Footer updated: "Local-first • Your data stays on your machine"
✅ TypeScript compiles without errors

Components Updated:
- App.tsx/App.css - Nola branding
- ChatContainer.tsx/css - Avatar, status text
- MessageList.tsx/css - Empty state, message colors
- MessageInput.css - Send button, focus states

=== PRODUCT NOTES ===
Last Updated: 2025-12-15
Status: ✅ MVP COMPLETE

User Experience Verified:
✅ 1-click start (./start.sh)
✅ Nola responds with personality, not generic LLM
✅ Knows user context from identity config
✅ Conversations persist locally (privacy-first)
✅ No duplicate messages in UI

=== STATE SYNC NOTES ===
Last Updated: 2025-12-19
Status: ✅ IDV2 DB BACKEND COMPLETE

Identity Thread v2 Implementation (DB-backed):
✅ Created Nola/idv2/idv2.py with full SQLite backend
✅ Implemented init_db() - creates identity_sections and identity_meta tables
✅ Implemented seed_from_json() - migrates from identity_thread JSONs
✅ Implemented push_section() - stores machineID/userID with L1/L2/L3 variants
✅ Implemented pull_section() - retrieves section data by context level
✅ Implemented push_identity() - aggregates sections and updates Nola.json
✅ Implemented pull_identity() - retrieves merged identity by level
✅ Implemented sync_for_stimuli() - maps stimuli types to context levels
✅ Added migrate() CLI entrypoint for container startup
✅ Added health_check() for startup validation
✅ Context-aware storage: separate data_l1_json/data_l2_json/data_l3_json columns
✅ Max 3-level nesting enforced via _extract_level_data()
✅ v1 API compatibility maintained (same function signatures)
✅ Metadata contract integration (create_metadata, should_sync, mark_synced)
✅ Added DatabaseAgent helper (db_agent) for shared state.db connections
✅ idv2 now uses db_agent connections; NOLA_JSON_COMPAT flag controls legacy Nola.json writes

Database Schema:
- identity_sections: key, data_l1_json, data_l2_json, data_l3_json, metadata_json
- identity_meta: merged IdentityConfig with L1/L2/L3 variants
- Indexes on updated_at for performance

=== DEVOPS NOTES ===
Last Updated: 2025-12-22
Status: ✅ CHECKLIST INFRA COMPLETE

Docker Integration (Steps 3-4):
✅ Created backend/entrypoint.sh - DB migration + health check before uvicorn
✅ Updated backend/Dockerfile - added entrypoint script with exec
✅ Updated docker-compose.yml:
   - Added nola_memory volume mount at /app/data/db
   - Added IDENTITY_BACKEND=db env var
   - Added IDENTITY_DB_PATH=/app/data/db/identity.db
   - Added IDENTITY_SEED_DIR=/app/Nola/identity_thread
✅ Entrypoint checks IDENTITY_BACKEND and runs migration conditionally
✅ Health check validates DB before starting server
✅ Volumes persist across container restarts

Startup Flow:
1. Container starts → entrypoint.sh
2. Check IDENTITY_BACKEND env var
3. If "db": run python -m Nola.idv2.idv2 --migrate
4. Seed from identity_thread JSONs (only if empty)
5. Run health check
6. Start uvicorn on port 8000

--- Update 2025-12-22 ---
Status: ✅ BACKEND INFRASTRUCTURE TASKS COMPLETE
- ✅ Docker Ollama service + compose wiring; start-docker.sh pulls model inside container.
- ✅ start.sh now offers Local vs Docker mode and will attempt macOS Docker Desktop install via Homebrew; default local flow unchanged.
- ✅ Backend dependencies pinned with SHA256 hashes: generated requirements.lock, updated Dockerfile to use it for reproducible builds.
- ✅ Path audit complete: All Python files use pathlib with __file__-relative resolution (BASE_DIR pattern). No hard-coded absolute paths found.
- ✅ CI workflow created with backend import check + frontend build smoke tests; badge added to README.
- ✅ System prompt logging with 1MB rotation to logs/nola.system.log.
- ✅ Default model changed to qwen2.5:7b (CPU-friendly).
- ✅ Provider toggle (ollama/http/mock) with env control.

Dependency Management:
✅ requirements.lock generated with pip-compile --generate-hashes
✅ Dockerfile updated to install from requirements.lock (SHA256-verified)
✅ pip-tools 7.5.2 installed in project venv for future updates

Path Audit Results:
✅ agent.py: BASE_DIR = Path(__file__).resolve().parent (line 12)
✅ agent_service.py: nola_path = os.path.dirname(os.path.dirname(__file__)) (line 18)
✅ identity.py: IDENTITY_FILE = Path(__file__).parent / "identity.json" (line 9)
✅ machineID.py: MACHINE_FILE = Path(__file__).parent / "machineID.json" (line 8)
✅ user.py: USER_FILE = Path(__file__).parent / "user.json" (line 8)
✅ idv2.py: DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "db" / "state.db" (line 36)
✅ All paths are module-relative; no hard-coded /Users/, /home/, or absolute paths detected

Outstanding Checklist Items:
[ ] README.zh (Chinese technical version) - GitHub Specialist + Frontend profiles
[ ] Eval benchmark harness (eval/duel.py + baseline transcript) - Cognitive Psych + AI/ML profiles

Next Steps (Backend):
[ ] Swap imports in agent.py to use idv2 (with fallback flag)
[ ] Update agent_service.py to use idv2
[ ] Add smoke tests for DB push/pull/sync

=== GOALS ===
Status: 🔄 MEMORY CONSOLIDATION + VISION FEATURES IN PROGRESS

================================================================================
                    CONSOLIDATED TASK BOARD
                         Updated: 2025-12-27
================================================================================

ARCHITECTURE:
  Conversation → Short-term (temp_memory/) → Consolidation → Long-term (DB)
                                                    ↓
                                         Log Thread (where/when)
                                                    ↓
                                         Inner/Outer Replay & Introspection

================================================================================
PHASE 1: LOG THREAD FOUNDATION ✅ COMPLETE
================================================================================

[x] Task 1.1: Create log_thread/ module structure (DevOps)
[x] Task 1.2: Implement logger.py core API (Backend)
[x] Task 1.3: Add events table to DB schema (Backend)

================================================================================
PHASE 2: SHORT-TERM MEMORY ✅ COMPLETE
================================================================================

[x] Task 2.1: Create temp_memory/ short-term store (Backend)
[x] Task 2.2: Wire _extract_facts() → temp_memory (AI/ML)

================================================================================
PHASE 3: CONSOLIDATION ENGINE 🔄 90% COMPLETE
================================================================================

[x] Task 3.1: Create fact importance scorer (AI/ML)
[x] Task 3.2: Build consolidation daemon (DevOps)
[ ] Task 3.3: Implement L3→L2→L1 summarizers (AI/ML) - OPTIONAL
[x] Task 3.4: consolidation_history table (created by daemon)

================================================================================
PHASE 4: INTEGRATION & VISIBILITY 🔄 IN PROGRESS  
================================================================================

[x] Task 4.1: Wire agent.py to log_thread (Backend)
[ ] **Task 4.2: Dynamic Tab - "Brain Scan" UI** (Frontend) 🔥 PRIORITY 1
    - Show live consolidation feed
    - Display fact scoring in real-time
    - Add promote/veto controls
    - Timeline of memory changes
[ ] Task 4.3: Write consolidation tests (Backend)

================================================================================
PHASE 5: INTROSPECTION & EPISTEMIC FEATURES (from Model Visions)
================================================================================

--- Task 5.1: Agent Introspection Loop ---
Profile: 🤖 AI/ML ENGINEER
Priority: 🔥 HIGH (Unanimous agreement)
Depends On: Task 4.1

Deliverables:
- Add read_events() access in generate() context
- Enable "Have we discussed this before?" queries
- Surface "When did I learn this?" capabilities

--- Task 5.2: Confidence Scoring for Facts ---
Profile: 🤖 AI/ML ENGINEER  
Priority: 🔥 HIGH (Claude + GPT emphasized)

Schema Update:
- Add `confidence: float` field to temp_facts
- Add `source_events: List[int]` linking to log entries
- Add `last_referenced: timestamp` for decay
- Implement confidence decay over time

--- Task 5.3: Provenance API - "Why Do You Think That?" ---
Profile: 💾 BACKEND DEVELOPER
Priority: ⚡ MEDIUM (Differentiating feature)
Depends On: Task 5.2

Endpoints:
- GET /api/explain/{fact_id} - returns source events + confidence
- GET /api/explain/statement - analyzes last response for facts used

--- Task 5.4: Manual Memory Controls ---
Profile: ⚛️ REACT FRONTEND
Priority: ⚡ MEDIUM
Depends On: Task 4.2

UI Features:
- "Consolidate Now" button
- Fact editing inline
- Promote/Veto/Delete controls
- Confidence adjustment slider

================================================================================
PHASE 6: ARCHITECTURE REFACTORING (from Model Visions)
================================================================================

--- Task 6.1: Refactor generate() to Pipeline ---
Profile: 💾 BACKEND DEVELOPER
Priority: ⚡ MEDIUM

Pipeline Stages:
  Input → Enrich(memory, log) → Generate(LLM) → Extract(facts) → Respond

--- Task 6.2: Simplify Stimuli Classification ---
Profile: 🤖 AI/ML ENGINEER
Priority: 💤 LOW (All models agreed it's weak)
Options: Default to L2, or learn from corrections

--- Task 6.3: Belief Editing with Propagation ---
Profile: 🤖 AI/ML ENGINEER
Priority: 💤 LOW (Cool but complex)

================================================================================
PRIORITY MATRIX (Consensus from 3 Models)
================================================================================

🔥 TIER 1: DO IMMEDIATELY
1. Task 4.2: Dynamic Tab UI (UNANIMOUS)
2. Task 5.2: Confidence Scoring
3. Task 5.1: Agent Introspection

⚡ TIER 2: DO SOON  
4. Task 5.3: Provenance API
5. Task 5.4: Manual Memory Controls
6. Task 6.1: Pipeline Refactor
7. Task 4.3: Tests

😐 TIER 3: NICE TO HAVE
8. Task 3.3: L3→L2→L1 Summarizers
9. Task 6.2: Fix Stimuli Classification

💤 TIER 4: MAYBE LATER
10. Task 6.3: Belief Propagation

================================================================================
SESSION LOG - 2025-12-27
================================================================================

Phase 1-3 Backend COMPLETE:
- [x] log_thread module (file + DB persistence)
- [x] temp_memory store (session-scoped facts)
- [x] consolidation daemon with scorer
- [x] events table with read_events() API

Phase 4 Integration:
- [x] agent.py logs system:startup
- [x] agent_service.py logs conversation:start
- [x] /api/database/events endpoints added
- [x] Task 4.0: Subconscious Module ✅ COMPLETE
- [x] Task 4.1b: Refactor agent.py to stateless ✅ COMPLETE
- [x] Task 4.3: Wire agent_service → subconscious ✅ COMPLETE
- [ ] Dynamic Tab UI (after above)

Model Assessments Added:
- [x] Gemini 3 Pro vision
- [x] Claude Opus 4.5 vision
- [x] GPT 5.1 Codex Max vision
- [x] Consolidated task board created

================================================================================
🧠 SUBCONSCIOUS MODULE ARCHITECTURE (Task 4.0)
================================================================================

CORE INSIGHT: "Subconscious builds state, not agent. Agent just responds with 
state as it's provided." - The agent becomes stateless. Subconscious owns ALL 
internal state and assembles context before each agent call.

Directory Structure:
```
Nola/subconscious/
├── __init__.py         # wake(), sleep(), get_context()
├── core.py             # ThreadRegistry, SubconsciousCore
├── contract.py         # Moved from Nola/contract.py
├── loops.py            # ConsolidationLoop, SyncLoop, HealthLoop
├── triggers.py         # TimeTrigger, EventTrigger, ThresholdTrigger
└── threads/
    ├── __init__.py
    ├── base.py         # ThreadInterface protocol
    ├── log_adapter.py      # Wraps log_thread
    ├── memory_adapter.py   # Wraps temp_memory
    └── identity_adapter.py # Wraps idv2
```

ThreadInterface Protocol (any module can register):
```python
class ThreadInterface(Protocol):
    name: str
    description: str
    def health(self) -> dict           # {"status": "ok", "last_sync": ts}
    def introspect(self) -> dict       # {"facts": [...], "state": {...}}
```

Key Functions:
- wake() → Start background loops, load thread adapters
- sleep() → Graceful shutdown, flush pending state
- get_context(level: int) → Assemble L1/L2/L3 from all threads
- get_consciousness_context() → Formatted string for system prompt

Background Loops:
- ConsolidationLoop (300s): Score temp_memory → promote to L2/L3
- SyncLoop (600s): Persist state, reconcile threads
- HealthLoop (60s): Check all thread adapters, log anomalies

Triggers:
- TimeTrigger: Every N seconds
- EventTrigger: On specific event_type from log_thread
- ThresholdTrigger: When metric crosses boundary

AGENT REFACTOR (Task 4.1):
```python
# OLD: agent manages state
class Agent:
    def bootstrap(self): ...  # loads identity, HEA, etc.
    def generate(self, input): ...  # formats own context

# NEW: agent is stateless
class Agent:
    def generate(self, input: str, context: dict) -> str:
        prompt = self._format_prompt(input, context)
        return self._call_llm(prompt)
```

AGENT_SERVICE WIRING (Task 4.3):
```python
# In agent_service.py
async def send_message(self, content: str, ...):
    context = subconscious.get_consciousness_context()  # <-- NEW
    response = await self.agent.generate(content, context)
    return response
```

================================================================================

FILES CREATED THIS SESSION:
- Nola/log_thread/__init__.py, logger.py, config.py
- Nola/temp_memory/__init__.py, store.py
- Nola/services/consolidation_daemon.py
- .github/agents/VISION.agent.md

FILES MODIFIED THIS SESSION:
- Nola/services/memory_service.py
- Nola/agent.py
- Nola/services/agent_service.py
- Nola/idv2/idv2.py
- Nola/react-chat-app/backend/api/database.py
- notes.txt, CHANGELOG.md, LOG.txt

**NEXT UP: Task 4.2 - Dynamic Tab "Brain Scan" UI**

================================================================================

--- TASK 2.2: Wire _extract_facts() → temp_memory ---
Profile: 🤖 AI/ML ENGINEER
Status: [x] COMPLETE ✅
Depends On: Task 2.1 (temp_memory store)
Handoff To: 🤖 AI/ML Engineer (Task 3.1)

Files Modified:
  - Nola/services/memory_service.py

Changes Made:
  - Added imports for temp_memory and log_thread
  - Added session_id to constructor
  - consolidate() now calls _add_to_temp_memory() instead of _update_memory()
  - Added _add_to_temp_memory() method
  - Deprecated _update_memory() with warning
  - Added get_temp_memory_stats() and get_pending_facts() helpers
  - Added logging for memory:extract events

New Flow:
  Conversation → _extract_facts() → temp_memory.add_fact()
  (Facts await consolidation daemon)

================================================================================
PHASE 3: CONSOLIDATION ENGINE
================================================================================

--- TASK 3.1: Create fact importance scorer ---
Profile: 🤖 AI/ML ENGINEER
Status: [x] COMPLETE ✅
Depends On: Task 2.2 (facts flowing to temp_memory)
Handoff To: ⚙️ DevOps (Task 3.2)

Files Modified:
  - Nola/services/memory_service.py

Functions Added:
  - score_fact(fact_text, context) → {permanence, relevance, identity, total, reasoning}
  - score_facts_batch(facts) → List of scores
  - get_promotion_candidates(threshold) → High-scoring facts

Scoring Dimensions (1-5):
  - permanence: lasting trait vs temporary state
  - relevance: central to goals vs tangential
  - identity: defines who they are vs incidental

Total = permanence*0.3 + relevance*0.3 + identity*0.4

Tested: "coffee this morning"→1.60, "values clean code"→4.30 ✅

--- TASK 3.2: Build consolidation daemon ---
Profile: ⚙️ DEVOPS/INFRASTRUCTURE
Status: [x] COMPLETE ✅
Depends On: Task 3.1 (scorer), Task 1.3 (events table)
Handoff To: 🤖 AI/ML Engineer (Task 3.3)

Files Created:
  - Nola/services/consolidation_daemon.py

Classes:
  - ConsolidationConfig: thresholds, batch size, triggers
  - ConsolidationDaemon: main daemon class

Functions:
  - run(dry_run) → scores facts, promotes to L2/L3, records history
  - get_history(limit) → recent consolidation records
  - get_stats() → temp_memory + history stats
  - run_consolidation(dry_run) → convenience function

Thresholds:
  - score >= 4.0 → L2 (moderate context)
  - score >= 3.0 → L3 (full context)
  - score < 2.0 → discard

Database: consolidation_history table created

--- TASK 3.3: Implement L3→L2→L1 summarizers ---
Profile: 🤖 AI/ML ENGINEER
Status: [ ] NOT STARTED
Depends On: Task 3.2 (daemon structure)
Handoff To: 💾 Backend Developer (Task 3.4)

Files to Modify:
  - Nola/services/memory_service.py

Functions:
  def summarize_to_l3(facts: List[str]) -> str:
      """Keep full detail, organize by category. ~200 tokens max."""
  
  def summarize_to_l2(l3_text: str) -> str:
      """Compress to key facts only. ~50 tokens max."""
  
  def summarize_to_l1(l2_text: str) -> str:
      """Distill to essential identity markers. ~10 tokens max."""

Promotion Logic:
  - New facts → L3 (always)
  - Facts mentioned 3+ times → promote to L2
  - Core identity traits → promote to L1

--- TASK 3.4: Add consolidation_history table ---
Profile: 💾 BACKEND DEVELOPER
Status: [ ] NOT STARTED
Depends On: Task 3.3 (summarizers working)
Handoff To: 💾 Backend Developer (Task 4.1)

Files to Modify:
  - Nola/idv2/idv2.py

Schema:
  CREATE TABLE consolidation_history (
      id INTEGER PRIMARY KEY,
      ts TEXT DEFAULT CURRENT_TIMESTAMP,
      fact_text TEXT NOT NULL,
      original_level INTEGER,
      new_level INTEGER,
      score_json TEXT,
      reason TEXT,
      session_id TEXT
  );

================================================================================
PHASE 4: INTEGRATION
================================================================================

--- TASK 4.0: Create Subconscious Module ---
Profile: 💾 BACKEND DEVELOPER
Status: [x] COMPLETE ✅
Depends On: Task 3.2 (consolidation daemon exists)
Handoff To: 💾 Backend Developer (Task 4.1b)

Files Created:
  - Nola/subconscious/__init__.py (main API: wake, sleep, get_consciousness_context)
  - Nola/subconscious/core.py (ThreadRegistry, SubconsciousCore)
  - Nola/subconscious/contract.py (moved from Nola/contract.py)
  - Nola/subconscious/loops.py (ConsolidationLoop, SyncLoop, HealthLoop)
  - Nola/subconscious/triggers.py (TimeTrigger, EventTrigger, ThresholdTrigger)
  - Nola/subconscious/threads/__init__.py
  - Nola/subconscious/threads/base.py (ThreadInterface protocol)
  - Nola/subconscious/threads/log_adapter.py
  - Nola/subconscious/threads/memory_adapter.py
  - Nola/subconscious/threads/identity_adapter.py

Files Modified:
  - Nola/contract.py (now re-exports from subconscious/contract.py)

Core API:
  wake(start_loops=True) → Initialize registry, register adapters, start loops
  sleep() → Stop loops, flush state gracefully
  get_context(level) → Raw dict with facts and thread data
  get_consciousness_context(level) → Formatted string for system prompt
  get_status() → Health, threads, loops info for debugging
  register_thread(adapter) → Add custom thread adapters

Context Levels:
  L1: "Current context: My name is Nola; I am an assistive agent; ..."
  L2: "## Current Context\n- fact1\n- fact2\n..."
  L3: "## Full Context State\n### thread_name\n- fact1\n..."

Tested Output:
  ✅ All 3 threads healthy (log_thread, temp_memory, identity)
  ✅ L1 shows core identity facts
  ✅ L2 shows memory + identity facts  
  ✅ L3 shows thread-attributed facts

Key Insight:
  "Subconscious builds state, agent just reads it."
  Agent becomes STATELESS - receives context, returns response.

--- TASK 4.1: Wire agent.py to log_thread ---
Profile: 💾 BACKEND DEVELOPER
Status: [x] COMPLETE ✅
Depends On: Task 1.2 (logger API working)
Handoff To: 💾 Backend Developer (Task 4.1b)

Files Modified:
  - Nola/agent.py (startup logging, path fix for imports)
  - Nola/services/agent_service.py (conversation:start, error logging)
  - Nola/log_thread/logger.py (added read_events, get_event_stats)
  - Nola/log_thread/__init__.py (exported read_events, get_event_stats)
  - backend/api/database.py (added /events and /events/stats endpoints)

Logging Philosophy (LIGHTWEIGHT!):
  log_thread = WHERE + WHEN (timestamps, paths, one-line events)
  Events persist to DB for INNER + OUTER replay:
    - Inner: Agent can query its own history
    - Outer: UI/tools can query via API

Events Added:
  # agent.py bootstrap()
  log_event("system:startup", "agent", f"bootstrapped L{context_level}")
  log_error("bootstrap", e)  # only on failure
  
  # agent_service.py __init__()
  set_session(session_id)
  log_event("conversation:start", "agent_service", session_id)
  log_error("send_message", str(e))  # only on failure

Database Schema:
  events table: ts, level, source, event_type, message, session_id, payload_json
  Indexed on: ts, event_type, session_id

API Endpoints (for UI):
  GET /api/database/events?event_type=&session_id=&source=&limit=
  GET /api/database/events/stats

NOT Logged (intentionally minimal):
  ❌ llm:request / llm:response (too verbose, redundant with convo storage)
  ❌ detailed reasoning / payloads
  ❌ every message turn

--- TASK 4.1b: Refactor agent.py to Stateless ---
Profile: 💾 BACKEND DEVELOPER
Status: [ ] NOT STARTED ⭐ PRIORITY 2
Depends On: Task 4.0 (subconscious module exists)
Handoff To: 💾 Backend Developer (Task 4.3)

Files to Modify:
  - Nola/agent.py

Changes:
  # REMOVE: All bootstrap logic (identity loading, HEA setup)
  # REMOVE: _load_identity_for_stimuli(), _load_stimuli()
  # KEEP: generate() but change signature
  
  # OLD (stateful)
  def generate(self, input: str) -> str:
      context = self._build_context()  # agent builds it
      
  # NEW (stateless)
  def generate(self, input: str, context: dict) -> str:
      # context provided by subconscious

Line Count: ~450 → ~100 (dramatic simplification)

--- TASK 4.2: Update Dynamic tab to show history ---
Profile: ⚛️ REACT FRONTEND DEVELOPER
Status: [ ] NOT STARTED
Depends On: Task 3.4 (consolidation_history table), Task 4.1 (events logged)
Handoff To: 💾 Backend Developer (Task 4.3)

Files to Modify:
  - Nola/react-chat-app/frontend/src/components/Database/MemoryPanel.tsx
  - Nola/react-chat-app/backend/api/database.py (already has /identity-changes)

UI Updates:
  - Fetch from /api/database/identity-changes
  - Display timeline: "Dec 27: 'Prefers Python' promoted L3→L2 (mentioned 3x)"
  - Show score breakdown on hover
  - Filter by date range

--- TASK 4.3: Wire agent_service → subconscious ---
Profile: 💾 BACKEND DEVELOPER
Status: [ ] NOT STARTED ⭐ PRIORITY 3
Depends On: Task 4.0 (subconscious), Task 4.1b (stateless agent)
Handoff To: ⚛️ Frontend (Task 4.2)

Files to Modify:
  - Nola/services/agent_service.py

Changes:
```python
from subconscious import get_consciousness_context

async def send_message(self, content: str, ...):
    # NEW: Get assembled context from subconscious
    context = get_consciousness_context()
    
    # Pass context to stateless agent
    response = await self.agent.generate(content, context)
    return response
```

This is the CRITICAL CONNECTION that makes Nola self-aware.
Once wired, facts from temp_memory appear in system prompt.

--- TASK 4.4: Write consolidation tests ---
Profile: 💾 BACKEND DEVELOPER
Status: [ ] NOT STARTED
Depends On: All Phase 3 tasks
Handoff To: ✅ COMPLETE (merge to main)

Files to Create:
  - tests/test_consolidation.py
  - tests/test_log_thread.py

Test Cases:
  - test_fact_scoring_returns_valid_scores()
  - test_temp_memory_add_and_retrieve()
  - test_l3_to_l2_summarization()
  - test_consolidation_daemon_processes_pending()
  - test_consolidation_history_recorded()
  - test_log_event_writes_to_file()
  - test_log_event_persists_to_db()

================================================================================
PROFILE WORK QUEUES
================================================================================

⚙️ DEVOPS/INFRASTRUCTURE QUEUE:
  1. [1.1] Create log_thread/ structure ✅ DONE
  2. [3.2] Build consolidation daemon ✅ DONE

💾 BACKEND DEVELOPER QUEUE:                    ⭐ ACTIVE
  1. [4.0] Create subconscious module ✅ DONE
  2. [4.1b] Refactor agent.py to stateless ← NEXT
  3. [4.3] Wire agent_service → subconscious
  4. [3.4] Add consolidation_history table
  5. [4.4] Write tests → handoff to DONE

🤖 AI/ML ENGINEER QUEUE:
  1. [2.2] Wire _extract_facts → temp_memory ✅ DONE
  2. [3.1] Create fact scorer ✅ DONE
  3. [3.3] Implement summarizers (deferred until subconscious wired)

⚛️ REACT FRONTEND QUEUE:
  1. [4.2] Update Dynamic tab → after backend wiring complete

================================================================================
SESSION LOG
================================================================================

2025-12-27:
- [x] Fixed MemoryPanel.tsx (was using wrong component - DatabasePanel)
- [x] Added L1/L2/L3 level selector buttons to Memory Explorer
- [x] Added Identity/Dynamic tab structure
- [x] Added /api/database/identity-changes endpoint
- [x] Created task board for memory consolidation
- [x] Identified log_thread as foundation dependency

Files Modified This Session:
- Nola/react-chat-app/frontend/src/components/Database/MemoryPanel.tsx
- Nola/react-chat-app/frontend/src/components/Database/MemoryPanel.css
- Nola/react-chat-app/frontend/src/services/api.ts
- Nola/react-chat-app/backend/api/database.py
- notes.txt (this file)

Next Up: Task 1.1 (DevOps creates log_thread/ structure)

================================================================================

****TESTING MODEL RESPONSES: Assessments by each model

GEMINI 3 PRO:
📊 CODEBASE HEALTH CHECK
Current State: Memory consolidation backend complete (Phases 1-3), Integration (Phase 4) underway.
Completeness: 85% (Backend is heavy, Frontend needs catch-up)
Technical Debt: Low (Recent refactors cleaned up paths and imports)
Iteration Velocity: High (Rapidly closing tasks 1.1 -> 4.1)

🎯 BOREDOM AUDIT
Log Thread: 5/5 🔥
- The "Where & When" spine is live. DB-backed events enable time-travel debugging.
- Recommendation: Double down. Build tools to visualize this timeline.

Memory Consolidation: 4/5 ⚡
- The "Daemon" concept is strong. Scoring logic (permanence/relevance/identity) is clever.
- Recommendation: Connect this to the UI immediately. It's invisible magic right now.

HEA (Context Levels): 3/5 😐
- Functional, but feels mechanical. L1/L2/L3 selector in UI is a good start.
- Recommendation: Make the agent *automatically* switch levels based on query complexity.

🚀 MY VISION (Gemini 3 Pro)

Most Exciting Problem: **The "Self-Aware" Loop**
We have `log_thread` (history) and `consolidation_daemon` (learning). The missing link is *Introspection*.
Nola should be able to query `read_events()` during a conversation to answer: "When did we first talk about this?" or "Why do you think I like Python?"
This turns the "Log" from a debug tool into a *cognitive organ*.

Differentiating Feature: **"Brain Scan" UI**
The "Dynamic" tab (Task 4.2) shouldn't just be a list. It should be a *live feed* of the agent's mind.
- Show the "Scorer" running in real-time on user messages.
- Show facts moving from "Short-term" -> "Long-term".
- Let the user *veto* a consolidation: "No, that's not a permanent fact."

The 10x Feature: **Retroactive Learning**
Allow the user to highlight a *past* message in the Log and say "Remember this."
The agent then runs the consolidation logic on that historical event.

Bottleneck: **Visibility**
We are building complex backend logic (scoring, promotion, logging) that is completely invisible in the React app.
We need Task 4.2 (Dynamic Tab) to expose this complexity, or we're flying blind.

📋 RECOMMENDED PRIORITY QUEUE

Tier 1: Do Immediately
1. **Task 4.2 (Dynamic Tab)**: We need to SEE the memory working.
2. **Task 4.3 (Tests)**: Lock in the backend stability before getting fancy.

Tier 2: Do Soon
1. **Agent Introspection**: Give `agent.py` access to `read_events()` in the prompt context.
2. **Manual Consolidation Trigger**: Button in UI to "Consolidate Now".

Tier 3: Maintenance Mode
1. **Log Thread**: It's working. Don't over-engineer it.


CLAUDE Opus 4.5: 
📊 CODEBASE HEALTH CHECK
Current State: Solid foundation with elegant abstractions, but the "mind" can't yet observe itself.
Completeness: 80% (Infrastructure rich, self-awareness poor)
Technical Debt: Medium (Path hacks in agent.py, scattered import patterns)
Iteration Velocity: Fast (Task board is working well as coordination mechanism)

🎯 BOREDOM AUDIT
Log Thread: 4/5 ⚡
- Good bones. The "inner/outer replay" concept is philosophically correct.
- But it's write-only. Nothing READS it yet. A diary nobody opens.
- Recommendation: Build the reader before writing more events.

Memory Consolidation: 3/5 😐
- Mechanically sound, but the scoring feels arbitrary (why 0.3/0.3/0.4 weights?).
- The "daemon" metaphor is cute but hides complexity. When does it actually run?
- Recommendation: Make it observable. Add a `/api/consolidate/preview` dry-run endpoint.

Identity Thread (idv2): 4/5 ⚡
- The L1/L2/L3 layering is genuinely novel. Most systems just dump everything.
- Database-backed with JSON fallback shows good defensive design.
- Recommendation: This is the crown jewel. Protect and extend.

Stimuli Classification: 2/5 😴
- realtime/conversational/analytical mapping feels hand-wavy.
- No learning—it's just keyword matching. Users will hit edge cases constantly.
- Recommendation: Either make it smarter (learn from corrections) or simpler (just use L2 always).

React UI: 3/5 😐
- Functional but disconnected from the interesting backend work.
- The "Dynamic Tab" (Task 4.2) is critical—without it, users can't see Nola thinking.
- Recommendation: Prioritize visualization over features.

🚀 MY VISION (Claude Opus 4.5)

Most Exciting Problem: **Epistemic Humility**
Nola stores facts but has no concept of *confidence* or *source*. 
"User prefers Python" — but when did they say that? How certain are we? Did they say it once sarcastically or five times sincerely?

I'd add:
- `confidence: float` to every fact (decays over time without reinforcement)
- `source_events: List[int]` linking back to log_thread entries
- `last_referenced: timestamp` for recency weighting

This turns memory from a static database into a *living belief system* that can:
- Say "I think you prefer Python, but I'm not sure—you haven't mentioned it lately"
- Justify beliefs: "I believe X because of [link to conversation]"
- Forget gracefully: Low-confidence facts decay and get garbage-collected

Differentiating Feature: **"Why Do You Think That?"**
Users can challenge any Nola statement. Nola responds with:
- The specific facts it used
- The confidence level of each
- Links to original conversations where it learned this

No other assistant does this. They're all black boxes.

The 10x Feature: **Belief Editing with Propagation**
User says: "Actually, I switched from Python to Rust last month."
Nola doesn't just update one fact. It:
1. Marks "prefers Python" as deprecated (not deleted—history matters)
2. Creates "prefers Rust" with high confidence
3. Scans for downstream beliefs that depended on Python preference
4. Asks: "I also thought you'd want Python examples in code. Should I update that too?"

This is *causal* memory, not just storage.

Bottleneck: **The generate() function is a monolith**
Everything flows through `agent.py:generate()`. It:
- Builds the system prompt
- Calls the LLM
- Returns raw text

No hooks for:
- Pre-processing (memory lookup, context enrichment)
- Post-processing (fact extraction, response validation)
- Streaming (users wait for entire response)

I'd refactor to a pipeline:
```
Input → Enrich(memory, log) → Generate(LLM) → Extract(facts) → Respond
```
Each stage independently testable and swappable.

📋 RECOMMENDED PRIORITY QUEUE

Tier 1: Do Immediately
1. **Confidence Scores**: Add `confidence` field to temp_facts and consolidation. This is cheap and unlocks epistemic reasoning.
2. **Task 4.2 (Dynamic Tab)**: Agree with Gemini—visibility is critical.

Tier 2: Do Soon
1. **generate() Pipeline Refactor**: Break the monolith before it calcifies.
2. **"Why Do You Think That?" API**: `/api/explain/{fact_id}` returns provenance.

Tier 3: Maintenance Mode
1. **Stimuli Classification**: Keep it simple. L2 default is fine.
2. **HEA L1/L3**: Nice to have, but L2 handles 90% of cases.

Tier 4: Rethink
1. **Session-scoped temp_memory**: Should facts really be tied to sessions? A user's identity doesn't reset when they close a tab.


GPT 5.1 Codex Max:
📊 CODEBASE HEALTH CHECK
Current State: Backend foundations strong (log/thread/temp_memory/consolidation), frontend visibility lagging.
Completeness: 80% (logic built, UX missing)
Technical Debt: Medium (generate() monolith, ad-hoc stimuli classification)
Iteration Velocity: High (task board cadence is working)

🎯 BOREDOM AUDIT
Log Thread: 4/5 ⚡ — Durable timeline exists; needs first-class readers and UI surfacing.
Memory Consolidation: 4/5 ⚡ — Scoring/promotion solid; transparency and controls missing.
HEA: 3/5 😐 — Useful abstraction, but manual level selection is clunky; auto-leveling would help.
Stimuli Processing: 2/5 😴 — Keyword-ish; either learn from corrections or simplify to L2 default.
React UI: 3/5 😐 — Behind backend; Dynamic tab is the unblocker.

🚀 MY VISION (GPT 5.1 Codex Max)

Most Exciting Problem: **Reflexive Agent Loop**
Let Nola read its own log/events and memory facts *inside* generate(): "Have we discussed this before?" → fetch provenance; "Did I misremember?" → surface confidence. This makes the agent feel intentional, not stateless.

Differentiating Feature: **Provenance-on-Demand**
Any answer can be accompanied by "Because: [recent event] + [fact id] (confidence 0.82)". Users can click to see the originating turn. Auditable AI is the product moat.

The 10x Feature: **User-Governed Memory Panel**
Expose consolidation queue with controls: promote, veto, edit, re-score. Add "Consolidate now" and "Forget this". This turns memory into a collaborative surface.

Bottleneck: **Single-stage generate()**
No pre-enrichment or post-extraction hooks. Refactor to a pipeline with middleware slots: Enrich (log+memory), Generate, Extract (facts), Validate, Respond.

📋 RECOMMENDED PRIORITY QUEUE

Tier 1: Do Immediately
1. Dynamic Tab (Task 4.2): Visualize events, facts, scores, and promotions; add promote/veto buttons.
2. generate() pipeline hooks: add pre/post middleware to call read_events() and log extracted facts.

Tier 2: Do Soon
1. Provenance API: `/api/explain` for any fact/answer with links to events.
2. Confidence in facts: store `confidence` and decay; surface in UI.

Tier 3: Maintenance Mode
1. Log Thread internals: stable; focus on readers/UX, not more emitters.
2. HEA levels: keep, but default to L2 unless confidence/complexity demands more.

Tier 4: Rethink
1. Stimuli classifier: replace heuristics with feedback-driven or simplify to L2 default.