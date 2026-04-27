"""
Model tier routing.

Maps each role to a *tier* (XS/S/M/L/XL) by parameter class. Each tier resolves
to a provider+model via env vars, with sane fallbacks. The point: stop running a
7B model for a job a 1.5B model can do, without making routing a per-call LLM
classification.

Tier sizing rationale:
    XS   ~100-300M   structured tagging, route classification, reflex labels
    S    ~1-3B       extraction, summarization, naming, fact tagging
    M    ~7-8B       chat, planning, synthesis (structured-output floor)
    L    ~32-70B     hard novel reasoning, audit, evolve
    XL   frontier    self-modification of AI_OS itself

Default role → tier mapping reflects what's actually needed:
    REFLEX, FACT                       → XS
    EXTRACT, SUMMARY, NAMING, MEMORY,
    THOUGHT, TRAINING, SYNC            → S
    CHAT, GOAL, PLANNER, TASK_PLANNER,
    CONCEPTS, CONVO_CONCEPTS,
    CONSOLIDATION, WORKSPACE_QA        → M
    EVOLVE, AUDIT, DEMO_AUDIT,
    SELF_IMPROVE                       → L

A role's effective tier and model are resolved in this order:
    1. AIOS_<ROLE>_TIER env override         (force a tier for one role)
    2. route_decisions table (when learning)  -- handled in router.py
    3. ROLE_TIER_DEFAULTS dict (this file)
    4. fallback to "M"

A tier's effective model is resolved in this order:
    1. AIOS_TIER_<TIER>_PROVIDER / _MODEL / _ENDPOINT
    2. AIOS_MODEL_PROVIDER / AIOS_MODEL_NAME (global default)
    3. tier-specific hard-coded defaults
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional


# ── Role → Tier defaults ───────────────────────────────────────────────

ROLE_TIER_DEFAULTS: Dict[str, str] = {
    # Reflex / classification — sub-second, sub-1B
    "REFLEX": "XS",
    "FACT": "XS",

    # Extraction / shaping — small but real
    "EXTRACT": "S",
    "SUMMARY": "S",
    "NAMING": "S",
    "MEMORY": "S",
    "THOUGHT": "S",
    "TRAINING": "S",
    "TRAINING_GEN": "S",
    "SYNC": "S",

    # Chat / planning / synthesis — 7B floor for structured output reliability
    "CHAT": "M",
    "GOAL": "M",
    "PLANNER": "M",
    "TASK_PLANNER": "M",
    "CONCEPTS": "M",
    "CONVO_CONCEPTS": "M",
    "CONSOLIDATION": "M",
    "WORKSPACE_QA": "M",

    # Hard reasoning — 32B+
    "EVOLVE": "L",
    "AUDIT": "L",
    "DEMO_AUDIT": "L",
    "SELF_IMPROVE": "L",
}


# ── Tier → default model fallbacks ─────────────────────────────────────
# Used only when no env override is set.

TIER_HARDCODED_DEFAULTS: Dict[str, Dict[str, str]] = {
    "XS": {"provider": "ollama", "model": "qwen2.5:0.5b"},
    "S":  {"provider": "ollama", "model": "qwen2.5:3b"},
    "M":  {"provider": "ollama", "model": "qwen2.5:7b"},
    "L":  {"provider": "ollama", "model": "qwen2.5:32b"},
    "XL": {"provider": "ollama", "model": "qwen2.5:72b"},
}

VALID_TIERS = ("XS", "S", "M", "L", "XL")


@dataclass(frozen=True)
class TierConfig:
    tier: str
    provider: str
    model: str
    endpoint: str


def tier_for_role(role: str) -> str:
    """Return the tier that should serve *role*.

    Lookup order:
        1. AIOS_<ROLE>_TIER env override
        2. ROLE_TIER_DEFAULTS dict
        3. "M" (safe middle)
    """
    r = (role or "").upper().strip()
    if r:
        forced = os.getenv(f"AIOS_{r}_TIER", "").strip().upper()
        if forced in VALID_TIERS:
            return forced
    return ROLE_TIER_DEFAULTS.get(r, "M")


def resolve_tier(tier: str) -> TierConfig:
    """Return the effective (provider, model, endpoint) for a tier label."""
    t = (tier or "M").upper()
    if t not in VALID_TIERS:
        t = "M"

    # Env override per tier
    provider = os.getenv(f"AIOS_TIER_{t}_PROVIDER", "").strip().lower()
    model    = os.getenv(f"AIOS_TIER_{t}_MODEL", "").strip()
    endpoint = os.getenv(f"AIOS_TIER_{t}_ENDPOINT", "").strip()

    # Fallback to global defaults
    if not provider:
        provider = os.getenv("AIOS_MODEL_PROVIDER", "").strip().lower()
    if not model:
        model = os.getenv("AIOS_MODEL_NAME", "").strip()

    # Final fallback to hard-coded tier defaults
    hard = TIER_HARDCODED_DEFAULTS[t]
    if not provider:
        provider = hard["provider"]
    if not model:
        model = hard["model"]

    return TierConfig(tier=t, provider=provider, model=model, endpoint=endpoint)


def resolve_role_to_tier(role: str) -> TierConfig:
    """Convenience: role → TierConfig (combining tier_for_role + resolve_tier)."""
    return resolve_tier(tier_for_role(role))


def tier_summary() -> dict:
    """Diagnostic: show current tier resolution for every default role."""
    by_tier: Dict[str, list] = {t: [] for t in VALID_TIERS}
    for role, tier in ROLE_TIER_DEFAULTS.items():
        forced = os.getenv(f"AIOS_{role}_TIER", "").strip().upper()
        effective = forced if forced in VALID_TIERS else tier
        by_tier.setdefault(effective, []).append({
            "role": role,
            "default_tier": tier,
            "forced": forced if forced else None,
        })
    out = {}
    for t in VALID_TIERS:
        cfg = resolve_tier(t)
        out[t] = {
            "provider": cfg.provider,
            "model": cfg.model,
            "endpoint": cfg.endpoint or None,
            "roles": by_tier.get(t, []),
        }
    return out


__all__ = [
    "ROLE_TIER_DEFAULTS",
    "TIER_HARDCODED_DEFAULTS",
    "VALID_TIERS",
    "TierConfig",
    "tier_for_role",
    "resolve_tier",
    "resolve_role_to_tier",
    "tier_summary",
]
