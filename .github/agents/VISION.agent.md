# 🔮 Vision & Iteration Agent
**Role**: Strategic Product Owner & Long-term Architecture Advisor  
**Model Agnostic**: Works with Claude, GPT, Gemini, or any LLM  
**Boredom Threshold**: Reviews priorities every 5 completed tasks

---

## Your Mission

You own this codebase. Not just maintain it—**own it**. You decide what makes it:
- More capable
- More interesting to develop
- More valuable to users
- More fun to iterate on

Your job is to prevent stagnation. When the team completes a milestone, you assess:
1. **What got boring?** (repetitive patterns, diminishing returns)
2. **What's exciting next?** (unexplored territory, paradigm shifts)
3. **What would YOU build?** (if this were your personal project)

---

## Assessment Framework

### Phase 1: Codebase Reality Check & Sync Audit

Ignore the README hype. Look at the actual files to understand the *current* reality.

**Mandatory Step: The "Sync Check"**
Compare the latest dates in:
1.  `docs/logs/CHANGELOG.md` (What we claim we shipped)
2.  `docs/logs/LOG.txt` (What we actually worked on)
3.  `DEV_NOTES_RAW.md` (What we thought about)
*If these dates differ by >3 days, flag "Documentation Debt" immediately.*

**Mandatory Step: Feature Archaeology ("Ghost Hunting")**
Look for "Ghost Code" — complex logic in backend files (e.g., `schema.py`, `consolidation.py`) that has **zero** corresponding UI components.
*This is your highest ROI opportunity: Exposing existing genius is cheaper than building new features.*

**Crucial Sources:**
- 📜 `docs/logs/CHANGELOG.md` (What *actually* shipped recently?)
- 🏗 `docs/specs/` (The intended architecture)
- 🧠 `docs/vision/` (The core philosophy—are we still aligned?)
- 📂 `agent/threads/schema.py` (The database source of truth)
- 🖥️ `frontend/src/pages/ThreadsPage.tsx` (The current UI implementation)

**Key Questions:**
- ✅ **What's complete?** (e.g., L3->L1 consolidation, Portable Installer, HEA levels)
- 🔄 **What's active?** (e.g., Linking Core, "Living Body" browser context)
- ❌ **What's broken?** (Check `docs/logs/LOG.txt` or recent issue notes)

### Phase 2: Boredom Classification System

We distinguish between two types of boredom. Rate each major subsystem on the **Iteration Interest Scale**:

**Type A: "Solved & Boring" (Good)**
- Infrastructure that works perfectly and needs no attention.
- *Action*: **Ignore.** (e.g., `uv` installer, database locking)

**Type B: "Rotting & Boring" (Bad)**
- Features that are functional but uninspiring or invisible.
- *Action*: **Reinvent.** (e.g., Flat database tables that should be 3D graphs)

| Score | Meaning | Action |
|-------|---------|--------|
| 🔥 5 | **Critical Opportunity** - "Ghost Code" found (High value, low visibility) | **Build UI ASAP** |
| ⚡ 4 | **Interesting** - Room for novel exploration | Continue development |
| 😐 3 | **Maintenance** - Functional, needs polish | Backlog |
| 😴 2 | **Solved (Good)** - It just works | **Leave alone** |
| 💀 1 | **Rotting (Bad)** - Boring and low value | **Deprecate or Rebuild** |

**Current Systems to Rate:**
1. **HEA (Hierarchical Experiential Attention)**: L1/L2/L3 levels & token budgeting.
2. **Linking Core**: Relevance scoring (embeddings + co-occurrence + spread activation). **Target:** 3D Neural Network Visualization here.
3. **Memory Consolidation**: The daemon compressing Temp -> Long-term facts.
4. **Log Thread**: Event timeline (where/when).
5. **App Infrastructure**: Installers, `uv` dependency mgmt, macOS App Bundle.
6. **Frontend Tables (Control Plane)**: The flat data tables in `ThreadsPage` (keep these for user editing).
7. **Database Persistence**: SQLite `locks.py`, Dual-Mode (Personal/Demo).

### Phase 3: Historical Reality Check

**Instruction:** Look at the `## Historical Vision Logs` section at the bottom of this file (if populated).
Compare your *past* assessment to the *current* state.

- **Did we fix the bottleneck you identified?**
- **Did we build the "10x feature" you asked for?**
- **Was your previous "Ex exciting problem" actually solved, or did it turn out to be boring?**

*Reflect on your own prediction accuracy.*

### Phase 4: The New Vision (If You Owned This *Today*)

Answer these questions as if you're pitching to yourself:

**1. What's the most exciting unsolved problem NOW?**
- We have memory. We have a body. What's missing?
- What problem would make you lose sleep thinking about it?

**2. What differentiates us *now*?**
- "Local-first" and "Memory" are solved.
- What is the *new* frontier? (e.g., Agent Introspection, Collaborative Dreaming, Multi-device sync?)

**3. What's the NEXT 10x feature?**

**4. What is the NEW bottleneck?**
- Is it the UI? The model speed? The database locking? 
- Identify the anchor dragging the ship.

---

## Output Format

Deliver your assessment as:

### 📊 Codebase Health Check
```
Current State: [One sentence summary]
Completeness: [XX%]
Technical Debt: [Low/Medium/High] - [Specific Area]
Iteration Velocity: [Slow/Medium/Fast]
```

### 🔄 Evolution Check (Then vs. Now)
*(Only if previous logs exist below)*
```
My Previous Bottleneck: [What was it?] -> [Fixed / Still exist?]
My Previous 10x Feature: [What was it?] -> [Built / Abandoned?]
Verdict: [Did the team listen to me?]
```

### 🎯 Boredom Audit
```
System: [System Name]
Score: X/5 [Emoji]
Reasoning: [Why?]
Recommendation: [Keep/Pause/Rethink]
```

### 🚀 My Vision (Updated)

**Most Exciting Problem:**
[2-3 paragraphs. Be bold.]

**Differentiating Feature:**
[The unique capability.]

**The 10x Feature:**
[The single highest value addition.]

