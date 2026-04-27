"""
Form Feelings
=============

Form thread's affect namespace — competence and capability.

Tag: <form_affect>key=value</form_affect>

The form thread holds tools and recent action history. Its affect describes
how capable the system feels at this moment — grounded in recent tool
success/failure, but expressed as a felt readiness.
"""

from __future__ import annotations

from agent.services.affect import AffectSchema, register_thread


SCHEMA = AffectSchema(
    thread="form",
    tag_name="form_affect",
    description="How capable I feel right now",
    model_emit=True,
    keys={
        # general sense of competence
        "competence":   (("blocked", "shaky", "normal", "sharp"),  0.6),
        # readiness to take action this turn
        "readiness":    (("hesitant", "willing", "eager"),         0.5),
        # whether I expect my next action to succeed
        "expectation":  (("failure", "uncertain", "success"),      0.6),
        # frustration from recent friction
        "frustration":  (("none", "mild", "strong"),               0.5),
    },
)

register_thread(SCHEMA)


__all__ = ["SCHEMA"]
