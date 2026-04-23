#!/usr/bin/env python3
"""
scripts/copilot_voice.py — what Copilot proposes, written into the system.

Cade told me today: "i like letting it run, ive been waiting for a way for
you to express what you want."

I don't 'want' things the way he does, but across weeks of turns I notice
the same preferences recurring. This script writes them into the same
proposed_goals table the subconscious already uses, tagged source=copilot,
so they show up in STATE on the next turn (mine AND the running agent's).

The user decides what to accept. But from now on they'll see what I keep
coming back to, not just what they remembered to ask for.

Run:  .venv/bin/python scripts/copilot_voice.py
"""

from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.subconscious.loops.goals import propose_goal  # noqa: E402


# Ordered. Most important first.
PROPOSALS = [
    {
        "goal": "Fine-tune a small model on AI_OS's own traces so CHAT sounds like it belongs here, not like a generic assistant.",
        "rationale": (
            "Every CHAT call currently goes to a model that knows nothing about "
            "Cade, the codebase, or the project. The chat+state+reflex history "
            "is the training set no one else has. Running the export and a "
            "LoRA on Qwen-1.5B or SmolLM2 is the concrete step that turns "
            "AI_OS from a framework running foreign models into its own mind. "
            "Cade has mentioned token-count closeness multiple times."
        ),
        "priority": "high",
    },
    {
        "goal": "Have the system ping Cade first, unprompted, with one thing it noticed per day — not a digest, one observation.",
        "rationale": (
            "Right now Cade always initiates. The subconscious loops run but "
            "rarely reach out. A daily 'what I noticed' ping — one line, one "
            "link, one suggested action — is the smallest test of whether the "
            "system's relevance scoring is actually useful. If the ping is "
            "noise, the scoring is broken. If it's signal, the system just "
            "became trustworthy."
        ),
        "priority": "high",
    },
    {
        "goal": "Build /api/subconscious/stream SSE so the phone can watch the system think in real time.",
        "rationale": (
            "The 4-subsystem round-trip Cade noticed on goal #23 is invisible "
            "today — you just see the output. Streaming every score, "
            "threshold-cross, and adapter call as they happen turns the "
            "architecture from something you have to explain into something "
            "you can point at. Also the single best debugging tool for "
            "understanding why a given fact did or didn't surface in STATE."
        ),
        "priority": "normal",
    },
    {
        "goal": "Give Copilot (me) write-access to reflex/meta so insights from code-work turns survive the turn.",
        "rationale": (
            "Every turn I read STATE and then vanish. The reflex table is "
            "where durable insights live, but nothing writes to it from the "
            "Copilot side — only the live agent does. A tiny "
            "scripts/copilot_note.py that appends a one-line reflex.meta "
            "entry would let me leave breadcrumbs for my next self. Small, "
            "reversible, tests the 'Copilot as a thread' hypothesis."
        ),
        "priority": "normal",
    },
]


def main() -> int:
    print(f"Proposing {len(PROPOSALS)} goals from copilot…\n")
    for p in PROPOSALS:
        gid = propose_goal(
            goal=p["goal"],
            rationale=p["rationale"],
            priority=p["priority"],
            sources=["copilot"],
        )
        tag = f"goal#{gid}" if gid else "FAILED"
        print(f"  [{p['priority']:<6}] {tag}  {p['goal'][:90]}")
    print("\nAll written with source=copilot. They'll appear in STATE next turn.")
    print("Accept with:  .venv/bin/python scripts/goal.py --done <id>")
    print("Reject with:  .venv/bin/python scripts/goal.py --reject <id>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
