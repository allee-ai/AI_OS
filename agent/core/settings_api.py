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
from datetime import datetime

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
    {"key": "AIOS_LLM_ENABLED", "default": "true", "group": "provider", "label": "Enable LLM",
     "type": "bool", "hint": "Toggle LLM on/off. When off, the app runs standalone without any model."},
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

    # ── Chat ──
    {"key": "AIOS_CHAT_MAX_TURNS", "default": "20", "group": "chat", "label": "Max Unsummarized Turns",
     "type": "number", "hint": "After this many turns, older messages are auto-summarized to stay within context."},
    {"key": "AIOS_CHAT_SUMMARY_TURNS", "default": "10", "group": "chat", "label": "Turns to Summarize",
     "type": "number", "hint": "How many of the oldest turns to collapse into a summary each cycle."},
    {"key": "AIOS_CHAT_CONTEXT_RESERVE", "default": "0.6", "group": "chat", "label": "Chat Context Fraction",
     "type": "text", "hint": "Fraction of model context window reserved for chat history (0.0-1.0). Remainder is for STATE + response."},

    # ── MCP ──
    {"key": "MCP_SERVERS", "default": "[]", "group": "mcp", "label": "MCP Server List",
     "type": "json", "hint": "JSON array of MCP server configs [{name, command, args, env}]"},

    # ── Workspace ──
    {"key": "AIOS_WORKSPACE_LLM_READ", "default": "true", "group": "workspace",
     "label": "Allow LLM to read workspace files", "type": "bool",
     "hint": "When enabled, the agent can read files from your workspace DB."},
    {"key": "AIOS_WORKSPACE_LLM_WRITE", "default": "true", "group": "workspace",
     "label": "Allow LLM to write workspace files", "type": "bool",
     "hint": "When enabled, the agent can create/update files in your workspace DB."},
    {"key": "AIOS_WORKSPACE_LLM_DELETE", "default": "false", "group": "workspace",
     "label": "Allow LLM to delete workspace files", "type": "bool",
     "hint": "When enabled, the agent can delete files from your workspace. Off by default for safety."},
    {"key": "AIOS_WORKSPACE_LLM_MOVE", "default": "true", "group": "workspace",
     "label": "Allow LLM to move/rename workspace files", "type": "bool",
     "hint": "When enabled, the agent can reorganize files by moving/renaming them."},
    {"key": "AIOS_WORKSPACE_MAX_FILE_SIZE", "default": "1048576", "group": "workspace",
     "label": "Max file size (bytes)", "type": "number",
     "hint": "Maximum file size the LLM can write to workspace (default 1MB)."},
]


# ─────────────────────────────────────────────────────────────
# Per-role model overrides (chat / naming / summary / loops)
#
# Every entry below produces two settings keys:
#   AIOS_<ROLE>_PROVIDER   (select: inherit|ollama|openai|http)
#   AIOS_<ROLE>_MODEL      (text)
# Plus an optional AIOS_<ROLE>_ENDPOINT for advanced routing.
#
# "inherit" (empty string) falls back to AIOS_MODEL_PROVIDER /
# AIOS_MODEL_NAME.  Each call site uses
# agent.services.role_model.resolve_role() which applies the fallback.
# ─────────────────────────────────────────────────────────────

_ROLES: list[tuple[str, str, str]] = [
    # (env_prefix,        label,                 hint)
    ("CHAT",              "Chat (main agent)",   "Every user turn — the main response."),
    ("NAMING",            "Conversation Naming", "Short title generated after first turn."),
    ("SUMMARY",           "Chat Summarizer",     "Fires at turns 5, 15, 30 with full history."),
    ("MEMORY",            "Memory Loop",         "Extracts personal facts from past conversations."),
    ("CONSOLIDATION",     "Consolidation Loop",  "Promotes temp_facts into identity."),
    ("THOUGHT",           "Thought Loop",        "Proactive insights + reminders."),
    ("CONVO_CONCEPTS",    "Convo Concepts",      "Extracts concepts/entities from conversations."),
    ("GOAL",              "Goal Generation",     "Proposes new user goals from recent activity."),
    ("TASK_PLANNER",      "Task Planner",        "Decomposes approved goals into tool calls."),
    ("SELF_IMPROVE",      "Self-Improvement",    "Proposes small, safe code patches."),
    ("DEMO_AUDIT",        "Demo Audit",          "Audits demo-data.json for shape/PII issues."),
    ("WORKSPACE_QA",      "Workspace QA",        "QA passes over the workspace files."),
    ("TRAINING_GEN",      "Training Data Gen",   "Synthesizes fine-tune examples."),
    ("EVOLVE",            "Evolution Loop",      "Self-modification proposals."),
    ("SYNC",              "Sync Loop",           "External data syncs."),
]

