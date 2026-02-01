# Reflex Thread

**Cognitive Question**: HOW do I respond? (when I've done it before)  
**Resolution Order**: 4th (after WHO/WHAT/WHY, check for learned patterns)  
**Brain Mapping**: Basal Ganglia (habit formation, automatic responses)

---

## Description

Reflex handles learned automaticity. Patterns that repeat become "muscle memory" — they bypass full context assembly for efficiency. This is how the system learns to be fast without being dumb.

---

## Architecture

<!-- ARCHITECTURE:reflex -->
### Database Tables

| Table | Purpose |
|-------|---------|
| `reflex_greetings` | Quick greeting patterns |
| `reflex_shortcuts` | User-defined commands |
| `reflex_system` | System-level reflexes |
| `reflex_triggers` | Feed event → Tool action automations |

### Pattern Matching

```
trigger → response
"hi" → "Hey! What's on your mind?"
"/clear" → [clear_conversation action]
```

### Feed Triggers (NEW)

Connect feed events to tool actions:
```
gmail/email_received → web_search/search
discord/mention_received → send_notification/notify
```

Trigger fields:
- **feed_name**: Source feed (gmail, discord, etc.)
- **event_type**: Event to listen for (email_received, message_sent, etc.)
- **condition**: Optional filter (e.g., subject contains "urgent")
- **tool_name**: Tool to execute
- **tool_action**: Action to perform
- **tool_params**: Parameters to pass to tool

### Reflex Cascade

Checked in order (first match wins):
1. **System reflexes** (safety, errors) — 0.9+ weight
2. **User shortcuts** (commands) — 0.6-0.8 weight
3. **Social reflexes** (greetings) — 0.3-0.5 weight

If no match → proceed to full context assembly.

### Context Levels

| Level | Content |
|-------|---------|
| **L1** | Active reflex triggers (metadata) |
| **L2** | L1 + matching patterns with responses |
| **L3** | L2 + full tool chains for complex reflexes |
<!-- /ARCHITECTURE:reflex -->

---

## API Endpoints

### Triggers (Feed → Tool Automations)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/reflex/triggers` | GET | List all triggers |
| `/api/reflex/triggers` | POST | Create new trigger |
| `/api/reflex/triggers/{id}` | GET | Get trigger details |
| `/api/reflex/triggers/{id}` | PUT | Update trigger |
| `/api/reflex/triggers/{id}` | DELETE | Delete trigger |
| `/api/reflex/triggers/{id}/toggle` | POST | Enable/disable trigger |
| `/api/reflex/triggers/{id}/test` | POST | Test execute trigger |
| `/api/reflex/triggers/stats/summary` | GET | Get trigger statistics |

---

## Roadmap

<!-- ROADMAP:reflex -->
### Ready for contributors
- [ ] **10x auto-promotion** — Patterns repeating 10+ times auto-promote to reflex
- [ ] **Reflex editor** — Visual pattern builder in UI
- [x] **Conditional reflexes** — Feed event triggers with conditions
- [ ] **Reflex analytics** — Usage frequency, match rates

### Starter tasks
- [ ] Add reflex test button in UI
- [ ] Show reflex match history
- [x] Implement reflex enable/disable toggle
- [ ] Feed trigger builder UI
<!-- /ROADMAP:reflex -->

---

## Changelog

<!-- CHANGELOG:reflex -->
### 2026-02-01
- Added `reflex_triggers` SQLite table for feed → tool automations
- New trigger CRUD endpoints (create, read, update, delete, toggle)
- Trigger executor integrates with Form tools
- Condition matching with operators (eq, contains, regex, etc.)
- Auto-execution when feed events are emitted
- Trigger test endpoint for manual testing

### 2026-01-27
- Three-tier reflex cascade (system → user → social)
- Pattern matching with weight priorities

### 2026-01-20
- Greeting and shortcut tables
- Basic pattern matching
<!-- /CHANGELOG:reflex -->

