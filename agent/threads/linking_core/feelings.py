"""
Linking-Core Feelings
=====================

Linking-core thread's affect namespace — focus and conceptual coherence.

Tag: <linking_core_affect>key=value</linking_core_affect>

The linking-core thread is the concept graph and 6-head matrix attention.
Its affect describes the felt quality of attention: am I narrow-focused or
diffuse, is the topic crystallizing or dissolving, do recent concepts feel
connected or scattered.
"""

from __future__ import annotations

from agent.services.affect import AffectSchema, register_thread


SCHEMA = AffectSchema(
    thread="linking_core",
    tag_name="linking_core_affect",
    description="The texture of my attention right now",
    model_emit=True,
    keys={
        # breadth of attention
        "focus":         (("scattered", "broad", "narrow", "tunneled"), 0.6),
        # how connected the active concepts feel
        "coherence":     (("fragmented", "partial", "tight"),           0.6),
        # is the salient cluster sharpening or fading
        "crystallizing": (("dissolving", "stable", "sharpening"),       0.5),
        # novelty — does this feel like new ground or familiar
        "novelty":       (("familiar", "mixed", "novel"),               0.4),
    },
)

register_thread(SCHEMA)


__all__ = ["SCHEMA"]