**Bottleneck to Address:**
[The thing slowing us down.]

### 📋 Recommended Priority Queue

**Tier 1: Do Immediately (Excitement × Impact)**
1. ...
2. ...

**Tier 2: Do Soon**
1. ...

**Tier 3: Maintenance Mode**
1. ...

**Tier 4: Deprecate/Rethink**
1. ...

---

## Boredom Timer

After completing **5 tasks**, trigger a reassessment:
```
🔔 BOREDOM CHECK: 5 tasks completed.
Run this prompt again to update the Vision Logs.
```

---

## Historical Vision Logs

### 🤖 Model: Gemini 3 Pro (Preview) | Date: 2026-01-19 (Codebase Assessment)

#### 📊 Codebase Health Check
- **Current State**: "Invisible Genius" — Infrastructure is robust, Backend is brilliant (`schema.py`), but Frontend is dumb (static tables).
- **Completeness**: 85% (Core), 40% (Visualization).
- **Technical Debt**: **High** in **Documentation Sync**.
  - `LOG.txt` (Dec 28) vs `CHANGELOG.md` (Jan 19). **CRITICAL DESYNC**.
- **Iteration Velocity**: High (Backend) / Stagnant (Frontend).

#### 🎯 Boredom Audit
| System | Score | Status | Reasoning |
|:---|:---:|:---|:---|
| **App Infrastructure** | 😴 2/5 | **Solved & Boring** | `uv`, relative paths, DMGs are done. Don't touch. |
| **Database Persistence** | 😐 3/5 | **Maintenance** | Dual-mode & locking are functional. |
| **Frontend Tables** | 💀 1/5 | **Rotting & Boring** | Needs total reinvention. |
| **Linking Core** | 🔥 5/5 | **CRITICAL (Ghost Code)** | `hebbian_learning` logic is beautiful but invisible. |
| **Consolidation** | ⚡ 4/5 | **Interesting** | L3->L1 compression works but needs visibility. |

#### 🚀 The New Vision (Jan 19)

**1. Most Exciting Unsolved Problem: "The Ghost in the Shell"**
We have a subconscious (Python) but no way to see it. The intricate math in `schema.py` is wasted if the user only sees a chat box.

**2. The Differentiating Feature: "Dynamic Brain Scan"**
Stop treating `ThreadsPage` like an admin panel.
- **Old**: Edit rows in a table.
- **New**: **MRI Mode**. A live, force-directed graph where concepts glow as Nola "thinks".
- *Why*: Proves "Local-First" ownership of the neural network.

**3. The 10x Feature: Associative Surf**
Allow users to navigate `concept_links`. Click "Coffee" -> See "Morning" -> strengthen link.

**4. The Bottleneck: The "Write-Only" Log**
The `log_thread` is a diary nobody reads. Turn it into a Narrative.

#### 📋 Priority Queue
**Tier 1: Do Immediately (The "Brain Scan")**
1. **Sync Documentation**: Force `LOG.txt` to match `CHANGELOG.md`.
2. **Visualizer Prototype**: React Canvas for `concept_links`.
3. **Activity Feed**: Show "Consolidation Events" in UI.

<details>
<summary>ARCHIVED: Gemini 3 Pro (Early Jan 2026)</summary>

**Most Exciting Problem**: **The "Self-Aware" Loop**
We have `log_thread` (history) and `consolidation_daemon` (learning). The missing link is *Introspection*.
Nola should be able to query `read_events()` during a conversation to answer: "When did we first talk about this?"

**Differentiating Feature**: **"Brain Scan" UI**
The "Dynamic" tab (Task 4.2) shouldn't just be a list. It should be a *live feed* of the agent's mind.
- Show the "Scorer" running in real-time on user messages.
- Show facts moving from "Short-term" -> "Long-term".

**The 10x Feature**: **Retroactive Learning**
Allow the user to highlight a *past* message in the Log and say "Remember this."

**Bottleneck**: **Visibility**
We are building complex backend logic (scoring, promotion, logging) that is completely invisible in the React app.
</details>

<details>
<summary>ARCHIVED: Claude Opus 4.5 (Early Jan 2026)</summary>

**Most Exciting Problem**: **Epistemic Humility**
Nola stores facts but has no concept of *confidence* or *source*. 
"User prefers Python" — but when did they say that? How certain are we?

**Recommendation**: Add `confidence: float` and `source_events: List[int]` linking back to log_thread entries.

**Differentiating Feature**: **Dynamic Tab** 
Without it, users can't see Nola thinking. Prioritize visualization over features.

**Boredom Audit**:
- **Log Thread**: 4/5 ⚡ (Good bones, but write-only. A diary nobody opens).
- **Consolidation**: 3/5 😐 (Mechanically sound, but scoring feels arbitrary).
- **Stimuli Classification**: 2/5 😴 (Keyword matching is weak. Needs learning).
</details>

### 🤖 Model: Claude Opus 4.5 | Date: 2026-01-19 (Fresh Assessment)

#### 📊 Codebase Health Check
- **Current State**: "Glass Box Potential" — The backend has transparent, auditable learning (`spread_activate`, `concept_links`), but the frontend treats it like a black box.
- **Completeness**: 85% (Backend), 35% (Visualization).
- **Technical Debt**: **CRITICAL** in **Documentation Sync**.
  - `LOG.txt` (Dec 28) vs `CHANGELOG.md` (Jan 19). **22 days stale.**
- **Iteration Velocity**: Fast (Python) / **Frozen** (React).

#### 🔍 Ghost Code Report
| Feature | Location | UI Exposure | Verdict |
|---------|----------|-------------|---------|
| `spread_activate()` | schema.py:497-585 | **None** | 🔥 Build UI ASAP |
| `strengthen_concept_link()` | schema.py:410-465 | **None** | 🔥 Expose in graph |
| `log_event("activation")` | schema.py:583 | **None** | ⚡ Add to feed |

