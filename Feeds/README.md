# Feeds Module

> ✅ **Core Complete** — Modular feeds, OAuth, events, and triggers ready.

Universal inbox for external data streams — Email, Slack, SMS, and more.

---

## Description

The Feeds module manages external data streams entering and leaving AI OS. It abstracts various platforms into a unified message format so the Agent Core doesn't need platform-specific logic. Each feed is a modular directory with its own OAuth config, event types, and API adapter.

---

## Architecture

<!-- ARCHITECTURE:feeds -->
### Directory Structure

```
Feeds/
├── router.py              # Main message bus
├── api.py                 # FastAPI endpoints (secrets, OAuth, events)
├── events.py              # Event registry and emission system
└── sources/               # Modular feed directories
    ├── gmail/
    │   └── __init__.py    # OAuth, adapter, event types
    ├── discord/
    │   └── __init__.py    # Bot adapter, event types
    └── _template.yaml     # Legacy YAML structure
```

### Feed Modules

Each feed module defines:
- **Event types**: What events it can emit (email_received, message_sent, etc.)
- **OAuth config**: How to authenticate (Google OAuth2, bot tokens, etc.)
- **Adapter**: API wrapper for fetching/sending data

### Event System

```python
from Feeds.events import emit_event, EventPriority

# Emit an event (auto-logged, triggers reflexes)
emit_event(
    feed_name="gmail",
    event_type="email_received",
    payload={"from": "user@example.com", "subject": "Hello"},
    priority=EventPriority.HIGH,
)
```

### Secrets Management

Encrypted credential storage for API keys and OAuth tokens:
```python
from agent.core.secrets import store_secret, get_oauth_tokens

# Store API key
store_secret("discord", "bot_token", "MTEx...")

# Get OAuth tokens
tokens = get_oauth_tokens("gmail")
```

### Status

| Feature | Status |
|---------|--------|
| Router Logic | ✅ |
| API Endpoints | ✅ |
| Event System | ✅ |
| Secrets Storage | ✅ |
| Gmail OAuth | ✅ |
| Discord Adapter | ✅ |
| Reflex Triggers | ✅ |
<!-- /ARCHITECTURE:feeds -->

---

## API Endpoints

### Secrets Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/feeds/secrets/{feed}` | GET | Get stored secrets (masked) |
| `/api/feeds/secrets/{feed}` | POST | Store a secret |
| `/api/feeds/secrets/{feed}` | DELETE | Delete all secrets for feed |

### OAuth

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/feeds/{feed}/oauth/start` | GET | Start OAuth flow (returns URL) |
| `/api/feeds/{feed}/oauth/callback` | GET | OAuth callback handler |
| `/api/feeds/{feed}/oauth/status` | GET | Check connection status |
| `/api/feeds/{feed}/disconnect` | POST | Remove all credentials |

### Events

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/feeds/events/types` | GET | List registered event types |
| `/api/feeds/events/triggers` | GET | Get available triggers for Reflex |
| `/api/feeds/events/recent` | GET | Get recent feed events from log |
| `/api/feeds/{feed}/webhook` | POST | Receive webhook events |

---

## Roadmap

<!-- ROADMAP:feeds -->
### Ready for contributors
- [x] **Gmail adapter** — OAuth2 flow, draft creation
- [ ] **Slack adapter** — Bot token auth, message polling
- [ ] **SMS adapter** — Twilio integration
- [x] **Discord adapter** — Bot token, channel watching

### Starter tasks
- [x] Create gmail module from template
- [ ] Add feed status indicators in UI
- [ ] Feed viewer components (native dashboard)
<!-- /ROADMAP:feeds -->

---

## Changelog

<!-- CHANGELOG:feeds -->
### 2026-02-01
- Modular feed architecture (gmail/, discord/ directories)
- Event system with registry and handlers
- Encrypted secrets storage (Fernet encryption)
- Gmail OAuth2 flow with token refresh
- Discord bot adapter with event types
- Feed events auto-trigger Reflex automations
- New API endpoints for secrets, OAuth, events

### 2026-01-27
- YAML-driven source configuration
- Router message bus

### 2026-01-20
- Basic API endpoints for message CRUD
<!-- /CHANGELOG:feeds -->