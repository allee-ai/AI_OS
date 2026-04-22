#!/usr/bin/env python3
"""
scripts/goal.py — Fastest path from thought to logged goal.

Usage:
    .venv/bin/python scripts/goal.py "text of the goal"
    .venv/bin/python scripts/goal.py "..." --priority high --rationale "why"
    .venv/bin/python scripts/goal.py --list
    .venv/bin/python scripts/goal.py --done <id>
    .venv/bin/python scripts/goal.py --reject <id>

Writes to proposed_goals (the same table the subconscious goals loop uses)
so every goal you drop here shows up in STATE on my next turn.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def cmd_add(text: str, priority: str, rationale: str) -> int:
    from agent.subconscious.loops.goals import propose_goal
    gid = propose_goal(
        goal=text.strip(),
        rationale=rationale.strip(),
        priority=priority,
        sources=["user_vscode"],
    )
    if not gid:
        print("failed to store goal", file=sys.stderr)
        return 1
    print(f"goal#{gid} stored [{priority}] {text}")
    # Also emit an agent-visible event so log/consequences pick it up.
    try:
        from agent.threads.log.schema import log_event
        log_event(
            event_type="goal_added",
            data=text,
            metadata={"goal_id": gid, "priority": priority, "source": "user_vscode"},
            source="scripts/goal.py",
        )
    except Exception:
        pass
    return 0


def cmd_list(status: str, limit: int) -> int:
    from agent.subconscious.loops.goals import get_proposed_goals
    goals = get_proposed_goals(status=status, limit=limit)
    if not goals:
        print(f"(no goals with status={status})")
        return 0
    for g in goals:
        gid = g.get("id")
        pri = g.get("priority", "?")
        gt = g.get("goal", "")
        stat = g.get("status", "?")
        rat = g.get("rationale", "")
        line = f"#{gid:<4} [{stat:<9}] [{pri:<6}] {gt}"
        if rat:
            line += f"  — {rat}"
        print(line)
    return 0


def cmd_resolve(goal_id: int, status: str) -> int:
    from agent.subconscious.loops.goals import resolve_goal
    from agent.threads.log.schema import log_event
    ok = resolve_goal(goal_id, status)
    if not ok:
        print(f"could not resolve goal#{goal_id} -> {status}", file=sys.stderr)
        return 1
    print(f"goal#{goal_id} -> {status}")
    try:
        log_event(
            event_type="goal_resolved",
            data=f"goal#{goal_id} -> {status}",
            metadata={"goal_id": goal_id, "status": status},
            source="scripts/goal.py",
        )
    except Exception:
        pass
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fast goal entry for AIOS.")
    p.add_argument("text", nargs="?", help="Goal text (omit when using --list / --done / --reject).")
    p.add_argument("--priority", choices=["urgent", "high", "medium", "low"], default="medium")
    p.add_argument("--rationale", default="", help="Optional rationale.")
    p.add_argument("--list", dest="list_status", nargs="?", const="pending",
                   help="List goals (default status: pending).")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--done", type=int, help="Mark goal ID as approved/done.")
    p.add_argument("--reject", type=int, help="Reject goal ID.")
    p.add_argument("--dismiss", type=int, help="Dismiss goal ID.")
    args = p.parse_args(argv)

    if args.done is not None:
        return cmd_resolve(args.done, "approved")
    if args.reject is not None:
        return cmd_resolve(args.reject, "rejected")
    if args.dismiss is not None:
        return cmd_resolve(args.dismiss, "dismissed")
    if args.list_status is not None:
        return cmd_list(args.list_status, args.limit)

    if not args.text:
        p.print_help(sys.stderr)
        return 2
    return cmd_add(args.text, args.priority, args.rationale)


if __name__ == "__main__":
    sys.exit(main())