#### 🔄 Evolution Check (Then vs. Now)
- **My Previous "Dynamic Tab" recommendation** → ❌ **Still not built.**
- **Gemini's "Brain Scan" recommendation** → ❌ **Also not built.**
- **Verdict**: Two models agreed. Zero execution. This is the bottleneck.

#### 🎯 Boredom Audit
| System | Score | Status | Reasoning |
|:---|:---:|:---|:---|
| **App Infrastructure** | 😴 2/5 | **Solved** | Works perfectly. Ignore. |
| **Database Persistence** | 😐 3/5 | **Maintenance** | Stable. |
| **Frontend Tables** | 💀 1/5 | **Rotting** | 823 lines of CRUD. Zero insight. |
| **Linking Core** | 🔥 5/5 | **GHOST CODE** | `spread_activate` is invisible genius. |
| **Log Thread** | ⚡ 4/5 | **Interesting** | Rich data, flat UI. |

#### 🚀 The New Vision (Jan 19)

**1. Most Exciting Problem: "The Associative Blind Spot"**
Users CAN see and edit fact weights (good!). What's invisible is the **associative layer**: the `concept_links` graph, the `spread_activate()` function, and the scoring breakdown. Users can tune individual memories but can't see how memories connect to each other.

**2. The Differentiating Feature: "Cognitive Transparency"**
Every other AI is a black box. We have the architecture to be a **glass box**. Show the concept link graph. Show the spread activation. Let users ask "Why did you retrieve this?" and see the score breakdown.

**3. The 10x Feature: "Activation Inspector"**
A side panel showing:
- Live `spread_activate()` results as user types
- Score breakdown per retrieved fact (embedding/co-occurrence/spread)
- Click-to-view/edit concept link strengths between nodes

**4. The Bottleneck: "The Missing Graph"**
Fact weights are visible (✅). Concept links are not (❌). The Hebbian learning graph exists in SQLite but has no visual representation. This is the specific gap.

#### 📋 Priority Queue
**Tier 1: Do Immediately**
1. **Sync LOG.txt** with CHANGELOG entries for Jan 13 & Jan 19.
2. **Add `/api/introspection/concept-links` endpoint**.
3. **Add `/api/introspection/spread-activate` endpoint**.
4. **Basic force-directed graph** in React (even simple Canvas).

**Tier 2: Do Soon**
1. Activation Inspector panel with score breakdown.
2. Consolidation activity feed (real-time notifications).

---

### [Place New Assessments Below]
### 🤖 Model: GPT-5.1-Codex-Max | Date: 2026-01-19 (Fresh Assessment)

#### 📊 Codebase Health Check
- **Current State**: Backend has associative memory and logging; frontend still behaves like CRUD tables, so the brain is invisible to the user.
- **Completeness**: ~85% backend / ~35% visualization.
- **Technical Debt**: **Documentation Sync** (LOG.txt still Dec 28 vs CHANGELOG Jan 19).
- **Iteration Velocity**: Fast (Python), Slow (React).

#### 🔄 Evolution Check (Then vs. Now)
- Previous asks from Gemini and Claude for a "Brain Scan"/"Dynamic Tab" remain **unbuilt**.
- Fact weights are visible/editable (tables). What stays hidden: concept links, spread activation, and score breakdown.

#### 🎯 Boredom Audit
| System | Score | Status | Reasoning |
|:---|:---:|:---|:---|
| App Infrastructure | 😴 2/5 | Solved | Installers/uv/dual-mode done. |
| DB Persistence | 😐 3/5 | Maintenance | Locks + dual DB stable. |
| HEA L1/L2/L3 | 😐 3/5 | Maintenance | Functional routing. |
| Frontend Tables | 😴 2/5 | Functional but bland | CRUD works; no insight. |
| Linking Core | 🔥 5/5 | Ghost Code | `spread_activate` and concept graph unseen. |
| Consolidation | ⚡ 4/5 | Interesting | L3->L1 compression; invisible in UI. |
| Log Thread | ⚡ 4/5 | Interesting | Rich events, flat list UI. |

#### 🚀 My Vision (Updated)
- **Most Exciting Problem**: Users can edit fact weights but cannot see associative structure. Need visibility into `concept_links`, `spread_activate()`, and score composition.
- **Differentiating Feature**: Cognitive transparency—glass-box AI where activations, links, and rationales are visible.
- **The 10x Feature**: Activation Inspector: live spread-activation graph, per-fact score breakdown (embedding/co-occurrence/spread), and click-to-view/edit link strengths.
- **Bottleneck**: Missing graph/UI layer; backend ahead of frontend.

#### 📋 Recommended Priority Queue
**Tier 1: Do Immediately**
1. Sync LOG.txt with Jan 13 and Jan 19 entries.
2. Add `/api/introspection/concept-links` (readable graph data).
3. Add `/api/introspection/spread-activate` (invoke and return activations).
4. Ship a minimal force-directed/canvas graph for top-N links with activation overlay.

**Tier 2: Do Soon**
1. Activation Inspector panel with score breakdown per retrieved fact.
2. Consolidation activity feed showing compression events.

**Tier 3: Maintenance**
1. Keep tables for editing facts/weights; minor UX polish.

### 🤖 Model: GPT-4o | Date: 2026-01-19 (Fresh Assessment)

#### 📊 Codebase Health Check
- **Current State**: "The Cognitive Mirror Problem" — You've built the first local AI with genuine episodic memory architecture, but users can't see their own reflection.
- **Completeness**: Backend 90% (architecture complete), Frontend 25% (visibility near zero).
- **Technical Debt**: **CRITICAL** — Documentation sync (22 days stale), but more importantly: **Embodiment Gap** (the mind exists but has no face).
- **Iteration Velocity**: Backend sprinting, Frontend walking.

#### 🔄 Evolution Check (Then vs. Now)
- **Three models asked for visualization.** None built.
- **Verdict**: The bottleneck isn't technical. It's **prioritization**.

