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
└── kernel_service.py    # Kernel browser integration
```

### Components

| File | Purpose |
|------|---------|
| `agent_service.py` | Message pipeline, context assembly |
| `kernel_service.py` | Kernel browser automation |
| `api.py` | Agent control endpoints |

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
### Ready for contributors
- [ ] **Multi-agent support** — Multiple agent personas
- [ ] **Streaming responses** — Token-by-token output
- [ ] **Context window optimization** — Smart truncation
- [ ] **Response caching** — Cache common responses

### Starter tasks
- [ ] Add response time metrics
- [ ] Show context token count in UI
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
