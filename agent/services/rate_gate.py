"""
rate_gate.py — Shared cross-provider rate-limit cooldown
========================================================

Single source of truth for "is provider P allowed to make a call right now?"
Used by:
- agent/services/llm.py — every generate() call records success / 429
- agent/subconscious/loops/base.py — loops skip ticks when their target
  provider is cooling down
- scripts/run_task_worker.py — worker stops the pass on 429

State is held in-memory in this process (loops + worker run in the same
server process). Crash recovery is intentional: cooldowns reset on
restart, which is the correct conservative behavior.

Cooldown formula: exponential backoff with cap.
  cooldown_seconds = min(base * (2 ** consecutive_429s), max_cap)
  base = 60 s, cap = 3600 s (1 h)

Detection is substring-based on the error text because exception classes
differ across providers (anthropic.RateLimitError, google.api_core.…,
openai.RateLimitError, raw urllib HTTPError 429, etc.).
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ── Config ─────────────────────────────────────────────────

_BASE_COOLDOWN = float(os.getenv("AIOS_RATE_GATE_BASE", "60"))   # 1 min
_MAX_COOLDOWN = float(os.getenv("AIOS_RATE_GATE_MAX", "3600"))   # 1 hr
_GLOBAL_COOLDOWN_AFTER_N = int(os.getenv("AIOS_RATE_GATE_GLOBAL_AFTER", "3"))
_GLOBAL_COOLDOWN_SECONDS = float(os.getenv("AIOS_RATE_GATE_GLOBAL_SEC", "300"))  # 5 min

# Markers that indicate a 429 / quota / throttle error.
RATE_LIMIT_MARKERS: Tuple[str, ...] = (
    "rate limit", "rate_limit", "ratelimit",
    "too many requests", "429",
    "quota", "exceeded", "throttl",
    "resource exhausted", "resource_exhausted",
)


def is_rate_limit_error(err: BaseException | str) -> bool:
    """True if the error text contains a rate-limit marker."""
    text = (str(err) if not isinstance(err, str) else err).lower()
    return any(m in text for m in RATE_LIMIT_MARKERS)


# ── State ──────────────────────────────────────────────────

@dataclass
class _ProviderState:
    name: str
    consecutive_429s: int = 0
    cooldown_until: float = 0.0    # epoch seconds
    total_calls: int = 0
    total_429s: int = 0
    total_other_errors: int = 0
    last_call_at: float = 0.0
    last_429_at: float = 0.0
    recent_durations: List[float] = field(default_factory=list)


_lock = threading.RLock()
_providers: Dict[str, _ProviderState] = {}
_global_cooldown_until: float = 0.0
_recent_429_count: int = 0          # rolling count for global trip
_recent_429_window_start: float = 0.0


def _get(provider: str) -> _ProviderState:
    p = _providers.get(provider)
    if p is None:
        p = _ProviderState(name=provider)
        _providers[provider] = p
    return p


# ── Public API ─────────────────────────────────────────────

def should_skip(provider: str) -> Tuple[bool, str]:
    """
    Return (skip, reason). `skip=True` means the caller MUST NOT make the
    call right now. `reason` is a short human-readable string for logs.
    """
    now = time.time()
    with _lock:
        if _global_cooldown_until > now:
            return True, f"global_cooldown:{int(_global_cooldown_until - now)}s"
        p = _get(provider)
        if p.cooldown_until > now:
            return True, f"{provider}_cooldown:{int(p.cooldown_until - now)}s"
        return False, "ok"


def record_success(provider: str, duration_seconds: float = 0.0) -> None:
    """Call after a successful LLM request. Resets that provider's backoff."""
    with _lock:
        p = _get(provider)
        p.consecutive_429s = 0
        p.cooldown_until = 0.0
        p.total_calls += 1
        p.last_call_at = time.time()
        if duration_seconds > 0:
            p.recent_durations.append(duration_seconds)
            if len(p.recent_durations) > 20:
                p.recent_durations.pop(0)


def record_429(provider: str, error_text: str = "") -> float:
    """
    Call after a confirmed rate-limit error. Returns the cooldown
    duration applied to that provider (seconds).
    """
    global _global_cooldown_until, _recent_429_count, _recent_429_window_start
    now = time.time()
    with _lock:
        p = _get(provider)
        p.consecutive_429s += 1
        p.total_429s += 1
        p.total_calls += 1
        p.last_call_at = now
        p.last_429_at = now
        cooldown = min(_BASE_COOLDOWN * (2 ** (p.consecutive_429s - 1)), _MAX_COOLDOWN)
        p.cooldown_until = now + cooldown

        # Global trip: if N+ providers hit 429 in a 60 s window, cool everything
        if now - _recent_429_window_start > 60.0:
            _recent_429_count = 0
            _recent_429_window_start = now
        _recent_429_count += 1
        if _recent_429_count >= _GLOBAL_COOLDOWN_AFTER_N:
            _global_cooldown_until = max(_global_cooldown_until, now + _GLOBAL_COOLDOWN_SECONDS)

        return cooldown


def record_other_error(provider: str) -> None:
    """Call after a non-rate-limit error. Counts toward stats only."""
    with _lock:
        p = _get(provider)
        p.total_other_errors += 1
        p.last_call_at = time.time()


def status() -> Dict[str, object]:
    """Snapshot for STATE / dashboards."""
    now = time.time()
    with _lock:
        out: Dict[str, object] = {
            "global_cooldown_remaining": max(0.0, _global_cooldown_until - now),
            "providers": {},
        }
        for name, p in _providers.items():
            avg_dur = (
                sum(p.recent_durations) / len(p.recent_durations)
                if p.recent_durations else None
            )
            out["providers"][name] = {  # type: ignore[index]
                "consecutive_429s": p.consecutive_429s,
                "cooldown_remaining": max(0.0, p.cooldown_until - now),
                "total_calls": p.total_calls,
                "total_429s": p.total_429s,
                "total_other_errors": p.total_other_errors,
                "last_call_age": now - p.last_call_at if p.last_call_at else None,
                "avg_duration": round(avg_dur, 2) if avg_dur else None,
            }
        return out


def reset(provider: Optional[str] = None) -> None:
    """Clear cooldowns. If `provider` is None, clears everything."""
    global _global_cooldown_until, _recent_429_count
    with _lock:
        if provider is None:
            _providers.clear()
            _global_cooldown_until = 0.0
            _recent_429_count = 0
        elif provider in _providers:
            _providers[provider].cooldown_until = 0.0
            _providers[provider].consecutive_429s = 0