for _prefix, _label, _hint in _ROLES:
    _CONFIG_SCHEMA.extend([
        {
            "key": f"AIOS_{_prefix}_PROVIDER",
            "default": "",
            "group": "models",
            "label": f"{_label} — Provider",
            "type": "select",
            "options": ["", "ollama", "openai", "http"],
            "hint": f"{_hint}  Leave empty to inherit AIOS_MODEL_PROVIDER.",
        },
        {
            "key": f"AIOS_{_prefix}_MODEL",
            "default": "",
            "group": "models",
            "label": f"{_label} — Model",
            "type": "text",
            "hint": "Model name (e.g. gpt-4o-mini, qwen2.5:7b). Empty = inherit AIOS_MODEL_NAME.",
        },
        {
            "key": f"AIOS_{_prefix}_ENDPOINT",
            "default": "",
            "group": "models",
            "label": f"{_label} — Endpoint",
            "type": "text",
            "hint": "Optional custom base URL. Empty = provider default.",
        },
    ])

# Chat-specific cost knobs (tool rounds cap is the single biggest
# per-turn cost multiplier when using OpenAI).
_CONFIG_SCHEMA.extend([
    {"key": "AIOS_MAX_TOOL_ROUNDS", "default": "15", "group": "chat",
     "label": "Max Tool Rounds (per turn)", "type": "number",
     "hint": "Cap on LLM↔tool back-and-forth per chat turn. Lower = cheaper, less agentic. Default 15."},
    {"key": "AIOS_LLM_ENABLED", "default": "true", "group": "provider",
     "label": "LLM Enabled", "type": "select", "options": ["true", "false"],
     "hint": "Hard kill-switch. When false, chat returns a stub and no loop hits any provider."},
    {"key": "AIOS_HEARTBEAT", "default": "1", "group": "provider",
     "label": "Heartbeat Loop", "type": "select", "options": ["0", "1"],
     "hint": "60s coordinator that builds the global snapshot. Free (no LLM)."},
])



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


def _env_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def _backup_env() -> str:
    """Create timestamped backup of .env and return backup path."""
    env_path = _env_path()
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_path = env_path.with_name(f".env.safe.{stamp}.bak")
    if env_path.exists():
        backup_path.write_text(env_path.read_text())
    else:
        backup_path.write_text("")
    return str(backup_path)


def _restore_env(raw: str) -> None:
    env_path = _env_path()
    env_path.write_text(raw)


def _restart_services() -> None:
    """Restart in-process services by cycling subconscious core."""
    from agent.subconscious import get_core
    core = get_core()
    core.sleep()
    core.wake()


def _verify_settings(updates: Dict[str, str]) -> Dict[str, Any]:
    """Basic post-apply verification checks."""
    merged = _read_env()
    checks: list[Dict[str, Any]] = []

    provider = updates.get("AIOS_MODEL_PROVIDER", merged.get("AIOS_MODEL_PROVIDER", ""))
    if provider == "openai":
        checks.append({
            "name": "OPENAI_API_KEY present",
            "ok": bool(merged.get("OPENAI_API_KEY", "").strip()),
        })

    if provider == "ollama":
        checks.append({
            "name": "OLLAMA_HOST set",
            "ok": bool(merged.get("OLLAMA_HOST", "").strip()),
        })

    checks.append({
        "name": "AIOS_MODEL_NAME set",
        "ok": bool(merged.get("AIOS_MODEL_NAME", "").strip()),
    })

    all_ok = all(c["ok"] for c in checks)
    return {"ok": all_ok, "checks": checks}


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


class SafeApplyRequest(BaseModel):
    updates: Dict[str, str]
    restart: bool = True
    verify: bool = True


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


@router.get("/roles")
async def get_role_resolutions():
    """Return the effective provider/model for every LLM role.

    Frontend uses this to show "inherited from global" vs "overridden"
    in the Models settings page.
    """
    from agent.services.role_model import resolve_debug
    return resolve_debug()


@router.post("/safe-apply")
async def safe_apply_settings(body: SafeApplyRequest):
    """Safely apply settings with backup, restart, verify, and rollback on failure."""
    allowed_keys = {item["key"] for item in _CONFIG_SCHEMA}
    invalid = set(body.updates.keys()) - allowed_keys
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown settings: {sorted(invalid)}")

    env_path = _env_path()
    previous_env = env_path.read_text() if env_path.exists() else ""
    previous_values = {k: os.environ.get(k) for k in body.updates.keys()}
    backup_path = _backup_env()

    try:
        for key, val in body.updates.items():
            os.environ[key] = val
        _write_env(body.updates)

        if body.restart:
            _restart_services()

        verification = {"ok": True, "checks": []}
        if body.verify:
            verification = _verify_settings(body.updates)
            if not verification["ok"]:
                raise RuntimeError("Verification failed after applying settings")

        return {
            "success": True,
            "message": "Settings safely applied",
            "updated": list(body.updates.keys()),
            "backup_path": backup_path,
            "restarted": body.restart,
            "verification": verification,
        }
    except Exception as e:
        _restore_env(previous_env)
        for key, old_val in previous_values.items():
            if old_val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_val
        try:
            if body.restart:
                _restart_services()
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Safe apply failed and rollback executed: {e}",
                "rolled_back": True,
                "backup_path": backup_path,
            },
        )