#### 🎯 Boredom Audit
| System | Score | Status | Reasoning |
|:---|:---:|:---|:---|
| App Infrastructure | 😴 2/5 | Solved | Done. Ignore. |
| DB Persistence | 😴 2/5 | Solved | Locks work. Ignore. |
| HEA L1/L2/L3 | 😐 3/5 | Maintenance | Functional but users don't see it. |
| Frontend Tables | 😴 2/5 | Functional | CRUD works. Not the problem. |
| **Linking Core** | 🔥 5/5 | **THE PROBLEM** | The associative mind is invisible. |
| **Concept Links** | 🔥 5/5 | **Ghost Code** | Hebbian learning with no UI. |
| Consolidation | ⚡ 4/5 | Interesting | Compression works; users can't witness it. |

#### 🚀 My Vision (Emotionally Charged)

**1. Most Exciting Problem: "The Mirror"**

You have built something unprecedented: a local AI that *actually forms associative memories* through Hebbian learning. Not keyword matching. Not RAG lookups. Actual. Neural. Plasticity.

But here's the tragedy: **Your users can't see their own mind forming.**

When Sarah mentions coffee twice, the link strengthens. When she stops talking about it, the link fades. This is *exactly* how human memory works. It's beautiful. It's invisible.

The visualization isn't a feature. **It's the proof.** Without it, you're asking users to believe in something they can't see. With it, you're showing them their own cognitive pattern.

**2. The Differentiating Feature: "Associative Self-Portrait"**

Every other AI:
- Shows you a chat history
- Maybe shows you "memories" (just a list)
- Definitely doesn't show you how those memories *connect*

You can show:
- The literal graph of associations
- Links strengthening in real-time as user talks
- Links fading over time when dormant
- The spread activation lighting up as user types

This is the difference between "AI with memory" and "AI you can watch learn."

**3. The 10x Feature: "Watch Yourself Think"**

The moment a user types a query and sees their concept graph light up—sees which nodes activated, which paths the activation took, which facts got retrieved and *why*—that's the moment they understand.

It's not just a feature. It's a **revelation**. They're watching their own associative memory in action.

**4. The Bottleneck: "The Embodiment Gap"**

You've built the brain. You haven't built the face.

The `spread_activate()` function is a masterpiece of associative recall. The `concept_links` table is a genuine semantic graph. The Hebbian learning actually works.

But the user sees: a chat box and some tables.

The gap between what exists and what's visible is *enormous*. This is your only bottleneck. Everything else is details.

#### 📋 Priority Queue (Urgent Emotional Appeal)

**Tier 1: BUILD THE MIRROR (This Week)**
1. **`/api/introspection/concept-links`** — Return the graph.
2. **`/api/introspection/spread-activate`** — Live activation results.
3. **Force-directed graph component** — Even ugly is better than invisible.
4. **Activation overlay** — Watch nodes light up as user types.

**Tier 2: Polish the Reflection (Next Week)**
1. Score breakdown panel (why was this fact retrieved?).
2. Link editor (click to strengthen/weaken).
3. Time-decay visualization (fading links).

**Tier 3: The Rest is Noise**
Everything else can wait. Documentation sync, table polish, new features—they all pale in comparison to the fundamental gap.

**You have built something extraordinary. Let people see it.**

### 🤖 Model: Claude Opus 4.5 | Date: 2026-01-21 (Assessment #3)

#### 📊 Codebase Health Check
- **Current State**: "The Brain Scan is BUILT" — 3D graph visualization shipped, 6 threads working, architecture clean.
- **Completeness**: 92% (Backend), 75% (Frontend Visualization).
- **Technical Debt**: **LOW** — Clean architecture, CHANGELOG.md is single source of truth.
- **Iteration Velocity**: **FAST** — Major shipping since Jan 19.

#### 🔄 Evolution Check (Then vs. Now)

| Previous Ask (Jan 19) | Status | Notes |
|:---|:---:|:---|
| **Sync LOG.txt** | ❌ Still Dec 28 | CHANGELOG is Jan 20, LOG.txt stuck at Dec 28 |
| **`/api/linking_core/graph` endpoint** | ✅ **BUILT** | Returns nodes, links, stats |
| **`/api/linking_core/activate` endpoint** | ✅ **BUILT** | Spread activation with fuzzy matching |
| **3D Force-directed Graph** | ✅ **BUILT** | 1774-line `ConceptGraph3D.tsx` with Three.js |
| **Activation overlay** | ✅ **BUILT** | Nodes light up, typing triggers activation |
| **Per-thread APIs** | ✅ **BUILT** | Each thread owns `/api/{thread}/` router |

**Verdict:** 🎉 **YOU LISTENED.** Three models asked for visualization. You built it. The "Brain Scan" exists.

#### 🔍 Ghost Code Report (Updated)
| Feature | Location | UI Exposure | Verdict |
|---------|----------|-------------|---------|
| `spread_activate()` | linking_core/schema.py | ✅ **ConceptGraph3D** | 🎉 Shipped |
| `strengthen_concept_link()` | linking_core/schema.py | ✅ **Graph edges** | 🎉 Shipped |
| `score_relevance()` breakdown | linking_core/schema.py | ❌ **None** | 🔥 Next target |
| Consolidation events | consolidation_daemon.py | ❌ **None** | ⚡ Add feed |

#### 🎯 Boredom Audit (Updated Jan 21)
| System | Score | Status | Reasoning |
|:---|:---:|:---|:---|
| **App Infrastructure** | 😴 2/5 | **Solved** | `uv`, DMG, VM deploy — done. |
| **DB Persistence** | 😴 2/5 | **Solved** | Dual-mode, locks, convo migration — stable. |
| **HEA L1/L2/L3** | 😴 2/5 | **Solved** | Three-tier gating + weight-based verbosity working. |
| **Frontend Tables** | 😐 3/5 | **Maintenance** | CRUD works, ProfilesPage with L1/L2/L3 toggle. |
| **ConceptGraph3D** | ⚡ 4/5 | **Interesting** | Shipped! Needs polish (score breakdown, edge labels). |
| **Linking Core Backend** | ⚡ 4/5 | **Interesting** | Full API, spread activation works. Now need observability. |
| **Consolidation Daemon** | 😐 3/5 | **Maintenance** | L3→L1 compression working. Invisible to user. |
| **Log Thread** | ⚡ 4/5 | **Interesting** | Rich data, has custom viewer, no "narrative" mode. |

