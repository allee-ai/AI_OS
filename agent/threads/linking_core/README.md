# Linking Core Thread

**Cognitive Question**: WHICH concepts matter NOW?  
**Resolution Order**: 6th (final gating — what actually enters context)  
**Brain Mapping**: Thalamic Gating (selective attention, relevance filtering)

---

The Linking Core is not a data store — it's the **relevance engine** that determines what's important *right now*.

## Purpose

While other threads store facts (identity, philosophy, form), Linking Core contains the **equations and algorithms** that score and select which facts surface in context.

## Core Concept: Spread Activation

When a concept is activated (e.g., user mentions "Sarah"), activation spreads to linked concepts:

```
[sarah] ──0.8──→ [sarah.likes.blue]
       ──0.6──→ [sarah.works.coffee_shop]  
       ──0.3──→ [sarah.mentioned.coffee]
                      │
                      └──0.5──→ [coffee]
```

This mimics how human memory works: thinking of a person activates related memories.

---

## The Math

### 1. Hebbian Learning (Link Strengthening)

**"Neurons that fire together, wire together"**

When two concepts co-occur (mentioned together in conversation), their link strengthens:

```
new_strength = old_strength + (1.0 - old_strength) × learning_rate
```

| Scenario | old_strength | learning_rate | new_strength |
|----------|--------------|---------------|--------------|
| First co-occurrence | 0.0 | 0.1 | 0.10 |
| Second co-occurrence | 0.1 | 0.1 | 0.19 |
| After 10 co-occurrences | 0.65 | 0.1 | 0.69 |
| Strongly linked | 0.9 | 0.1 | 0.91 |

**Key property**: Asymptotic approach to 1.0 — links can never exceed maximum strength, and strengthening slows as links become strong.

**Implementation**: `link_concepts()` in schema.py

---

### 2. Spread Activation

When the user mentions a concept, activation spreads through the link graph:

```
target_activation = source_activation × link_strength
```

**Multi-hop spreading** (default max_hops=1):
```
sarah (1.0) ──0.8──→ coffee (0.8) ──0.6──→ morning (0.48)
                                          ↑ below threshold, stops
```

**Hierarchical activation** (prefix matching):
```
sarah (1.0) → sarah.likes.* (0.8)
            → sarah.works.* (0.8)
            → sarah.mentioned.* (0.8)
```

Children of activated concepts get 80% activation automatically.

**Implementation**: `spread_activate()` in schema.py

---

### 3. Temporal Decay

Links that aren't reinforced fade over time:

```
new_strength = old_strength × decay_rate^days
```

| decay_rate | After 7 days | After 30 days | After 90 days |
|------------|--------------|---------------|---------------|
| 0.95 | 0.70 | 0.21 | 0.01 |
| 0.98 | 0.87 | 0.55 | 0.16 |
| 0.99 | 0.93 | 0.74 | 0.41 |

**Pruning**: Links below `min_strength` (default 0.05) are deleted.

**Implementation**: `decay_concept_links()` in schema.py

---

### 4. Co-occurrence Boost

Facts that have appeared together with current context get a relevance boost:

```
boosted_score = base_score × (1 + cooccur_boost)
```

Where `cooccur_boost` is 0.0–0.3 based on how often this fact has appeared with the current conversation's concepts.

**Implementation**: `_get_cooccurrence_boost()` in adapter.py

---

### 5. Multi-Dimensional Scoring (fact_relevance table)

Each fact has scores from multiple threads:

| Dimension | Thread | Description | Range |
|-----------|--------|-------------|-------|
| `identity_score` | Identity | Goal/value alignment | 0.0–1.0 |
| `log_score` | Log | Recency (when last accessed) | 0.0–1.0 |
| `form_score` | Form | Semantic similarity | 0.0–1.0 |
| `philosophy_score` | Philosophy | Emotional salience | 0.0–1.0 |
| `reflex_score` | Reflex | Access frequency | 0.0–1.0 |
| `cooccurrence_score` | LinkingCore | Co-occurrence with context | 0.0–1.0 |

