"""Pull a goal from goals.open and run it through the task planner.

Pipeline:
    1. Pick a goal: --id N, --goal-text "...", or auto-pick the top-priority
       open goal from proposed_goals.
    2. Create a `tasks` row with source='run_goal'.
    3. Hand it to the existing TaskPlanner.execute_task() which:
         - decomposes via TASK_PLANNER role (planner / large model),
         - executes each step via WORKER role (smaller cloud or local),
         - synthesizes a final summary via TASK_PLANNER role again.
    4. Print the result and (optionally) mark the source goal completed.

Recommended env (you can scope to one role with AIOS_<ROLE>_*):

    # Planner (large) — pin to GPT-4o
    export AIOS_TASK_PLANNER_PROVIDER=openai
    export AIOS_TASK_PLANNER_MODEL=gpt-4o
    export OPENAI_API_KEY=sk-...

    # Worker (small) — Ollama Cloud
    export AIOS_WORKER_PROVIDER=ollama
    export AIOS_WORKER_ENDPOINT=https://ollama.com
    export AIOS_WORKER_MODEL=qwen3-coder:480b-cloud   # or any cloud-tagged model
    export OLLAMA_API_KEY=...                         # from ollama.com/settings/keys

Without these, both roles fall back to the local Ollama daemon at the
boot default (qwen2.5:7b). The script prints what it resolved before
running, so you can confirm the routing.

Usage:
    .venv/bin/python scripts/run_goal.py                     # auto-pick + run
    .venv/bin/python scripts/run_goal.py --id 45             # specific goal
    .venv/bin/python scripts/run_goal.py --goal-text "..."   # ad-hoc goal
    .venv/bin/python scripts/run_goal.py --dry-run           # plan only
    .venv/bin/python scripts/run_goal.py --mark-done         # close goal on success
"""
from __future__ import annotations

import argparse
import sys
import time
from contextlib import closing
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ── Goal selection ───────────────────────────────────────────────────

PRIORITY_RANK = {"urgent": 4, "high": 3, "medium": 2, "low": 1}


def _open_statuses() -> Tuple[str, ...]:
    return ("pending", "approved", "in_progress", "paused", "blocked")


def pick_goal(goal_id: Optional[int]) -> Optional[dict]:
    """Return the goal dict to run, or None if nothing eligible."""
    from data.db import get_connection
    with closing(get_connection(readonly=True)) as conn:
        if goal_id is not None:
            row = conn.execute(
                "SELECT * FROM proposed_goals WHERE id = ?", (goal_id,)
            ).fetchone()
            return dict(row) if row else None

        # Auto-pick: open goals, highest priority, oldest first.
        placeholders = ",".join("?" for _ in _open_statuses())
        rows = conn.execute(
            f"SELECT * FROM proposed_goals "
            f"WHERE status IN ({placeholders}) "
            f"ORDER BY id ASC",
            _open_statuses(),
        ).fetchall()
        if not rows:
            return None
        rows = sorted(
            rows,
            key=lambda r: (-PRIORITY_RANK.get((r["priority"] or "medium").lower(), 2), r["id"]),
        )
        return dict(rows[0])


# ── Routing report ───────────────────────────────────────────────────

def print_routing() -> None:
    from agent.services.role_model import resolve_role
    print("[run_goal] role routing:")
    for role in ("TASK_PLANNER", "WORKER"):
        cfg = resolve_role(role)
        endpoint = cfg.endpoint or "(provider default)"
        cloud_tag = " [☁ cloud]" if cfg.model.endswith("-cloud") else ""
        print(f"  {role:14s} provider={cfg.provider:8s} model={cfg.model}{cloud_tag}  endpoint={endpoint}")


# ── Run ──────────────────────────────────────────────────────────────

