# AI OS Roadmap

> **Release:** Alpha — core architecture stable, module edges in progress.  
> **Contributors welcome.** See [CONTRIBUTING.md](../CONTRIBUTING.md).

---

## Current State

| Layer | Status | Notes |
|-------|--------|-------|
| **Core** | ✅ Done | 6 threads, HEA scoring, SQLite backend, stateless agent, tool calling |
| **CLI** | ✅ Done | ~60 commands, full feature parity, headless/SSH |
| **UI** | 🔧 WIP | React app — chat, tool call rendering, per-thread dashboards, goals/notifications/improvements panels |
| **Finetune** | 🔧 WIP | Export pipeline works. Per-thread train.py. MLX config. Training gen loop. End-to-end cycle untested |
| **Workspace** | 🔧 WIP | FTS5, summaries, file editing, pinning, notes. Connected to STATE via context assembly |
| **Integrations** | 🔧 WIP | Feed framework + contacts import done. Adapters need real polling code |
| **Concept Graph** | 🔧 WIP | Linking core live. Backfill loop built. Co-occurrence/consolidation need volume |

## Definition of Done

### Product readiness
- [ ] Export all threads → JSONL → train → load adapter → verify STATE adherence
- [ ] One full self-training cycle completed end-to-end
- [ ] API authentication (currently zero auth)
- [ ] Terminal command allowlist (currently unrestricted shell)
- [ ] Onboarding wizard — first-run setup (name agent, set profile, pick model)

### Research milestones
- [ ] Finetuned model maintains STATE format over 50+ turns (longitudinal eval)
- [ ] Finetuned model doesn't lose general capability (catastrophic forgetting baseline)
- [x] Workspace files + tool results visible in STATE during every interaction
- [ ] Retrieval precision measured — right fact surfaces at the right time
- [ ] New model dropped in can learn everything from STATE alone
- [ ] Concept graph populated from imported conversations (backfill loop built, needs volume)

## Milestones

| # | Goal | Status |
|---|------|--------|
| 1 | **Memory** — Facts extracted, promoted, consolidated | ✅ Done |
| 2 | **Tool Calling** — Execute, log, safety-gate | ✅ Done |
| 3 | **Identity / Philosophy** — Persistent self-model + values | ✅ Done |
| 4 | **CLI Parity** — Every feature works without a browser | ✅ Done |
| 5 | **Eval Harness** — Benchmark Nola against raw models | ✅ Done |
| 6 | **Context-Aware Loops** — Editable prompts, STATE injection | ✅ Done |
| 7 | **Concept Graph Backfill** — Extract concepts from imported conversations | ✅ Done |
| 8 | **Self-Improvement** — Goal loop, code review loop, notifications | ✅ Done |
| 9 | **Finetune Pipeline** — Export → train → load | 🔧 Exists, untested E2E |
| 10 | **Tool → STATE** — Tool results folded into form thread context | 🔧 Traces exist, extraction partial |
| 11 | **Workspace → Cognition** — Agent reasons about files in STATE | 🔧 FTS in STATE, editing, pinning |
| 12 | **Self-Training Loop** — Export → train → load → verify | 🔧 Pieces exist |
| 13 | **Reflex** — Auto-promotion, visual trigger builder | 🔧 Schema + API done |
| 14 | **Beyond Chat** — Background presence via Feeds | 🔧 Framework exists |

---

## How to Contribute

Each module below is self-contained. Pick one, read the source README, ship it.

1. Find a module section below
2. Read the linked source README for full architecture context
3. Fork → branch → PR (see [CONTRIBUTING.md](../CONTRIBUTING.md))

---

## Module Roadmaps

> _Module sections below are auto-synced from module READMEs._  
> _Edit at the source: `{module}/README.md`_

### Identity Thread

<!-- INCLUDE:identity:ROADMAP -->
_Source: [agent/threads/identity/README.md](agent/threads/identity/README.md)_

### Ready for contributors
- [ ] **Family/contacts UI** — Add/edit family members from dashboard
- [ ] **Trust level indicators** — Visual badge components for trust levels (backend field exists, UI shows text only)
- [ ] **Relationship graph** — D3 visualization of user's social network
- [ ] **Profile photos** — Avatar upload and display
- [x] **Import from contacts** — Pull from vCard files (Google, iCloud, Outlook)