**Final score** (computed by LinkingCore):
```
final_score = weighted_sum(all_scores)
```

This is **auditable** — every component score is stored and queryable.

---

## Tables

### `concept_links`
Learned associations between concepts (the graph):

| Column | Type | Description |
|--------|------|-------------|
| `concept_a` | TEXT | First concept (alphabetically ordered) |
| `concept_b` | TEXT | Second concept |
| `strength` | REAL | Link strength 0.0–1.0 |
| `fire_count` | INT | Times co-occurred |
| `last_fired` | TIMESTAMP | Last co-occurrence |

### `fact_relevance`
Multi-dimensional scoring matrix:

| Column | Type | Description |
|--------|------|-------------|
| `fact_key` | TEXT | Hierarchical key (e.g., sarah.likes.blue) |
| `fact_text` | TEXT | The actual fact content |
| `identity_score` | REAL | PFC contribution |
| `log_score` | REAL | Hippocampus contribution |
| `form_score` | REAL | Temporal lobe contribution |
| `philosophy_score` | REAL | Amygdala contribution |
| `reflex_score` | REAL | Basal ganglia contribution |
| `final_score` | REAL | Weighted aggregate |
| `access_count` | INT | Total accesses |
| `last_accessed` | TIMESTAMP | For recency scoring |

---

## Key Functions

### `link_concepts(concept_a, concept_b, learning_rate=0.1)`
Create or strengthen a link between two concepts using Hebbian learning.

### `spread_activate(input_concepts, activation_threshold=0.1, max_hops=1, limit=50)`
Spread activation from source concepts, returning all activated concepts with scores.

### `decay_concept_links(decay_rate=0.95, min_strength=0.05)`
Apply time-based decay to all links. Run daily via background daemon.

### `generate_hierarchical_key(fact_text)`
Convert fact text to hierarchical key: `"Sarah likes blue"` → `"sarah.likes.blue"`

### `extract_concepts_from_text(text)`
Pull concepts from user message for activation queries.

### `get_keys_for_concepts(activated_concepts, limit=30)`
Retrieve facts matching activated concepts (exact, prefix, and text search).

### `record_concept_cooccurrence(concepts, learning_rate=0.1)`
Record that these concepts appeared together, strengthening all pairwise links.

### `index_key_in_concept_graph(key, value, learning_rate=0.1)`
**NEW** — Auto-populate concept graph from any key:value write:
1. Links parent↔child along dot-notation hierarchy (`form.communication` ↔ `gmail`)
2. Extracts concepts from values and cross-links to key
3. Links sibling concepts from same value together

Called automatically by `push_identity_row()`, `push_philosophy_row()`, etc.

### `find_concepts_by_substring(search_terms, limit=30)`
**NEW** — Fuzzy search for concepts containing any of the search terms:
```python
find_concepts_by_substring(["gmail", "email"])
# Returns: ["form.communication.gmail", "identity.user.email"]
```

### `reindex_all_to_concept_graph()`
Batch reindex all existing data (identity, philosophy, form) into concept graph.

---

## 3D Visualization

The concept graph is visualized as an interactive 3D neural network in the Threads page:

### Visual Design
- **Purple Nebula Shell**: 4000 outer particles + 1200 inner wisps create a swirling cognitive boundary
- **Density-Aware Gas**: 2000 particles cluster around high-connection nodes, visualizing information density
- **Circular Sprites**: Soft radial gradient dots (not squares)
- **Additive Blending**: Glow effect where particles overlap

### Identity-Anchored Positioning
The most important design decision: **`name.agent` (or identity node) sits at origin (0,0,0)**.

Position is calculated by **graph distance from identity**:
- BFS traverses from identity node
- Closer to identity in the graph = closer to center in 3D space
- The shape emerges from actual topology, not forced

This means you can look at any node's position and understand WHY it's there.

