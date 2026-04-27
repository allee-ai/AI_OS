#!/usr/bin/env python3
"""Decay/prune learned identity facts.

Touches only ``fact_type='learned'`` and ``protected=0``. Curated facts
(name, email, location, occupation, organization, hardware, os, phone,
relationship, birthday) are immune. The 'machine' (Nola) profile's
hand-set facts are immune. ``primary_user``'s curated facts are immune.

Usage:
    python scripts/decay_facts.py --dry-run
    python scripts/decay_facts.py
    python scripts/decay_facts.py --grace 7 --delete-age 21 --half-life 21

Defaults match what's intended for the daily reflex trigger.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.threads.identity.schema import decay_learned_facts  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be done; no DB writes.")
    p.add_argument("--grace", type=int, default=14,
                   help="Skip decay for facts touched in last N days (default 14).")
    p.add_argument("--delete-age", type=int, default=30,
                   help="Hard-prune unused learned facts older than N days (default 30).")
    p.add_argument("--max-access", type=int, default=1,
                   help="access_count <= this counts as 'unused' (default 1).")
    p.add_argument("--half-life", type=int, default=30,
                   help="Weight halves every N days of inactivity (default 30).")
    p.add_argument("--floor", type=float, default=0.05,
                   help="Min weight floor; access_count=0 facts at floor are deleted (default 0.05).")
    p.add_argument("--json", action="store_true",
                   help="Emit JSON instead of human summary.")
    args = p.parse_args()

    result = decay_learned_facts(
        grace_days=args.grace,
        delete_age_days=args.delete_age,
        delete_max_access=args.max_access,
        half_life_days=args.half_life,
        min_weight_floor=args.floor,
        dry_run=args.dry_run,
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    tag = "[dry-run] " if args.dry_run else ""
    print(f"{tag}identity decay summary")
    print(f"  pruned (age > {args.delete_age}d, ac <= {args.max_access}): {len(result['pruned'])}")
    for r in result["pruned"]:
        print(f"    - {r['profile_id']}.{r['key']} "
              f"(w={r['weight']:.2f}, ac={r['access_count']}, age={r['age_days']:.0f}d)")
    print(f"  decayed (age > {args.grace}d): {len(result['decayed'])}")
    for r in result["decayed"]:
        print(f"    - {r['profile_id']}.{r['key']} "
              f"{r['old_weight']:.2f} -> {r['new_weight']:.2f} (age={r['age_days']:.0f}d)")
    print(f"  floor-deleted (weight <= {args.floor}, ac = 0): {len(result['floor_deleted'])}")
    for r in result["floor_deleted"]:
        print(f"    - {r['profile_id']}.{r['key']}")
    print(f"  skipped (within grace): {result['skipped_recent']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
