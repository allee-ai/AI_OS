"""
run_loops — single-process supervisor for the substrate's living loops.
========================================================================

One Python process. Three cadences. The substrate stays alive.

  meditation.tick()        — every  AIOS_LOOP_MEDITATE_S    (default 2s)
  coma.run_once()          — every  AIOS_LOOP_COMA_S        (default 60s)
  task_worker.run_pass()   — every  AIOS_LOOP_TASK_S        (default 10s)

Why one process:
  - SQLite WAL handles concurrent readers fine, but multi-process write
    contention adds 'database is locked' retries. One writer is simpler.
  - One PID to supervise, one log file, one signal handler.
  - liveness.process_status() can read its own heartbeat and report.

Single-instance lock: data/.run_loops.pid. If another instance is
already running and alive, this one exits. Otherwise the stale pidfile
is replaced.

Logs: data/logs/loops.log (one line per loop tick).

Usage:
  .venv/bin/python scripts/run_loops.py
  .venv/bin/python scripts/run_loops.py --once  (run each loop once and exit)

Designed to be run under systemd (Linux) or launchd (macOS).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


_RUN = True


def _stop(_sig, _frame):
    global _RUN
    _RUN = False


def _log(logf, kind: str, payload: dict) -> None:
    line = (
        f"[{datetime.utcnow().isoformat()}Z] {kind} "
        + " ".join(f"{k}={v}" for k, v in payload.items())
    )
    try:
        logf.write(line + "\n")
    except Exception:
        pass


def _heartbeat_write(payload: dict) -> None:
    """Touch a single-row heartbeat for liveness checks."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS loop_heartbeat ("
                " loop TEXT PRIMARY KEY,"
                " last_ts TEXT NOT NULL,"
                " last_payload TEXT,"
                " ticks INTEGER NOT NULL DEFAULT 0,"
                " errors INTEGER NOT NULL DEFAULT 0)"
            )
            conn.execute(
                """
                INSERT INTO loop_heartbeat (loop, last_ts, last_payload, ticks, errors)
                VALUES (?, datetime('now'), ?, 1, ?)
                ON CONFLICT(loop) DO UPDATE SET
                    last_ts = datetime('now'),
                    last_payload = excluded.last_payload,
                    ticks = ticks + 1,
                    errors = errors + excluded.errors
                """,
                (payload["loop"], json.dumps(payload), int(payload.get("err", 0))),
            )
            conn.commit()
    except Exception:
        pass


def _acquire_lock() -> bool:
    pid_path = ROOT / "data" / ".run_loops.pid"
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    if pid_path.exists():
        try:
            other = int(pid_path.read_text().strip())
            os.kill(other, 0)  # signal 0 = check existence
            print(f"[run_loops] another instance already running (pid={other})")
            return False
        except (OSError, ValueError):
            pass  # stale
    pid_path.write_text(str(os.getpid()))
    return True


def _release_lock() -> None:
    pid_path = ROOT / "data" / ".run_loops.pid"
    try:
        if pid_path.exists() and pid_path.read_text().strip() == str(os.getpid()):
            pid_path.unlink()
    except Exception:
        pass


def _meditate_once(logf) -> None:
    try:
        from agent.subconscious import meditation
        s = meditation.tick()
        _log(logf, "meditate", {
            "ms": s.get("elapsed_ms"),
            "events": s.get("events_seen"),
            "kicked": s.get("concepts_kicked"),
            "cache": s.get("salience_rows"),
            "ready": round(float(s.get("readiness", 0) or 0), 2),
            "shift": s.get("shift_meta_id") or "",
        })
        _heartbeat_write({
            "loop": "meditate",
            "ms": s.get("elapsed_ms"),
            "ready": round(float(s.get("readiness", 0) or 0), 3),
        })
    except Exception as e:
        _log(logf, "meditate", {"ERR": f"{type(e).__name__}: {e}"})
        _heartbeat_write({"loop": "meditate", "err": 1})


def _coma_once(logf) -> None:
    try:
        from agent.subconscious import coma
        s = coma.run_once()
        # Summarize whatever it returns without depending on shape.
        keys = list(s.keys())[:8] if isinstance(s, dict) else []
        _log(logf, "coma", {k: s.get(k) for k in keys} if isinstance(s, dict) else {})
        _heartbeat_write({
            "loop": "coma",
            "keys": ",".join(keys),
        })
    except Exception as e:
        _log(logf, "coma", {"ERR": f"{type(e).__name__}: {e}"})
        _heartbeat_write({"loop": "coma", "err": 1})