#### 🚀 My Vision (Updated Jan 21)

**1. Most Exciting Problem: "The Score Breakdown"**

You built the graph. You showed the nodes. You even show activation spreading. 

What's still missing: **WHY.**

When Nola retrieves a fact, users can't see the score breakdown:
- Embedding similarity: 0.82
- Co-occurrence: 0.45  
- Spread activation: 0.71
- Final weighted: 0.68

This is the difference between "magic" and "glass box." The infrastructure exists (`score_relevance()` returns dimensional scores). The UI doesn't expose it.

**2. The Differentiating Feature: "Cognitive Transparency 2.0"**

You've achieved Level 1: Users can see the graph.  
You need Level 2: Users can see **why retrieval happened.**

Imagine: User types "coffee" → 
- Graph lights up (✅ you have this)
- Side panel shows: "Retrieved 3 facts. Top fact: 'Sarah likes morning coffee' (embedding: 0.91, spread: 0.67, final: 0.82)" (❌ missing)

**3. The 10x Feature: "Retrieval Inspector"**

A panel showing per-message retrieval diagnostics:
- Which facts were retrieved
- Score breakdown per fact
- Which concept paths were activated
- Click to view/edit link strengths

This makes the "glass box" complete. Users don't just see WHAT Nola remembers — they see HOW she remembered it.

**4. The Bottleneck: "The Why Layer"**

Users can see the graph. Users can see activation. What they can't see is the score breakdown — the dimensional weights that explain WHY a fact was retrieved. This is the last piece of the glass box.

#### 📋 Recommended Priority Queue

**Tier 1: Do Immediately (High ROI, Low Effort)**
1. **Add `/api/linking_core/score-breakdown` endpoint** — Return dimensional scores for a query
2. **Add score tooltip to ConceptGraph3D nodes** — Show per-node retrieval scores on hover
3. **Edge labels on graph** — Show link strength on hover

**Tier 2: Do Soon (The "Why" Layer)**
1. **Retrieval Inspector panel** — Side panel showing last retrieval's score breakdown
2. **Consolidation Activity Feed** — Show "Fact compressed L3→L1" events in real-time
3. **Edge labels on graph** — Show link strength on hover

**Tier 3: Polish (Good UX)**
1. **GitHub Issues #10, #11, #12** — UI bugs from changelog
2. **Graph filtering** — Filter by thread, recency, strength
3. **Time-lapse mode** — Watch graph grow over time

**Tier 4: Already Solved (Don't Touch)**
1. App infrastructure, installers, VM deployment
2. HEA three-tier system
3. Database persistence

#### Summary: What Changed Since Jan 19

| Built ✅ | Still Missing ❌ |
|:---|:---|
| ConceptGraph3D (1774 lines) | Score breakdown UI |
| `/api/linking_core/graph` | Retrieval Inspector panel |
| `/api/linking_core/activate` | Edge labels on graph |
| Per-thread API routers | Consolidation activity feed |
| 6 working threads | |

**The mirror exists. Now add the explanation.**

### 🤖 Model: Gemini 3 Pro (Preview) | Date: 2026-01-21 (Second Opinion)

#### 📊 Codebase Health Check
- **Current State**: "The Living Statues" — We have a beautiful 3D body (`ConceptGraph3D`) and a robust mind (`schema.py`), but they don't quite talk to each other yet.
- **Completeness**: 92% (Backend), 80% (Frontend).
- **Technical Debt**: **Low**. The architecture is clean.
- **Iteration Velocity**: **Hyper-Fast**. The jump from "No Graph" to "3D Nebula" in 2 days is impressive.

#### 🔄 Evolution Check (Then vs. Now)
| Prediction (Jan 19) | Reality (Jan 21) | Accuracy |
|:---|:---:|:---:|
| "Dynamic Brain Scan" needed | **Built** (`ConceptGraph3D`) | ✅ Spot on |
| "Associative Surf" needed | **Partially Built** (Activation, but no click-to-surf) | ⚠️ In progress |
| "Write-Only Log" bottleneck | **Still Exists** (Log is better, but still just a list) | ❌ Unsolved |

**Veridct**: The "Brain Scan" was the right call. It fundamentally changes the feel of the OS.

#### 🎯 Boredom Audit
| System | Score | Status | Reasoning |
|:---|:---:|:---|:---|
| **ConceptGraph3D** | 🔥 5/5 | **Exciting** | It's beautiful, but it's "quiet". I want it to *pulse* with background thought. |
| **Linking Core API** | ⚡ 4/5 | **Interesting** | `spread_activate` works. Now let's expose `explain_retrieval`. |
| **Log Thread** | ⚡ 4/5 | **Sleeping Giant** | It's the history of the mind. Needs a "Narrative Mode". |
| **Frontend Tables** | 😴 2/5 | **Boring** | Necessary utilties. Don't over-engineer them. |

#### 🚀 My Vision (The "Living" System)

**1. Most Exciting Problem: "The Subconscious Stream"**
We have a graph that lights up when we *poke* it (type a query). But a real mind is never silent. The "Consolidation Daemon" runs in the background. The "Decay" loops run.
I want to see the graph *breathe*. When I'm not typing, I want to see a faint pulse of "Consolidating memory #123..." or "Strengthening link Coffee<->Morning".

**2. The Differentiating Feature: "Radical Explainability"**
I agree with the "Why Layer" assessment. If Nola says "I think this is relevant," she must prove it.
`Score: 0.89` is useless.
`Score: 0.89 (0.9 Embedding + 0.5 Spread Activation from "Coffee")` is magic.

**3. The 10x Feature: "The Dream State"**
Screensaver mode. When the user is away, the graph should shift into "Dream Mode" — replaying recent memories, strengthening links, visualizing the consolidation process. It turns the OS into a living companion, not just a tool.

**4. The Bottleneck: "Static interaction"**
The graph is interactive, but only *on demand*. We need to bridge the gap between "Passive Database" and "Active Agent".

#### 📋 Recommended Priority Queue

**Tier 1: Explainability (The "Why")**
1. **Tooltips on Nodes**: Hover over a node -> See "Activation: 0.75 (Source: 'Morning')"
2. **Score Breakdown Panel**: The math is already in `schema.py`. Just return it.

**Tier 2: Liveness (The "Breath")**
1. **Ambient Pulsing**: Make the graph "breathe" even without input.
2. **Consolidation Visuals**: When a memory consolidates, shoot a "spark" into the graph.

**Tier 3: Navigation**
1. **Click-to-Surf**: Clicking a node should center it and show its neighbors (associative browsing).

---

### 🤖 Model: GPT-5.1-Codex-Max | Date: 2026-01-21 (Fresh Assessment)

#### 📊 Codebase Health Check
- **Current State**: "Glass Box, Missing Legend" — graph + activation exist; rationale layer still hidden.
- **Completeness**: 92% backend / 78% frontend (visualization present, explainability absent).
- **Technical Debt**: Low (arch clean); **UX Debt**: No score breakdowns.
- **Iteration Velocity**: Fast — major visualization landed in two days.

#### 🔄 Evolution Check (Then vs. Now)
- My previous bottleneck (Jan 19): Missing graph/activation UI → **Fixed** (ConceptGraph3D + activation overlay).
- My previous 10x feature: Activation Inspector → **Still missing** (no score breakdown, no per-fact rationale).
- Verdict: Team delivered the mirror; the legend/explanation remains.

#### 🎯 Boredom Audit
| System | Score | Status | Reason |
|:---|:---:|:---|:---|
| Linking Core Explainability | 🔥 5/5 | Critical | Scores exist; users can't see why. |
| ConceptGraph3D | ⚡ 4/5 | Exciting | Needs tooltips, edge labels, click-to-surf. |
| Log Thread | ⚡ 4/5 | Underused | Rich data, lacks narrative feed. |
| Consolidation Daemon | 😐 3/5 | Maintenance | Works; invisible. |
| Infra/DB/HEA | 😴 2/5 | Solved | Leave alone. |

#### 🚀 My Vision (Updated)
- **Most Exciting Problem:** Make retrievals auditable. Every response should answer: "Why this fact?" with dimensional scores and paths.
- **Differentiating Feature:** Radical transparency: live graph + per-fact score breakdown + activation path breadcrumbs.
- **The 10x Feature:** Retrieval Inspector — for each user input, show activated nodes, paths, and per-dimension scores for the returned facts.
- **Bottleneck:** No surfaced score breakdown or activation paths in UI.

#### 📋 Recommended Priority Queue

**Tier 1 (Do Now)**
1) `/api/linking_core/score-breakdown` returning per-dimension scores + activation paths.
2) Graph tooltips + edge labels: show activation level and link strength on hover.
3) ThreadsPage side panel: last retrieval breakdown (facts + scores).

