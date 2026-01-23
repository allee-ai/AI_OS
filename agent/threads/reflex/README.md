# Reflex Thread

**Cognitive Question**: HOW do I respond? (when I've done it before)  
**Resolution Order**: 4th (after WHO/WHAT/WHY, check for learned patterns)  
**Brain Mapping**: Basal Ganglia (habit formation, automatic responses)

---

## Necessity

Reflex handles learned automaticity. Patterns that repeat become "muscle memory" — they bypass full context assembly for efficiency. This is how the system learns to be fast without being dumb.

---

## Backend

### Database Tables

| Table | Location | Purpose |
|-------|----------|---------|
| `reflex_greetings` | `schema.py` (module) | Quick greeting patterns |
| `reflex_shortcuts` | `schema.py` (module) | User-defined commands |
| `reflex_system` | `schema.py` (module) | System-level reflexes |

### Adapter

| Method | Location | Purpose |
|--------|----------|---------|
| `get_greetings()` | `adapter.py:37` | Get greeting patterns |
| `get_shortcuts()` | `adapter.py:41` | Get user shortcuts |
| `get_system_reflexes()` | `adapter.py:45` | Get system reflexes |
| `add_greeting()` | `adapter.py:49` | Add greeting response |
| `add_shortcut()` | `adapter.py:59` | Add user shortcut |
| `match_greeting()` | `adapter.py:71` | Check if text matches greeting |
| `match_shortcut()` | `adapter.py:89` | Check if text matches shortcut |
| `try_quick_response()` | `adapter.py:107` | Try to get quick response |

---

## Context Levels

Reflex uses **pattern matching**, not depth-based L1/L2/L3:

| Level | Content |
|-------|---------|
| **L1** | Active reflex triggers only (metadata) |
| **L2** | L1 + top-k matching patterns with responses |
| **L3** | L2 + full tool chains for complex reflexes |

### Pattern Structure

```
trigger → response
"hi" → "Hey! What's on your mind?"
"/clear" → [clear_conversation action]
```

---

## Modules

### `reflex_greetings`
Quick social responses:
- `hi`, `hello`, `hey` → Warm greeting
- `thanks`, `thank you` → Acknowledgment
- `bye`, `goodbye` → Friendly farewell

### `reflex_shortcuts`
User-defined commands:
- `/clear` → Clear conversation
- `/status` → Show system status
- `/help` → Show available commands

### `reflex_system`
System-level reflexes:
- Error detected → Log and notify
- Low memory → Trigger consolidation
- Long silence → Check in with user

---

## Frontend

| Component | Location | Status |
|-----------|----------|--------|
| `ReflexDashboard.tsx` | `frontend/src/components/ReflexDashboard.tsx` | ✅ Done |
| Reflex tab in ThreadsPage | `ThreadsPage.tsx` | ✅ Done |

**Features**:
- ✅ View all reflexes
- ✅ Add new shortcuts
- ⬜ Edit existing reflexes
- ⬜ Test reflex matching

---

## The 10x Promotion Rule (Future)

When a pattern repeats 10+ times, it should auto-promote to reflex:

```
User says "what time is it" 10 times
→ Promote to reflex
→ Next time: instant response, no full context
```

This is how Agent learns efficiency through repetition.

---

## Integration Points

| Thread | Integration |
|--------|-------------|
| **Identity** | User preferences affect reflex responses |
| **Form** | Shortcuts can trigger tools |
| **Philosophy** | Reflexes must align with values |
| **Log** | Track reflex usage for 10x promotion |
| **Linking Core** | Reflex patterns have associated concepts |

---

## Weight Semantics

- **0.9+**: System reflexes (safety, errors) — checked first
- **0.6-0.8**: User shortcuts (custom commands)
- **0.3-0.5**: Social reflexes (greetings)

Higher weight = higher priority in cascade.

---

## Reflex Cascade

Checked in order (first match wins):
1. **System reflexes** (safety, errors) — always first
2. **User shortcuts** (custom commands)
3. **Social reflexes** (greetings, thanks)

If no match → proceed to full context assembly.

