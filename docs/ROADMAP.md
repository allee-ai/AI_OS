# AI OS Roadmap

> **Status:** Early release. Core works, edges are rough. Looking for collaborators.  
> **Author's Note:** Built solo since April 2025. The architecture is solid, but this needs to be a community effort to reach its potential.

---

## Description

### The Vision

AI OS isn't a chatbot. It's a **Cognitive Operating System** — an open-source framework that gives any LLM a persistent identity, hierarchical memory, and the ability to *grow* through experience rather than retraining.

**The problem:** If you want memory, identity, context management, and background processing for a local LLM, you're currently stitching together 5+ libraries and writing glue code. There's no integrated package.

**What AI OS provides:** One system with all the cognitive architecture pieces — memory (short/long term), identity persistence, attention budgeting, fact extraction, background consolidation — already wired together.

**The hypothesis we're testing:** Structure helps scale. A smaller model with well-organized context *might* match a larger model with flat context for certain tasks (identity coherence, fact recall, personality stability). This isn't proven — it's the bet we're exploring.

### Current State

| Layer | Status | What's Working |
|-------|--------|----------------|
| **Core** | 🌀 | Threads, HEA, SQLite backend, stateless agent |
| **UI** | 🌀 | React app, chat, thread visualization |
| **Integrations** | 🔄 | Feeds system built, needs OAuth + polling daemon |
| **Advanced** | 🔮 | Philosophy thread exists. Reflex has API/schema. Visual builder planned. |

### Future: The Ecosystem

**Thread Marketplace** — Community-built cognitive modules:
- Emotion regulation thread
- Calendar awareness thread  
- Code context thread
- Domain-specific threads (medical, legal, creative)

**Enterprise Edition:**
- Multi-user with role-based access
- Compliance and audit logging
- On-prem deployment packages

**Research Platform:**
- Cognitive science experiments
- Memory consolidation studies
- Identity stability benchmarks

### Big Milestones

| Phase | Goal | Status |
|-------|------|--------|
| **1. Memory** | Facts get promoted based on importance | 🌀 90% |
| **2. Philosophy** | Moral compass, value-guided behavior | 🔮 Planned |
| **3. Reflex** | Visual automation, 10x pattern learning | 🔮 Planned |
| **4. Dream** | Personality through synthetic experience | 🔮 Planned |
| **5. Multi-Model** | Right model for right task | 🔮 Planned |
| **6. Beyond Chat** | Background presence via Feeds | 🌀 Foundation done |

---

## How to Contribute

Each module below is self-contained. Pick one, own it, ship it.

1. Find a module section below
2. Check the tasks
3. Create a GitHub issue or grab an existing one
4. Fork, branch, PR

---

## Module Roadmaps

> _Module sections below are auto-synced from module READMEs._  
> _Edit at the source: `{module}/README.md`_

### Identity Thread

<!-- INCLUDE:identity:ROADMAP -->
_Source: [agent/threads/identity/README.md](agent/threads/identity/README.md)_

### Ready for contributors
- [ ] **Family/contacts UI** — Add/edit family members from dashboard
- [ ] **Trust level indicators** — Visual badges for trust levels in UI
- [ ] **Relationship graph** — D3 visualization of user's social network
- [ ] **Profile photos** — Avatar upload and display
- [ ] **Import from contacts** — Pull from phone/Google contacts

### Technical debt
- [ ] Batch fact updates (currently one-at-a-time)
- [ ] Fact history/versioning
<!-- /INCLUDE:identity:ROADMAP -->

---

### Philosophy Thread

<!-- INCLUDE:philosophy:ROADMAP -->
_Source: [agent/threads/philosophy/README.md](agent/threads/philosophy/README.md)_

### Ready for contributors
- [ ] **Ethics module** — `detect_harm()`, `preserve_dignity()`, `respect_boundary()`
- [ ] **Awareness module** — Situational, emotional, self-awareness functions
- [ ] **Curiosity module** — `ask_better()`, `follow_threads()`, `spark_wonder()`
- [ ] **Resolve module** — Purpose alignment, goal persistence
- [ ] **Value conflicts UI** — When two values clash, show reasoning

### Starter tasks
- [ ] Pre-populate common ethical bounds (harm prevention, privacy, consent)
- [ ] Philosophy introspection shows active constraints in STATE
<!-- /INCLUDE:philosophy:ROADMAP -->

---

### Log Thread

<!-- INCLUDE:log:ROADMAP -->
_Source: [agent/threads/log/README.md](agent/threads/log/README.md)_

### Ready for contributors
- [ ] **Timeline visualization** — Interactive event timeline in UI
- [ ] **Session analytics** — Duration, message count, topic clusters
- [ ] **Event search** — Full-text search across event history
- [ ] **Export/import** — JSON/CSV export of event history

