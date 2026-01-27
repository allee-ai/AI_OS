# Memory Architecture: Service Separation & Flow

**Date**: January 13, 2026

## TL;DR

Yes, consolidation should be **separate** from memory and linking_core. Each service has a distinct responsibility:

- **linking_core**: Pure scoring (no side effects)
- **memory_service**: CRUD operations + fact extraction
- **consolidation_daemon**: Orchestration policy (when/how to compress)

---

## Service Responsibilities

### 1. Linking Core (agent/threads/linking_core/)

**Role**: Relevance Scoring Engine

**Pure Functions** (no database writes, no side effects):
- `score_threads(stimuli)` → Which threads to activate (0-10 scale)
- `score_relevance(stimuli, facts)` → Rank facts by relevance (0-1.0 scale)
- `score_facts_multidimensional(query, facts)` → Full dimensional breakdown

**Data Structures** (read-only):
- `concept_links` table: Hebbian learning graph
- `key_cooccurrence` table: Concept co-occurrence weights
- Embedding cache (optional, via Ollama)

**Philosophy**: 
- Stateless scoring functions
- Can be called from anywhere without side effects
- Like a CPU: takes input, returns score, doesn't modify storage

---

### 2. Memory Service (agent/services/memory_service.py)

**Role**: Memory CRUD Operations + Fact Extraction

**Read Operations**:
- `get_recent_facts(limit)` → Retrieve from temp_memory
- `get_dynamic_memory()` → Fetch from identity thread
- `search_memories(query)` → Find relevant facts

**Write Operations**:
- `add_fact(text, metadata)` → Store to temp_memory
- `extract_facts(conversation)` → Parse conversation, create facts (via LLM)
- `push_to_permanent(fact, level)` → Write to thread database

**Scoring** (legacy, being phased out):
- `score_fact(text)` → Old LLM-based scoring (1-5 scale)
- Being replaced by linking_core's multi-method approach

**Philosophy**:
- Handles all memory I/O
- Extracts structured data from conversations
- CRUD layer between code and database

---

### 3. Consolidation Daemon (agent/services/consolidation_daemon.py)

**Role**: Memory Compression Orchestration

**Policy Decisions**:
- When to consolidate (after N turns, session end, scheduled)
- What thresholds to use (high/medium/low score cutoffs)
- How to compress (L3→L2→L1 tiers)
- Where to store results (which thread, which level)

**Orchestration Flow**:
```python
def run():
    # 1. Gather data
    facts = memory_service.get_pending()
    
    # 2. Score using linking_core
    scored = linking_core.score_relevance(session_summary, facts)
    
    # 3. Apply compression policy
    for fact, score in scored:
        if score >= 0.8:
            memory_service.push(fact, levels=[1,2,3], weight=0.9)
        elif score >= 0.5:
            memory_service.push(fact, levels=[1,2], weight=0.6)
        elif score >= 0.3:
            memory_service.push(fact, levels=[1], weight=0.3)
        else:
            discard(fact)
    
    # 4. Update learning graph
    concepts = extract_concepts(session_summary)
    record_concept_cooccurrence(concepts)
```

**Philosophy**:
- Policy layer (configurable thresholds, schedules)
- Orchestrates multiple services
- Implements business logic for memory management
- Like a supervisor: delegates work, makes decisions

---

## Complete Flow Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    CONVERSATION TURN                         │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  AGENT (agent/agent.py)                                       │
│  - Receives user message                                     │
│  - Calls context builder                                     │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  CONTEXT BUILDER (threads/base.py)                           │
│  1. Call linking_core.score_threads(message)                 │
│     → Get thread relevance scores                            │
│  2. For each high-scoring thread:                            │
│     → Pull facts with weight-based L1/L2/L3 selection        │
│  3. Assemble context for LLM                                 │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  LLM GENERATION                                              │
│  - Generate response using assembled context                 │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  MEMORY SERVICE (post-turn)                                  │
│  1. Extract facts from conversation via LLM                  │
│  2. Add to temp_memory (short-term buffer)                   │
│  3. Increment turn counter                                   │
└──────────────────────────────────────────────────────────────┘
                            ↓
                    (after N turns or session end)
                            ↓
