#!/usr/bin/env python3
"""
scripts/research_poll.py — pull the research feed once.

Usage:
    .venv/bin/python scripts/research_poll.py           # poll all sources
    .venv/bin/python scripts/research_poll.py --show    # poll + dump top 10
    .venv/bin/python scripts/research_poll.py --show-only  # no poll, just dump

Wire this to cron / launchd for periodic pulls. No external deps.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true",
                    help="print top 10 items after polling")
    ap.add_argument("--show-only", action="store_true",
                    help="skip polling; just show current top 10")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--source", action="append",
                    help="restrict to one or more sources "
                         "(hackernews|arxiv|github), can repeat")
    args = ap.parse_args()

    from Feeds.sources.research import (
        poll, get_top_by_score, total_count, counts_by_source,
    )

    if not args.show_only:
        counts = poll(verbose=not args.quiet, sources=args.source)
        print(f"[research] new items this poll: {counts}")
        print(f"[research] total items in store: {total_count()}")
        print(f"[research] counts by source: {counts_by_source()}")

    if args.show or args.show_only:
        print("\n── top 10 by score (last 48h) ──")
        for r in get_top_by_score(limit=10, hours=48):
            print(f"  [{r['source']:10s}] {r['score']:>7.1f}  {r['title'][:90]}")
            print(f"              {r['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
