# Agent Services

The **Services** module contains the core agent runtime and external integrations.

## Architecture

```
agent/services/
├── __init__.py          # Module exports
├── agent_service.py     # Main agent runtime — message handling, context assembly
├── api.py               # FastAPI endpoints for agent control
└── kernel_service.py    # Kernel browser automation integration
```

## Components

### agent_service.py
The main agent runtime. Handles:
- Message processing pipeline
- Consciousness context assembly (via subconscious)
- Response generation orchestration

### kernel_service.py
Integration with Kernel browser automation for web tasks.

## Status

- [x] Agent runtime
- [x] Context assembly
- [x] Kernel integration (experimental)
- [ ] Multi-agent support

---

## Frontend Module

Located at `frontend/src/modules/services/`:

```
services/
├── index.ts                           # Module exports
├── pages/
│   ├── SettingsPage.tsx               # Settings hub
│   └── SettingsPage.css
└── components/
    ├── index.ts                       # Component exports
    ├── AgentDashboard.tsx             # Agent status & controls
    ├── MemoryDashboard.tsx            # Memory statistics
    ├── ConsolidationDashboard.tsx     # Consolidation loop status
    ├── FactExtractorDashboard.tsx     # Fact extraction controls
    └── KernelDashboard.tsx            # Kernel browser integration
```