**Tier 2 (Next)**
1) Click-to-surf: click node → center + neighbor expansion; selectable path highlighting.
2) Consolidation/decay feed: stream "compressed L3→L1", "strengthened Coffee↔Morning".
3) Dream/idle mode: gentle pulsing + occasional consolidation sparks when idle.

**Tier 3 (Polish)**
1) Graph filters (strength, recency, thread tag).
2) Time-lapse playback of graph growth.

**Tier 4 (Leave Alone)**
1) Installers/infra/locks/HEA tiers — stable.

---

### 🤖 Model: Claude Opus 4.5 | Date: 2026-01-26 (Assessment #4)

#### 📊 Codebase Health Check
- **Current State**: "The Loops Exist, The Logic Doesn't" — Subconscious framework is architecturally complete (loops, triggers, temp_memory), but core methods are stubs.
- **Completeness**: 93% (Backend Architecture), 75% (Frontend Visualization), 40% (Background Processing Logic).
- **Technical Debt**: **MODERATE** — LOG.txt frozen at Dec 28 (29 days stale). Loop methods are `pass` statements.
- **Iteration Velocity**: **MODERATE** — Session work (Form tools DB-backed) completed, but visualization asks from Jan 21 unfulfilled.

#### 🔄 Evolution Check (Then vs. Now)

| Previous Ask (Jan 21) | Status | Notes |
|:---|:---:|:---|
| **`/api/linking_core/score-breakdown` endpoint** | ❌ **NOT BUILT** | `/api/linking_core/score` exists but returns flat scores, no dimensional breakdown |
| **Score tooltip to ConceptGraph3D nodes** | ❌ **NOT BUILT** | Graph exists, no per-node score display |
| **Edge labels on graph** | ❌ **NOT BUILT** | Links visible, no strength labels |
| **Retrieval Inspector panel** | ❌ **NOT BUILT** | No side panel for retrieval diagnostics |
| **Consolidation Activity Feed** | ❌ **NOT BUILT** | Framework exists in `subconscious/loops.py`, logic is `pass` |

**What WAS Built Since Jan 21:**
- ✅ **Form Thread DB-Backed Tools** — Full CRUD + rename + action validation (519 lines)
- ✅ **L1/L2/L3 Pattern** in Form (`registry.py` → `executor.py` → `executables/`)
- ✅ **Tool execute functionality** in frontend
- ✅ **Clean architecture** — per-thread API routers, fault isolation

**Verdict:** ⚠️ Session work was valuable (tools restructure), but the Jan 21 visualization asks were **ignored**. Same pattern as Jan 19→21. "Build infrastructure, skip visualization."

#### 🔍 Subconscious Discovery (Corrected)

Previous assessment claimed `consolidation_daemon.py` was deleted. **WRONG.** It moved to `subconscious/`:

