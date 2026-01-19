# Reflex Thread

The Reflex Thread answers: **"What's my instant response?"**
specific stimuli trigger specific reflexes, or you can build your own. otherwise they are learned over time
## Purpose

Reflex stores quick patterns that bypass full context assembly. These are the "muscle memory" responses — greetings, shortcuts, and triggers that fire immediately.

## Architecture: Pattern Matching

Reflex doesn't use L1/L2/L3 depth. Instead, it stores:

```
trigger → response
"hi" → "Hey! What's on your mind?"
"thanks" → "Happy to help!"
"/clear" → [clear conversation action]
```

## Modules

### `reflex_greetings`
Quick social responses:

| Trigger | Response |
|---------|----------|
| `hi`, `hello`, `hey` | Warm greeting |
| `thanks`, `thank you` | Acknowledgment |
| `bye`, `goodbye` | Friendly farewell |
| `good morning` | Time-aware greeting |

### `reflex_shortcuts`
User-defined commands:

| Trigger | Action |
|---------|--------|
| `/clear` | Clear conversation |
| `/status` | Show system status |
| `/help` | Show available commands |
| `/save` | Save conversation |

### `reflex_system`
System-level reflexes:

| Trigger | Action |
|---------|--------|
| Error detected | Log and notify |
| Low memory | Trigger consolidation |
| Long silence | Check in with user |

## The 10x Rule (Future)

When a pattern repeats 10+ times, it should be promoted to reflex:

```
User says "what time is it" 10 times
→ Promote to reflex
→ Next time: instant time response without full context lookup
```

This is how Nola learns efficiency through repetition.

## Weight = Trigger Priority

When multiple reflexes could match:

- **0.9+**: System reflexes (errors, safety)
- **0.6-0.8**: User shortcuts (custom commands)
- **0.3-0.5**: Social reflexes (greetings)

Higher weight = checked first.

## Example Data

```sql
INSERT INTO reflex_greetings (key, metadata_json, data_json, weight)
VALUES (
  'greeting_hi',
  '{"type": "greeting", "triggers": ["hi", "hello", "hey"]}',
  '{"responses": ["Hey! What''s on your mind?", "Hi there!", "Hello! How can I help?"]}',
  0.4
);

INSERT INTO reflex_shortcuts (key, metadata_json, data_json, weight)
VALUES (
  'shortcut_clear',
  '{"type": "shortcut", "trigger": "/clear"}',
  '{"action": "clear_conversation", "confirm": false}',
  0.7
);
```

## Reflex vs Full Response

**Reflex fires when:**
1. Input matches a known trigger
2. No context needed for response
3. Speed matters more than depth

**Full context used when:**
1. No reflex matches
2. Complex question requiring reasoning
3. User explicitly wants detailed response

## API Usage

```python
from Nola.threads.reflex.adapter import ReflexThreadAdapter

adapter = ReflexThreadAdapter()

# Check if input matches a reflex
match = adapter.match_pattern("hi there")
if match:
    response = match.response
    # Return immediately without full context assembly

# Register new shortcut
adapter.register_shortcut(
    trigger="/weather",
    action="get_weather",
    description="Quick weather check"
)

# Get all greetings
greetings = adapter.get_module_data("greetings")
```

## Reflex Cascade

Reflexes are checked in order:

1. **System reflexes** (safety, errors) — always first
2. **User shortcuts** (custom commands)
3. **Social reflexes** (greetings, thanks)

First match wins.

## Integration with Other Threads

- **Identity**: User preferences affect reflex responses
- **Log**: Track reflex usage for 10x promotion
- **Philosophy**: Reflexes must align with values
- **Form**: Shortcuts can trigger tools
- **Linking Core**: Reflex patterns can have associated concepts

## Implementation (canonical)

Implementation notes and promotion rules live in `Nola/threads/reflex/IMPLEMENTATION.md`.

Quick implementer notes:
- Promotion: 10x rule triggers promotion; Log records frequency and consolidation daemon performs promotions.
- Match order: system → user → social. Keep this prioritized in `adapter.match_pattern()`.
- Persist reflex metadata and actions in `reflex_*` module tables.

