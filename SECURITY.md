# Security Notes — AI OS

Last audited: 2025-06-25

## Summary

AI OS is designed as a **local-first, single-user** application. The server binds to `localhost` by default and is not intended for public network exposure. All 10 identified security issues have been addressed.

---

## Critical

### 1. Zero Authentication on API

**All endpoints are completely open.** No bearer tokens, API keys, or session management exist.

- Any process on the machine (or network, if bound to `0.0.0.0`) can read/write all data
- `PUT /api/settings` allows overwriting API keys without authorization
- `/api/db-mode/{mode}` switches databases with no check

**Files:** `scripts/server.py`, `agent/core/config.py`  
**Status:** ✅ Fixed — `agent/core/auth.py` generates bearer token stored in `.env`, applied as app-level FastAPI dependency. Public paths (`/health`, `/docs`, `/assets/`) exempted. WebSocket auth via `?token=` param.

### 2. Command Injection via Terminal Tool

The LLM tool executor passes commands directly to `subprocess.run(command, shell=True)`. A prompt-injected LLM could execute arbitrary shell commands.

**File:** `agent/threads/form/tools/executables/terminal.py`  
**Status:** ✅ Fixed — `shlex.split()` + `shell=False`. Blocked commands set (`rm -rf /`, `sudo`, `curl | bash`, fork bombs, etc.).

---

## High

### 3. API Key Exposure via Settings Endpoint

`GET /api/settings` returns all configuration values including `OPENAI_API_KEY`, `KERNEL_API_KEY`, `LINEAR_API_KEY`. The frontend masks them visually, but the full values are in the JSON response.

**File:** `agent/core/settings_api.py`  
**Status:** ✅ Fixed — Password-type fields return `"••••••••"` with `is_set: bool`. Raw values never sent in GET responses.

---

## Medium

### 4. SSRF in Feeds Module

Feeds router and calendar source fetch arbitrary URLs without validating against private IP ranges. A malicious calendar iCal URL could target `http://169.254.169.254/` (cloud metadata) or internal network services.

**Files:** `Feeds/router.py`, `Feeds/sources/calendar/__init__.py`  
**Status:** ✅ Fixed — `agent/core/url_validation.py` resolves hostnames and blocks RFC 1918, loopback, link-local, and IPv6 ULA ranges before any outbound request.

### 5. No Upload Size or ZIP Bomb Protection

File upload endpoint (`POST /api/import/upload`) has no size limit. ZIP extraction has no bomb protection — a 1 MB compressed file could expand to gigabytes.

**File:** `agent/services/api.py`  
**Status:** ✅ Fixed — 50 MB upload cap, ZIP bomb protection (200 MB extracted limit, 5000 file limit), `zipfile.is_zipfile()` validation, path traversal check on ZIP entries.

### 6. Unbounded WebSocket Connections

No limit on concurrent WebSocket connections per client. An attacker could open thousands of connections to exhaust memory.

**File:** `chat/api.py`  
**Status:** ✅ Fixed — `MAX_CONNECTIONS = 50` global cap. New connections rejected with code 1013 when limit reached.

### 7. Path Traversal in Workspace

`normalize_path()` doesn't fully prevent `../` traversal sequences. Database UNIQUE constraints provide some mitigation but shouldn't be the only defense.

**File:** `workspace/schema.py`  
**Status:** ✅ Fixed — `normalize_path()` now rejects any path containing `..` segments. Double-checked with `PurePosixPath` resolution.

---

## Low

### 8. Verbose Error Messages

Multiple endpoints return `str(exception)` in HTTP 500 responses, leaking filesystem paths, database schema details, and internal module names.

**Files:** `chat/api.py`, `agent/services/api.py`, others  
**Status:** ✅ Fixed — All error handlers now log full exception server-side and return generic messages to clients.

### 9. Permissive CORS Headers

`allow_headers=["*"]` combined with `allow_credentials=True` is overly broad.

**File:** `scripts/server.py`  
**Status:** ✅ Fixed — Explicit allow list: `["Content-Type", "Authorization", "X-Requested-With"]`.

### 10. Dynamic Module Import

`Feeds/api.py` uses `importlib.import_module()` with filesystem-sourced module names. Low risk since it requires filesystem write access, but should use a whitelist.

**File:** `Feeds/api.py`  
**Status:** ✅ Fixed — `_ALLOWED_MODULES` frozenset built at startup from directories containing `__init__.py`. Import blocked for any module not in whitelist.

---

## Mitigating Factors

- **Local-only by default:** Server binds to `127.0.0.1`, limiting exposure to localhost
- **Single-user design:** No multi-tenancy means no privilege escalation between users
- **SQLite with parameterized queries:** No SQL injection found — all database access uses proper parameterization
- **No pickle deserialization:** All serialization uses JSON

## Priority Order

1. Bearer token auth (blocks all unauthenticated access)
2. Terminal tool `shell=False` (blocks RCE via prompt injection)
3. Settings endpoint secret masking (blocks key theft)
4. Everything else (SSRF, uploads, WebSocket, error messages)