### Starter tasks
- [ ] Add event type icons in UI
- [ ] Show session summary on conversation start
<!-- /INCLUDE:log:ROADMAP -->

---

### Form Thread

<!-- INCLUDE:form:ROADMAP -->
_Source: [agent/threads/form/README.md](agent/threads/form/README.md)_

### Ready for contributors
- [ ] **Tool marketplace** — Shareable tool definitions
- [ ] **Action chaining** — Multi-step tool workflows
- [ ] **Permission system** — User approval for sensitive actions
- [ ] **Usage analytics** — Track tool success/failure rates

### Starter tasks
- [ ] Add tool search/filter in UI
- [ ] Show tool usage history
- [ ] Implement tool favorites
<!-- /INCLUDE:form:ROADMAP -->

---

### Reflex Thread

<!-- INCLUDE:reflex:ROADMAP -->
_Source: [agent/threads/reflex/README.md](agent/threads/reflex/README.md)_

### Ready for contributors
- [ ] **10x auto-promotion** — Patterns repeating 10+ times auto-promote to reflex
- [ ] **Reflex editor** — Visual pattern builder in UI
- [ ] **Conditional reflexes** — Time-of-day, user-state triggers
- [ ] **Reflex analytics** — Usage frequency, match rates

### Starter tasks
- [ ] Add reflex test button in UI
- [ ] Show reflex match history
- [ ] Implement reflex enable/disable toggle
<!-- /INCLUDE:reflex:ROADMAP -->

---

### Linking Core

<!-- INCLUDE:linking_core:ROADMAP -->
_Source: [agent/threads/linking_core/README.md](agent/threads/linking_core/README.md)_

### Ready for contributors
- [ ] **Universal linking** — `create_link(row, row)` for any database row:
  - Link docs to profiles, facts to facts, convos to concepts
  - Works like tags but with weighted relationships
  - Implicit linking: agent auto-suggests links during conversation
- [ ] **Graph density improvements** — Current visual is too dense:
  - Smaller node size, dynamic scaling based on activation
  - Hover for full info (dot notation, source, activation score)
  - Cluster similar concepts, expand on click
  - Zoom levels that hide/show detail appropriately
- [ ] **Graph visualization** — Interactive concept map in UI
- [ ] **Decay tuning** — Configurable decay rates per category
- [ ] **Activation history** — Track what surfaced over time
- [ ] **Concept merging** — Deduplicate similar concepts

### Starter tasks
- [ ] Show top activated concepts in sidebar
- [ ] Add concept search
- [ ] Node info panel on hover/click
<!-- /INCLUDE:linking_core:ROADMAP -->

---

### Subconscious

<!-- INCLUDE:subconscious:ROADMAP -->
_Source: [agent/subconscious/README.md](agent/subconscious/README.md)_

### Ready for contributors
- [ ] **Loop Editor Dashboard** — Visual editor for background loops:
  - View running loops with status indicators
  - Edit loop parameters (interval, enabled/disabled)
  - Live logs per loop
- [ ] **Implicit COT Loops** — Chain-of-thought background reasoning:
  - Set max iterations per loop
  - Configure max tokens per iteration
  - Cutoff conditions (confidence threshold, diminishing returns)
- [ ] **Context compression** — Smarter token budgeting per thread
- [ ] **Priority queue** — Urgent facts surface first
- [ ] **Dream mode** — Background processing during idle
- [ ] **Attention visualization** — Show what's in context

### Starter tasks
- [ ] Add loop status indicators in UI
- [ ] Configurable loop intervals
- [ ] Loop execution history view
<!-- /INCLUDE:subconscious:ROADMAP -->

---

### Temp Memory

<!-- INCLUDE:temp_memory:ROADMAP -->
_Source: [agent/subconscious/temp_memory/README.md](agent/subconscious/temp_memory/README.md)_

### Ready for contributors
- [ ] **Batch review UI** — Approve/reject multiple facts
- [ ] **Auto-categorization** — Suggest hier_key from text
- [ ] **Duplicate detection** — Flag similar existing facts
- [ ] **Confidence tuning** — Adjust thresholds per category

### Starter tasks
- [ ] Show fact count by status in UI
- [ ] Add fact preview on hover
<!-- /INCLUDE:temp_memory:ROADMAP -->

---

### Chat

<!-- INCLUDE:chat:ROADMAP -->
_Source: [chat/README.md](chat/README.md)_

