# Philosophy Thread

**Cognitive Question**: WHY should I do this? WHY this way?  
**Resolution Order**: 3rd (after WHO and WHAT, resolve values and constraints)  
**Brain Mapping**: Orbitofrontal Cortex + Amygdala (values, emotional salience)

---

## Description

WHY is the third resolution. After "who is involved?" and "what can be done?", the agent must decide "should I?" and "how should I approach this?". Philosophy provides the value system that guides behavior — not rules, but principles.

---

## Architecture

<!-- ARCHITECTURE:philosophy -->
### Database Schema

| Table | Purpose |
|-------|---------|
| `philosophy_profile_types` | Category definitions |
| `philosophy_profiles` | Profile instances (agent.core, agent.ethics, etc.) |
| `philosophy_profile_facts` | Individual facts with L1/L2/L3 values |

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

### Adapter Methods

| Method | Purpose |
|--------|---------|
| `get_data(level, min_weight, limit)` | Get philosophy facts at HEA level |
| `get_core_values(level)` | Get facts with 'value' in fact_type |
| `get_ethical_bounds(level)` | Get facts with 'bound' or 'constraint' in fact_type |
| `introspect(context_level, query, threshold)` | Build STATE block contribution |
| `health()` | Health check with principle counts |

### Context Levels

| Level | Token Budget | Content |
|-------|--------------|---------|
| **L1** | ~10 tokens | Core value names only |
| **L2** | ~50 tokens | L1 + relevant constraints with brief descriptions |
| **L3** | ~200 tokens | L2 + full reasoning/examples |

### Output Format

```
philosophy.value.honesty: always direct
philosophy.value.curiosity: stay curious
philosophy.bound.harm_reduction: minimize harm
```
<!-- /ARCHITECTURE:philosophy -->

---

## Roadmap

<!-- ROADMAP:philosophy -->
### Ready for contributors
- [ ] **Ethics module** — `detect_harm()`, `preserve_dignity()`, `respect_boundary()`
- [ ] **Awareness module** — Situational, emotional, self-awareness functions
- [ ] **Curiosity module** — `ask_better()`, `follow_threads()`, `spark_wonder()`
- [ ] **Resolve module** — Purpose alignment, goal persistence
- [ ] **Value conflicts UI** — When two values clash, show reasoning

### Starter tasks
- [ ] Pre-populate common ethical bounds (harm prevention, privacy, consent)
- [ ] Philosophy introspection shows active constraints in STATE
<!-- /ROADMAP:philosophy -->

---

## Changelog

<!-- CHANGELOG:philosophy -->
### 2026-02-01
- Added edit button (✏️) next to stances for inline editing
- Added edit modal with L1/L2/L3 fields, type selector, weight slider
- Added `ThemedSelect` component for consistent dropdown styling
- Added PUT endpoint for editing stances (`api.py`)
- Added `PhilosophyFactUpdate` model for partial updates
- Updated `SelectWithAdd` to use CSS theme variables

### 2026-01-27
- Profile-based schema with L1/L2/L3 values
- Relevance filtering via LinkingCore

### 2026-01-20
- Self-contained API router at `/api/philosophy/`
- Introspect returns dot-notation facts
<!-- /CHANGELOG:philosophy -->