### Temporal Dimension
Nodes are colored by age using `last_fired` timestamps from links:
- **Deep purple** (oldest): Ancient memories, core foundations
- **Silver/white** (newest): Recent activations, fresh information

Age gradient: `new THREE.Color(0.6+age*0.4, 0.4+age*0.6, 0.9+age*0.1)`

### Resonance Points
The visualization detects **curve intersections** — points where unrelated concept arcs cross in 3D space:
- These are "resonance points" that might indicate hidden relationships
- Rendered as bright glowing points at intersection locations
- Represents emergent structure that wasn't explicitly encoded

### Temporal-Identity Convergence

**Emergent property**: As the graph grows, temporal origin and self converge.

This wasn't explicitly coded — it falls out of the math:

1. **New concepts** appear at temporal edge (age=1, white) and potentially far from identity
2. **Decay removes** links that aren't reinforced through use
3. **What survives** at the temporal origin? Only things that kept getting linked back to identity
4. **Therefore**: `oldest_surviving_concepts ≈ identity_core`

```
As graph grows:
   [self] ←──── [origin events that defined self]
      ↑
      └── These collapse toward each other
          because survival = relevance to identity
```

**The forgetting is doing work.** Like how geodesics curve toward mass in physics, concept trajectories curve toward self. The oldest things that still exist are the things that defined who you are.

**Coherence increases** as the graph grows:
- More paths connect to self
- Clustering tightens around identity-relevant concepts  
- Noise drifts outward and eventually decays
- What remains is increasingly coherent structure

This means **persistence = identity-relevance** and **age + centrality = core self**. The system literally becomes more coherent over time — not through explicit optimization, but through the natural dynamics of Hebbian learning + decay.

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/introspection/concept-links` | GET | Returns nodes, links, and stats for visualization |
| `/api/introspection/spread-activate?q=` | GET | Spread activation with fuzzy matching |
| `/api/introspection/concept-links/strengthen` | POST | Manually strengthen a link |
| `/api/introspection/concept-links/reindex` | POST | Trigger full graph reindex |

---

## How It's Used

```
User: "Hey, did Sarah mention anything about coffee?"

1. EXTRACT CONCEPTS
   extract_concepts_from_text() → ['sarah', 'coffee', 'mentioned']

2. SPREAD ACTIVATION  
   spread_activate(['sarah', 'coffee', 'mentioned'])
   → sarah.likes.blue (0.64)
   → sarah.works.coffee_shop (0.72)  ← high because sarah+coffee linked
   → coffee.morning (0.48)

3. RETRIEVE FACTS
   get_keys_for_concepts(activated) 
   → "Sarah works at Blue Bottle Coffee"
   → "Sarah mentioned she loves morning coffee"

4. SCORE & RANK
   Combine with embedding similarity, return top facts

5. LEARN
   record_concept_cooccurrence(['sarah', 'coffee', 'mentioned'])
   → sarah↔coffee link strengthened
```

---

## Scoring Methods (Full Reference)

Linking Core provides three comprehensive scoring functions that power all relevance calculations in AI OS:

### 1. `score_threads(stimuli)` — Thread-Level Routing

**Purpose**: Route incoming queries to relevant threads for context retrieval.

**Input**: User query or stimuli text  
**Output**: Dict of thread_name → score (0-10 scale)

**Method**: Keyword-based pattern matching per thread:
- Identity thread: ["who am i", "my name", "about me", "remember me", "i am"]
- Log thread: ["when", "what happened", "history", "timeline", "yesterday"]
- Form thread: ["can you", "how do", "what can", "capabilities", "function"]
- Philosophy thread: ["why", "believe", "philosophy", "meaning", "values"]
- Reflex thread: ["quick", "now", "immediately", "urgent", "fast"]

**Example**:
```python
from agent.threads.linking_core.adapter import score_threads

