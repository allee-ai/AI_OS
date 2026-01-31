# Feeds Module

> 🚧 **In Development** — The universal router is being tested.

The **Feeds** module manages external data streams entering and leaving the AI OS. It abstracts various platforms (Email, Slack, SMS) into a unified message format so the Agent Core doesn't need platform-specific logic.

## Goals

1.  **Unified Inbox**: Treat all inputs (chat, email, code comments) as "Messages" with a standard schema.
2.  **Config-Driven**: Add new integrations via YAML without writing Python adapters.
3.  **Draft-First**: AI generates drafts in the native platform (Gmail drafts, Slack unsent), never sending automatically.

## Architecture

```
Feeds/
├── router.py          # The main message bus
├── api.py             # FastAPI endpoints used by the frontend
├── sources/           # YAML configurations for external APIs
│   ├── gmail.yaml     # (Planned)
│   ├── slack.yaml     # (Planned)
│   └── _template.yaml # structure for new sources
└── __init__.py
```

## Status

- [x] **Router Logic**: `router.py` can load and parse YAML configs.
- [x] **API Endpoints**: Basic CRUD for messages.
- [ ] **Auth Handlers**: OAuth2 flow for Gmail/Slack.
- [ ] **Polling**: Background loop to fetch new messages.
- [ ] **Draft Push**: Writing back to external APIs.

## Usage (Planned)

The goal is to allow adding a new source by simply dropping a YAML file:

```yaml
# sources/slack.yaml
name: slack
type: rest
poll_interval: 60
auth:
  method: bearer
  token_env: SLACK_BOT_TOKEN
pull:
  endpoint: https://slack.com/api/conversations.history
  mapping:
    messages: "$.messages"
    body: "$.text"
```

---

## Frontend Module

Located at `frontend/src/modules/feeds/`:

```
feeds/
├── index.ts                # Module exports
└── pages/
    ├── FeedsPage.tsx       # Main feeds view
    └── FeedsPage.css       # Styles
```