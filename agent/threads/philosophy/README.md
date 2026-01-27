# Philosophy Thread

**Cognitive Question**: WHY should I do this? WHY this way?  
**Resolution Order**: 3rd (after WHO and WHAT, resolve values and constraints)  
**Brain Mapping**: Orbitofrontal Cortex + Amygdala (values, emotional salience)

---

## Purpose

WHY is the third resolution. After "who is involved?" and "what can be done?", the agent must decide "should I?" and "how should I approach this?". Philosophy provides the value system that guides behavior — not rules, but principles.

---

## Database Schema

### Tables

| Table | Purpose |
|-------|---------|
| `philosophy_profile_types` | Category definitions |
| `philosophy_profiles` | Profile instances (agent.core, agent.ethics, etc.) |
| `philosophy_profile_facts` | Individual facts with L1/L2/L3 values |

### philosophy_profile_facts

```sql
CREATE TABLE philosophy_profile_facts (
    profile_id TEXT NOT NULL,
    key TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    l1_value TEXT,
    l2_value TEXT,
    l3_value TEXT,
    weight REAL DEFAULT 0.5,
    PRIMARY KEY (profile_id, key)
)
```

---

## Adapter Methods

| Method | Purpose |
|--------|---------|
| `get_data(level, min_weight, limit)` | Get philosophy facts at HEA level |
| `get_table_data()` | Get all rows for table display |
| `get_core_values(level)` | Get facts with 'value' in fact_type |
| `get_ethical_bounds(level)` | Get facts with 'bound' or 'constraint' in fact_type |
| `get_reasoning_style(level)` | Get facts with 'reasoning' or 'style' in fact_type |
| `introspect(context_level, query, threshold)` | Build STATE block contribution |
| `health()` | Health check with principle counts |

### introspect()

Returns `IntrospectionResult` with facts filtered by:
1. Weight threshold (converted from 0-10 to 0-1 scale)
2. Query relevance using LinkingCore concept extraction

Facts use the fact_type as category in dot notation.

---

## Context Levels

| Level | Token Budget | Content |
|-------|--------------|---------|
| **L1** | ~10 tokens | Core value names only |
| **L2** | ~50 tokens | L1 + relevant constraints with brief descriptions |
| **L3** | ~200 tokens | L2 + full reasoning/examples |

### L1/L2/L3 Value Example

```
key: "honesty"
fact_type: "value"

l1_value: "Be honest"
l2_value: "Be honest, even when uncomfortable. Prefer truth over comfort."
l3_value: "Honesty is foundational. Prefer truth over comfort, but deliver with care."
```

---

## Output Format

Facts are formatted with dot notation using fact_type as category:

```
philosophy.value.honesty: always direct
philosophy.value.curiosity: stay curious
philosophy.principle.consent: never act without agreement
philosophy.bound.harm_reduction: minimize harm
```

---

## Relevance Filtering

When a query is provided, `_filter_by_relevance()`:

1. Extracts concepts from query using LinkingCore
2. Extracts concepts from each fact (key + l2_value + l3_value)
3. Scores by concept overlap
4. Returns top-k most relevant facts

---

## Integration Points

| Thread | Integration |
|--------|-------------|
| **Subconscious** | Calls `introspect()` to build STATE block |
| **Identity** | Identity informs value application |
| **Form** | Tools must respect ethical bounds |
| **Reflex** | Reflexes must align with values |
| **Linking Core** | Philosophy scores emotional salience |

---

## Weight Semantics

| Weight | Meaning | Examples |
|--------|---------|----------|
| 0.95+ | Ethical bounds | Never violate |
| 0.7-0.9 | Core values | Always consider |
| 0.4-0.6 | Reasoning preferences | Usually apply |
| <0.4 | Style suggestions | Context-dependent |