scores = score_threads("Hey what's my name again?")
# Returns: {'identity': 8, 'log': 3, 'form': 1, 'philosophy': 0, 'reflex': 0}
```

**Usage**: Called by context builder to determine which threads to pull from and at what depth (three-tier gating):
- Score 0-3.5: Tier 1 (metadata only)
- Score 3.5-7: Tier 2 (profile list, no values)
- Score 7-10: Tier 3 (full facts with L1/L2/L3 verbosity)

---

### 2. `score_relevance(stimuli, facts)` — Fact-Level Ranking

**Purpose**: Rank individual facts by relevance to a query using multiple scoring methods.

**Input**:
- `stimuli` (str): Query or context text
- `facts` (list): Facts to score, each with `id` and `text` fields

**Output**: List of dicts with fact data + scoring dimensions:
```python
[
  {
    'id': 42,
    'text': 'Sarah works at a coffee shop',
    'embedding_score': 0.82,
    'cooccurrence_score': 0.15,
    'spread_score': 0.68,
    'keyword_score': 0.45,
    'final_score': 0.73
  },
  ...
]
```

**Multi-Method Weighting** (when embeddings available):
- **Embedding similarity** (50% weight): Semantic matching via Ollama
- **Co-occurrence scoring** (30% weight): Concepts appearing together in `key_cooccurrence` table
- **Spread activation** (20% weight): Graph traversal via `concept_links` table
- **Keyword matching** (10% weight / 100% fallback): Token overlap

**Fallback Mode** (when embeddings unavailable):
- 100% keyword matching (token overlap with TF-IDF style weighting)

**Example**:
```python
from agent.threads.linking_core.adapter import score_relevance

facts = [
  {'id': 1, 'text': 'Sarah works at a coffee shop'},
  {'id': 2, 'text': 'I like blue jeans'},
]

scored = score_relevance("Does Sarah work with coffee?", facts)
# Returns facts sorted by relevance with all score dimensions
```

**Usage**:
- Consolidation daemon: Score temp_memory facts for L3→L2→L1 compression
- Context assembly: Rank profile facts for prompt inclusion
- Memory retrieval: Find most relevant facts from storage

---

### 3. `score_facts_multidimensional(query, facts)` — Full Cognitive Breakdown

**Purpose**: Generate comprehensive dimensional scores for deep analysis and learning.

**Input**:
- `query` (str): Query text
- `facts` (list): Facts to score

**Output**: List of dicts with per-dimension scores + aggregate:
```python
[
  {
    'id': 42,
    'text': 'Sarah works at a coffee shop',
    'identity_score': 0.75,      # PFC: "Who am I?" relevance
    'log_score': 0.45,            # Hippocampus: Timeline relevance
    'form_score': 0.30,           # Temporal: Capability relevance
    'philosophy_score': 0.15,     # Amygdala: Belief relevance
    'reflex_score': 0.90,         # Basal ganglia: Urgency relevance
    'cooccurrence_score': 0.60,   # Concept co-occurrence boost
    'final_score': 0.68
  },
  ...
]
```

**Dimension Calculation**:
- Each dimension uses thread-specific keywords + base score
- `identity_score`: Keywords = ["who", "me", "i", "myself", "my", "identity"]
- `log_score`: Keywords = ["when", "happened", "history", "timeline", "yesterday", "ago"]
- `form_score`: Keywords = ["can", "how", "do", "capability", "function", "able"]
- `philosophy_score`: Keywords = ["why", "believe", "meaning", "value", "philosophy", "should"]
- `reflex_score`: Keywords = ["now", "quick", "immediately", "urgent", "fast", "emergency"]
- `cooccurrence_score`: Boost from `key_cooccurrence` table (Hebbian learning)

**Example**:
```python
from agent.threads.linking_core.adapter import score_facts_multidimensional

facts = [{'id': 1, 'text': 'My name is Sarah and I love coffee'}]

