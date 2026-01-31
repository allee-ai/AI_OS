# Feeds Module

> 🚧 **In Development** — The universal router is being tested.

Universal inbox for external data streams — Email, Slack, SMS, and more.

---

## Description

The Feeds module manages external data streams entering and leaving AI OS. It abstracts various platforms into a unified message format so the Agent Core doesn't need platform-specific logic. The goal is config-driven integrations via YAML, with draft-first responses (never auto-sending).

---

## Architecture

<!-- ARCHITECTURE:feeds -->
### Directory Structure

```
Feeds/
├── router.py          # Main message bus
├── api.py             # FastAPI endpoints
└── sources/           # YAML configurations
    └── _template.yaml # Structure for new sources
```

### Source Configuration

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
```

### Status

| Feature | Status |
|---------|--------|
| Router Logic | ✅ |
| API Endpoints | ✅ |
| Auth Handlers | 🔜 |
| Polling | 🔜 |
| Draft Push | 🔜 |
<!-- /ARCHITECTURE:feeds -->

---

## Roadmap

<!-- ROADMAP:feeds -->
### Ready for contributors
- [ ] **Gmail adapter** — OAuth2 flow, draft creation
- [ ] **Slack adapter** — Bot token auth, message polling
- [ ] **SMS adapter** — Twilio integration
- [ ] **Discord adapter** — Bot token, channel watching

### Starter tasks
- [ ] Create gmail.yaml from template
- [ ] Add feed status indicators in UI
<!-- /ROADMAP:feeds -->

---

## Changelog

<!-- CHANGELOG:feeds -->
### 2026-01-27
- YAML-driven source configuration
- Router message bus

### 2026-01-20
- Basic API endpoints for message CRUD
<!-- /CHANGELOG:feeds -->