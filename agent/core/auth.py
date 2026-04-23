"""
Auth — Bearer Token Authentication for AI OS API
==================================================
Generates a local API token on first run, stores it in .env.
Provides a FastAPI dependency that validates the token on every request.

Public (no-auth) endpoints:
    /health
    /api/db-mode/mode (GET only)
    /docs, /openapi.json, /redoc

All other /api/* and /ws endpoints require:
    Authorization: Bearer <token>
"""

import os
import secrets
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, Request, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# ── Token storage ────────────────────────────────────────────────────

_ENV_KEY = "AIOS_API_TOKEN"
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

_bearer_scheme = HTTPBearer(auto_error=False)


def _read_token_from_env() -> Optional[str]:
    """Read token from runtime env or .env file."""
    # Check runtime env first
    val = os.environ.get(_ENV_KEY)
    if val:
        return val
    # Fall back to .env file
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{_ENV_KEY}="):
                return stripped.split("=", 1)[1].strip()
    return None


def _append_to_env(key: str, value: str):
    """Append a key=value to .env, creating if needed."""
    lines = []
    if _ENV_PATH.exists():
        lines = _ENV_PATH.read_text().splitlines()
    lines.append(f"{key}={value}")
    _ENV_PATH.write_text("\n".join(lines) + "\n")


def get_or_create_token() -> str:
    """Return existing token or generate + persist a new one."""
    token = _read_token_from_env()
    if token:
        return token
    token = secrets.token_urlsafe(32)
    os.environ[_ENV_KEY] = token
    _append_to_env(_ENV_KEY, token)
    return token


# ── Paths that skip authentication ──────────────────────────────────

PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    # Mobile panel HTML itself is public so the phone's first hit with
    # ?key=TOKEN can load the page. The JS then captures the token and
    # sends it as Authorization: Bearer on every subsequent API call.
    # No data is exposed here — the HTML is a static shell.
    "/api/mobile/",
    "/api/mobile",
    "/api/mobile/voice/",
    "/api/mobile/voice",
    "/api/mobile/voice/health",
}

PUBLIC_PREFIXES = (
    "/assets/",     # Static frontend files
)


def _is_public(path: str) -> bool:
    """Check if a request path is public (no auth required)."""
    if path in PUBLIC_PATHS:
        return True
    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    # SPA fallback — non-API paths serve index.html
    if not path.startswith("/api/") and not path.startswith("/ws"):
        return True
    return False


# ── FastAPI dependencies ─────────────────────────────────────────────

async def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
):
    """Dependency that enforces bearer token auth on non-public paths."""
    if _is_public(request.url.path):
        return None

    # Public-demo bypass: when the server is intentionally read-only AND has
    # LLM calls disabled, allow anonymous access. Visitors to the live demo
    # iframe must not need a token. The read-only middleware still blocks
    # any state-changing request (POST/PUT/PATCH/DELETE).
    if (
        os.environ.get("AIOS_READ_ONLY", "").lower() in ("1", "true", "yes")
        and os.environ.get("AIOS_NO_LLM", "").lower() in ("1", "true", "yes")
    ):
        return None

    expected = _read_token_from_env()
    if not expected:
        # No token configured — auth disabled (first-run / local dev)
        return None

    if not credentials or credentials.credentials != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials


async def require_ws_auth(websocket: WebSocket) -> bool:
    """Validate bearer token for WebSocket connections.
    
    Check query param ?token=<token> or first message auth.
    """
    expected = _read_token_from_env()
    if not expected:
        return True  # No token configured — auth disabled

    # Check query param
    token = websocket.query_params.get("token")
    if token and token == expected:
        return True

    # Check Authorization header (some WS clients support it)
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.startswith("Bearer ") and auth_header[7:] == expected:
        return True

    return False
