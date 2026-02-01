# Chat Module

Conversation logic, real-time API, and import system for AI OS.

---

## Description

The Chat module handles all conversation interactions. It provides the real-time API for the frontend, persistent history storage, and a powerful import system for migrating data from other AI providers (ChatGPT, Claude, Gemini, VS Code Copilot).

---

## Architecture

<!-- ARCHITECTURE:chat -->
### Directory Structure

```
chat/
├── api.py              # FastAPI endpoints
├── schema.py           # SQLite tables
├── import_convos.py    # Import from other providers
└── parsers/            # Format-specific parsers
```

### Database Schema

| Table | Purpose |
|-------|---------|
| `convos` | Session metadata |
| `convo_turns` | Message content |
| `message_ratings` | User feedback |

### Key Functions

| Function | Purpose |
|----------|---------|
| `save_conversation()` | Persist full conversation state |
| `add_turn()` | Append single interaction |
| `ImportConvos.import_conversations()` | Import pipeline |

### Supported Import Formats

- ChatGPT (`conversations.json`)
- Claude (`conversations.json`)
- Gemini (JSON export)
- VS Code Copilot (JSON export)
<!-- /ARCHITECTURE:chat -->

---

## Roadmap

<!-- ROADMAP:chat -->
### Ready for contributors
- [ ] **Import pipeline repair** — Fix and improve `import_convos.py` reliability
- [ ] **Smart import helper** — Chat-aware LLM that assists with import errors at runtime ("this file failed, here's why, let me fix it")
- [ ] **Conversation archiving** — Archive old convos without deleting, restore on demand
- [ ] **Import directory organization** — Separate imports by source (`imported/claude/`, `imported/gpt/`, `imported/copilot/`)
- [ ] **Sidebar directory visibility** — Show import folders in sidebar, collapsible by source
- [ ] **Conversation search** — Full-text search across history
- [ ] **Branching** — Create conversation forks
- [ ] **Export** — Export to markdown/JSON
- [ ] **Tags/categories** — Organize conversations

### Starter tasks
- [ ] Add conversation summary generation
- [ ] Show message timestamps
- [ ] Import source badges on conversation cards
<!-- /ROADMAP:chat -->

---

## Changelog

<!-- CHANGELOG:chat -->
### 2026-01-27
- Multi-provider import system
- Message ratings for fine-tuning

### 2026-01-20
- Real-time WebSocket chat
- Conversation CRUD operations
<!-- /CHANGELOG:chat -->