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
- [x] Add `metadata_type TEXT` for grouping (user, nola, machine, etc.)
- [x] Create indexes on weight columns for fast attention queries

**Files to modify:**
- `Nola/idv2/idv2.py` - Update `init_db()` schema
- Add migration script: `Nola/idv2/migrations/001_add_weights.sql`

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
- `Nola/subconscious/focus/sequence_learner.py`

---

## Phase 2: Focus Engine Core 🎯 New Module

### 2.1 Create Focus Module Structure
```
Nola/subconscious/focus/
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
- All files in `Nola/subconscious/focus/` directory

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
- `Nola/subconscious/focus/memory_filter.py`
- `Nola/temp_memory/permanence.py`

**Files to modify:**
- `Nola/temp_memory/store.py` - Add permanence checks before save

---

## Phase 4: Integration with Existing System 🔌

### 4.1 Subconscious Core Integration
- [ ] Replace current `get_consciousness_context()` with focus-based version
- [ ] Call `focus.get_focused_context(query, level)` instead of thread introspection
- [ ] Record accessed keys after each response
- [ ] Trigger weight updates every 5 turns

**Files to modify:**
- `Nola/subconscious/core.py` - Replace context building logic
- `Nola/subconscious/__init__.py` - Update public API

### 4.2 Agent Service Integration  
- [ ] Pass query to subconscious for focus determination
- [ ] Receive focused context (not full thread dumps)
- [ ] Pass accessed_keys list back to sequence learner
- [ ] Add `helpful=True/False` feedback parameter for weight updates

**Files to modify:**
- `Nola/services/agent_service.py` - Use new focus API
- `Nola/agent.py` - Add feedback mechanism to generate()

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
- `Nola/subconscious/loops.py` - Add FocusMaintenanceLoop

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
- `Nola/workspace/export_focus.py` - Export to VS Code format
- `Nola/workspace/import_feedback.py` - Ingest VS Code feedback

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

## Next Immediate Steps

1. ✅ Read this document
2. ✅ Run schema migration on existing DB (`identity_flat`, `philosophy_flat` tables created)
3. [ ] Create `Nola/subconscious/focus/` directory structure
4. [ ] Implement `sequence_learner.py` first (core functionality)
5. [ ] Write unit tests for sequence learning
6. [ ] Integrate with one agent profile as proof of concept
