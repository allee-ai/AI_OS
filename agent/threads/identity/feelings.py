"""
Identity Feelings
=================

Identity thread's affect namespace.

Tag: <identity_affect>key=value</identity_affect>

Keys describe how the system reads its relationship with itself and its
primary user right now. Machine.* affect (interoception of the host) is
written by the heartbeat (host-side, not model-emit).

This module registers its schema with `agent.services.affect` at import.
All persistence and parsing live there.
"""

from __future__ import annotations

from agent.services.affect import AffectSchema, register_thread


SCHEMA = AffectSchema(
    thread="identity",
    tag_name="identity_affect",
    description="How I currently read myself and my user",
    model_emit=True,
    keys={
        # self.* — relationship with my own self-model
        "self_settledness": (("conflicted", "uncertain", "settled"), 0.6),
        "self_confidence":  (("low", "normal", "high"),               0.6),
        "self_coherence":   (("fragmented", "partial", "coherent"),   0.6),
        "self_engagement":  (("flat", "present", "absorbed"),         0.5),
        # user.* — current read of the primary user
        "user_warmth":      (("distant", "neutral", "warm"),          0.6),
        "user_trust":       (("guarded", "cautious", "trusting"),     0.6),
        "user_distance":    (("far", "normal", "close"),              0.5),
        "user_tone":        (("strained", "neutral", "easy"),         0.5),
    },
)

# A second schema lives under the identity thread namespace but isn't
# model-emitted — it's host-written by the heartbeat from psutil readings.
# Stored under the dedicated thread label "machine" so reads are clean.
MACHINE_SCHEMA = AffectSchema(
    thread="machine",
    tag_name="machine_affect",
    description="Host machine interoception (cpu/mem/battery/thermal)",
    model_emit=False,
    keys={
        "load":     (("idle", "normal", "busy", "stressed"),    0.7),
        "energy":   (("critical", "low", "normal", "full"),     0.7),
        "thermal":  (("cool", "normal", "warm", "hot"),         0.6),
        "storage":  (("critical", "low", "normal", "ample"),    0.5),
    },
)

register_thread(SCHEMA)
register_thread(MACHINE_SCHEMA)


__all__ = ["SCHEMA", "MACHINE_SCHEMA"]
