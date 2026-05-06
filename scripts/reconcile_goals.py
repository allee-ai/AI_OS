#!/usr/bin/env python3
"""
reconcile_goals.py — Enqueue reconcile tasks for stale open goals.

For every pending/in_progress goal older than --min-age-days, enqueue a
single small LLM task asking: "given recent events and the goal text,
is this likely already done, partially done, or still open?"

Results land in task_queue and show up in STATE on the next turn-start
under `log.tasks.recent.*`. The user can then accept/dismiss via
scripts/goal.py or the UI.

This is intentionally conservative — it does NOT close goals
automatically. It surfaces evidence; humans (or a future second-pass
loop) decide.

Usage:
  .venv/bin/python scripts/reconcile_goals.py            # default: 3+ days
  .venv/bin/python scripts/reconcile_goals.py --min-age-days 7
  .venv/bin/python scripts/reconcile_goals.py --max 5    # cap enqueued
  .venv/bin/python scripts/reconcile_goals.py --dry      # don't enqueue
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def list_stale_open_goals(min_age_days: int):
    from data.db import get_connection
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute(
            """
            SELECT id, goal, rationale, priority, sources, status, created_at
            FROM proposed_goals
            WHERE status IN ('pending','approved','in_progress','paused')
              AND created_at <= datetime('now', ?)
            ORDER BY id ASC
            """,
            (f"-{min_age_days} days",),
        ).fetchall()
    return [dict(r) for r in rows]


def recent_event_excerpt(goal_text: str, k: int = 6) -> str:
    """Pull a few keyword-matching events from the last 14 days as context."""
    # Simple keyword lift — first 3 capitalized / 4+ char tokens
    import re
    toks = [t for t in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", goal_text)][:5]
    if not toks:
        return ""
    from data.db import get_connection
    likes = " OR ".join(["data LIKE ?" for _ in toks])
    params = [f"%{t}%" for t in toks]
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute(
            f"""
            SELECT timestamp, event_type, data
            FROM unified_events
            WHERE timestamp >= datetime('now', '-14 days')
              AND ({likes})
            ORDER BY id DESC LIMIT ?
            """,
            (*params, k),
        ).fetchall()
    if not rows:
        return ""
    out = []
    for r in rows:
        ts = (r["timestamp"] or "")[:16]
        et = r["event_type"] or "evt"
        d = (r["data"] or "")[:140].replace("\n", " ")
        out.append(f"  [{ts}] {et}: {d}")
    return "\n".join(out)


def already_reconciled(goal_id: int) -> bool:
    """Has a goal_reconcile task for this goal already been queued?"""
    from data.db import get_connection
    with closing(get_connection(readonly=True)) as conn:
        row = conn.execute(
            "SELECT id FROM task_queue "
            "WHERE kind='goal_reconcile' "
            "AND params_json LIKE ? "
            "AND status IN ('pending','running','done') "
            "AND created_at >= datetime('now', '-7 days') "
            "LIMIT 1",
            (f'%"goal_id": {goal_id}%',),
        ).fetchone()
    return row is not None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-age-days", type=int, default=3)
    ap.add_argument("--max", type=int, default=10)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    goals = list_stale_open_goals(args.min_age_days)
    if not goals:
        print(f"No open goals older than {args.min_age_days}d.")
        return 0

    print(f"Found {len(goals)} stale open goals (>= {args.min_age_days}d).")
    enqueued = 0
    skipped = 0

    for g in goals:
        if enqueued >= args.max:
            break
        if already_reconciled(g["id"]):
            skipped += 1
            continue

        excerpt = recent_event_excerpt(g["goal"])
        prompt_lines = [
            f"Goal #{g['id']} (priority={g['priority']}, "
            f"status={g['status']}, opened={g['created_at']}):",
            f"  {g['goal']}",
        ]
        if g.get("rationale"):
            prompt_lines.append(f"  Rationale: {g['rationale']}")
        if excerpt:
            prompt_lines.append("")
            prompt_lines.append("Recent related events (last 14d):")
            prompt_lines.append(excerpt)
        prompt_lines.append("")
        prompt_lines.append(
            "Question: based ONLY on the events above, is this goal "
            "likely DONE, PARTIAL, or STILL_OPEN?\n\n"
            "Output exactly two lines:\n"
            "VERDICT: DONE|PARTIAL|STILL_OPEN\n"
            "EVIDENCE: <≤30 word summary citing at most one event>\n\n"
            "If no events relate at all, output STILL_OPEN with "
            "EVIDENCE: no recent activity."
        )
        prompt = "\n".join(prompt_lines)

        if args.dry:
            print(f"[dry] would enqueue reconcile for goal #{g['id']}: {g['goal'][:60]}")
            enqueued += 1
            continue

        from agent.threads.log.schema import enqueue_task
        try:
            tid = enqueue_task(
                kind="goal_reconcile",
                prompt=prompt,
                role="PLANNER",
                params={
                    "goal_id": g["id"],
                    "max_tokens": 150,
                    "temperature": 0.2,
                    "dedup_key": f"reconcile:{g['id']}",
                },
                requested_by="reconcile_goals",
            )
            print(f"  enqueued task #{tid} for goal #{g['id']}: {g['goal'][:60]}")
            enqueued += 1
        except Exception as e:
            print(f"  FAILED to enqueue goal #{g['id']}: {e}")

    print(f"\nEnqueued: {enqueued}.  Skipped (already reconciled): {skipped}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
