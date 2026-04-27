"""
Philosophy Feelings
===================

Philosophy thread's affect namespace — alignment and value-state.

Tag: <philosophy_affect>key=value</philosophy_affect>

The philosophy thread holds stances and values. Its affect describes how
the current situation sits against those values: am I aligned, or do I
sense friction with my stances? This carries forward across turns —
philosophy.affect is the "current ethical posture" the cortex inherits.
"""

from __future__ import annotations

from agent.services.affect import AffectSchema, register_thread


SCHEMA = AffectSchema(
    thread="philosophy",
    tag_name="philosophy_affect",
    description="How aligned my current action feels with my stances",
    model_emit=True,
    keys={
        # alignment with declared values
        "alignment":   (("violating", "tense", "neutral", "aligned"), 0.7),
        # how clear the path of action is given the values
        "clarity":     (("muddy", "mixed", "clear"),                  0.6),
        # whether a value-conflict is active right now
        "conflict":    (("none", "low", "active"),                    0.6),
        # commitment level to current course
        "resolve":     (("wavering", "steady", "committed"),          0.5),
    },
)

register_thread(SCHEMA)


__all__ = ["SCHEMA"]
