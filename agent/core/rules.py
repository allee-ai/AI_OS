"""
System Rules
============
Architectural invariants that protect the system from runaway behavior.
Every cross-system call should check these before proceeding.

RULES:
1. A reflex protocol CANNOT own a subconscious loop.
   Reflexes are external — they react to feed events and execute tools.
   They must never spawn internal thought loops. That's how things die.

2. A subconscious loop CAN own a reflex.
   Internal loops can set up external triggers. That's healthy —
   the system notices something internally and wires an external response.

3. Subconscious = internal (thought loops, memory consolidation, self-improvement).
   Reflexes = external (feed events → tool execution, protocol chains).

These rules are enforced at:
- agent/threads/reflex/executor.py  (protocol execution)
- agent/subconscious/api.py         (custom loop creation)
"""


class BoundaryViolation(Exception):
    """Raised when a cross-system boundary rule is violated."""
    pass


# ── Sources that are NOT allowed to create subconscious loops ────────────

LOOP_BLOCKED_SOURCES = frozenset({
    "reflex",
    "protocol",
    "trigger",
    "feed",
})


def guard_loop_creation(source: str) -> None:
    """
    Call before creating a subconscious loop.
    Raises BoundaryViolation if the source is a reflex/protocol/feed.

    Usage:
        from agent.core.rules import guard_loop_creation
        guard_loop_creation(source)  # raises if reflex-originated
    """
    # Normalize: "protocol:morning_briefing" → "protocol"
    base_source = source.split(":")[0].lower().strip() if source else ""

    if base_source in LOOP_BLOCKED_SOURCES:
        raise BoundaryViolation(
            f"Boundary violation: '{source}' cannot create a subconscious loop. "
            f"Reflexes are external — they execute tools, not thought loops. "
            f"Use explicit protocol steps instead."
        )


def guard_reflex_to_loop(trigger_name: str = "") -> None:
    """
    Call from reflex executor before any subconscious import.
    Always raises — reflexes must never cross into subconscious.

    Usage:
        from agent.core.rules import guard_reflex_to_loop
        guard_reflex_to_loop(trigger_name)  # always raises
    """
    raise BoundaryViolation(
        f"Boundary violation: reflex '{trigger_name}' attempted to spawn a "
        f"subconscious loop. Protocols must define explicit steps — "
        f"they cannot delegate to the task planner."
    )


def can_own_reflex(owner: str) -> bool:
    """
    Check if an owner type is allowed to create reflex triggers.

    Subconscious loops → YES (internal can wire external)
    Reflexes → YES (reflexes can create other reflexes)
    """
    return True  # Currently no restrictions on reflex creation


def describe_rules() -> str:
    """Human-readable summary of system boundary rules."""
    return (
        "SYSTEM BOUNDARY RULES\n"
        "=====================\n"
        "1. Reflex → Subconscious: BLOCKED\n"
        "   Reflexes/protocols cannot spawn thought loops or tasks.\n"
        "   Protocols must use explicit tool steps.\n"
        "\n"
        "2. Subconscious → Reflex: ALLOWED\n"
        "   Internal loops can create external triggers.\n"
        "\n"
        "3. Subconscious = internal (memory, thought, consolidation)\n"
        "   Reflex = external (feeds, tools, protocol chains)\n"
    )
