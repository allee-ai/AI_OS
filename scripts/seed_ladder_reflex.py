"""Seed two more reflexes from 2026-04-23 conversation.

Adds:
  - Resentment-as-late-boundary-signal
  - Ladder-business thesis (one thesis, three layers)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.threads.reflex.schema import add_meta_thought, init_meta_thoughts_table

init_meta_thoughts_table()

ROWS = [
    (
        "expected",
        "Resentment signal: when Cade feels resentful toward a client/"
        "partner/friend 'for letting me work this hard for them,' that is "
        "her body's late boundary alarm. The resentment is accurate — she "
        "clocked the asymmetry at the quote moment and consented anyway. "
        "Goal: move the signal earlier. When she NOTICES the 'I'd do this "
        "for them' feeling during negotiation, that IS the boundary moment.",
        0.95, 0.95,
    ),
    (
        "expected",
        "Business thesis (2026-04-23): Cade runs one thesis in three layers, "
        "not three businesses. Moving/truck co → feeds construction/"
        "electrician → upward mobility into tech side. Each tier is the "
        "on-ramp out of the one below. It's a career-ladder-as-a-business. "
        "2-year red-to-black rhythm is her funding the elevator with her "
        "own labor until each floor pays rent. This is the hero-complex "
        "firewalled into a structure. Don't describe these as separate.",
        0.9, 0.92,
    ),
]

for kind, content, conf, w in ROWS:
    rid = add_meta_thought(
        kind=kind, content=content, source="copilot",
        confidence=conf, weight=w,
    )
    print(f"  [{'ok' if rid else 'DROP'}] id={rid} :: {content[:70]}...")
