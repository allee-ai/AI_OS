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
├── secrets.py       # Encrypted credential storage
├── auth.py          # Bearer token authentication middleware
├── mcp_api.py       # MCP (Model Context Protocol) API endpoints
├── mcp_client.py    # MCP client for external tool servers
├── migrations.py    # Database schema migrations
├── settings_api.py  # User settings API endpoints
└── url_validation.py # URL validation and sanitization
```

### Components

| File | Purpose |
|------|---------|
| `config.py` | Application settings. Loads from `.env`. |
| `locks.py` | Thread-safe locks. Prevents race conditions. |
| `models_api.py` | Lists available models, switches active model. |
| `secrets.py` | Encrypted API keys, OAuth tokens, etc. |
| `auth.py` | Bearer token auth for API and mobile endpoints. |
| `mcp_api.py` | MCP server endpoints for external tool integration. |
| `mcp_client.py` | Client for connecting to MCP tool servers. |
| `migrations.py` | DDL migrations for all SQLite tables. |
| `settings_api.py` | User-facing settings CRUD (model, theme, etc.). |
| `url_validation.py` | URL validation and SSRF prevention. |

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
### Infrastructure
- [ ] **Config validation** — Validate required settings on startup, fail fast with clear errors
- [ ] **Secret rotation** — Automatic key rotation for long-running instances
- [ ] **Crypto requirement** — Remove base64 fallback in secrets.py — require cryptography package (security: base64 is not encryption)

### Starter tasks
- [ ] Secret audit logging (who accessed what, when)
<!-- /ROADMAP:core -->

---

## Changelog

<!-- CHANGELOG:core -->
### 2026-03-05
- New `migrations.py`: `ensure_schema()` calls every module `init_*` function so any table drift is repaired on startup; `ensure_all_schemas()` syncs both `state.db` and `state_demo.db` by temporarily overriding `STATE_DB_PATH`
- `data/db/__init__.py` `set_demo_mode()` now calls `ensure_schema()` after writing the mode file
- `scripts/server.py` startup calls `ensure_all_schemas()` before `wake()` — logs `[Startup] Schema synced`
- Guarantees `git clone + docker compose up` works on any machine with zero manual DB steps

### 2026-01-27
- Secrets management with Fernet encryption
- Machine-derived key for at-rest encryption

### 2026-01-20
- Config module with pydantic-settings
- Thread locks for memory writes
- Models API for model switching
<!-- /CHANGELOG:core -->