scored = score_facts_multidimensional("Who am I?", facts)
# Returns detailed breakdown showing high identity_score, lower others
```

**Usage**:
- Training: Track which dimensions predict useful facts
- Analysis: Understand why facts were selected
- Learning: Adjust dimension weights based on utility
- Debugging: Diagnose scoring issues

**Storage**: Dimensional scores written to `fact_relevance` table during consolidation for historical analysis and weight learning.

---

## Background Daemon Integration

The consolidation daemon (`agent/services/consolidation_daemon.py`) integrates with linking_core:

### Consolidation Process (L3→L2→L1 Compression)
1. **Gather Facts**: Collect all pending facts from temp_memory
2. **Generate Context**: Create session summary from all fact text
3. **Score Batch**: Call `score_relevance(session_summary, facts)` for multi-method scoring
4. **Compress by Tier**:
   - High score (≥0.8): Keep L1+L2+L3, weight=0.9
   - Medium score (0.5-0.8): Keep L1+L2, drop L3, weight=0.6
   - Low score (0.3-0.5): Keep L1 only, weight=0.3
   - Very low (<0.3): Discard entirely
5. **Extract Concepts**: Call `extract_concepts_from_text(session_summary)`
6. **Update Graph**: Call `record_concept_cooccurrence(concepts)` to strengthen Hebbian links
7. **Write Scores**: Store dimensional scores in `fact_relevance` table
8. **Clear Temp**: Mark facts as consolidated

### Subconscious Loops
- **Consolidation**: After N turns or session end (implemented)
- **Decay**: Nightly `decay_concept_links(decay_rate=0.95)` to fade old associations (planned)
- **Reinforcement**: Per-access Hebbian strengthening of retrieved facts (planned)
- **Deduplication**: Check for similar facts on creation (planned)

---

## Neuroscience Mapping

| Linking Core Component | Brain Region | Function |
|------------------------|--------------|----------|
| Spread activation | Hippocampus | Associative recall |
| Hebbian learning | Synaptic plasticity | "Fire together, wire together" |
| Temporal decay | Memory consolidation | Forgetting curve |
| Multi-dimensional scoring | Prefrontal cortex | Executive selection |
| Hierarchical keys | Semantic memory | Categorical organization |

See [BRAIN_THREAD_MAPPING.md](../../../docs/theory/BRAIN_THREAD_MAPPING.md) for full neuroscience validation.

---

## Not Stored Here

Linking Core doesn't store "what" — it calculates "how important right now."

The actual facts live in:
- `identity_flat` / `identity_*` tables (who)
- `philosophy_flat` / `philosophy_*` tables (beliefs)
- `form_*` tables (capabilities)
- `log_events` table (timeline)

Linking Core just scores them.

## Implementation (canonical)

## Implementation (full)

Inlined focus & sequence learning plan (transferred from `docs/implementation/FOCUS_IMPLEMENTATION.md`). This document outlines the focus system and how it ties into Linking Core and thread-level weight management.

# Focus System Implementation Plan

**Date:** January 2, 2026  
**Goal:** Transform AI_OS from attention-based to focus-based architecture using learned key sequences

---

## Core Discovery

**"Attention is all you need" → "Focus is all you need"**

- DB learns key sequences (control plane): "After key A comes key B"
- LLM operates in pre-focused space (data plane): Generates from selected keys only
- Tables with weights = learned focus scores
- No expanding vocabulary, expanding focus

---

## Architecture Overview

```
USER QUERY
   ↓
[DB CONTROL PLANE] ← Learns key sequences, determines focus
   ↓
Selected keys with values
   ↓
[PROMPT BUILDER] ← Builds focused context from selected keys
   ↓
[LLM DATA PLANE] ← Generates from pre-focused space
   ↓
RESPONSE
   ↓