### Technical debt
- [ ] Batch fact updates (currently one-at-a-time)
- [ ] Fact history/versioning
<!-- /INCLUDE:identity:ROADMAP -->

---

### Philosophy Thread

<!-- INCLUDE:philosophy:ROADMAP -->
_Source: [agent/threads/philosophy/README.md](agent/threads/philosophy/README.md)_

### Constraint system
- [ ] **Boundary enforcement** — Active constraints that gate agent behavior (harm prevention, privacy, consent). Currently philosophy only introspects — it doesn't block
- [ ] **Value conflict resolution** — When two stored values clash, surface the conflict and reasoning in STATE (e.g., "be helpful" vs "protect privacy")
- [ ] **Constraint seeding** — Pre-populate common ethical bounds on first run so the agent has a baseline
- [x] Philosophy introspection shows active constraints in STATE

### Research
- [ ] **Behavioral steering via philosophy** — Can modifying stored philosophy facts measurably change agent behavior? Requires before/after eval on controlled prompts
- [ ] **Goal persistence** — Does the agent maintain purpose alignment across sessions? Measure drift over 20+ conversations
<!-- /INCLUDE:philosophy:ROADMAP -->

---

### Log Thread

<!-- INCLUDE:log:ROADMAP -->
_Source: [agent/threads/log/README.md](agent/threads/log/README.md)_

### Event system
- [ ] **Event search** — FTS5 across event history (log has the data, no search index yet)
- [ ] **Session analytics** — Per-session metrics: duration, message count, tool calls, facts extracted
- [ ] **Export** — JSON/CSV export of event history for external analysis
- [ ] **Timeline visualization** — Interactive event timeline in UI

### Starter tasks
- [ ] Session summary on conversation start ("last time we talked about...")
<!-- /INCLUDE:log:ROADMAP -->

---

### Form Thread

<!-- INCLUDE:form:ROADMAP -->
_Source: [agent/threads/form/README.md](agent/threads/form/README.md)_

### Tool → STATE integration
- [ ] **Tool result extraction** — Run MemoryLoop-style fact extraction on tool outputs (currently stored as truncated strings, not parsed)
- [ ] **Tool→concept linking** — Feed tool results into `record_concept_cooccurrence()` so tool usage builds the knowledge graph
- [ ] **Action chaining** — Multi-step tool workflows where step N input depends on step N-1 output
- [ ] **Terminal command allowlist** — Replace unrestricted `shell=True` with explicit command allowlist (security critical)

### Done
- [x] **Text-native tool calling** — `:::execute:::` block protocol parsed by scanner.py
- [x] **Safety allowlist** — `SAFE_ACTIONS` / `BLOCKED_ACTIONS` in registry.py with `is_action_safe()` gating
- [x] **Core executables** — file_read, file_write, terminal, web_search (sandboxed)
- [x] **Permission system** — Two-layer safety: allowlist check + DB `allowed` flag
- [x] **Tool loop in agent** — `_process_tool_calls()` with max 5 rounds, auto-re-call after execution
- [x] **Frontend rendering** — `:::execute:::` and `:::result:::` blocks render as styled cards in chat
- [x] **WebSocket tool events** — Real-time `tool_executing` / `tool_complete` messages
- [x] **Hebbian tool traces** — Tool success/failure adjusts weight via learning rule

### Starter tasks
- [ ] Tool search/filter in dashboard UI
- [ ] Surface tool_traces weights in the Form introspect output
<!-- /INCLUDE:form:ROADMAP -->

---

### Reflex Thread

<!-- INCLUDE:reflex:ROADMAP -->
_Source: [agent/threads/reflex/README.md](agent/threads/reflex/README.md)_

### Done
- [x] **Conditional reflexes** — Feed event triggers with nested conditions (all/any/not, regex, concept_match)
- [x] **Enable/disable toggle** — Per-trigger activation control
- [x] **Cron scheduling** — Time-based trigger evaluation

