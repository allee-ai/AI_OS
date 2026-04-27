"""
Reflex Feelings
===============

Reflex thread's affect namespace — cognitive load and meta-thought pressure.

Tag: <reflex_affect>key=value</reflex_affect>

The reflex thread holds meta-thoughts (rejected/expected/unknown/compression)
and learned patterns. Its affect describes the load of holding those:
how many predictions are pending, how much I feel I'm noticing vs missing,
whether the thinking is converging or churning.
"""

from __future__ import annotations

from agent.services.affect import AffectSchema, register_thread


SCHEMA = AffectSchema(
    thread="reflex",
    tag_name="reflex_affect",
    description="My current meta-cognitive load",
    model_emit=True,
    keys={
        # how heavy the cognitive load feels
        "load":         (("light", "normal", "heavy", "overloaded"),   0.6),
        # convergence of thinking
        "convergence":  (("scattered", "exploring", "narrowing", "settled"), 0.6),
        # how much I trust my own current take
        "self_trust":   (("doubting", "hedged", "confident"),          0.5),
        # how much surprise the recent turn produced
        "surprise":     (("none", "mild", "strong"),                   0.5),
    },
)

register_thread(SCHEMA)


__all__ = ["SCHEMA"]
