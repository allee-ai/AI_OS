#!/usr/bin/env python3
"""
Drop a task into the AIOS task_queue.

Usage:
  .venv/bin/python scripts/queue_task.py \\
      --kind summarize --role SUMMARY \\
      --prompt "Summarize the lead pipeline status in 5 bullets."

  echo "long prompt..." | .venv/bin/python scripts/queue_task.py \\
      --kind plan --role PLANNER --stdin

  .venv/bin/python scripts/queue_task.py --list
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.threads.log.schema import (  # noqa: E402
    enqueue_task, list_pending_tasks, list_recent_tasks, task_counts
)


def cmd_list() -> int:
    counts = task_counts()
    print("counts:", counts or "(empty)")
    pending = list_pending_tasks(limit=20)
    if pending:
        print(f"\npending ({len(pending)}):")
        for t in pending:
            print(f"  #{t['id']:>4}  {t['kind']:<14} role={t['role']:<10} "
                  f"by={t['requested_by']:<10} biz={t.get('business_id') or '-':<10} "
                  f"queued={t['created_at']}")
    recent = list_recent_tasks(limit=10)
    if recent:
        print(f"\nrecent ({len(recent)}):")
        for t in recent:
            print(f"  #{t['id']:>4}  [{t['status']:<12}] {t['kind']:<14} "
                  f"model={t.get('model_used') or '-':<22} "
                  f"dur={t.get('duration_ms') or 0}ms")
            if t.get("preview"):
                print(f"        :: {t['preview']}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--kind", help="task kind tag, e.g. summarize/plan/extract/classify")
    p.add_argument("--role", default="PLANNER",
                   help="role tag for resolve_role() — CHAT, EXTRACT, SUMMARY, PLANNER, ...")
    p.add_argument("--prompt", help="prompt text (or use --stdin)")
    p.add_argument("--stdin", action="store_true", help="read prompt from stdin")
    p.add_argument("--system", help="optional system prompt")
    p.add_argument("--max-tokens", type=int, default=1024)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--by", default="copilot", help="requested_by tag")
    p.add_argument("--biz", default=None, help="business_id (vanguard, aios, ...)")
    p.add_argument("--list", action="store_true", help="just list current queue state")
    args = p.parse_args()

    if args.list:
        return cmd_list()

    if not args.kind:
        p.error("--kind is required (unless --list)")

    if args.stdin:
        prompt = sys.stdin.read()
    else:
        prompt = args.prompt or ""
    if not prompt.strip():
        p.error("empty prompt — pass --prompt or pipe via --stdin")

    params = {"max_tokens": args.max_tokens, "temperature": args.temperature}
    if args.system:
        params["system"] = args.system

    tid = enqueue_task(
        kind=args.kind,
        prompt=prompt,
        role=args.role.upper(),
        params=params,
        requested_by=args.by,
        business_id=args.biz,
    )
    print(f"queued task #{tid} (kind={args.kind}, role={args.role.upper()})")
    print(f"  -> next worker tick will run it; check with: .venv/bin/python scripts/queue_task.py --list")
    return 0


if __name__ == "__main__":
    sys.exit(main())