### Ready for contributors
- [ ] **Import pipeline repair** — Fix and improve `import_convos.py` reliability
- [ ] **Smart import helper** — Chat-aware LLM that assists with import errors at runtime ("this file failed, here's why, let me fix it")
- [ ] **Conversation archiving** — Archive old convos without deleting, restore on demand
- [ ] **Import directory organization** — Separate imports by source (`imported/claude/`, `imported/gpt/`, `imported/copilot/`)
- [ ] **Sidebar directory visibility** — Show import folders in sidebar, collapsible by source
- [ ] **Conversation search** — Full-text search across history
- [ ] **Branching** — Create conversation forks
- [ ] **Export** — Export to markdown/JSON
- [ ] **Tags/categories** — Organize conversations

### Starter tasks
- [ ] Add conversation summary generation
- [ ] Show message timestamps
- [ ] Import source badges on conversation cards
<!-- /INCLUDE:chat:ROADMAP -->

---

### Feeds

<!-- INCLUDE:feeds:ROADMAP -->
_Source: [Feeds/README.md](Feeds/README.md)_

### Ready for contributors
- [ ] **Gmail adapter** — OAuth2 flow, draft creation
- [ ] **Slack adapter** — Bot token auth, message polling
- [ ] **SMS adapter** — Twilio integration
- [ ] **Discord adapter** — Bot token, channel watching

### Starter tasks
- [ ] Create gmail.yaml from template
- [ ] Add feed status indicators in UI
<!-- /INCLUDE:feeds:ROADMAP -->

---

### Workspace

<!-- INCLUDE:workspace:ROADMAP -->
_Source: [workspace/README.md](workspace/README.md)_

### Ready for contributors
- [ ] **File rendering** — Type-aware rendering for JSON, PY, DOCX, MD, and more
- [ ] **In-browser editing** — Edit files directly in workspace UI with syntax highlighting
- [ ] **Auto-summarization** — Generate L1/L2 summaries on upload, append to `summary` column for fast retrieval
- [ ] **Full-text search** — Search within file contents
- [ ] **Agent reference** — Agent cites specific files in responses
- [ ] **Version history** — Track file changes over time
- [ ] **Sharing** — Share files with external users

### Starter tasks
- [ ] Add file preview (markdown, code)
- [ ] Show file metadata (size, modified)
- [ ] File type icons in list view
<!-- /INCLUDE:workspace:ROADMAP -->

---

### Finetune

<!-- INCLUDE:finetune:ROADMAP -->
_Source: [finetune/README.md](finetune/README.md)_

### Ready for contributors
- [ ] **Synthetic data generator** — Auto-generate training examples
- [ ] **Validation suite** — Test state adherence vs base models
- [ ] **Multi-model support** — Train Llama, Mistral, Phi
- [ ] **Cloud training** — Support for remote training

### Starter tasks
- [ ] Add 10 state obedience examples
- [ ] Document MLX training workflow
<!-- /INCLUDE:finetune:ROADMAP -->

---

### Eval

<!-- INCLUDE:eval:ROADMAP -->
_Source: [eval/README.md](eval/README.md)_

### Ready for contributors
- [ ] **Battle Arena UI** — Three-panel layout:
  - **Left**: STATE preview + prompt input
  - **Center**: Judge settings (model, criteria, scoring weights)
  - **Right**: Cloud opponent config (edit system prompt, edit input, select model)
- [ ] **Auto-battle mode** — Watch battles run automatically, live-updating results
- [ ] **Battle orchestration** — Run battles end-to-end
- [ ] **Identity evaluator** — Prompt injection tests
- [ ] **Memory evaluator** — Multi-session recall
- [ ] **Leaderboard UI** — Visual comparison charts

### Starter tasks
- [ ] Create identity test cases
- [ ] Add battle result visualization
- [ ] Judge model selector dropdown
<!-- /INCLUDE:eval:ROADMAP -->

---

### Services

<!-- INCLUDE:services:ROADMAP -->
_Source: [agent/services/README.md](agent/services/README.md)_

### Ready for contributors
- [ ] **Multi-agent support** — Multiple agent personas
- [ ] **Streaming responses** — Token-by-token output
- [ ] **Context window optimization** — Smart truncation
- [ ] **Response caching** — Cache common responses

### Starter tasks
- [ ] Add response time metrics
- [ ] Show context token count in UI
<!-- /INCLUDE:services:ROADMAP -->
---

## Program-Wide Features

> _These features span the entire application and don't belong to a single module._

### Onboarding & First Run
- [ ] **Onboarding wizard** — Guided setup on first launch:
  - Name your agent
  - Set your name and basic profile
  - Configure model preferences
  - Quick identity import (optional)