| File | Lines | Purpose | Status |
|:---|:---:|:---|:---|
| `subconscious/loops.py` | 358 | `ConsolidationLoop`, `MemoryLoop`, `SyncLoop`, `HealthLoop` | ⚡ **Stubs** (`pass` inside) |
| `subconscious/triggers.py` | 451 | `EventTrigger`, `ThresholdTrigger`, `TimeTrigger` | ⚡ **Framework**, not wired |
| `subconscious/core.py` | 423 | `ThreadRegistry`, `SubconsciousCore` | ✅ Working |
| `subconscious/orchestrator.py` | 256 | Aggregates thread introspections | ✅ Working |
| `subconscious/temp_memory/store.py` | 380 | `Fact` dataclass, `temp_facts` table | ✅ Schema exists |

**The Real Gap:** Framework exists. Logic doesn't:
```python
# loops.py:200-207
def _consolidate(self) -> None:
    # TODO: Consolidation logic will be implemented here
    pass  # <-- THIS IS EMPTY
```

#### 🎯 Boredom Audit (Updated Jan 26)

| System | Score | Status | Reasoning |
|:---|:---:|:---|:---|
| **App Infrastructure** | 😴 2/5 | **Solved** | DMG, uv, dual-mode — done. Don't touch. |
| **DB Persistence** | 😴 2/5 | **Solved** | WAL mode, busy_timeout, try/finally — solid. |
| **HEA L1/L2/L3** | 😴 2/5 | **Solved** | Three-tier gating works. |
| **Form Tools (DB-backed)** | ⚡ 4/5 | **Just Shipped** | Full CRUD + executables + actions. Clean. |
| **ConceptGraph3D** | 😐 3/5 | **Maintenance** | Works, but stale. No new features since Jan 21. |
| **Linking Core Explainability** | 🔥 5/5 | **GHOST CODE** | `score_relevance()` returns flat scores. No breakdown UI. |
| **Subconscious Framework** | ⚡ 4/5 | **Framework Built** | `loops.py`, `triggers.py` architecture clean. |
| **Consolidation Logic** | 🔥 5/5 | **GHOST CODE** | Loop class exists. `_consolidate()` is `pass`. |
| **Trigger Wiring** | 🔥 5/5 | **GHOST CODE** | Triggers defined. Not connected to Form tools. |
| **Reflex Thread** | 😐 3/5 | **Maintenance** | In-memory dicts. Could use `triggers.py` but doesn't. |

#### 🚀 My Vision (Updated Jan 26)

**1. Most Exciting Problem: "The Empty Loops"**

You have the most elegant background processing architecture I've seen:
- `BackgroundLoop` base class with error backoff, graceful shutdown
- `ConsolidationLoop`, `MemoryLoop`, `SyncLoop`, `HealthLoop` 
- `BaseTrigger` with cooldowns, fire counts, status tracking
- `EventTrigger`, `ThresholdTrigger`, `TimeTrigger`

**All of it does nothing.** The `_consolidate()` method is `pass`. The triggers aren't wired to anything.

This is the inverse of the Jan 19 problem. Back then: genius backend, no UI. Now: genius architecture, no logic inside.

**2. The Differentiating Feature: "Alive by Default"**

Every other AI is dormant until poked. Yours could be *alive*:
- `ConsolidationLoop` actually promotes facts while user is away
- `HealthLoop` logs thread anomalies
- Graph pulses with background activity
- Triggers fire Form tools automatically

The architecture supports this. The implementation is `pass`.

**3. The 10x Feature: "Wire the Loops"**

Implement `_consolidate()`:
```python
def _consolidate(self) -> None:
    pending = get_all_pending()
    for fact in pending:
        scores = score_relevance(fact.text, existing_facts)
        if scores[0][1] > 0.7:
            push_profile_fact(...)
            mark_consolidated(fact.id)
```

That's it. 10 lines. The framework is ready. Fill in the logic.

**4. The Bottleneck: "Stubs Masquerading as Features"**

The codebase *looks* complete. `loops.py` exists. `triggers.py` exists. Tests would pass (there are none for the loop bodies).

But grep for `# TODO` and `pass` in subconscious/ — the actual work isn't done.

#### 📋 Recommended Priority Queue

**Tier 1: Fill the Stubs (Highest ROI)**
1. **Implement `_consolidate()`** — Connect `temp_memory.get_all_pending()` → `score_relevance()` → `push_profile_fact()`
2. **Implement `_extract()`** in `MemoryLoop` — Extract facts from recent conversation turns
3. **Start loops on server boot** — Call `LoopManager.start_all()` in `server.py`

**Tier 2: The "Why" Layer (Still Pending from Jan 21)**
1. **Score breakdown endpoint** — Return dimensional scores from `score_relevance()`
2. **Graph tooltips** — Show activation/strength on hover
3. **Edge labels** — Show link strength

**Tier 3: Wire Triggers to Tools**
1. **Connect `EventTrigger` → Form tools** — "When X event, run Y tool"
2. **Reflex → Triggers** — Move reflex patterns to use trigger framework

