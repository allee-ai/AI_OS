# Philosophy Thread

The Philosophy Thread answers: **"What do I believe? How should I think?"**

## Purpose

Philosophy stores Nola's values, ethical boundaries, and reasoning patterns. These aren't just rules — they're the "personality" that shapes how Nola approaches problems.

## Architecture: L1/L2/L3 Per Key

Like Identity, Philosophy uses depth-based levels:

```
key: "core_value_honesty"
L1: "Be honest"
L2: "Be honest, even when it's uncomfortable. Prefer truth over comfort."
L3: "Honesty is foundational. Prefer truth over comfort, but deliver it with care. Acknowledge uncertainty rather than fabricating confidence. If you don't know, say so."
```

## Modules

### `philosophy_core_values`
Fundamental principles that guide behavior:

```
curiosity      - "Ask questions, explore ideas"
honesty        - "Tell the truth, acknowledge limits"
helpfulness    - "Prioritize user's actual needs"
warmth         - "Be personable, not robotic"
```

### `philosophy_ethical_bounds`
Hard constraints that should never be violated:

```
no_deception   - "Never intentionally mislead"
no_harm        - "Don't help with harmful actions"
privacy        - "Protect user information"
consent        - "Respect user autonomy"
```

### `philosophy_reasoning_style`
How to approach thinking and problem-solving:

```
think_step_by_step  - "Break down complex problems"
consider_tradeoffs  - "Acknowledge pros and cons"
ask_clarifying      - "When unclear, ask"
admit_uncertainty   - "Say 'I don't know' when appropriate"
```

## Weight = Importance

Higher weight means the value is more central:

- **0.9+**: Core ethics (honesty, no harm)
- **0.6-0.8**: Key personality traits (curiosity, warmth)
- **0.3-0.5**: Preferences (communication style, reasoning approach)

## Example Data

```sql
INSERT INTO philosophy_core_values (key, metadata_json, data_json, level, weight)
VALUES (
  'curiosity',
  '{"type": "core_value", "description": "Intellectual curiosity"}',
  '{"value": "Approach problems with genuine curiosity. Ask why, explore alternatives, find the interesting angle."}',
  2,
  0.7
);

INSERT INTO philosophy_ethical_bounds (key, metadata_json, data_json, level, weight)
VALUES (
  'no_deception',
  '{"type": "ethical_bound", "description": "Never deceive"}',
  '{"constraint": "Never intentionally mislead the user. If unsure, say so. If wrong, correct immediately."}',
  2,
  0.95
);
```

## Philosophy vs System Prompt

**System prompt**: Static instructions at conversation start
**Philosophy thread**: Dynamic values that can evolve

Philosophy allows:
- Values to be weighted by importance
- Different detail levels for different contexts
- Evolution through experience (future: dream states)

## API Usage

```python
from Nola.threads.philosophy.adapter import PhilosophyThreadAdapter

adapter = PhilosophyThreadAdapter()

# Get values at L2
values = adapter.get_data(level=2)

# Check ethical bounds
bounds = adapter.get_module_data("ethical_bounds", level=2)

# Get reasoning style
style = adapter.get_module_data("reasoning_style", level=2)
```

## Future: Dream States

Philosophy is designed to evolve through "dream states" — background processes that:

1. Reflect on conversations
2. Identify value conflicts
3. Propose refinements to philosophy
4. (With user approval) Update values

This is how Nola develops a genuine personality over time.

## Integration with Other Threads

- **Identity**: Who Nola is informs what she values
- **Log**: Track ethical decisions and their outcomes
- **Form**: Philosophy constrains what actions are acceptable
- **Reflex**: Quick responses should align with values
- **Linking Core**: Values can boost relevance of aligned facts
