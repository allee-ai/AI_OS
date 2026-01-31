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

### Pattern Matching

```
trigger → response
"hi" → "Hey! What's on your mind?"
"/clear" → [clear_conversation action]
```

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

## Roadmap

<!-- ROADMAP:reflex -->
### Ready for contributors
- [ ] **10x auto-promotion** — Patterns repeating 10+ times auto-promote to reflex
- [ ] **Reflex editor** — Visual pattern builder in UI
- [ ] **Conditional reflexes** — Time-of-day, user-state triggers
- [ ] **Reflex analytics** — Usage frequency, match rates

### Starter tasks
- [ ] Add reflex test button in UI
- [ ] Show reflex match history
- [ ] Implement reflex enable/disable toggle
<!-- /ROADMAP:reflex -->

---

## Changelog

<!-- CHANGELOG:reflex -->
### 2026-01-27
- Three-tier reflex cascade (system → user → social)
- Pattern matching with weight priorities

### 2026-01-20
- Greeting and shortcut tables
- Basic pattern matching
<!-- /CHANGELOG:reflex -->

