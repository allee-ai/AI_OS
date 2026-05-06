#!/usr/bin/env python3
"""
Task worker — claim pending task_queue rows, run them via cloud LLM, write back.

Usage:
  .venv/bin/python scripts/run_task_worker.py            # one pass, run all pending
  .venv/bin/python scripts/run_task_worker.py --max 1    # claim at most one
  .venv/bin/python scripts/run_task_worker.py --loop 30  # poll every 30s

Behavior:
  - Calls agent.services.llm.generate(prompt, role=..., ...)
  - On success → status='done', writes result + duration + model
  - On rate-limit error → status='rate_limited', logs unified_event
                          'rate_limit' so reflex can pattern-match
  - On other error → status='failed', logs error event
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.threads.log.schema import (  # noqa: E402
    claim_next_task, complete_task, fail_task, log_event,
)
from agent.services.rate_gate import is_rate_limit_error  # noqa: E402


def _is_rate_limited(err_text: str) -> bool:
    return is_rate_limit_error(err_text)


def _resolve_model_for_role(role: str) -> str:
    try:
        from agent.services.role_model import resolve_role
        cfg = resolve_role(role)
        return f"{cfg.provider}:{cfg.model}"
    except Exception:
        return "unknown"


def run_one(task: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single claimed task. Returns summary dict."""
    from agent.services.llm import generate

    tid = task["id"]
    role = task.get("role") or "PLANNER"
    prompt = task["prompt"]
    params = {}
    try:
        params = json.loads(task.get("params_json") or "{}") or {}
    except Exception:
        pass
    system = params.get("system")
    max_tokens = int(params.get("max_tokens", 1024))
    temperature = float(params.get("temperature", 0.7))

    model_label = _resolve_model_for_role(role)

    started = time.time()
    try:
        result = generate(
            prompt=prompt,
            system=system,
            role=role,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        dur_ms = int((time.time() - started) * 1000)
        complete_task(
            task_id=tid,
            result=str(result)[:20000],
            model_used=model_label,
            duration_ms=dur_ms,
        )
        log_event(
            event_type="task_done",
            data=f"task #{tid} {task['kind']} done via {model_label} ({dur_ms}ms)",
            metadata={
                "task_id": tid,
                "kind": task["kind"],
                "role": role,
                "model": model_label,
                "duration_ms": dur_ms,
                "business_id": task.get("business_id"),
                "result_preview": str(result)[:200],
            },
            source="agent",
            thread_subject="task_queue",
            tags=["task", "done", task["kind"]],
        )
        return {"id": tid, "status": "done", "duration_ms": dur_ms,
                "preview": str(result)[:120]}

    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        rl = _is_rate_limited(err)
        fail_task(tid, err, rate_limited=rl)
        log_event(
            event_type="rate_limit" if rl else "task_failed",
            data=f"task #{tid} {task['kind']} {'rate-limited' if rl else 'failed'}: {err[:160]}",
            metadata={
                "task_id": tid,
                "kind": task["kind"],
                "role": role,
                "model": model_label,
                "error": err[:1000],
                "business_id": task.get("business_id"),
            },
            source="agent",
            thread_subject="task_queue",
            tags=["task", "rate_limit" if rl else "failed", task["kind"]],
        )
        return {"id": tid, "status": "rate_limited" if rl else "failed",
                "error": err[:160]}


def run_pass(max_tasks: int) -> int:
    n = 0
    while n < max_tasks:
        task = claim_next_task()
        if not task:
            break
        n += 1
        print(f"[{n}] claimed task #{task['id']} kind={task['kind']} role={task['role']}")
        out = run_one(task)
        print(f"    -> {out['status']}", end="")
        if "duration_ms" in out:
            print(f" ({out['duration_ms']}ms)", end="")
        print()
        if out.get("preview"):
            print(f"       :: {out['preview']}")
        if out.get("error"):
            print(f"       !! {out['error']}")
        # Back off on rate-limit so we don't immediately re-trigger
        if out["status"] == "rate_limited":
            print("    rate-limited — stopping this pass")
            break
    return n


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--max", type=int, default=10, help="max tasks per pass")
    p.add_argument("--loop", type=int, default=0,
                   help="if >0, run forever, sleeping N seconds between passes")
    args = p.parse_args()

    if args.loop > 0:
        print(f"task worker looping every {args.loop}s (Ctrl-C to stop)")
        while True:
            try:
                ran = run_pass(args.max)
                if ran == 0:
                    pass  # quiet idle
                else:
                    print(f"  pass complete: {ran} task(s)")
            except KeyboardInterrupt:
                print("stopped.")
                return 0
            except Exception as e:
                print(f"  worker pass error: {e}")
            time.sleep(args.loop)
    else:
        ran = run_pass(args.max)
        print(f"done. ran {ran} task(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