def run(goal_text: str, source: str, dry_run: bool) -> dict:
    from agent.subconscious.loops.task_planner import (
        create_task, get_task, TaskPlanner, update_task_status,
    )

    task = create_task(goal_text, source=source)
    print(f"[run_goal] task #{task['id']} created — goal: {goal_text!r}")

    planner = TaskPlanner(interval=30.0, enabled=False)

    if dry_run:
        # Plan only — don't execute steps.
        context = planner._gather_context(goal_text)
        steps = planner._plan_steps(goal_text, context)
        update_task_status(task["id"], "planning", steps=steps,
                           context_summary=context["summary"])
        result = get_task(task["id"])
        print(f"[run_goal] dry-run — {len(steps)} step(s) planned, not executed")
        return result

    t0 = time.time()
    result = planner.execute_task(task["id"])
    elapsed = time.time() - t0
    print(f"[run_goal] task #{task['id']} finished — status={result.get('status')} "
          f"in {elapsed:.1f}s")
    return result


def maybe_mark_goal_done(goal_id: int, task_status: str) -> None:
    if task_status != "completed":
        return
    from data.db import get_connection
    with closing(get_connection()) as conn:
        conn.execute(
            "UPDATE proposed_goals SET status='completed', resolved_at=datetime('now') "
            "WHERE id = ?",
            (goal_id,),
        )
        conn.commit()
    print(f"[run_goal] goal #{goal_id} marked completed")


# ── Pretty-print result ──────────────────────────────────────────────

def render_result(result: dict) -> None:
    print("─" * 64)
    print(f"task #{result.get('id')} | status: {result.get('status')}")
    if result.get("context_summary"):
        print(f"context: {result['context_summary']}")
    steps = result.get("steps") or []
    results = result.get("results") or []
    print(f"steps: {len(steps)}, results: {len(results)}")
    for i, s in enumerate(steps):
        desc = s.get("description") or s.get("action") or "(unnamed step)"
        tool = s.get("tool", "?")
        print(f"  [{i+1}] {tool}: {desc}")
        # Find matching result
        for r in results:
            if r.get("step") == i + 1 or r.get("step") == i:
                ok = "✓" if r.get("success") else "✗"
                out = (r.get("output") or r.get("error") or "")
                if isinstance(out, str):
                    out = out.strip()
                    if len(out) > 240:
                        out = out[:240] + "…"
                print(f"      {ok} {out}")
                break
    # Final summary, if present
    summary = next((r for r in results if r.get("step") == "summary"), None)
    if summary:
        print()
        print("summary:")
        print(f"  {summary.get('output', '').strip()}")
    print("─" * 64)


# ── Main ─────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, default=None,
                    help="proposed_goals.id to run; default = top open goal")
    ap.add_argument("--goal-text", default=None,
                    help="ad-hoc goal text (skips proposed_goals lookup)")
    ap.add_argument("--dry-run", action="store_true",
                    help="plan only, don't execute steps")
    ap.add_argument("--mark-done", action="store_true",
                    help="on success, mark the source goal completed")
    ap.add_argument("--planner", default=None,
                    help="override planner model (e.g. gpt-4o, gpt-oss:120b-cloud)")
    ap.add_argument("--worker", default=None,
                    help="override worker model (e.g. gpt-oss:20b-cloud, qwen2.5:7b)")
    args = ap.parse_args()

    import os
    if args.planner:
        os.environ["AIOS_TASK_PLANNER_MODEL"] = args.planner
        # If user passed an OpenAI model name without setting provider,
        # leave provider untouched — they can do that explicitly.
    if args.worker:
        os.environ["AIOS_WORKER_MODEL"] = args.worker

    print_routing()

    if args.goal_text:
        goal_text = args.goal_text.strip()
        goal_id = None
    else:
        goal = pick_goal(args.id)
        if not goal:
            print("[run_goal] no goal to run", file=sys.stderr)
            return 1
        goal_text = goal["goal"]
        goal_id = goal["id"]
        print(f"[run_goal] selected goal #{goal_id} [{goal['priority']}/{goal['status']}]: "
              f"{goal_text}")

    source = f"run_goal#{goal_id}" if goal_id else "run_goal:adhoc"
    result = run(goal_text, source=source, dry_run=args.dry_run)
    render_result(result)

    if args.mark_done and goal_id and result.get("status") == "completed":
        maybe_mark_goal_done(goal_id, result["status"])

    return 0 if result.get("status") in ("completed", "planning") else 2


if __name__ == "__main__":
    sys.exit(main())
