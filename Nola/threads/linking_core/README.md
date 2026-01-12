# Linking Core Thread

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

## Background Daemon Integration

The consolidation daemon (`Nola/services/consolidation_daemon.py`) runs:
- **Every conversation end**: `record_concept_cooccurrence()` on extracted concepts
- **Nightly**: `decay_concept_links(decay_rate=0.95)` to fade old associations

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
