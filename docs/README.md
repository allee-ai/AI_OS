# AI_OS Documentation

Welcome to the AI_OS documentation. Use the tree on the left to browse all markdown files in the project.

## Quick Start

- **README.md** — Every module has a README explaining its purpose
- **ARCHITECTURE.md** — System design overview
- **ROADMAP.md** — Feature status and future plans
- **CHANGELOG.md** — Version history

## Project Structure

```
AI_OS/
├── agent/           # Core agent logic
│   ├── core/        # Config, locks, API models
│   ├── services/    # Runtime, Kernel integration
│   ├── subconscious/# Context assembly, loops
│   └── threads/     # 5 data threads + linking core
│       ├── identity/
│       ├── log/
│       ├── form/
│       ├── philosophy/
│       ├── reflex/
│       └── linking_core/
├── chat/            # Conversation API and storage
├── Feeds/           # External data sources
├── workspace/       # User file management
├── finetune/        # Model training
├── eval/            # Benchmarking
├── docs/            # This documentation
├── frontend/        # React UI (modules mirror backend)
└── scripts/         # Utilities
```

## Documentation Guidelines

Each backend module should have a README.md that includes:
1. **Purpose** — What it does
2. **Architecture** — File structure
3. **API** — Endpoints (if applicable)
4. **Frontend Module** — Corresponding UI location
