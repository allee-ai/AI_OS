# Identity Thread

The Identity Thread answers: **"Who am I? Who are you?"**

## Purpose

Identity stores facts about self and user that persist across conversations. This is the most important thread — user identity facts take highest priority in context assembly.

## Architecture: L1/L2/L3 Per Key

Each identity key has three levels of detail:

```
key: "user_name"
L1: "Jordan"                                    (~5 tokens, realtime)
L2: "Jordan, software developer"                (~15 tokens, conversational)
L3: "Jordan, software developer building AI_OS, prefers morning work sessions"  (~30 tokens, analytical)
```

### Why Levels?

- **L1 (Realtime)**: Minimum viable context for quick responses
- **L2 (Conversational)**: Standard context for normal chat
- **L3 (Analytical)**: Full context for complex reasoning

## Modules

### `identity_flat`
The main identity table with hierarchical levels:

| Column | Purpose |
|--------|---------|
| `key` | Unique identifier (e.g., "user_name", "nola_personality") |
| `metadata_type` | Category: "user", "nola", "machine", "relationship" |
| `metadata_desc` | Human-readable description |
| `l1` | Quick fact (~10 tokens) |
| `l2` | Standard fact (~30 tokens) |
| `l3` | Full context (~100 tokens) |
| `weight` | 0.0-1.0, higher = more important |

## Key Principles

### User is Most Important
User identity facts should have the highest weights. Nola exists to serve the user — their name, preferences, and projects matter most.

### Slow to Change
Identity facts are stable. They update through:
1. **Explicit correction**: User says "Actually, my name is..."
2. **Consolidation daemon**: Repeated patterns promote to identity
3. **Manual editing**: Through the Threads UI

### Weight Decay
Facts not accessed decay over time. Frequently referenced facts maintain high weight.

## Example Data

```sql
INSERT INTO identity_flat (key, metadata_type, l1, l2, l3, weight)
VALUES 
  ('user_name', 'user', 'Jordan', 'Jordan, software developer', 
   'Jordan, software developer building AI_OS project, prefers concise responses', 0.95),
  
  ('nola_personality', 'nola', 'Helpful assistant', 
   'Nola: curious, warm, direct communicator',
   'Nola: curious and engaged, warm but professional, prefers direct communication, asks clarifying questions', 0.8);
```

## API Usage

```python
from Nola.threads.identity.adapter import IdentityThreadAdapter

adapter = IdentityThreadAdapter()

# Get facts at L2
facts = adapter.get_data(level=2, limit=10)

# Push new fact
adapter.push_identity(
    key="user_project",
    l1="AI_OS",
    l2="AI_OS, a cognitive architecture project",
    l3="AI_OS, a cognitive architecture with 5 threads...",
    metadata_type="user",
    weight=0.8
)
```

## Integration with Other Threads

- **Log**: Records when identity facts are accessed/modified
- **Linking Core**: Scores which identity facts are relevant right now
- **Philosophy**: Identity informs how Nola approaches values
- **Form**: User preferences affect tool behavior