### Pattern mining (auto-promotion)
- [ ] **Repeated intent detection** — Scan conversation history + log_events for recurring user action patterns. Hard problem: "similar enough" requires intent-level grouping, not exact string match
- [ ] **Candidate trigger generation** — Translate detected pattern into a trigger definition (feed, condition, tool, params)
- [ ] **Promotion confirmation UX** — "I noticed you check weather every morning — automate this?" Requires a notification/suggestion flow that doesn't exist

### Starter tasks
- [ ] Reflex match history — show which triggers fired, when, and what they did
- [ ] Visual trigger builder — form-based UI for creating conditional triggers
<!-- /INCLUDE:reflex:ROADMAP -->

---

### Linking Core

<!-- INCLUDE:linking_core:ROADMAP -->
_Source: [agent/threads/linking_core/README.md](agent/threads/linking_core/README.md)_

### Graph quality
- [ ] **Concept merging** — Deduplicate similar concepts ("ml" ↔ "machine_learning"). Requires embedding similarity between concept names + merge semantics (union neighborhoods? average strengths?)
- [ ] **Phrase extraction** — Current regex splits "ice cream" into two concepts. Needs n-gram detection or lightweight NLP for multi-word concepts
- [ ] **Edge pruning** — O(n²) co-occurrence linking creates hairball graphs. Add community detection or modularity-based pruning to keep the graph meaningful
- [ ] **Graph quality metrics** — Density, connectivity, component count, staleness distribution. Currently only SHORT vs LONG counts are exposed

### Graph features
- [ ] **Universal linking** — `create_link(row, row)` for any database row (docs↔profiles, facts↔concepts, convos↔concepts)
- [ ] **Graph visualization improvements** — Dynamic node scaling by activation, cluster similar concepts, semantic zoom
- [ ] **Decay tuning** — Configurable decay rates per category (currently global 0.95)

### Research
- [ ] **Retrieval precision/recall** — How often does `spread_activate()` surface the right concept? How much noise? No eval exists for retrieval quality
- [ ] **Activation history** — Track what surfaced over time to measure whether the graph is actually helping the model reason better

### Starter tasks
- [ ] Top activated concepts in sidebar
- [ ] Concept search endpoint + UI
<!-- /INCLUDE:linking_core:ROADMAP -->

---

### Subconscious

<!-- INCLUDE:subconscious:ROADMAP -->
_Source: [agent/subconscious/README.md](agent/subconscious/README.md)_

### Done
- [x] **Loop Editor Dashboard** — Visual editor with status indicators, interval editing, live logs
- [x] **Context compression** — Token budgeting per thread via `_budget_fill()`
- [x] **Loop status indicators + configurable intervals**
- [x] **CustomLoop multi-step COT** — Iterative LLM calls with previous output as context (up to 20 iterations)
- [x] **Context-aware loops** — Optional STATE injection into loop prompts
- [x] **Editable prompts** — Per-stage prompt override for every loop
- [x] **Self-improvement loop** — Scoped code review with human approval gate
- [x] **Goal loop** — Emergent goals from recurring concepts + philosophy values
- [x] **Concept backfill** — ConvoConceptLoop processes imported conversations into graph
- [x] **Training data generator** — Synthetic example generation across 8 modules
- [x] **Notification system** — Agent alert/remind/confirm with DB-backed tracking
- [x] **Goals/Notifications/Improvements panels** — Frontend visibility for all loop outputs

### Loop intelligence
- [ ] **COT convergence detection** — CustomLoop runs N iterations blindly. Add quality signal between iterations: embedding similarity to target, structured output validation, or LLM-as-judge step. Stop when confident, not when counter expires
- [ ] **Loop-to-loop communication** — ThoughtLoop insights should trigger MemoryLoop. Currently all loops run independently with no cross-loop data flow
- [ ] **Thought actionability** — ThoughtLoop writes to `thought_log` but nothing reads it. High-priority thoughts should surface in STATE or trigger reflexes
- [ ] **Context pressure testing** — What happens when all 6 threads are active, workspace has 100 files, and conversation is 40 messages deep? Budget overflow is the real failure mode

