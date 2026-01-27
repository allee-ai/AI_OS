# Philosophy Thread

**Cognitive Question**: WHY should I do this? WHY this way?  
**Resolution Order**: 3rd (after WHO and WHAT, resolve values and constraints)  
**Brain Mapping**: Orbitofrontal Cortex + Amygdala (values, emotional salience)

---

## Necessity

WHY is the third resolution. After "who is involved?" and "what can be done?", the agent must decide "should I?" and "how should I approach this?". Philosophy provides the value system that guides behavior — not rules, but principles.

---

## Backend

### Database Tables

| Table | Location | Purpose |
|-------|----------|---------|
| `philosophy_flat` | `schema.py:1601` | Main philosophy storage with L1/L2/L3 columns |
| `philosophy_core_values` | `schema.py` (module) | Fundamental values |
| `philosophy_ethical_bounds` | `schema.py` (module) | Hard constraints |
| `philosophy_reasoning_style` | `schema.py` (module) | Reasoning approaches |

### Key Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `init_philosophy_flat()` | `schema.py:1594` | Create philosophy table |

### Adapter

| Method | Location | Purpose |
|--------|----------|---------|
| `get_core_values()` | `adapter.py:37` | Get core values at level |
| `get_ethical_bounds()` | `adapter.py:41` | Get ethical constraints |
| `get_reasoning_style()` | `adapter.py:45` | Get reasoning approach |
| `add_value()` | `adapter.py:49` | Add a core value |
| `add_bound()` | `adapter.py:62` | Add an ethical constraint |
| `introspect()` | `adapter.py:73` | Return structured introspection |

---

## Context Levels

| Level | Token Budget | Content |
|-------|--------------|---------|
| **L1** | ~10 tokens | Core value names only |
| **L2** | ~50 tokens | L1 + top-k relevant constraints with brief descriptions |
| **L3** | ~200 tokens | L2 + full reasoning/examples |

### Example L1/L2/L3

\`\`\`
key: "core_value_honesty"
L1: "Be honest"
L2: "Be honest, even when uncomfortable. Prefer truth over comfort."
L3: "Honesty is foundational. Prefer truth over comfort, but deliver with care. 
     Acknowledge uncertainty rather than fabricating confidence."
\`\`\`

---

## Modules

### `philosophy_core_values`
Fundamental principles:
- `curiosity` — "Ask questions, explore ideas"
- `honesty` — "Tell the truth, acknowledge limits"
- `helpfulness` — "Prioritize user's actual needs"
- `warmth` — "Be personable, not robotic"

### `philosophy_ethical_bounds`
Hard constraints (weight 0.95+):
- `no_deception` — "Never intentionally mislead"
- `no_harm` — "Don't help with harmful actions"
- `privacy` — "Protect user information"
- `consent` — "Respect user autonomy"

### `philosophy_reasoning_style`
Thinking approach:
- `think_step_by_step` — "Break down complex problems"
- `consider_tradeoffs` — "Acknowledge pros and cons"
- `ask_clarifying` — "When unclear, ask"
- `admit_uncertainty` — "Say 'I don't know' when appropriate"

---

## Frontend

| Component | Location | Status |
|-----------|----------|--------|
| Philosophy table | `ThreadsPage.tsx` | 🌀 Done |

**Features**:
- 🌀 View all philosophy facts
- 🌀 Edit L1/L2/L3 values inline
- 🌀 Adjust weights
- 🌀 Add new values/constraints
- 🌀 Filter by type (value/constraint/style)

---

## Integration Points

| Thread | Integration |
|--------|-------------|
| **Identity** | Identity informs value application |
| **Form** | Tools must respect ethical bounds |
| **Reflex** | Reflexes must align with values |
| **Log** | Can track ethical decisions over time |
| **Linking Core** | Philosophy scores emotional salience |

---

## Weight Semantics

- **0.95+**: Ethical bounds (never violate)
- **0.7-0.9**: Core values (always consider)
- **0.4-0.6**: Reasoning preferences (usually apply)
- **<0.4**: Style suggestions (context-dependent)
