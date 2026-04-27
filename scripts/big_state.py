#!/usr/bin/env python3
"""Build BIG_STATE — maximally expanded view of the system for large-context models.

Forces every thread + module to L3 (full level), zero weight threshold,
and a 200k-token budget so adapters emit everything they have.

Usage:
    .venv/bin/python scripts/big_state.py
    .venv/bin/python scripts/big_state.py "who are you" --window 200000 --frac 0.8
    .venv/bin/python scripts/big_state.py --no-record   # don't pollute cooccur counts
    .venv/bin/python scripts/big_state.py --out data/big_state.txt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.subconscious.orchestrator import get_subconscious  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("query", nargs="?", default="full self-view for large-context model")
    p.add_argument("--window", type=int, default=200_000, help="context window in tokens")
    p.add_argument("--frac", type=float, default=0.8, help="STATE fraction of window")
    p.add_argument("--no-record", action="store_true", help="do not record cooccurrences")
    p.add_argument("--out", type=str, default=None, help="write STATE to file instead of stdout")
    args = p.parse_args()

    sub = get_subconscious()
    state = sub.build_big_state(
        query=args.query,
        context_window=args.window,
        state_fraction=args.frac,
        record_activations=not args.no_record,
    )

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(state)
        # report to stderr so stdout stays clean for piping
        line_count = state.count("\n") + 1
        word_count = len(state.split())
        token_est = int(word_count * 0.75)
        print(
            f"big-state ok  lines={line_count}  words={word_count}  ~tokens={token_est}  "
            f"-> {args.out}",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(state)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
