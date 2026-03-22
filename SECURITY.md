# Security Notes — AI OS

Last audited: 2026-03-21

## Summary

AI OS is designed as a **local-first, single-user** application. The server binds to `localhost` by default and is not intended for public network exposure. That said, several areas need hardening before any multi-user or LAN deployment.

---

## Critical

### 1. Zero Authentication on API

**All endpoints are completely open.** No bearer tokens, API keys, or session management exist.

- Any process on the machine (or network, if bound to `0.0.0.0`) can read/write all data
- `PUT /api/settings` allows overwriting API keys without authorization
- `/api/db-mode/{mode}` switches databases with no check

**Files:** `scripts/server.py`, `agent/core/config.py`  
**Status:** Open — acknowledged in `docs/ROADMAP.md` line 376  
**Fix:** Add `Depends(HTTPBearer())` middleware to all `/api/*` routes. Generate a local token on first run, store in `.env`.

### 2. Command Injection via Terminal Tool

The LLM tool executor passes commands directly to `subprocess.run(command, shell=True)`. A prompt-injected LLM could execute arbitrary shell commands.

**File:** `agent/threads/form/tools/executables/terminal.py`  
**Status:** Open  
**Fix:** Use `shlex.split()` + `shell=False`. Add a command allowlist or confirmation step for destructive commands.

---

## High

### 3. API Key Exposure via Settings Endpoint

`GET /api/settings` returns all configuration values including `OPENAI_API_KEY`, `KERNEL_API_KEY`, `LINEAR_API_KEY`. The frontend masks them visually, but the full values are in the JSON response.

**File:** `agent/core/settings_api.py`  
**Status:** Open  
**Fix:** Never return secret values in GET responses. Only return whether a key is set (boolean). Require re-authentication for PUT updates to password-type fields.

---

## Medium

### 4. SSRF in Feeds Module

Feeds router and calendar source fetch arbitrary URLs without validating against private IP ranges. A malicious calendar iCal URL could target `http://169.254.169.254/` (cloud metadata) or internal network services.

**Files:** `Feeds/router.py`, `Feeds/sources/calendar/__init__.py`  
**Status:** Open  
**Fix:** Reject private/reserved IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8, 169.254.0.0/16) before making outbound requests. Whitelist allowed domains per feed source.

### 5. No Upload Size or ZIP Bomb Protection

File upload endpoint (`POST /api/import/upload`) has no size limit. ZIP extraction has no bomb protection — a 1 MB compressed file could expand to gigabytes.

**File:** `agent/services/api.py`  
**Status:** Open  
**Fix:** Set `max_upload_size` (e.g. 50 MB). Validate ZIP contents and total extracted size before extraction. Use `zipfile.is_zipfile()` + member size checks.

### 6. Unbounded WebSocket Connections

No limit on concurrent WebSocket connections per client. An attacker could open thousands of connections to exhaust memory.

**File:** `chat/api.py`  
**Status:** Open  
**Fix:** Cap connections per client ID (e.g. 5). Add a global connection limit. Implement idle timeout.

### 7. Path Traversal in Workspace

`normalize_path()` doesn't fully prevent `../` traversal sequences. Database UNIQUE constraints provide some mitigation but shouldn't be the only defense.

**File:** `workspace/schema.py`  
**Status:** Open  
**Fix:** Resolve paths with `PurePosixPath` and verify they remain under the workspace root. Reject any path containing `..`.

---

## Low

### 8. Verbose Error Messages

Multiple endpoints return `str(exception)` in HTTP 500 responses, leaking filesystem paths, database schema details, and internal module names.

**Files:** `chat/api.py`, `agent/services/api.py`, others  
**Status:** Open  
**Fix:** Log full exceptions server-side. Return generic error messages to clients: `"An internal error occurred"`.

### 9. Permissive CORS Headers

`allow_headers=["*"]` combined with `allow_credentials=True` is overly broad.

**File:** `scripts/server.py`  
**Status:** Open  
**Fix:** Explicitly list allowed headers: `["Content-Type", "Authorization"]`.

### 10. Dynamic Module Import

`Feeds/api.py` uses `importlib.import_module()` with filesystem-sourced module names. Low risk since it requires filesystem write access, but should use a whitelist.

**File:** `Feeds/api.py`  
**Status:** Open  
**Fix:** Pre-scan and whitelist valid source modules at startup. Reject any module name not in the whitelist.

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
