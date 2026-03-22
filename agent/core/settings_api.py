"""
Settings API - Unified Configuration Endpoint
==============================================
Read/write ALL configurable env vars through a single API.
Covers: server, provider, model, kernel, MCP, CORS, and more.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pathlib import Path
import os

router = APIRouter(prefix="/api/settings", tags=["settings"])

# All known configuration keys with defaults and descriptions
_CONFIG_SCHEMA: list[dict] = [
    # ── Server ──
    {"key": "HOST", "default": "0.0.0.0", "group": "server", "label": "Server Host", "type": "text",
     "hint": "Bind address (0.0.0.0 = all interfaces, 127.0.0.1 = local only)"},
    {"key": "BACKEND_PORT", "default": "8000", "group": "server", "label": "Backend Port", "type": "number",
     "hint": "Port the API server listens on"},
    {"key": "FRONTEND_PORT", "default": "5173", "group": "server", "label": "Frontend Port", "type": "number",
     "hint": "Port the dev frontend runs on (Vite)"},
    {"key": "CORS_ORIGINS", "default": "http://localhost:5173,http://127.0.0.1:5173", "group": "server",
     "label": "CORS Origins", "type": "text",
     "hint": "Comma-separated allowed origins for cross-origin requests"},
    {"key": "AIOS_BASE_URL", "default": "http://localhost:8000", "group": "server",
     "label": "Public Base URL", "type": "text",
     "hint": "The externally-reachable URL of the backend (used for OAuth callbacks, etc.)"},

    # ── Provider / Model ──
    {"key": "AIOS_MODEL_PROVIDER", "default": "ollama", "group": "provider", "label": "LLM Provider",
     "type": "select", "options": ["ollama", "openai", "http", "mock"],
     "hint": "Which LLM backend to use"},
    {"key": "AIOS_MODEL_NAME", "default": "qwen2.5:7b", "group": "provider", "label": "Model Name",
     "type": "text", "hint": "Model tag (e.g. qwen2.5:7b, gpt-4o-mini)"},
    {"key": "AIOS_MODEL_ENDPOINT", "default": "", "group": "provider", "label": "Custom Endpoint",
     "type": "text", "hint": "Full URL for http provider or custom OpenAI-compatible base"},
    {"key": "OPENAI_API_KEY", "default": "", "group": "provider", "label": "OpenAI API Key",
     "type": "password", "hint": "sk-... key for OpenAI or compatible API"},
    {"key": "OLLAMA_HOST", "default": "http://localhost:11434", "group": "provider",
     "label": "Ollama Host", "type": "text",
     "hint": "Ollama server address (if not default localhost)"},

    # ── Extract / Subconscious overrides ──
    {"key": "AIOS_EXTRACT_MODEL", "default": "", "group": "provider",
     "label": "Extraction Model Override", "type": "text",
     "hint": "Separate model for concept extraction (leave empty to use main model)"},
    {"key": "AIOS_EXTRACT_PROVIDER", "default": "", "group": "provider",
     "label": "Extraction Provider Override", "type": "text",
     "hint": "Separate provider for extraction (leave empty to use main provider)"},

    # ── Kernel ──
    {"key": "KERNEL_API_KEY", "default": "", "group": "kernel", "label": "Kernel API Key",
     "type": "password", "hint": "API key from https://app.onkernel.com"},
    {"key": "KERNEL_PROFILE_NAME", "default": "agent_identity", "group": "kernel",
     "label": "Browser Profile Name", "type": "text", "hint": "Persistent browser profile name"},
    {"key": "KERNEL_HEADLESS", "default": "false", "group": "kernel",
     "label": "Headless Mode", "type": "bool", "hint": "Run browser without GUI"},
    {"key": "KERNEL_STEALTH", "default": "true", "group": "kernel",
     "label": "Stealth Mode", "type": "bool", "hint": "Enable bot-detection avoidance"},
    {"key": "KERNEL_TIMEOUT", "default": "3600", "group": "kernel",
     "label": "Session Timeout (s)", "type": "number", "hint": "Browser session timeout in seconds"},

    # ── MCP ──
    {"key": "MCP_SERVERS", "default": "[]", "group": "mcp", "label": "MCP Server List",
     "type": "json", "hint": "JSON array of MCP server configs [{name, command, args, env}]"},
]


def _read_env() -> Dict[str, str]:
    """Read the project .env file into a dict."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    result: Dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, val = stripped.split("=", 1)
                result[key.strip()] = val.strip()
    return result


def _write_env(updates: Dict[str, str]):
    """Write/update key=value pairs in the project .env file."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()

    existing_keys: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                existing_keys.add(key)
                continue
        new_lines.append(line)

    for key, val in updates.items():
        if key not in existing_keys:
            new_lines.append(f"{key}={val}")

    env_path.write_text("\n".join(new_lines) + "\n")


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("")
async def get_all_settings():
    """Return all configurable settings with current values."""
    env_file = _read_env()
    groups: Dict[str, list] = {}
    for item in _CONFIG_SCHEMA:
        key = item["key"]
        # Current value: env var (runtime) > .env file > default
        current = os.environ.get(key, env_file.get(key, item["default"]))
        # Mask secrets
        display = current
        if item["type"] == "password" and current:
            display = current[:4] + "•" * max(0, len(current) - 8) + current[-4:] if len(current) > 8 else "••••"
        # Never return raw secret values — only whether they're set
        if item["type"] == "password":
            entry = {**item, "value": "" if not current else "••••••••", "display": display, "is_set": bool(current)}
        else:
            entry = {**item, "value": current, "display": display}
        groups.setdefault(item["group"], []).append(entry)
    return {"groups": groups}


class SettingsUpdate(BaseModel):
    updates: Dict[str, str]


@router.put("")
async def update_settings(body: SettingsUpdate):
    """Update one or more settings. Writes to .env and sets runtime env vars."""
    allowed_keys = {item["key"] for item in _CONFIG_SCHEMA}
    invalid = set(body.updates.keys()) - allowed_keys
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown settings: {sorted(invalid)}")

    # Apply to running process
    for key, val in body.updates.items():
        os.environ[key] = val

    # Persist to .env
    _write_env(body.updates)

    return {"success": True, "updated": list(body.updates.keys())}


@router.get("/schema")
async def get_settings_schema():
    """Return the configuration schema (for dynamic form rendering)."""
    return {"schema": _CONFIG_SCHEMA}
