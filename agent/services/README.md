# Agent Services

The core agent runtime and external integrations.

---

## Description

Services contains the main agent runtime that handles message processing, context assembly, and response orchestration. It's the "spine" connecting threads to the LLM.

---

## Architecture

<!-- ARCHITECTURE:services -->
### Directory Structure

```
agent/services/
├── agent_service.py     # Main runtime — message handling
├── api.py               # FastAPI endpoints
├── kernel_service.py    # Kernel browser integration
├── mobile_api.py        # Mobile app REST API
└── mobile_panel.html    # Mobile web panel
```

### Components

| File | Purpose |
|------|---------|
| `agent_service.py` | Message pipeline, context assembly |
| `kernel_service.py` | Kernel browser automation |
| `api.py` | Agent control endpoints |
| `mobile_api.py` | Mobile-optimized REST API with bearer token auth |
| `mobile_panel.html` | Mobile web interface |

### Data Flow

```
User Message → agent_service.py
    → get_consciousness_context()
    → agent.generate()
    → Response
```
<!-- /ARCHITECTURE:services -->

---

## Roadmap

<!-- ROADMAP:services -->
### Runtime
- [ ] **API authentication** — Optional bearer token auth for all endpoints (currently zero auth — security critical)
- [ ] **Streaming responses** — Token-by-token output via SSE/WebSocket
- [ ] **Context window monitoring** — Track actual token usage per request, alert on budget overflow
- [ ] **Multi-session goal tracking** — Long-horizon tasks that span multiple conversations: decompose, checkpoint, resume

### Starter tasks
- [ ] Response time + token count metrics per request
- [ ] Context budget usage display in UI
<!-- /ROADMAP:services -->

---

## Changelog

<!-- CHANGELOG:services -->
### 2026-01-27
- Consciousness context assembly via subconscious
- Kernel browser integration

### 2026-01-20
- Agent runtime with message pipeline
- FastAPI endpoints for agent control
<!-- /CHANGELOG:services -->