def _task_once(logf, max_per_pass: int = 5) -> None:
    try:
        # Import lazily so syntax issues don't kill the supervisor.
        from scripts.run_task_worker import run_pass  # type: ignore
        # Capture stdout would be nice; settle for ran-count.
        ran = run_pass(max_per_pass)
        _log(logf, "tasks", {"ran": ran})
        _heartbeat_write({"loop": "tasks", "ran": ran})
    except Exception as e:
        _log(logf, "tasks", {"ERR": f"{type(e).__name__}: {e}"})
        _heartbeat_write({"loop": "tasks", "err": 1})


def _exec_once(logf) -> None:
    """Run the copilot_executor: pick up pending phone-submitted requests
    and act on them (prose-execute or plan-for-laptop)."""
    try:
        from outbox.copilot_executor import tick_once
        result = tick_once()
        _log(logf, "exec", result)
        _heartbeat_write({"loop": "exec", **result})
    except Exception as e:
        _log(logf, "exec", {"ERR": f"{type(e).__name__}: {e}"})
        _heartbeat_write({"loop": "exec", "err": 1})


def _reflect_once(logf) -> None:
    """Run the reflector: emit one grounded thought based on STATE.
    Slow cadence (default 5min) so cloud rate budget stays healthy."""
    try:
        from outbox.reflector import tick_once
        result = tick_once()
        _log(logf, "reflect", result)
        _heartbeat_write({"loop": "reflect", **result})
    except Exception as e:
        _log(logf, "reflect", {"ERR": f"{type(e).__name__}: {e}"})
        _heartbeat_write({"loop": "reflect", "err": 1})


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--meditate-s", type=float,
                   default=float(os.getenv("AIOS_LOOP_MEDITATE_S", "2.0")))
    p.add_argument("--coma-s", type=float,
                   default=float(os.getenv("AIOS_LOOP_COMA_S", "60.0")))
    p.add_argument("--task-s", type=float,
                   default=float(os.getenv("AIOS_LOOP_TASK_S", "10.0")))
    p.add_argument("--exec-s", type=float,
                   default=float(os.getenv("AIOS_LOOP_EXEC_S", "15.0")),
                   help="copilot_executor cadence (phone request acting)")
    p.add_argument("--reflect-s", type=float,
                   default=float(os.getenv("AIOS_LOOP_REFLECT_S", "300.0")),
                   help="reflector cadence — one grounded thought per tick")
    p.add_argument("--once", action="store_true",
                   help="run each loop once and exit")
    p.add_argument("--no-meditate", action="store_true")
    p.add_argument("--no-coma", action="store_true")
    p.add_argument("--no-tasks", action="store_true")
    p.add_argument("--no-exec", action="store_true")
    p.add_argument("--no-reflect", action="store_true")
    args = p.parse_args()

    if not _acquire_lock():
        return 2

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    log_dir = ROOT / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logf = open(log_dir / "loops.log", "a", buffering=1)
    _log(logf, "start", {
        "pid": os.getpid(),
        "meditate_s": args.meditate_s,
        "coma_s": args.coma_s,
        "task_s": args.task_s,
        "exec_s": args.exec_s,
        "reflect_s": args.reflect_s,
        "once": args.once,
    })
    print(
        f"[run_loops] pid={os.getpid()} "
        f"meditate={args.meditate_s}s coma={args.coma_s}s tasks={args.task_s}s "
        f"exec={args.exec_s}s reflect={args.reflect_s}s once={args.once}"
    )

    next_med = 0.0
    next_coma = 0.0
    next_task = 0.0
    next_exec = 0.0
    next_reflect = 0.0

    try:
        while _RUN:
            now = time.time()
            if not args.no_meditate and now >= next_med:
                _meditate_once(logf)
                next_med = now + args.meditate_s
            if not args.no_coma and now >= next_coma:
                _coma_once(logf)
                next_coma = now + args.coma_s
            if not args.no_tasks and now >= next_task:
                _task_once(logf)
                next_task = now + args.task_s
            if not args.no_exec and now >= next_exec:
                _exec_once(logf)
                next_exec = now + args.exec_s
            if not args.no_reflect and now >= next_reflect:
                _reflect_once(logf)
                next_reflect = now + args.reflect_s
            if args.once:
                break
            # Sleep until the soonest deadline, but wake every 200ms for signals.
            until = min(next_med, next_coma, next_task, next_exec, next_reflect) - time.time()
            if until > 0.2:
                until = 0.2
            if until > 0:
                time.sleep(until)
    finally:
        _log(logf, "stop", {"pid": os.getpid()})
        try:
            logf.close()
        except Exception:
            pass
        _release_lock()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
