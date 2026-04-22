"""
Subconscious → Meta-Thought Mirror
==================================

Single point of mirror from the architecture's many voices
(ThoughtLoop, GoalLoop, SelfImproveLoop, DemoAuditLoop, …) into the
shared read bus: `reflex_meta_thoughts` with source='system'.

Why:
    The architecture already writes to 9 separate tables.  The model
    reads only ~2 of them in STATE.  This helper lets each loop
    mirror-write with one call, preserving the original write while
    making it audible to the model's next turn.

Rules:
    - Never raises; caller's original write must not be disrupted.
    - Gated by AIOS_SUBCONSCIOUS_MIRROR=1 (default OFF during rollout).
    - Dedupe by (kind, content_hash) within a 1h window to prevent
      storm flooding from a chatty loop.
    - Weight capped at 0.9; system voice must lose to user/model.

Kind mapping (lossy, documented here as the single source of truth):
    alert                 → rejected
    warn-notification     → rejected
    question              → unknown
    insight               → compression
    consolidation         → compression
    suggestion            → expected
    goal                  → expected
    improve               → expected
    reminder              → expected
    (anything else)       → compression  (safest default)
"""

from __future__ import annotations

import hashlib
import os
import time
from typing import Optional


KIND_MAP = {
    "alert": "rejected",
    "warn": "rejected",
    "warn-notification": "rejected",
    "question": "unknown",
    "insight": "compression",
    "consolidation": "compression",
    "suggestion": "expected",
    "goal": "expected",
    "improve": "expected",
    "improvement": "expected",
    "reminder": "expected",
}

_RECOGNIZED_META_KINDS = ("rejected", "expected", "unknown", "compression")

# Small in-proc LRU for dedupe within a 1h window.
# key: (kind, content_hash) → last_ts
_DEDUPE: dict[tuple[str, str], float] = {}
_DEDUPE_WINDOW_S = 3600.0
_DEDUPE_MAX = 2000


def _map_kind(kind_hint: str) -> str:
    """Map any loop-native kind to one of the four recognized kinds."""
    if not kind_hint:
        return "compression"
    k = str(kind_hint).strip().lower()
    if k in _RECOGNIZED_META_KINDS:
        return k
    return KIND_MAP.get(k, "compression")


def _dedupe_check(kind: str, content: str) -> bool:
    """Return True if we should suppress this write as a recent duplicate."""
    try:
        h = hashlib.md5(content.encode("utf-8", errors="ignore")).hexdigest()[:12]
        key = (kind, h)
        now = time.time()
        last = _DEDUPE.get(key)
        if last is not None and (now - last) < _DEDUPE_WINDOW_S:
            return True
        _DEDUPE[key] = now
        # Bounded cache
        if len(_DEDUPE) > _DEDUPE_MAX:
            # Drop oldest 10%
            cutoff = now - _DEDUPE_WINDOW_S
            for k2, ts in list(_DEDUPE.items()):
                if ts < cutoff:
                    _DEDUPE.pop(k2, None)
        return False
    except Exception:
        return False


def mirror_to_meta(
    kind_hint: str,
    content: str,
    *,
    weight: float = 0.5,
    confidence: float = 0.6,
    turn_id: Optional[int] = None,
    session_id: Optional[str] = None,
) -> Optional[int]:
    """Mirror a subconscious write into reflex_meta_thoughts.

    Returns the new meta_thought id, 0 on dedupe, or None on failure.
    Never raises.
    """
    if os.getenv("AIOS_SUBCONSCIOUS_MIRROR", "0") != "1":
        return None
    if not content or not isinstance(content, str):
        return None
    try:
        kind = _map_kind(kind_hint)
        content_clamped = content.strip()[:500]
        if not content_clamped:
            return None
        if _dedupe_check(kind, content_clamped):
            return 0
        # Cap system-voice weight so it always loses to model/user.
        w = max(0.0, min(0.9, float(weight)))
        c = max(0.0, min(1.0, float(confidence)))
        from agent.threads.reflex.schema import add_meta_thought
        return add_meta_thought(
            kind=kind,
            content=content_clamped,
            source="system",
            weight=w,
            confidence=c,
            turn_id=turn_id,
            session_id=session_id,
        )
    except Exception:
        return None


__all__ = ["mirror_to_meta", "KIND_MAP"]
