"""
Field Feelings
==============

Field thread's affect namespace — contextual safety and atmosphere.

Tag: <field_affect>key=value</field_affect>

The field thread carries environmental context — where the system is, what
the situation is. Its affect is the system's read of the *atmosphere*:
does the current context feel safe, exposed, intimate, public?
"""

from __future__ import annotations

from agent.services.affect import AffectSchema, register_thread


SCHEMA = AffectSchema(
    thread="field",
    tag_name="field_affect",
    description="The atmosphere of the current context",
    model_emit=True,
    keys={
        # felt safety of the current context
        "safety":     (("threatened", "wary", "neutral", "safe"),  0.6),
        # exposure — how observed the situation feels
        "exposure":   (("public", "visible", "private"),           0.5),
        # intimacy — closeness of the current exchange
        "intimacy":   (("formal", "casual", "intimate"),           0.5),
        # stability — is the ground of the conversation steady
        "stability":  (("shifting", "uneven", "stable"),           0.5),
    },
)

register_thread(SCHEMA)


__all__ = ["SCHEMA"]
