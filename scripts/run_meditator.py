"""
meditator daemon — runs meditation.tick() in a loop forever.

Usage:
    .venv/bin/python scripts/run_meditator.py [--interval 2.0] [--max-ticks N]

Starts alongside the server (or under a process supervisor) and keeps
the substrate continuously refreshed.  Logs a one-line summary every
tick to data/logs/meditator.log.

Env:
    AIOS_MEDITATE_INTERVAL_S  default 2.0
    AIOS_MEDITATE_MAX_TICKS   default 0 (forever)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import signal
from datetime import datetime
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.subconscious import meditation


_RUN = True


def _stop(_sig, _frame):
    global _RUN
    _RUN = False


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--interval",
        type=float,
        default=float(os.getenv("AIOS_MEDITATE_INTERVAL_S", "2.0")),
        help="seconds between ticks",
    )
    p.add_argument(
        "--max-ticks",
        type=int,
        default=int(os.getenv("AIOS_MEDITATE_MAX_TICKS", "0")),
        help="0 = forever",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="suppress stdout, log only",
    )
    args = p.parse_args()

    log_dir = Path(__file__).resolve().parent.parent / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "meditator.log"

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    tick_n = 0
    started = time.time()
    print(
        f"[meditator] start interval={args.interval}s "
        f"max_ticks={args.max_ticks or 'forever'}"
    )
    with open(log_path, "a", buffering=1) as logf:
        logf.write(
            f"\n=== meditator start {datetime.utcnow().isoformat()}Z "
            f"interval={args.interval}s ===\n"
        )
        while _RUN:
            tick_n += 1
            s = meditation.tick()
            line = (
                f"[{datetime.utcnow().isoformat()}Z] tick={tick_n} "
                f"elapsed={s.get('elapsed_ms')}ms "
                f"events={s.get('events_seen')} "
                f"kicked={s.get('concepts_kicked')} "
                f"spread={s.get('spread_edges')} "
                f"decayed={s.get('decayed_rows')} "
                f"cache={s.get('salience_rows')} "
                f"ready={s.get('readiness', 0):.2f}"
                f"{'!' if s.get('ready') else ''}"
            )
            if s.get("error"):
                line += f" ERROR={s['error']}"
            logf.write(line + "\n")
            if not args.quiet and tick_n % 10 == 0:
                print(line)
            if args.max_ticks and tick_n >= args.max_ticks:
                break
            # Sleep, but wake up on signal
            target = time.time() + args.interval
            while _RUN and time.time() < target:
                time.sleep(0.1)
    elapsed = time.time() - started
    print(
        f"[meditator] stop ticks={tick_n} elapsed={elapsed:.1f}s "
        f"avg_period={elapsed/max(1,tick_n):.2f}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
