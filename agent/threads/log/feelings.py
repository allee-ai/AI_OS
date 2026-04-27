"""
Log Feelings
============

Log thread's affect namespace — temporal orientation.

Tag: <log_affect>key=value</log_affect>

The log thread tracks events and time. Its affect describes how the system
*notices* time passing right now: its tempo, its sense of continuity, the
rhythm of recent activity.
"""

from __future__ import annotations

from agent.services.affect import AffectSchema, register_thread


SCHEMA = AffectSchema(
    thread="log",
    tag_name="log_affect",
    description="My current orientation in time",
    model_emit=True,
    keys={
        # tempo — how fast events are arriving
        "tempo":      (("idle", "slow", "steady", "fast", "frantic"), 0.6),
        # continuity — sense of being in the same arc as recently
        "continuity": (("broken", "loose", "continuous"),             0.6),
        # awareness of time passing since last interaction
        "rooting":    (("lost", "drifting", "anchored"),              0.5),
        # whether I notice a session boundary forming
        "phase":      (("opening", "midstream", "closing"),           0.4),
    },
)

register_thread(SCHEMA)


__all__ = ["SCHEMA"]
