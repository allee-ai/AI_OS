# Log Thread

The Log Thread answers: **"What happened? When? How long have we been talking?"**

## Purpose

Log provides temporal awareness — a timeline of events, sessions, and patterns. Unlike other threads that store "what is true", Log stores "what has occurred".

## Architecture: Recency-Based Levels

Log doesn't use depth-based L1/L2/L3. Instead, levels determine **how far back** to look:

```
L1 = Last 10 events    (quick glance at recent activity)
L2 = Last 100 events   (conversation-scale history)
L3 = Last 1000 events  (full timeline)
```

### Why Recency?

Events are inherently temporal. You don't need "more detail" about an event — you need to know if it happened recently or long ago.

## Modules

### `log_events`
System events with timestamps:

| Column | Purpose |
|--------|---------|
| `key` | Unique event ID (e.g., "evt_20260108_143022_123456") |
| `metadata_json` | Event type and source |
| `data_json` | Message and details |
| `weight` | Importance (higher = more significant) |
| `created_at` | When it happened |

### `log_sessions`
Conversation session tracking:

| Column | Purpose |
|--------|---------|
| `key` | Session ID (e.g., "session_20260108_143022") |
| `data_json` | Start time, status, message count |
| `weight` | Session importance |

## Event Types

```
system:wake      - Nola started up
system:shutdown  - Nola shut down
convo:start      - Conversation began
convo:end        - Conversation ended
memory:extract   - Fact extracted from conversation
memory:consolidate - Facts consolidated to long-term
identity:update  - Identity fact changed
error:*          - Various error events
```

## Weight for Temporal Importance

Weight in Log represents **significance**, not permanence:

- **High weight (0.7+)**: Important events (user corrections, errors, milestones)
- **Medium weight (0.3-0.6)**: Normal events (messages, tool uses)
- **Low weight (0.1-0.2)**: Routine events (system wakes, heartbeats)

Over time, Linking Core can use weight + recency to surface contextually important past events.

## Example Data

```sql
-- System wake event
INSERT INTO log_events (key, metadata_json, data_json, weight)
VALUES (
  'evt_20260108_143022_123456',
  '{"type": "system:wake", "source": "subconscious"}',
  '{"message": "Subconscious awakened with 6 threads", "timestamp": "2026-01-08T14:30:22Z"}',
  0.2
);

-- Memory extraction (more important)
INSERT INTO log_events (key, metadata_json, data_json, weight)
VALUES (
  'evt_20260108_144500_789012',
  '{"type": "memory:extract", "source": "memory_service"}',
  '{"message": "Learned: User prefers morning meetings", "fact_key": "user_schedule_pref"}',
  0.6
);
```

## API Usage

```python
from Nola.threads.log.adapter import LogThreadAdapter

adapter = LogThreadAdapter()

# Get last 10 events (L1)
recent = adapter.get_data(level=1)

# Get last 100 events (L2)
history = adapter.get_data(level=2)

# Log a new event
adapter.log_event(
    event_type="user_action",
    source="chat",
    message="User asked about weather",
    weight=0.3
)

# Start a session
session_id = adapter.start_session()
```

## Temporal Patterns

The Log thread enables temporal reasoning:

- "We talked about this yesterday"
- "You've been working for 2 hours"
- "Last time you mentioned Sarah..."

Linking Core can activate concepts based on temporal proximity — recent mentions of "Sarah" boost related facts.

## Integration with Other Threads

- **Identity**: Log records when identity facts change
- **Linking Core**: Temporal proximity affects relevance scoring
- **Form**: Action history lives in Form, but Log timestamps everything
- **Philosophy**: Log can track ethical decisions over time
