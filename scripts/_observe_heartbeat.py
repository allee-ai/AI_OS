"""Observe heartbeat: run HealthLoop._check_health() at 0/5/10/15/20 min.

Prints each tick's output and writes it to data/logs/heartbeat_observe.log.
Pure programmatic — no server required.
"""
from __future__ import annotations
import time
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.subconscious.loops.health import HealthLoop  # noqa: E402

LOG = Path("data/logs/heartbeat_observe.log")
LOG.parent.mkdir(parents=True, exist_ok=True)

# Force shorter heartbeat for this run so first emission is immediate.
loop = HealthLoop(interval=5.0)

INTERVAL_S = int(os.getenv("HB_INTERVAL_S", "300"))   # 5 min default
TICKS = int(os.getenv("HB_TICKS", "5"))                # 5 ticks = 20 min span


def banner(i: int) -> str:
    return f"\n========== TICK {i+1}/{TICKS} @ {datetime.now().isoformat(timespec='seconds')} =========="


with LOG.open("a") as f:
    f.write(f"\n\n##### observe run started {datetime.now().isoformat()} #####\n")
    for i in range(TICKS):
        b = banner(i)
        print(b, flush=True); f.write(b + "\n")
        try:
            out = loop._check_health()
        except Exception as e:
            out = f"ERROR: {e}"
        print(out, flush=True)
        f.write(out + "\n")
        f.flush()
        if i < TICKS - 1:
            time.sleep(INTERVAL_S)

print("\n[observe] done")
