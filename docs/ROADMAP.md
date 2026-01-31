# AI OS Roadmap

> **Status:** Early release. Core works, edges are rough. Looking for collaborators.  
> **Author's Note:** Built solo since April 2025. The architecture is solid, but this needs to be a community effort to reach its potential.

---

## Description

### The Vision

AI OS isn't a chatbot. It's a **Cognitive Operating System** — an open-source framework that gives any LLM a persistent identity, hierarchical memory, and the ability to *grow* through experience rather than retraining.

**The core insight:** Structure beats scale. A 7B model with proper cognitive architecture outperforms a 100B model with flat context.

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
- [ ] **Graph visualization** — Interactive concept map in UI
- [ ] **Decay tuning** — Configurable decay rates per category
- [ ] **Activation history** — Track what surfaced over time
- [ ] **Concept merging** — Deduplicate similar concepts

### Starter tasks
- [ ] Show top activated concepts in sidebar
- [ ] Add concept search
<!-- /INCLUDE:linking_core:ROADMAP -->

---

### Subconscious

<!-- INCLUDE:subconscious:ROADMAP -->
_Source: [agent/subconscious/README.md](agent/subconscious/README.md)_

### Ready for contributors
- [ ] **Context compression** — Smarter token budgeting per thread
- [ ] **Priority queue** — Urgent facts surface first
- [ ] **Dream mode** — Background processing during idle
- [ ] **Attention visualization** — Show what's in context

### Starter tasks
- [ ] Add loop status indicators in UI
- [ ] Configurable loop intervals
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
- [ ] **Conversation search** — Full-text search across history
- [ ] **Branching** — Create conversation forks
- [ ] **Export** — Export to markdown/JSON
- [ ] **Tags/categories** — Organize conversations

### Starter tasks
- [ ] Add conversation summary generation
- [ ] Show message timestamps
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
- [ ] **Full-text search** — Search within file contents
- [ ] **Agent reference** — Agent cites specific files
- [ ] **Version history** — Track file changes
- [ ] **Sharing** — Share files with external users

### Starter tasks
- [ ] Add file preview (markdown, code)
- [ ] Show file metadata (size, modified)
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
- [ ] **Battle orchestration** — Run battles end-to-end
- [ ] **Identity evaluator** — Prompt injection tests
- [ ] **Memory evaluator** — Multi-session recall
- [ ] **Leaderboard UI** — Visual comparison charts

### Starter tasks
- [ ] Create identity test cases
- [ ] Add battle result visualization
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
