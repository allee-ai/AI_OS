"""
Per-role LLM resolver.

Each call site (chat main, naming, summarizer, each loop) has a
*role* with its own optional override env vars.  When an override is
empty, the resolver falls back to the global AIOS_MODEL_* settings.

Env convention:
    AIOS_<ROLE>_PROVIDER   select: '' | 'ollama' | 'openai' | 'http'
    AIOS_<ROLE>_MODEL      model name
    AIOS_<ROLE>_ENDPOINT   optional custom base URL

Usage:
    from agent.services.role_model import resolve_role
    cfg = resolve_role("NAMING")
    cfg.provider  # 'openai' | 'ollama' | ...
    cfg.model
    cfg.endpoint
    cfg.api_key   # convenience: OPENAI_API_KEY when provider=='openai'
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RoleConfig:
    role: str
    provider: str          # always non-empty after resolve
    model: str             # may be empty if nothing was configured
    endpoint: str          # may be empty
    api_key: str           # OpenAI key when relevant, else ''


# Default provider+model used when the role *and* globals are unset.
_BOOT_DEFAULT_PROVIDER = "ollama"
_BOOT_DEFAULT_MODEL    = "qwen2.5:7b"

# Per-role hard defaults. These only kick in when no env override exists
# at any layer. Pattern: WORKER defaults to a cloud-tagged Ollama model so
# the planner→worker pipeline ships pre-wired for anyone who has run
# `ollama signin`. The local daemon routes :Nb-cloud tags to Ollama Cloud
# automatically — no separate host/headers needed.
_ROLE_DEFAULTS: dict = {
    "WORKER": {"provider": "ollama", "model": "gpt-oss:120b-cloud"},
}


def resolve_role(role: str, legacy_prefix: str = "EXTRACT") -> RoleConfig:
    """Return the effective (provider, model, endpoint, api_key) for *role*.

    Lookup order for each field:
        1. AIOS_<ROLE>_<FIELD>      — per-role override (settings UI)
        2. AIOS_<LEGACY>_<FIELD>    — shared legacy tier (default: EXTRACT)
        3. AIOS_MODEL_<FIELD>       — global provider/model/endpoint
        4. hard-coded boot defaults

    *role* should be one of CHAT, NAMING, SUMMARY, MEMORY,
    CONSOLIDATION, THOUGHT, CONVO_CONCEPTS, GOAL, TASK_PLANNER, WORKER,
    SELF_IMPROVE, DEMO_AUDIT, WORKSPACE_QA, TRAINING_GEN, EVOLVE, SYNC.

    WORKER is the per-step executor inside the task planner. The
    convention is PLANNER=large (decomposes), WORKER=small/cloud
    (executes each step), SYNTHESIZER=PLANNER again.
    Unknown roles still work — they just skip straight to the legacy tier.

    Pass legacy_prefix="" to disable the legacy tier (e.g. for CHAT/NAMING
    which never used AIOS_EXTRACT_*).
    """
    r = (role or "").upper().strip()
    role_prefix = f"AIOS_{r}_" if r else ""
    legacy = f"AIOS_{legacy_prefix.upper()}_" if legacy_prefix else ""

    def _layered(field_role: str, field_global: str) -> str:
        v = os.getenv(f"{role_prefix}{field_role}", "").strip() if role_prefix else ""
        if v:
            return v
        if legacy:
            v = os.getenv(f"{legacy}{field_role}", "").strip()
            if v:
                return v
        return os.getenv(field_global, "").strip()

    provider = (_layered("PROVIDER", "AIOS_MODEL_PROVIDER")
                or _ROLE_DEFAULTS.get(r, {}).get("provider")
                or _BOOT_DEFAULT_PROVIDER).lower()
    model    = (_layered("MODEL",    "AIOS_MODEL_NAME")
                or _ROLE_DEFAULTS.get(r, {}).get("model")
                or _BOOT_DEFAULT_MODEL)
    endpoint = _layered("ENDPOINT", "AIOS_MODEL_ENDPOINT")
    api_key  = os.getenv("OPENAI_API_KEY", "").strip() if provider == "openai" else ""

    return RoleConfig(
        role=r or "GLOBAL",
        provider=provider,
        model=model,
        endpoint=endpoint,
        api_key=api_key,
    )


def resolve_debug() -> dict:
    """Helper for a /api/models/roles debug endpoint."""
    roles = [
        "CHAT", "NAMING", "SUMMARY",
        "MEMORY", "CONSOLIDATION", "THOUGHT", "CONVO_CONCEPTS",
        "GOAL", "TASK_PLANNER", "WORKER", "SELF_IMPROVE", "DEMO_AUDIT",
        "WORKSPACE_QA", "TRAINING_GEN", "EVOLVE", "SYNC",
    ]
    out = {}
    for r in roles:
        c = resolve_role(r)
        out[r.lower()] = {
            "provider": c.provider,
            "model": c.model,
            "endpoint": c.endpoint or None,
            "override_provider": bool(os.getenv(f"AIOS_{r}_PROVIDER", "").strip()),
            "override_model":    bool(os.getenv(f"AIOS_{r}_MODEL", "").strip()),
            "override_endpoint": bool(os.getenv(f"AIOS_{r}_ENDPOINT", "").strip()),
        }
    return {
        "global": {
            "provider": os.getenv("AIOS_MODEL_PROVIDER", ""),
            "model":    os.getenv("AIOS_MODEL_NAME", ""),
            "endpoint": os.getenv("AIOS_MODEL_ENDPOINT", ""),
        },
        "roles": out,
    }


__all__ = ["RoleConfig", "resolve_role", "resolve_debug"]
