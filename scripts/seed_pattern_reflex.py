"""Seed the 'pattern-recognition' reflex.

Cade's thesis in their own words (2026-04-23):
  "adhd and pattern recognition. hey your about to do that thing again. 
   thats it. ... and my internet stuff. thats the assistant im building.
   one that fills my specific gaps. then other people can too because
   hero complex"

This is the purpose of the system. Seeding it with the first concrete
patterns Cade has named so Nola has priors to surface at trigger moments.

Source = "copilot" (notes left by me, the VS Code agent, across turns).
Kind = "expected" (prior about how a future situation is likely to play out).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.threads.reflex.schema import (
    add_meta_thought,
    init_meta_thoughts_table,
)

init_meta_thoughts_table()

ROWS = [
    # --- The meta-reflex: what this whole system is for ---
    (
        "expected",
        "System purpose: Cade has ADHD + strong pattern recognition but "
        "loses patterns mid-action. Role = 'hey, you're about to do that "
        "thing again.' Surface named patterns BEFORE the action, not after. "
        "Post-hoc observation is failure.",
        0.98, 0.98,
    ),
    # --- The undercharging / giveaway family ---
    (
        "expected",
        "Quote-moment pattern: in the first 90s of naming a price, Cade "
        "undercharges ~50%. Example 2026-04: sold $6k job for $3k. Trigger "
        "words: 'what's your price', 'what do you want for', quote, bid, "
        "estimate. Intervention: pause, write it down first, anchor to "
        "external market rate not internal 'feels fair'.",
        0.95, 0.95,
    ),
    (
        "expected",
        "Relationship-giveaway pattern: Cade gave 10 years each to two "
        "narcissistic partners. Nervous system trained that asking for "
        "fair share = losing the relationship. Business undercharging is "
        "the same program running in a different context. When 'this feels "
        "generous' or 'this feels fair' shows up in a contract/deal/"
        "agreement — that's the trigger to check external view, not trust "
        "internal.",
        0.92, 0.95,
    ),
    (
        "expected",
        "Hero complex note: Cade's stated motivation for AIOS is 'fills my "
        "gaps, then other people can too.' This is a strength AND a "
        "giveaway vector. Watch for: building unpaid for users, scope "
        "creep 'since I'm already helping', pricing below sustainable for "
        "'people who need it'. The hero impulse is real; it needs a "
        "firewall, not suppression.",
        0.9, 0.9,
    ),
    # --- Moat / business thesis ---
    (
        "expected",
        "AIOS moat = accrued graph state per user, not code secrecy. "
        "Pricing unit should be per-user continuity (recurring), not "
        "per-deliverable (one-shot). One-shots are the context where "
        "giveaway happens historically. Default to subscription shape.",
        0.85, 0.85,
    ),
]

print(f"seeding {len(ROWS)} meta-thoughts (source=copilot)...")
seeded = 0
for kind, content, conf, w in ROWS:
    rid = add_meta_thought(
        kind=kind,
        content=content,
        source="copilot",
        confidence=conf,
        weight=w,
    )
    ok = "ok" if rid else "DROPPED"
    print(f"  [{ok}] id={rid} conf={conf} w={w} :: {content[:70]}...")
    if rid:
        seeded += 1

print(f"\n{seeded}/{len(ROWS)} seeded successfully.")