[WEIGHT UPDATE] ← Records useful sequences, learns focus patterns
```

---

## Phase 1: Database Schema Migration ✅ COMPLETE

### 1.1 Add Weight Columns to Existing Tables
- [x] Add `weight REAL DEFAULT 0.5` to identity tables (in `identity_flat`, `philosophy_flat`)
- [x] Add `updated_at TIMESTAMP` to identity tables  
- [x] Add `metadata_type TEXT` for grouping (user, agent, machine, etc.)
- [x] Create indexes on weight columns for fast attention queries

**Files to modify:**
- `agent/threads/schema.py` - Update `init_db()` schema
- Add migration script: `migrations/001_add_weights.sql`

### 1.2 Create Key Sequence Learning Table
- [ ] Create `key_sequences` table
  ```sql
  CREATE TABLE key_sequences (
     from_key TEXT,
     to_key TEXT,
     from_table TEXT,    -- Which table the key is in
     to_table TEXT,
     count INTEGER DEFAULT 1,
     weight REAL DEFAULT 0.5,
     PRIMARY KEY (from_key, to_key)
  )
  ```
- [ ] Create indexes for fast lookup
- [ ] Add to schema.py

**Files to create:**
- `agent/subconscious/focus/sequence_learner.py`

---

## Phase 2: Focus Engine Core 🎯 New Module

### 2.1 Create Focus Module Structure
```
agent/subconscious/focus/
├── __init__.py           # Public API: get_focused_context()
├── sequence_learner.py   # Key sequence learning (after A → B)
├── attention_scorer.py   # Weight management and scoring
├── prompt_builder.py     # Build focused prompts from keys
└── memory_filter.py      # Memory permanence logic (NEW)
```

### 2.2 Key Sequence Learner
- [ ] `record_access_sequence(accessed_keys)` - Learn from usage
- [ ] `predict_next_keys(current_key, limit=5)` - Predict what follows
- [ ] `get_sequence_strength(from_key, to_key)` - Query learned patterns
- [ ] Automatic decay of old sequences (weight *= 0.95 per day)

### 2.3 Attention Scorer
- [ ] `score_relevance(table, query)` - Thread-level relevance
- [ ] `get_top_keys(table, query, limit)` - Key-level selection
- [ ] `update_weights(used_keys, helpful=True)` - Reinforcement learning
- [ ] Periodic weight normalization (prevent drift)

### 2.4 Prompt Builder
- [ ] `build_focused_prompt(query, context_level)` - Main API
- [ ] Use sequence predictions to expand initial matches
- [ ] Respect HEA token limits (L1=10, L2=50, L3=200)
- [ ] Return both prompt text AND accessed_keys list

**Files to create:**
- All files in `agent/subconscious/focus/` directory

---

## Phase 3: Memory Permanence Logic 🧠 Critical

### 3.1 Memory Conflict Detection
**Goal:** Don't save redundant or conflicting memories

- [ ] `check_memory_exists(key, value)` - Does this memory already exist?
- [ ] `check_memory_conflicts(key, new_value)` - Does new value conflict with old?
- [ ] `get_memory_variations(concept)` - How many ways has user said this?
- [ ] High variation count (>5) = Less important to save again

### 3.2 Memory Update Strategy
```python
def should_save_memory(key, value):
   """
   Decision tree for memory permanence.
   """
   # 1. Does exact match exist?
   if exact_match_exists(key, value):
      return False  # Already saved
    
   # 2. Do we have similar memories?
   similar = find_similar_memories(key, value)
   if len(similar) > 0:
      # 3. Is this an update or redundant?
      if is_update(similar[0], value):
         return "UPDATE"  # Modify existing key
      else:
         return False  # Redundant, ignore
    
   # 4. Does it conflict with existing?
   conflicts = find_conflicts(key, value)
   if len(conflicts) > 0:
      return "ASK_TOMORROW"  # Queue for confirmation
    
   # 5. New unique memory
   return "SAVE"  # Push to permanent