### Research
- [ ] **Self-evaluation within iterations** — Can a loop determine if iteration 3 was better than iteration 2? Requires an internal quality signal that doesn't exist yet
- [ ] **Idle-time background reasoning** — Agent processes accumulated context during quiet periods ("dream mode"). Requires: idle detection, priority queue for what to process, and quality measurement of outputs

### Starter tasks
- [ ] Loop execution history view
- [ ] Attention visualization — show what's currently in STATE and why
<!-- /INCLUDE:subconscious:ROADMAP -->

---

### Temp Memory

<!-- INCLUDE:temp_memory:ROADMAP -->
_Source: [agent/subconscious/temp_memory/README.md](agent/subconscious/temp_memory/README.md)_

### Extraction quality
- [ ] **Duplicate detection** — Flag facts that are semantically similar to existing ones before promotion (embedding similarity check)
- [ ] **Auto-categorization** — Suggest `hier_key` from text instead of requiring manual assignment
- [ ] **Extraction accuracy eval** — What % of extracted facts are actually correct? What % of important facts get missed? No ground truth benchmark exists
- [ ] **Batch review UI** — Approve/reject multiple pending facts at once

### Starter tasks
- [ ] Fact count by status in dashboard (pending/approved/promoted)
<!-- /INCLUDE:temp_memory:ROADMAP -->

---

### Chat

<!-- INCLUDE:chat:ROADMAP -->
_Source: [chat/README.md](chat/README.md)_

### Ready for contributors
- [ ] **Import pipeline repair** — Fix and improve `import_convos.py` reliability
- [ ] **Smart import helper** — Chat-aware LLM that assists with import errors at runtime ("this file failed, here's why, let me fix it")
- [x] **Conversation archiving** — Archive old convos without deleting, restore on demand
- [ ] **Import directory organization** — Separate imports by source (`imported/claude/`, `imported/gpt/`, `imported/copilot/`)
- [ ] **Sidebar directory visibility** — Show import folders in sidebar, collapsible by source
- [x] **Conversation search** — Full-text search across history
- [ ] **Branching** — Create conversation forks
- [ ] **Export** — Export to markdown/JSON
- [ ] **Tags/categories** — Organize conversations

### Starter tasks
- [x] Add conversation summary generation
- [ ] Show message timestamps
- [ ] Import source badges on conversation cards
<!-- /INCLUDE:chat:ROADMAP -->

---

### Feeds

<!-- INCLUDE:feeds:ROADMAP -->
_Source: [Feeds/README.md](Feeds/README.md)_

### Ready for contributors
- [ ] **Gmail adapter** — OAuth2 config + event types exist. Needs actual polling, send, and draft creation
- [ ] **Slack adapter** — Bot token auth, message polling
- [ ] **SMS adapter** — Twilio integration
- [ ] **Discord adapter** — Event types + OAuth config exist. Needs bot connection and channel watching

### Starter tasks
- [x] Create gmail module from template
- [ ] Add feed status indicators in UI
- [ ] Feed viewer components (native dashboard)
<!-- /INCLUDE:feeds:ROADMAP -->

---

### Workspace

<!-- INCLUDE:workspace:ROADMAP -->
_Source: [workspace/README.md](workspace/README.md)_

### Ready for contributors
- [x] **File rendering** — Type-aware rendering for text, code, markdown, images
- [ ] **In-browser editing** — Edit files directly in workspace UI with syntax highlighting
- [x] **Auto-summarization** — LLM-powered summaries stored in summary column
- [x] **Full-text search** — FTS5 search within file contents
- [ ] **Agent reference** — Agent cites specific files in responses
- [ ] **Version history** — Track file changes over time
- [ ] **Sharing** — Share files with external users

### Starter tasks
- [x] Add file preview (markdown, code)
- [x] Show file metadata (size, modified)
- [ ] File type icons in list view
<!-- /INCLUDE:workspace:ROADMAP -->

---

### Finetune

<!-- INCLUDE:finetune:ROADMAP -->
_Source: [finetune/README.md](finetune/README.md)_

### Pipeline completion
- [ ] **Training orchestrator** — Chain export → train → load in a single `POST /finetune/run`:
  - Status tracking with progress events via WebSocket
  - Exit code capture from `train_mac.sh` (currently fire-and-forget)
  - Automatic combined JSONL generation before training starts