┌──────────────────────────────────────────────────────────────┐
│  CONSOLIDATION DAEMON (triggered)                            │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 1. GET PENDING FACTS                               │     │
│  │    memory_service.get_all_pending()                │     │
│  │    → List of facts from temp_memory                │     │
│  └────────────────────────────────────────────────────┘     │
│                      ↓                                       │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 2. SCORE FACTS (via linking_core)                  │     │
│  │    linking_core.score_relevance(summary, facts)    │     │
│  │    → Multi-method scoring (embedding + graph)      │     │
│  │    → Returns: [(fact, score_dict), ...]           │     │
│  └────────────────────────────────────────────────────┘     │
│                      ↓                                       │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 3. APPLY COMPRESSION POLICY                        │     │
│  │    if score >= 0.8: keep L1+L2+L3, weight=0.9     │     │
│  │    elif score >= 0.5: keep L1+L2, weight=0.6      │     │
│  │    elif score >= 0.3: keep L1, weight=0.3         │     │
│  │    else: discard                                   │     │
│  └────────────────────────────────────────────────────┘     │
│                      ↓                                       │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 4. WRITE TO PERMANENT STORAGE                      │     │
│  │    memory_service.push_to_thread(fact, levels)     │     │
│  │    → Writes to identity thread DB                  │     │
│  └────────────────────────────────────────────────────┘     │
│                      ↓                                       │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 5. UPDATE LEARNING GRAPH                           │     │
│  │    extract_concepts_from_text(session_summary)     │     │
│  │    record_concept_cooccurrence(concepts)           │     │
│  │    → Strengthens Hebbian links in concept_links   │     │
│  └────────────────────────────────────────────────────┘     │
│                      ↓                                       │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 6. TRACK DIMENSIONAL SCORES                        │     │
│  │    upsert_fact_relevance(fact, scores)             │     │
│  │    → Stores identity/log/form/etc scores           │     │
│  │    → Used for future learning                      │     │
│  └────────────────────────────────────────────────────┘     │
│                      ↓                                       │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 7. CLEAR TEMP MEMORY                               │     │
│  │    mark_consolidated(fact_ids)                     │     │
│  └────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
                            ↓
                    (next conversation)
```

---

## Why Separation Matters

### ❌ BAD: Monolithic Memory Service
```python
class MemoryService:
    def consolidate():
        # Scoring logic embedded here
        score = self._calculate_relevance(fact)
        
        # Compression policy embedded here
        if score > threshold:
            self._push_to_db(fact, level=2)
        
        # Graph updates embedded here
        self._update_concept_links()
```

**Problems**:
- Can't reuse scoring in other contexts
- Can't change compression policy without modifying memory code
- Testing requires mocking database
- Tight coupling

### 🌀 GOOD: Separated Concerns
```python
# linking_core: Pure scoring
scores = linking_core.score_relevance(query, facts)

# consolidation_daemon: Policy
daemon = ConsolidationDaemon(config)
daemon.run()  # Uses linking_core + memory_service

# memory_service: CRUD
memory_service.push(fact, levels=[1,2], weight=0.6)
```

**Benefits**:
- Reuse scoring in: consolidation, context building, search, training
- Change policy without touching scoring or storage
- Test each component independently
- Loose coupling via interfaces

---

## Future Extensions

### Subconscious Loops (Planned)

**Decay Daemon** (separate from consolidation):
```python
# Run nightly
decay_daemon = DecayDaemon()
decay_daemon.run()
# Uses: linking_core (read concept_links), memory_service (write decayed weights)
```

**Reinforcement Daemon** (separate from consolidation):
```python
# Run on fact access
def on_fact_retrieved(fact_id):
    reinforcement.boost_weight(fact_id)
    linking_core.strengthen_links(fact_concepts)
```

**Deduplication Daemon** (separate from consolidation):
```python
# Run on new fact creation
def before_add_fact(new_fact):
    similar = linking_core.score_relevance(new_fact, existing_facts)
    if max(similar) > 0.95:
        merge_or_discard()
```

Each daemon:
- Has single responsibility
- Uses linking_core for scoring
- Uses memory_service for I/O
- Implements specific policy

---

## Service Interaction Matrix

| Service | Reads From | Writes To | Calls |
|---------|------------|-----------|-------|
| **linking_core** | concept_links (read), key_cooccurrence (read), embeddings (cache) | Nothing | None |
| **memory_service** | temp_memory, thread DB | temp_memory, thread DB | linking_core (for search) |
| **consolidation_daemon** | temp_memory (via memory_service) | thread DB (via memory_service), concept_links, fact_relevance | linking_core (for scoring), memory_service (for I/O) |
| **agent** | All threads (via context builder) | temp_memory (via memory_service) | linking_core (for thread scoring), memory_service (for facts) |

---

## Configuration: Consolidation Policy

Thresholds are configurable without code changes:

```python
# Development: Keep more for testing
config = ConsolidationConfig(
    high_score_threshold=0.7,   # Lower threshold
    medium_score_threshold=0.4,
    low_score_threshold=0.2,
    max_facts_per_run=100
)

# Production: Aggressive compression
config = ConsolidationConfig(
    high_score_threshold=0.9,   # Only keep best
    medium_score_threshold=0.7,
    low_score_threshold=0.5,
    max_facts_per_run=50
)

daemon = ConsolidationDaemon(config)
```

---

## Summary: Architecture Principles

1. **linking_core = Pure Functions**
   - Input: query + facts
   - Output: scores
   - No side effects, no database writes
   - Reusable across all contexts

2. **memory_service = CRUD Layer**
   - Handles all database I/O
   - Extracts structured data from text
   - No policy decisions (just read/write)

3. **consolidation_daemon = Orchestrator**
   - Implements compression policy
   - Coordinates linking_core + memory_service
   - Configurable thresholds and schedules
   - Single responsibility: memory lifecycle management

This separation enables:
- **Testing**: Mock each service independently
- **Reusability**: Use linking_core in many contexts
- **Flexibility**: Change policy without touching scoring
- **Clarity**: Each service has obvious purpose
- **Performance**: Can optimize each layer separately

The separation is **correct** and should be maintained.