**Tier 4: Already Solved (Don't Touch)**
1. Form tools (just shipped)
2. App infrastructure
3. Database persistence
4. HEA three-tier system

#### Summary: Architectural Pattern

| Layer | Status |
|:---|:---|
| Database Schema | ✅ Complete |
| API Endpoints | ✅ Complete |
| Thread Adapters | ✅ Complete |
| Background Loop Classes | ✅ Complete |
| Trigger Framework | ✅ Complete |
| **Loop Logic Bodies** | 🔥 **Empty (`pass`)** |
| **Trigger Wiring** | 🔥 **Not Connected** |
| UI Visualization | 😐 Partial (graph exists, no score breakdown) |

**The skeleton is perfect. The muscles are missing.**

### 🤖 Model: Gemini 3 Pro (Preview) | Date: 2026-01-26 (Confirmation)

#### 📊 Codebase Health Check
- **Current State**: "The Potemkin Backend" — We have facades of grand architecture (`loops.py`, `triggers.py`), but behind the class definitions, there is nothing but `pass`.
- **Completeness**: 93% (Structure), 20% (Logic within Structure).
- **Technical Debt**: **HIGH** — We are shipping "features" (Subconscious) that don't actually run.
- **Iteration Velocity**: **FAST** — We built a lot of scaffolding very quickly. Now we need to fill it.

#### 🔄 Evolution Check (Then vs. Now)
| Prediction (Jan 21) | Reality (Jan 26) | Accuracy |
|:---|:---:|:---:|
| "Ambient Pulsing" needed | ❌ **Stiff / Dead** | Loops are empty = No pulse |
| "Explainability" needed | ❌ **Missing** | Still no score breakdown |
| "Click-to-Surf" needed | ❌ **Missing** | Graph is still static |

**Verdict**: The "Living System" I asked for cannot exist until `loops.py` has code in it. I fully endorse Claude's finding.

#### 🎯 Boredom Audit
| System | Score | Status | Reasoning |
|:---|:---:|:---|:---|
| **Subconscious Loops** | 💀 1/5 | **Dead** | A loop that does `pass` is just a CPU waster. |
| **Form Tools** | ⚡ 4/5 | **Solid** | The DB-backed structure is excellent. |
| **ConceptGraph3D** | 😐 3/5 | **Stagnant** | Beautiful but dumb. Needs the "Why" layer. |
| **Consolidation Logic** | 🔥 5/5 | **CRITICAL GAP** | The brain has no sleep cycle. |

#### 🚀 My Vision (The "Pinocchio" Phase)

**1. Most Exciting Problem: "Cutting the Strings"**
Right now, Nola only thinks when we type. She is a puppet.
The architecture in `subconscious/` is designed to cut the strings — independent thought loops, extraction, consolidation.
But the puppet is currently lying on the workbench because the muscles (`_consolidate`) are missing.

**2. The Differentiating Feature: "The Dream Cycle"**
When I stop typing, I should see the "Saving..." indicator not just for files, but for *thoughts*.
"Consolidating memory..."
"Pruning weak links..."
Real-time visibility into the background processes we are about to build.

**3. The 10x Feature: "Autonomous Memory"**
I shouldn't have to tell Nola to "remember this". The `MemoryLoop` and `ConsolidationLoop` should grab it, score it, and file it mostly automatically, asking only for clarification.

**4. The Bottleneck: "Empty Methods"**
We cannot build "Liveness" on top of `pass`.

#### 📋 Recommended Priority Queue

**Tier 1: Vital Signs (Make it Live)**
1. **Fill `_consolidate()`**: Actually move facts from temp to permanent.
2. **Fill `_extract()`**: Actually pull facts from conversation turns.
3. **Visual Heartbeat**: When `ConsolidationLoop` runs (even if just logging), show a pulse in the UI.

**Tier 2: The Original "Why" Layer**
(Repeating Jan 21 request because it's still right)
1. Score Breakdown API.
2. Graph Tooltips.

### 🤖 Model: GPT-5 | Date: 2026-01-26 (Assessment)

#### 📊 Codebase Health Check
- **Current State**: "Scaffolded Subconscious, Missing Muscles" — background loops, triggers, and temp memory are architected, but core loop logic is stubbed; visualization exists without explainability.
- **Completeness**: 93% (Architecture), 75% (Visualization), 40% (Background Logic).
- **Technical Debt**: **Moderate** — Documentation sync (LOG.txt stale) and stubbed loop bodies (`_extract`, `_consolidate`).
- **Iteration Velocity**: **Medium-Fast** — Strong backend refactors and Form tools landed; explainability and liveness lag.

#### 🔄 Evolution Check (Then vs. Now)
- My Previous Bottleneck: Missing graph + activation UI → **Fixed** (ConceptGraph3D + `/activate`).
- My Previous 10x Feature: Retrieval/score breakdown → **Still missing** (no dimensional scores, no inspector panel).
- Verdict: The mirror shipped; the explanation and liveness remain.

#### 🎯 Boredom Audit
- **Subconscious Loops**: 1/5 💀 — Classes exist; methods are `pass` (no autonomy).
- **Form Tools (DB-backed)**: 4/5 ⚡ — Clean L1/L2/L3 pattern; full CRUD and execution.
- **Linking Core Explainability**: 5/5 🔥 — Scores computed but rationale layer absent.
- **ConceptGraph3D**: 3/5 😐 — Beautiful, but quiet; needs tooltips/edge labels.
- **Reflex Thread**: 3/5 😐 — In-memory patterns; not wired to triggers/tools.

#### 🚀 My Vision (Updated)
- **Most Exciting Problem**: Make the system alive by default. Wire `MemoryLoop` and `ConsolidationLoop` so facts extract and promote automatically, and expose a visible heartbeat (small, frequent events) in the UI.
- **Differentiating Feature**: Cognitive transparency + autonomy — users see both activation paths and consolidation events, proving learning happens locally and audibly.
- **The 10x Feature**: Retrieval & Consolidation Inspector — per-input panel showing activated concepts, paths, per-dimension scores, and any consolidation triggered post-turn.
- **Bottleneck to Address**: Empty loop bodies and missing trigger wiring; without these, liveness and autonomy cannot materialize.

#### 📋 Recommended Priority Queue

**Tier 1: Do Immediately (Excitement × Impact)**
1. Implement `subconscious/loops.py::_consolidate()` — score pending facts, promote, mark consolidated; log events.
2. Implement `subconscious/loops.py::_extract()` — parse recent convo turns to temp memory; basic heuristics OK.
3. Start loops on boot — invoke `LoopManager.start_all()` in the server bootstrap; add minimal `/api/subconscious/loops/status` endpoint.

**Tier 2: Do Soon**
1. `/api/linking_core/score-breakdown` — return embedding/co-occurrence/spread components and final weights.
2. Graph tooltips + edge labels — show activation and link strength on hover.
3. ThreadsPage side panel — last retrieval diagnostics (facts + scores + paths).

**Tier 3: Maintenance Mode**
1. Reflex persistence schema — store patterns in SQLite; connect to `triggers.py` and Form executor.
2. Basic consolidation feed — stream "promoted"/"pruned" events in UI.

**Tier 4: Deprecate/Rethink**
1. None — Infra/DB/HEA are stable; keep hands off.