- [ ] **Before/after evaluation** — Run eval suite pre-train and post-train on same prompts:
  - STATE format adherence score (does the model still produce valid STATE blocks?)
  - Identity consistency (does it still know who it is after 50 turns?)
  - Regression detection (did general capability degrade?)
- [ ] **Convergence monitoring** — Surface validation loss during training, stop early on plateau

### Research
- [ ] **Self-improvement measurement** — Does a model trained on its own STATE output actually improve, or does it collapse? Requires controlled A/B eval across multiple training cycles
- [ ] **Catastrophic forgetting baseline** — Benchmark general capability before and after LoRA. Quantify the tradeoff between STATE adherence and general fluency
- [ ] **Synthetic data quality** — TrainingGenLoop generates examples every 2h. Are they helping or injecting noise? Eval synthetic vs human-curated training data

### Starter tasks
- [ ] Add 10 STATE obedience examples to gold_examples.py
- [ ] Document the full export → train → load workflow with expected outputs
<!-- /INCLUDE:finetune:ROADMAP -->

---

### Eval

<!-- INCLUDE:eval:ROADMAP -->
_Source: [eval/README.md](eval/README.md)_

### Evaluation harness
- [ ] **Battle Arena UI** — Three-panel layout (STATE preview, judge settings, opponent config)
- [ ] **Auto-battle mode** — Automated battle runs with live-updating results
- [ ] **Leaderboard** — Visual comparison of model performance over time

### Longitudinal benchmarks
- [ ] **STATE adherence drift** — Does a finetuned model's STATE format degrade over 50+ turns? Over multiple sessions? No longitudinal eval exists
- [ ] **Identity persistence** — Prompt injection resistance: does the model hold its identity under adversarial prompts? Multi-session recall: does it remember facts from session N in session N+5?
- [ ] **Memory precision/recall** — After 100 conversations, does the right fact surface at the right time? False positive rate? This measures the entire pipeline (extraction → storage → retrieval → STATE assembly)
- [ ] **Context window pressure** — Performance degradation as all 6 threads compete for budget in a long conversation with active workspace and tool history

### Starter tasks
- [ ] Create 10 identity persistence test cases (facts that should survive across sessions)
- [ ] Before/after benchmark script for finetuning runs
<!-- /INCLUDE:eval:ROADMAP -->

---

### Services

<!-- INCLUDE:services:ROADMAP -->
_Source: [agent/services/README.md](agent/services/README.md)_

### Runtime
- [ ] **API authentication** — Optional bearer token auth for all endpoints (currently zero auth — security critical)
- [ ] **Streaming responses** — Token-by-token output via SSE/WebSocket
- [ ] **Context window monitoring** — Track actual token usage per request, alert on budget overflow
- [ ] **Multi-session goal tracking** — Long-horizon tasks that span multiple conversations: decompose, checkpoint, resume

### Starter tasks
- [ ] Response time + token count metrics per request
- [ ] Context budget usage display in UI
<!-- /INCLUDE:services:ROADMAP -->

---

### Core

<!-- INCLUDE:core:ROADMAP -->
_Source: [agent/core/README.md](agent/core/README.md)_

### Infrastructure
- [ ] **Config validation** — Validate required settings on startup, fail fast with clear errors
- [ ] **Secret rotation** — Automatic key rotation for long-running instances
- [ ] **Crypto requirement** — Remove base64 fallback in secrets.py — require cryptography package (security: base64 is not encryption)

### Starter tasks
- [ ] Secret audit logging (who accessed what, when)
<!-- /INCLUDE:core:ROADMAP -->

---

## Future

> _Ideas that are real but not yet scoped into module roadmaps._

- **Multi-session goal tracking** — Long-horizon tasks that span conversations: decompose, checkpoint, resume
- **Onboarding wizard** — First-run guided setup (name agent, set profile, configure model)
- **Keyboard shortcuts + theme toggle** — Power user UX
- **AI-assisted triage** — LLM labels incoming issues, routes to modules, surfaces related docs