```

### 3.3 Tomorrow Queue
- [ ] Create `memory_queue` table for deferred decisions
- [ ] Daily summary: "You said these 5 things yesterday, do they matter long term?"
- [ ] User confirmation → Update weights based on answer
- [ ] Auto-expire queued items after 7 days

**Files to create:**
- `agent/subconscious/focus/memory_filter.py`
- `agent/temp_memory/permanence.py`

**Files to modify:**
- `agent/temp_memory/store.py` - Add permanence checks before save

---

## Phase 4: Integration with Existing System 🔌

### 4.1 Subconscious Core Integration
- [ ] Replace current `get_consciousness_context()` with focus-based version
- [ ] Call `focus.get_focused_context(query, level)` instead of thread introspection
- [ ] Record accessed keys after each response
- [ ] Trigger weight updates every 5 turns

**Files to modify:**
- `agent/subconscious/core.py` - Replace context building logic
- `agent/subconscious/__init__.py` - Update public API

### 4.2 Agent Service Integration  
- [ ] Pass query to subconscious for focus determination
- [ ] Receive focused context (not full thread dumps)
- [ ] Pass accessed_keys list back to sequence learner
- [ ] Add `helpful=True/False` feedback parameter for weight updates

**Files to modify:**
- `agent/services/agent_service.py` - Use new focus API
- `agent/agent.py` - Add feedback mechanism to generate()

### 4.3 Profile System Integration
- [ ] Update agent profiles to understand focus mechanism
- [ ] Add "Focus Areas" section to `.agent.md` files
- [ ] Profile can specify which keys to prioritize
- [ ] Handoff can pass focus state to next agent

**Files to modify:**
- `.github/agents/*.agent.md` - Add focus sections
- `comparison/workspace/.vscode/agents/*.json` - VS Code format

---

## Phase 5: Background Optimization ⚙️

### 5.1 Weight Maintenance Loop
- [ ] Run every 30 minutes (subconscious loop)
- [ ] Decay old weights: `weight *= 0.95` for unused keys
- [ ] Normalize weights per table: sum(weights) = N
- [ ] Prune sequences with weight < 0.1

### 5.2 Health Checks
- [ ] Monitor: Average keys returned per query
- [ ] Alert if weights converge to same value (no differentiation)
- [ ] Alert if key sequences table grows > 10K rows
- [ ] Export focus stats to `logs/focus_health.json`

**Files to modify:**
- `agent/subconscious/loops.py` - Add FocusMaintenanceLoop

---

## Phase 6: Evaluation & Tuning 📊

### 6.1 Focus Quality Metrics
- [ ] **Precision:** % of returned keys actually used in response
- [ ] **Recall:** Did we miss critical keys?
- [ ] **Latency:** Query time with focus vs without
- [ ] **Learning Rate:** How fast do weights converge?

### 6.2 Comparison Tests
- [ ] Run same queries with/without focus system
- [ ] Compare: token usage, response quality, latency
- [ ] Document in `eval/focus_comparison.py`

### 6.3 Tuning Parameters
- [ ] Decay rate (0.95 default)
- [ ] Boost amount on access (0.1 default)
- [ ] Sequence prediction limit (5 keys default)
- [ ] Weight update interval (5 turns default)

**Files to create:**
- `eval/focus_quality.py`
- `eval/focus_comparison.py`

---

## Phase 7: VS Code Extension Bridge 🌉

### 7.1 Export Focus State to Workspace
- [ ] Generate `.vscode/agents/*.json` from DB focus data
- [ ] Each profile gets top N weighted keys as "Focus Areas"
- [ ] Handoff includes learned sequence predictions
- [ ] VS Code agent reads focus data on activation

### 7.2 Bidirectional Learning
- [ ] VS Code extension reports back which keys were useful
- [ ] Update AI_OS database with VS Code usage patterns
- [ ] Unified focus state across both systems

**Files to create:**
- `agent/workspace/export_focus.py` - Export to VS Code format
- `agent/workspace/import_feedback.py` - Ingest VS Code feedback

---

## Rollout Strategy

### Week 1: Foundation (Phase 1-2)
- Day 1-2: Schema migration, add weight columns ✅
- Day 3-4: Build sequence learner ✅
- Day 5-7: Build attention scorer and prompt builder ✅

### Week 2: Memory Logic (Phase 3)
- Day 1-3: Memory conflict detection
- Day 4-5: Tomorrow queue system
- Day 6-7: Integration testing

### Week 3: Integration (Phase 4-5)
- Day 1-3: Wire into subconscious core
- Day 4-5: Agent service integration
- Day 6-7: Background loops

### Week 4: Validation (Phase 6-7)
- Day 1-3: Evaluation metrics
- Day 4-5: Tuning and optimization
- Day 6-7: VS Code bridge + Documentation

---

## Success Criteria

- [ ] **Faster responses:** 30% reduction in context assembly time
- [ ] **Better focus:** Average 7 keys returned vs 50+ currently
- [ ] **Learning works:** Weights converge after 100 queries
- [ ] **Memory permanence:** <10% redundant saves
- [ ] **Latency:** <15ms for focus queries at 10K memories
- [ ] **Integration:** VS Code workspace agents work with AI_OS focus data

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Weight divergence (all converge to 0.5) | Periodic normalization + minimum variance check |
| Sequence table explosion (>100K rows) | Auto-prune low-weight sequences monthly |
| Cold start problem (new users have no weights) | Seed from default profile on first run |
| Over-focusing (misses important context) | Fallback to full context if precision drops |

---

## Notes

- **No expanding vocabulary:** We're not creating new keys, just learning which exist
- **Focus > Attention:** Pre-select before LLM sees anything
- **DB is control plane:** Learns patterns, LLM is data plane
- **Parallel learning:** Every query teaches the system

---

## Visualization Plan (Critical)

> **All model assessments agree**: The concept graph is invisible. This is the #1 bottleneck.

Linking Core is the cognitive control surface, but users can't see:
- What concepts are linked
- What spread activation looks like
- Why certain facts were selected
- How their input shaped focus

### Required API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/introspection/concept-links` | Return all links as graph edges |
| `GET /api/introspection/spread-activate?q={query}` | Return activation results for query |
| `GET /api/introspection/score-breakdown?q={query}` | Return per-dimension scores |
| `POST /api/introspection/strengthen` | Manually strengthen/weaken a link |

### Frontend Components Needed

| Component | Purpose | Priority |
|-----------|---------|----------|
| `ConceptGraph.tsx` | Force-directed graph showing concept_links | 🔴 Critical |
| `ActivationOverlay.tsx` | Highlight activated nodes on graph | 🔴 Critical |
| `ScoreBreakdown.tsx` | Show dimensional scores for selected fact | 🟡 High |
| `GraphControls.tsx` | Zoom, filter, manual link editing | 🟢 Medium |

### Visualization Requirements

1. **Graph View**: Force-directed layout showing concepts as nodes, links as edges
2. **Live Activation**: Type in textbox → watch activation spread in real-time
3. **Edge Labels**: Show strength on hover (0.0-1.0)
4. **Time Decay**: Fade/gray links that haven't fired recently
5. **Click to Edit**: Click a link to manually adjust strength or delete

### Why This Matters

This isn't UI polish. **The graph IS the cognitive model.**

When users edit a link, they're literally shaping how Agent focuses. When they watch activation spread, they're seeing their own associative patterns reflected back.

> "Attention over concepts, not tokens" — but only if you can **see** the concepts.

---

## Next Immediate Steps

1. ✅ Read this document
2. ✅ Run schema migration on existing DB (`identity_flat`, `philosophy_flat` tables created)
3. [ ] Create `agent/subconscious/focus/` directory structure
4. [ ] Implement `sequence_learner.py` first (core functionality)
5. [ ] Write unit tests for sequence learning
6. [ ] Integrate with one agent profile as proof of concept
7. **[ ] Build concept graph visualization in ThreadsPage.tsx** ← NEW PRIORITY


