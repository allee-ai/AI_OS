# Core

Shared infrastructure used across all agent modules. No business logic — just plumbing.

---

## Description

Core provides the foundational utilities that all other modules depend on: configuration, thread safety, model management, and secrets storage. It's designed to have zero dependencies on other agent modules to prevent circular imports.

---

## Architecture

<!-- ARCHITECTURE:core -->
### Directory Structure

```
agent/core/
├── config.py        # Application settings via pydantic-settings
├── locks.py         # Thread-safe locks for memory/DB writes
├── models_api.py    # Model management API endpoints
└── secrets.py       # Encrypted credential storage
```

### Components

| File | Purpose |
|------|---------|
| `config.py` | Application settings. Loads from `.env`. |
| `locks.py` | Thread-safe locks. Prevents race conditions. |
| `models_api.py` | Lists available models, switches active model. |
| `secrets.py` | Encrypted API keys, OAuth tokens, etc. |

### Data Flow

```
.env / Environment Variables → config.py → settings singleton
                                              ↓
                              All modules import settings
```

```
API Key → secrets.py → Fernet encryption → SQLite (encrypted)
                                              ↓
                              Feed adapters retrieve decrypted
```
<!-- /ARCHITECTURE:core -->

---

## Usage

### Config

```python
from agent.core.config import settings

print(settings.app_name)  # "AI OS"
print(settings.port)       # 8000
```

### Locks

```python
from agent.core.locks import MEMORY_WRITE_LOCK

with MEMORY_WRITE_LOCK:
    db.execute("INSERT INTO facts ...")
```

### Models API

```python
from agent.core.models_api import get_available_models

models = get_available_models()  # List of ModelInfo
```

Endpoints:
- `GET /api/models` — List available models
- `POST /api/models/set` — Switch active model

### Secrets

```python
from agent.core.secrets import store_secret, get_secret

store_secret("gmail", {"client_id": "...", "refresh_token": "..."})
creds = get_secret("gmail")
```

---

## Roadmap

<!-- ROADMAP:core -->
### Ready for contributors
- [ ] **Config validation** — Validate required settings on startup
- [ ] **Multi-environment support** — Dev/staging/prod config profiles
- [ ] **Secret rotation** — Automatic key rotation for long-running instances

### Starter tasks
- [ ] Add config documentation generator
- [ ] Add secret audit logging
<!-- /ROADMAP:core -->

---

## Changelog

<!-- CHANGELOG:core -->
### 2026-01-27
- Secrets management with Fernet encryption
- Machine-derived key for at-rest encryption

### 2026-01-20
- Config module with pydantic-settings
- Thread locks for memory writes
- Models API for model switching
<!-- /CHANGELOG:core -->