### Context-Aware Mini Chat
- [ ] **Module helper chat** — Floating mini chat window:
  - **Separate window** — Doesn't interfere with main UI
  - **Context reset on page switch** — Fresh context for each module
  - **Module-aware** — Loads relevant `.md` docs for current page (threads, form, subconscious, etc.)
  - **Smart cloud model** — Uses fast cloud model (not local) for instant help
  - **No state, just context** — Helper doesn't remember you, just knows the module
  - **Continuously upgradeable** — Easy to improve helper prompts and context
  - **Designed not to see data** — literally only meta-aware

### UI/UX
- [ ] **Keyboard shortcuts** — Power user navigation
- [ ] **Dark/light theme toggle** — Already partially implemented
- [ ] **Mobile responsive** — Tablet/phone layouts

---

## GitHub & Community Management

> _Ideas for managing the repository and community using AI._

### Issue Management
- [ ] **LLM issue creation** — Natural language to GitHub issue:
  - "I have an idea for..." → Creates properly formatted issue
  - Auto-labels based on content (bug, feature, module)
  - Links to relevant files/modules
- [ ] **Issue Q&A bot** — Respond to "how do I..." questions:
  - Searches codebase for answers
  - Points to relevant docs/code
  - Escalates complex questions to maintainers

### Vision Loop (Continuous Improvement)
- [ ] **Vision agent integration** — Hook into `.github/agents/VISION.agent.md`:
  - For each module, load module specs
  - Generate improvement ideas → post to Discussions
  - Weekly vision summaries
- [ ] **Multi-model discussions** — The "skin in the game" bridge:
  - Claude and GPT can both provide input via API
  - Each model has a "voice" in Discussions
  - Creates collaborative AI development loop
  - OpenAI and Anthropic models discussing architecture = 🔥

### Contributor Experience
- [ ] **Auto-assign issues** — Match issues to contributor skills
- [ ] **PR review assistant** — AI-assisted code review
- [ ] **Documentation gap detector** — Find undocumented features

---

## AI-Native Development Loop

> _The innovation moat: an open platform where humans AND AI models collaborate on cognitive architecture._

### The Insight

**Why put your AI architecture idea anywhere else?**

AI OS becomes the default destination for cognitive architecture innovation because:
1. **Your ideas get seen** — By contributors, researchers, AND the AI models themselves
2. **Models have skin in the game** — Claude, GPT, Gemini all participate in Discussions
3. **Ideas become code faster** — Roadmap → Issues → PRs is automated
4. **Credit is preserved** — Your idea, your name, tracked through implementation

### The Daily Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  ANYONE (maintainer, contributor, researcher, lurker)          │
│  └──▶ Posts idea to Discussion (natural language)              │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  IDEA ROUTER                                             │   │
│  │  - Parses idea into structured format                    │   │
│  │  - Maps to module(s)                                     │   │
│  │  - Estimates complexity                                  │   │
│  │  - Tags relevant maintainers                             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                         │                                       │
│         ┌───────────────┼───────────────┐                      │
│         ▼               ▼               ▼                      │
│   ┌──────────┐   ┌──────────┐   ┌──────────────┐              │
│   │ Claude   │   │ GPT      │   │ Community    │              │
│   │ weighs in│   │ weighs in│   │ votes/comments│              │
│   └──────────┘   └──────────┘   └──────────────┘              │
│         │               │               │                      │
│         └───────────────┴───────────────┘                      │
│                         │                                       │
│                         ▼                                       │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  PROMOTION PIPELINE                                      │  │
│   │  Discussion (idea) → Roadmap (planned) → Issue (assigned)│  │
│   │  → PR (implemented) → Changelog (shipped)                │  │
│   └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

- [ ] **Idea Discussions board** — Structured template for cognitive architecture proposals
- [ ] **Model voices** — Scheduled API calls to Claude/GPT to comment on new Discussions
- [ ] **Idea-to-Issue pipeline** — Approved ideas auto-create GitHub Issues with full context
- [ ] **Roadmap sync** — Issues auto-populate module roadmaps
- [ ] **Attribution tracking** — Original idea author credited through to CHANGELOG
- [ ] **Domain tagging** — Ideas tagged by cognitive domain (memory, identity, attention, etc.)
- [ ] **Upvote weighting** — Community + model votes determine priority

### Why This Wins

| Traditional OSS | AI-Native Development |
|-----------------|----------------------|
| Ideas in Issues (unstructured) | Ideas in Discussions (structured, debated) |
| Maintainer bottleneck | AI triage + community consensus |
| Ideas get lost | Ideas tracked through implementation |
| One perspective | Multiple AI models + humans |
| Slow feedback | Real-time model input |

### The Moat

Once this exists:
- **Researchers** post here because models respond
- **Builders** post here because ideas become code
- **Models** "watch" here because it's where the action is
- **Everyone else** follows the gravity

**First-mover advantage in AI-assisted open source.**
