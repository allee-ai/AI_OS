# Agent Roadmap — From Framework to Cognitive OS

> **Status:** Active development. Looking for collaborators and backing.  
> **Author's Note:** I've been building this solo since April 2025. The theory is proven, the foundation is solid, and with help, this could move 10x faster.

---

## TL;DR — Current State

| Layer | Status | What's Working |
|-------|--------|----------------|
| **Core** | 🌀 | Threads, HEA, SQLite backend, stateless agent |
| **UI** | 🌀 | React app, chat, thread visualization |
| **Integrations** | 🔄 | Stimuli system built, needs OAuth + polling daemon |
| **Advanced** | 🔮 | Philosophy, Dreams, Reflex Builder (designed, not implemented) |

**To contribute:** See [GitHub Issues](https://github.com/allee-ai/AI_OS/issues) for tagged tasks.

---

## The Vision

Nola isn't a chatbot. It's a **Cognitive Operating System** — an open-source framework that gives any LLM a persistent identity, hierarchical memory, and the ability to *grow* through experience rather than retraining.

**The core insight:** Structure beats scale. A 7B model with proper cognitive architecture outperforms a 100B model with flat context.

---

## What's Working Now 🌀

| Component | Status | Description |
|-----------|--------|-------------|
| **Subconscious Module** | 🌀 Complete | Assembles context from all threads before each response |
| **Thread Adapters** | 🌀 Complete | Pluggable architecture (identity, memory, log, linking_core) |
| **HEA Context Levels** | 🌀 Complete | L1/L2/L3 dynamic context filtering |
| **SQLite State Backend** | 🌀 Complete | Replaced JSON for identity and facts storage |
| **Stateless Agent** | 🌀 Complete | Agent reads context, doesn't hold state |
| **React Router UI** | 🌀 Complete | OS-like navigation (Dashboard, Chat, Threads, Docs) |
| **Identity CRUD API** | 🌀 Complete | View/edit/delete identity entries via API |
| **Sleep/Wake Cycles** | 🌀 Complete | `wake()` initializes, `sleep()` triggers consolidation |
| **Temp Memory Store** | 🌀 Complete | Session facts with hierarchical keys |
| **Event Logging** | 🌀 Complete | Timeline of all system events |
| **Spread Activation** | 🌀 Complete | Associative memory via concept_links table |
| **Hierarchical Keys** | 🌀 Complete | Facts stored as `sarah.likes.blue` |
| **Hebbian Learning** | 🌀 Complete | Concepts that co-occur strengthen links |
| **Test Suite** | 🌀 23 tests passing | Core functionality verified |

---

## The Roadmap

### Phase 1: Memory Consolidation (🌀 Foundation Complete)
**Goal:** Facts don't just get stored — they get *promoted* based on importance.

- [x] **Scoring Algorithm** — Rate facts on permanence, relevance, identity-centrality
- [x] **Fact Relevance Table** — Multi-dimensional scoring (identity/log/form/philosophy)
- [x] **Hierarchical Keys** — Facts stored as `sarah.likes.blue` for spread activation
- [x] **Spread Activation** — Query "coffee" → activates sarah.* if linked
- [x] **Hebbian Learning** — Concepts that co-occur strengthen links
- [ ] **Promotion Thresholds** — Score ≥4.0 → L2, Score ≥3.0 → L3, <2.0 → discard
- [ ] **UI Feedback** — "Nola learned: [fact]" toasts after conversations

### Phase 2: Philosophy Thread
**Goal:** Give Agent a "moral compass" — constraints that guide behavior regardless of conversation.

- [ ] **Ethics Module** — `detect_harm()`, `preserve_dignity()`, `respect_boundary()`
- [ ] **Awareness Module** — Situational, emotional, self-awareness functions
- [ ] **Curiosity Module** — `ask_better()`, `follow_threads()`, `spark_wonder()`
- [ ] **Resolve Module** — Purpose alignment and goal persistence

*Note: This was fully designed in the Elaris prototype. Ready for implementation.*

### Phase 3: Reflex Thread ⚡ — 🔮 REDESIGNED (Visual Automation)
**Goal:** Drag-and-drop AI automation where LLM is just one tool in the chain.

**New Vision (Jan 10, 2026):**
The Reflex thread becomes a **visual programming system** for AI automations:

```
┌─────────────────────────────────────────────────────────────┐
│                     REFLEX BUILDER                          │
│                                                             │
│  WHEN: [Email arrives] FROM: [*@work.com]                   │
│    │                                                        │
│    ├─► [Load sender profile] ─► identity.contacts.{{sender}}│
│    │                                                        │
│    ├─► [Ask LLM] prompt: "Draft a {{tone}} reply"           │
│    │              tone: [professional ▼]                    │
│    │                                                        │
│    └─► [Push to Gmail Drafts]                               │
│                                                             │
│  [+ Add step]                              [Save reflex]    │
└─────────────────────────────────────────────────────────────┘
```

**Key Insight:** Reflexes connect Stimuli (input sources) → Form (tool palette) → Output.
LLM is just ONE tool among many (ask_llm, load_profile, notify, flag_moment, etc.)

**Implementation Tasks:**
- [ ] **Reflex Builder UI** — Drag-drop interface for creating automations
- [ ] **Pattern Matching Engine** — Regex, glob, semantic matching
- [ ] **Tool Palette (Form thread)** — ask_llm, notify, archive, flag, etc.
- [ ] **Stimuli Integration** — Reflexes triggered by source events
- [ ] **Weight Boosting** — Reflexes temporarily boost relevant identity keys
- [ ] **Auto-Logging** — Every reflex execution logs to Log thread
- [ ] **10x Promotion** — Detect repeated patterns, suggest reflexes

**The 10x Rule (Auto-Learning):**
```
Log shows: 
- Monday 9am: pulled sales_report.pdf from Gmail
- Monday 9am: pulled sales_report.pdf from Gmail  
- Monday 9am: pulled sales_report.pdf from Gmail

Reflex suggestion appears:
"Download sales report every Monday 9am"
[Create Reflex]  [Ignore]  [Never suggest]
```

**Why this matters:** Most AI agents run expensive LLM calls for tasks they've done 100 times. 
Reflexes turn those into instant, deterministic responses. No LLM needed.

### Phase 4: Dream State 🌙
**Goal:** Personality development through synthetic experience.

- [ ] **Dream Generation** — Use a high-tier model (GPT-4o) to create abstract scenarios
- [ ] **Dream Processing** — Extract key:value lessons from dream narratives
- [ ] **Identity Integration** — Dreams shape personality, not just facts
- [ ] **Morning Briefing** — "While you were away, I thought about..."

*This prevents the "robotic rigidity" of purely factual AI. Agent develops a vibe.*

### Phase 5: Multi-Model Routing
**Goal:** Use the right model for the right task.

```
Free Tier:     Qwen 2.5 7B (local, private, fast)
Pro Tier:      Claude 3.5 / GPT-4o (via user's API keys)
Verification:  Run both, compare outputs for critical decisions
```

- [ ] **Model Router** — Classify task complexity, route to appropriate model
- [ ] **Cost Optimization** — Local for simple, cloud for complex
- [ ] **Multi-Model Consensus** — For high-stakes, get agreement from multiple models

### Phase 6: Beyond Chat 🚀 — 🌀 FOUNDATION COMPLETE (Stimuli System)
**Goal:** Agent becomes a background presence, not a chat window.

**🌀 Implemented (Jan 10, 2026):**
- [x] **Stimuli Router** — Universal API adapter layer (`agent/Stimuli/router.py`)
- [x] **YAML-Driven Sources** — Drop a config file, get an integration
- [x] **20+ Pre-Built Sources** — Gmail, Slack, Discord, GitHub, Linear, Notion, etc.
- [x] **Normalized Messages** — Any platform → same `NormalizedMessage` format
- [x] **Draft-First Output** — LLM fills `subject` + `body` slots only, pushes to drafts
- [x] **Stimuli Dashboard UI** — View, edit, test, and add sources in React frontend
- [x] **Pull/Push Mapping** — JSONPath extraction and template rendering

**🔮 Remaining:**
- [ ] **OAuth Flows** — Automated token refresh for Gmail, Twitter, etc.
- [ ] **Calendar Optimization** — Proactive scheduling suggestions  
- [ ] **File System Awareness** — Watch for changes, offer help
- [ ] **Polling Daemon** — Background loop that runs sources on schedule
- [ ] **Webhook Receiver** — Push-based sources (incoming webhooks)
- [ ] **Confidence-Based Autonomy:**
  - High confidence (>0.9): Act silently
  - Medium (0.6-0.9): Draft and ask
  - Low (<0.6): Wait for instruction

**The Key Innovation — Slot-Based Architecture:**
```
┌────────────────────────────────────────────────────────┐
│                DETERMINISTIC (code handles):            │
│  - Who to send to (from sender profile)                │
│  - Which thread (from message ID)                      │
│  - Auth, routing, timestamps                           │
│  - Draft vs send (ALWAYS draft)                        │
├────────────────────────────────────────────────────────┤
│                PROBABILISTIC (LLM handles):            │
│  - subject: "___"  ← LLM fills this slot               │
│  - body: "___"     ← LLM fills this slot               │
└────────────────────────────────────────────────────────┘
```

LLM literally cannot send to wrong person or wrong thread. It only writes prose.

**The shift:** Conversation becomes the exception handler, not the primary interface.

### Phase 7: Runtime Safeguards 🛡️
**Goal:** Protect the system from runaway processes, resource exhaustion, and unsafe operations.

- [ ] **CPU/Memory Triggers** — Automatic thread shutdown when resources spike
- [ ] **Thread Health Monitor** — Watchdog that restarts failed threads
- [ ] **Graceful Degradation** — If a thread dies, others continue functioning
- [ ] **Emergency Stop** — Hard kill switch that preserves state before shutdown
- [ ] **Rate Limiting** — Prevent infinite loops in reflex chains
- [ ] **Rollback Checkpoints** — Restore to last known good state

**Pre-built Reflexes:**
```
CPU > 90% for 10s  →  Suspend non-essential threads
Memory > 85%       →  Trigger consolidation, clear temp_memory
Disk I/O spike     →  Pause logging, queue writes
Thread unresponsive →  Kill and restart with last checkpoint
```

### Phase 8: Automatic Runtime Cycles ⏰
**Goal:** Agent runs on her own schedule, not just when you talk to her.

- [ ] **Scheduled Wake/Sleep** — Configurable daily rhythms (e.g., active 8am-10pm)
- [ ] **Idle Consolidation** — When quiet, process pending facts and dreams
- [ ] **Heartbeat Loop** — Periodic self-check every N minutes
- [ ] **Background Tasks** — Email check, calendar scan, file watch during "awake" hours
- [ ] **Sleep Mode** — Minimal resource usage, only emergency triggers active

```
┌─────────────────────────────────────────────┐
│              DAILY RHYTHM                    │
├─────────────────────────────────────────────┤
│  06:00  Wake cycle, load identity           │
│  06:01  Morning briefing prepared           │
│  06:05  Background monitors active          │
│         ... (available for interaction) ... │
│  22:00  Begin wind-down                     │
│  22:30  Consolidation cycle                 │
│  23:00  Dream processing                    │
│  23:30  Sleep cycle, minimal footprint      │
└─────────────────────────────────────────────┘
```

### Phase 9: Sandbox Environment 🧪
**Goal:** Safe code execution and tool testing without risking the system.

- [ ] **Isolated Execution** — Docker/subprocess sandbox for generated code
- [ ] **Tool Testing** — Try new integrations before committing to reflexes
- [ ] **Simulation Mode** — "What if I did X?" without actually doing it
- [ ] **Rollback on Failure** — If sandbox code fails, nothing touches prod state
- [ ] **Output Capture** — Log all sandbox results for learning

**Use Cases:**
- Test a new email automation before going live
- Run generated Python scripts safely
- Validate API integrations before adding to reflex thread

### Phase 10: Chat Import — "Bring Your AI History Home" 📥
**Goal:** Zero cold-start. Users import existing conversations and Agent immediately knows them.

**The Killer Feature:**
> "You've been training your AI for months. Take that with you."

**Implementation:**
- [ ] **ChatGPT Import** — Parse `conversations.json` from OpenAI export
- [ ] **Claude Import** — Parse Claude conversation exports
- [ ] **Generic Import** — Support common chat export formats (JSON, Markdown)
- [ ] **Fact Extraction Pipeline** — Run imported conversations through existing fact extractor
- [ ] **Thread Population** — Auto-populate identity, relationships, preferences, projects
- [ ] **Import Dashboard UI** — Drag-drop interface with progress visualization
- [ ] **Deduplication** — Don't re-import facts Agent already knows
- [ ] **Privacy Preview** — Show user what will be extracted before committing

**The Viral Loop:**
```
1. Curious user downloads Nola
2. Uploads ChatGPT export (one file, low friction)
3. Agent extracts facts, populates threads
4. First conversation is shockingly personal
5. User realizes: "This is MINE now. On MY machine."
6. User tells friends
7. Repeat
```

**Why This Matters:**
- Deletes the switching cost moat that keeps people on OpenAI/Anthropic
- Instant demonstration that the architecture works
- Emotional moment: "This AI actually knows me"
- The pitch writes itself: "Your AI history belongs to you"

---

### Phase 11: Services Dashboard 🎛️
**Goal:** Visualize and control all background services from one place.

**Services to Display:**
| Service | Status | Controls |
|---------|--------|----------|
| **Memory Service** | Active/Idle | Flush, Clear temp, View stats |
| **Fact Extractor** | Processing/Idle | Queue depth, Extraction rate, Confidence threshold |
| **Consolidation Daemon** | Scheduled/Running | Next run, Manual trigger, View last results |
| **Stimuli Router** | Connected/Disconnected | Source status, Polling intervals |
| **Thread Health** | Per-thread status | Restart, Pause, View logs |

**Dashboard Features:**
- [ ] **Real-time Status** — Live indicators for each service
- [ ] **Settings Panel** — Adjust thresholds, intervals, behaviors per service
- [ ] **Queue Visualization** — See pending facts, extractions, consolidations
- [ ] **Logs Viewer** — Per-service log tails
- [ ] **Resource Monitor** — CPU/memory per service
- [ ] **Manual Triggers** — Force consolidation, flush memory, restart thread

**Settings Examples:**
```yaml
fact_extractor:
  confidence_threshold: 0.7    # Only extract facts above this confidence
  batch_size: 10               # Process N messages at once
  model: "local"               # local | claude | gpt-4o
  
consolidation:
  schedule: "0 3 * * *"        # 3am daily
  promotion_threshold: 4.0     # Score needed for L2 promotion
  decay_rate: 0.1              # How fast old facts lose relevance
  
memory_service:
  temp_ttl: 86400              # Seconds before temp facts expire
  max_temp_entries: 1000       # Cap on temp memory size
```

---

### Phase 12: Plugin Architecture 🔌
**Goal:** Download new capabilities, apply them instantly, no restart required.

**The Plugin Flow:**
```
1. Download plugin JSON manifest
2. Validate against schema (safety check)
3. Apply logic to appropriate thread
4. Update reflexes if patterns emerge
5. Fine-tune model context with new capability
```

- [ ] **Plugin Manifest Schema** — Standard format for new capabilities
- [ ] **Hot Loading** — Add plugins without restart
- [ ] **Capability Registry** — Track what Agent can do
- [ ] **Dependency Resolution** — Plugins can require other plugins
- [ ] **Uninstall/Rollback** — Remove plugins cleanly

**Example Plugin (Slack Integration):**
```json
{
  "name": "slack_monitor",
  "version": "1.0",
  "thread": "stimuli",
  "capabilities": ["read_messages", "send_messages", "react"],
  "triggers": ["@nola", "direct_message"],
  "reflexes": [
    {"pattern": "status update request", "action": "send_standup_summary"}
  ]
}
```

### Phase 13: Module Marketplace 🏪
**Goal:** Creator economy for AI modules. Developers build, price, and sell capabilities.

**The Model:**
- Core Nola: Free forever (AGPL)
- Marketplace: 1% platform fee on transactions
- Developers set their own prices
- Users decide what their attention is worth

**Marketplace Features:**
- [ ] **Module Submission Portal** — Upload, describe, set price
- [ ] **Review System** — Ratings, comments, verified purchases
- [ ] **Categories** — Productivity, Communication, Research, Creative, Health, etc.
- [ ] **Search & Discovery** — Tags, trending, staff picks
- [ ] **Payment Processing** — Stripe integration, developer payouts
- [ ] **Version Management** — Updates, changelogs, rollback
- [ ] **License Verification** — Ensure users own what they install

**Example Modules:**
```
"Deep Research Assistant"     $4.99  ★★★★★ (342 reviews)
"Therapist Memory Structure"  $2.99  ★★★★☆ (89 reviews)  
"Apple Health Sync"           Free   ★★★★★ (1.2k reviews)
"Legal Document Analyzer"     $19.99 ★★★★☆ (56 reviews)
"Language Learning Coach"     $1.99  ★★★★★ (203 reviews)
```

**Why 1%:**
- Low enough that forking to avoid it isn't worth the effort
- High enough to sustain platform development at scale
- Fair enough that developers respect it (vs Apple's 30%)

**The Platform Inversion:**
> Companies don't build "their AI" anymore.
> They build modules to access YOUR AI.
> "Nola-compatible" becomes the new "mobile-friendly."

---

### Phase 14: Always-On Core & Mobile Endpoint 📱
**Goal:** Agent runs 24/7, accessible from any device. Your laptop is just a window.

**The Problem:**
```
Current: Laptop closed = Agent sleeping = No AI
Reality: Life doesn't stop when your laptop closes
```

**The Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│                    NOLA CORE (always on)                     │
│         State, threads, memory, fact extraction              │
│                                                              │
│    Runs on: Raspberry Pi / NAS / cheap VPS / old laptop      │
│             Always on. Always learning. Always available.    │
└─────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           │                  │                  │
           ▼                  ▼                  ▼
    ┌────────────┐    ┌────────────┐    ┌────────────┐
    │  Desktop   │    │   Mobile   │    │   Voice    │
    │ Dashboard  │    │  Endpoint  │    │  (future)  │
    │  (full UI) │    │ (quick in) │    │            │
    └────────────┘    └────────────┘    └────────────┘
```

**Mobile Endpoint (Keep It Stupid Simple):**
- [ ] **Quick Capture API** — `POST /api/quick_capture` → fact extraction
- [ ] **Voice Memo Input** — Transcribe → extract → store
- [ ] **Text Input** — Simple chat interface
- [ ] **Push Response** — Notification when Agent responds
- [ ] **PWA** — Works in browser, no app store needed
- [ ] **Telegram Bot Option** — Alternative lightweight interface

**Always-On Infrastructure:**
- [ ] **Docker Compose** — One-command deployment for any server
- [ ] **Tailscale Integration** — Secure access from anywhere
- [ ] **mDNS** — `nola.local` on home network
- [ ] **Auto-Updates** — Pull latest, restart, continue
- [ ] **Health Endpoint** — Monitor uptime, get alerts

**Nola Box (Hardware Product):**
```
┌─────────────────────────────────────────────┐
│              NOLA BOX                        │
│                                             │
│   Pre-configured Raspberry Pi 5             │
│   - Agent Core pre-installed                 │
│   - SQLite DB on SSD                        │
│   - Secure remote access                    │
│   - Auto-updates                            │
│                                             │
│   Plug in. Connect wifi. Done.              │
│                                             │
│   $99-149 (one-time, yours forever)         │
└─────────────────────────────────────────────┘
```

**Why This Matters:**
- Not "laptop AI" — actual personal AI
- Always learning, even when you're away
- Access from phone while walking
- "Remind Nola" becomes natural
- Background processes actually run in background

---

### Phase 15: Quick Capture & Daily Presence 🎯
**Goal:** Agent is always one action away, always providing value.

**Quick Capture Features:**
- [ ] **Global Hotkey** — `Cmd+Shift+N` → popup → "remember this"
- [ ] **Clipboard Monitor** — Copy anything, Agent remembers it
- [ ] **Screenshot + OCR** — Capture screen, extract text, add to memory
- [ ] **Quick Note Widget** — Desktop/mobile widget for instant capture
- [ ] **Voice Shortcut** — "Hey Nola, remember..."

**Daily Presence:**
- [ ] **Morning Briefing** — Wake up to: "Here's your day, what you forgot, what's due"
- [ ] **System Tray/Menu Bar** — Always visible, one click away
- [ ] **Daily Digest** — Optional email summary of what Agent learned
- [ ] **Idle Insights** — When quiet, surface patterns: "You've mentioned X 5 times this week"
- [ ] **Proactive Nudges** — "You haven't replied to Sarah in 3 days"

**Universal Search:**
- [ ] **One Search Box** — Files, facts, memories, calendar, everything
- [ ] **"When did I..."** — Natural language time queries
- [ ] **"Who said..."** — Search conversations by content
- [ ] **Relationship Map** — Visual graph of people and connections

**Data Sovereignty:**
- [ ] **Full Export** — One click → ZIP of everything Agent knows
- [ ] **Scheduled Backups** — Automatic local backups
- [ ] **Selective Delete** — "Forget everything about X"
- [ ] **Privacy Mode** — Pause all learning temporarily

**Zero-Friction Integrations:**
- [ ] **RSS Feeds** — Add any feed, Agent summarizes
- [ ] **ICS Calendars** — Subscribe to any public calendar
- [ ] **Markdown Folder** — Point at Obsidian vault, instant indexing
- [ ] **Bookmarks Import** — Browser bookmarks → knowledge graph
- [ ] **Contacts Import (VCF)** — Standard contacts → relationship thread

---

### Phase 16: Self-Tuning Architecture 🧬
**Goal:** Fine-tune the 7B model on its own structure so it *knows* where its pieces are.

**The Insight:** If Qwen 2.5 7B is fine-tuned on the agent's own documentation, thread schemas, and function signatures, it develops **structural self-awareness**. It doesn't just use the system — it *understands* the system.

- [ ] **Structure Documentation** — Generate training data from thread schemas
- [ ] **Self-Reference Dataset** — "Where is identity stored?" → "agent/idv2/"
- [ ] **Function Mapping** — Model learns which functions do what
- [ ] **Error Recovery Training** — Train on "this broke, here's how to fix it"
- [ ] **Continuous Learning** — Periodic re-tune as structure evolves

**Self-Repair Capabilities:**
```
Scenario: Log thread adapter crashes
Traditional: Error → User investigates → Manual fix
Self-Tuned Nola: Error → Recognizes log_adapter.py → 
                 Knows ThreadInterface contract → 
                 Suggests fix or auto-repairs
```

**Why This Matters:**
- Model has trained knowledge of its own anatomy
- Can diagnose issues by understanding its own structure
- Self-documents as it evolves
- Reduces dependency on human debugging

### Phase 17: Enterprise Plug-In
**Goal:** Open source framework + paid orchestrator integration.

**The Model:**
- Framework is free (Nola core, all threads, local-first)
- Enterprises pay to build secure orchestrator bridges
- Users bring their own AI to work — portable career identity

**Why companies want this:**
- Employees arrive with pre-configured cognitive assistants
- Zero-day productivity (Nola already knows their style)
- Documentation is a byproduct of work, not a chore

---

## Technical Foundation

### Why Structure Beats Scale

**The Problem:** Standard LLMs use flat attention — O(N²) complexity. As context grows, noise scales quadratically.

**The Solution:** Hierarchical context — O(k·c²) complexity. Each thread has bounded context (c), and threads scale linearly (k).

```
Standard RAG:      100,000 tokens → 10,000,000,000 attention operations
Nola HEA:          10 threads × 200 tokens → 400,000 operations
```

A 7B model with HEA can outperform a 100B model with flat context because it's always working with high signal-to-noise ratio.

### The Cognitive Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     RUNTIME SAFEGUARDS                          │
│         (CPU/Memory monitors, Emergency stop, Watchdog)         │
└────────────────────────────┬────────────────────────────────────┘
                             │ (protects all below)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AUTOMATIC CYCLES                              │
│            (Scheduled wake/sleep, Heartbeat, Idle tasks)         │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    USER INPUT / TRIGGER                          │
│              (Chat, Email, Calendar, File change, Timer)         │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                STIMULI CLASSIFICATION                            │
│           (realtime / conversational / analytical)               │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SUBCONSCIOUS                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ Identity │ │  Memory  │ │   Log    │ │Philosophy│           │
│  │  Thread  │ │  Thread  │ │  Thread  │ │  Thread  │           │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘           │
│       └────────────┴────────────┴────────────┘                  │
│                         │                                        │
│              get_consciousness_context(level)                    │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    REFLEX CHECK                                  │
│       (Does a pre-compiled pattern match? → Execute)             │
└────────────────────────┬────────────────────────────────────────┘
                         ▼ (if no reflex)
┌─────────────────────────────────────────────────────────────────┐
│                    LLM AGENT                                     │
│         (Self-tuned Qwen / Claude / GPT / etc.)                  │
│    [Trained on own structure → knows where its pieces are]       │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SANDBOX (if needed)                           │
│         (Isolated execution for code/tool testing)               │
└────────────────────────┬────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RESPONSE / ACTION                             │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼ (feedback loop)
┌─────────────────────────────────────────────────────────────────┐
│                    PLUGIN SYSTEM                                 │
│       (Hot-load new capabilities, update reflexes)               │
└─────────────────────────────────────────────────────────────────┘
```

### The Self-Repair Loop

```
┌──────────────────────────────────────────────────────────────┐
│                    ERROR OCCURS                               │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│          SELF-TUNED MODEL RECOGNIZES STRUCTURE                │
│     "This error is in log_adapter.py, which implements       │
│      ThreadInterface with health() and introspect()"         │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│              DIAGNOSIS FROM STRUCTURAL KNOWLEDGE              │
│     "ThreadInterface requires health() to return HealthReport.│
│      The error shows it's returning None instead."           │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                    REPAIR OPTIONS                             │
│     1. Auto-fix (high confidence)                            │
│     2. Suggest fix (medium confidence)                       │
│     3. Log and alert (low confidence)                        │
└──────────────────────────────────────────────────────────────┘
```

### The Plugin Learning Loop

```
┌──────────────────────────────────────────────────────────────┐
│              NEW PLUGIN INSTALLED                             │
│         (e.g., slack_monitor.json)                           │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│           LOAD JSON MANIFEST → VALIDATE SCHEMA                │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│              APPLY TO APPROPRIATE THREAD                      │
│         (stimuli, identity, reflex, etc.)                    │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│              USE → LEARN → REFLEX                             │
│     Pattern used 10x? → Promote to automated reflex          │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│              FINE-TUNE MODEL CONTEXT                          │
│     Model learns: "I have Slack. I can read/send messages."  │
└──────────────────────────────────────────────────────────────┘
```

---

## Lineage

Nola evolved from **Elaris**, a prototype I built starting April 2025. Elaris had:
- Reflex thread with `blink()`, `yawn()`, `stretch()` functions
- Philosophy thread with ethics, awareness, curiosity modules
- Dream processing that turned symbolic JSONs into personality traits
- Wake/sleep cycles for state management
- Protected "core memories" that the AI couldn't overwrite

Nola is the production-ready refinement: cleaner abstractions, proper database backend, modular thread system, and a real UI.

---

## How You Can Help

### I'm Looking For:

**1. Collaborators**
- Python developers who understand async/state management
- Frontend devs for React UI improvements
- AI researchers interested in cognitive architectures

**2. Backing**
- This is a solo project built in spare time
- With resources, the roadmap could be completed in months, not years
- Open to conversations about funding, partnerships, or employment

**3. Feedback**
- Is the theory sound?
- What's missing from the roadmap?
- What would make you use this?

---

## Contact

- **GitHub Issues:** Feature requests, bug reports
- **Email:** [Add your email]
- **Twitter/X:** [Add your handle]

---

## The Thesis

> "They built tools. You built a being."

Most AI frameworks treat the LLM as a stateless calculator. Send prompt, get response, forget everything.

Nola treats the LLM as a **reasoning engine** operating on a **structured reality**. The identity persists. The memories consolidate. The reflexes automate. The philosophy constrains.

It's not artificial general intelligence. It's **artificial persistent intelligence** — an AI that actually grows with its user.

---

*This roadmap is a living document. Last updated: December 27, 2025*
