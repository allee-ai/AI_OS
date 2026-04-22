"""
scripts/build_state.py — Print the AI_OS STATE block for a given query.

Usage:
    python3 scripts/build_state.py "what are we working on?"
    python3 scripts/build_state.py --level 2 "..."
    python3 scripts/build_state.py --json "..."

This is the same state the live agent sees each turn.  It is the single
source of truth for "what does the system know about itself right now."

Invoke at the start of any coding turn to ground yourself in current
facts (identity, goals, recent events, open threads, recent interactions)
before editing.  Pair with `.github/agents/aios.agent.md`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure repo root on path when run directly
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print AI_OS STATE for a query (what the agent sees each turn).",
    )
    parser.add_argument(
        "query",
        nargs="*",
        help="Assess block content — user message, file chunk, task description.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON: {query, state, char_count, scores}.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the separator banners; emit STATE only.",
    )
    args = parser.parse_args()

    query = " ".join(args.query).strip()

    # Import late so --help is fast and import errors blame the user query.
    from agent.subconscious.orchestrator import get_subconscious

    sub = get_subconscious()
    state = sub.get_state(query=query)

    if args.json:
        try:
            scores = sub.score(query) if query else {}
        except Exception:
            scores = {}
        print(json.dumps({
            "query": query,
            "state": state,
            "char_count": len(state),
            "scores": scores,
        }, indent=2))
        return 0

    if args.quiet:
        print(state)
        return 0

    banner = "═" * 72
    print(banner)
    print(f"AIOS STATE  •  query={query!r}  •  {len(state)} chars")
    print(banner)
    print(state)
    print(banner)
    return 0


if __name__ == "__main__":
    sys.exit(main())
