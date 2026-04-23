#!/usr/bin/env python3
"""
scripts/swarm.py — conventions for spawning subagents and collecting results.

When Copilot fans out to multiple subagents in one turn, the results are
only visible to that one turn unless someone writes them down. This script
is the mailbox.

Usage patterns:

  # Before dispatch — create a swarm context id
  swarm_id = $(scripts/swarm.py new --goal "research claude-code v4 features")

  # Each subagent writes its result back:
  scripts/swarm.py result --swarm $swarm_id --agent Explore \\
      --summary "claude-code adds X, Y, Z" --artifact path/or/json

  # Collect all results for a swarm:
  scripts/swarm.py collect --swarm $swarm_id

  # List recent swarms:
  scripts/swarm.py list

Stores results in reflex_meta_thoughts with kind='compression' and
source='copilot', tagged [swarm:<id>] so they can be pulled back by LIKE
and surface in STATE under reflex.meta.copilot.* next turn.

This is the memory hack: by the time my next turn starts, every subagent
result I got IS in STATE, which means I don't need to remember to paste
them.  The flywheel is on the write, not the read.
"""

from __future__ import annotations
import argparse
import json
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.threads.reflex.schema import (  # noqa: E402
    add_meta_thought,
    get_recent_meta_thoughts,
    init_meta_thoughts_table,
)


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def cmd_new(goal: str) -> int:
    init_meta_thoughts_table()
    sid = _short_id()
    content = f"[swarm:{sid}] OPENED goal={goal[:200]}"
    rid = add_meta_thought(
        kind="compression",
        content=content,
        source="copilot",
        confidence=0.5,
        weight=0.6,
    )
    if rid is None:
        print("failed to open swarm", file=sys.stderr)
        return 1
    # Write a machine-readable file too so subagents can grep for it
    mbox = ROOT / "data" / "swarms"
    mbox.mkdir(parents=True, exist_ok=True)
    (mbox / f"{sid}.json").write_text(json.dumps({
        "swarm_id": sid,
        "goal": goal,
        "opened_at": time.time(),
        "note_id": rid,
    }, indent=2))
    # Print only the id so it's easy to capture in shell: SID=$(swarm.py new ...)
    print(sid)
    return 0


def cmd_result(swarm: str, agent: str, summary: str, artifact: str | None) -> int:
    init_meta_thoughts_table()
    tag = f"[swarm:{swarm}] {agent}"
    if artifact:
        tag += f" → {artifact[:80]}"
    content = f"{tag} :: {summary[:300]}"
    rid = add_meta_thought(
        kind="compression",
        content=content,
        source="copilot",
        confidence=0.7,
        weight=0.6,
    )
    if rid is None:
        print("failed to record result", file=sys.stderr)
        return 1
    print(f"result#{rid} logged for swarm={swarm} agent={agent}")
    return 0


def cmd_collect(swarm: str, limit: int) -> int:
    init_meta_thoughts_table()
    rows = get_recent_meta_thoughts(kinds=["compression"], limit=500)
    matching = [r for r in rows if f"[swarm:{swarm}]" in r.get("content", "")]
    if not matching:
        print(f"(no entries for swarm {swarm})")
        return 0
    # oldest first feels more like a timeline
    matching.reverse()
    for r in matching[-limit:]:
        rid = r.get("id")
        ts = r.get("created_at", "")
        c = r.get("content", "")
        print(f"#{rid:<4} {ts}  {c}")
    return 0


def cmd_list(limit: int) -> int:
    mbox = ROOT / "data" / "swarms"
    if not mbox.exists():
        print("(no swarms yet)")
        return 0
    files = sorted(mbox.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files[:limit]:
        try:
            d = json.loads(f.read_text())
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(d.get("opened_at", 0)))
            print(f"{d['swarm_id']}  {ts}  {d.get('goal', '')[:70]}")
        except Exception:
            pass
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Swarm mailbox for subagent coordination")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s_new = sub.add_parser("new", help="open a new swarm context")
    s_new.add_argument("--goal", required=True)

    s_res = sub.add_parser("result", help="record one agent's result")
    s_res.add_argument("--swarm", required=True)
    s_res.add_argument("--agent", required=True, help="agent name or label")
    s_res.add_argument("--summary", required=True)
    s_res.add_argument("--artifact", default=None, help="file path or url")

    s_col = sub.add_parser("collect", help="show all results for a swarm")
    s_col.add_argument("--swarm", required=True)
    s_col.add_argument("--limit", type=int, default=50)

    s_lst = sub.add_parser("list", help="list recent swarms")
    s_lst.add_argument("--limit", type=int, default=10)

    args = ap.parse_args()
    if args.cmd == "new":
        return cmd_new(args.goal)
    if args.cmd == "result":
        return cmd_result(args.swarm, args.agent, args.summary, args.artifact)
    if args.cmd == "collect":
        return cmd_collect(args.swarm, args.limit)
    if args.cmd == "list":
        return cmd_list(args.limit)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
