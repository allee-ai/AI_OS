"""
liveness — is the substrate actually alive?
============================================

The supervisor (scripts/run_loops.py) writes one row per loop to
`loop_heartbeat` every tick. This module reads that table and answers:

  - Is each loop ticking?
  - When did it last tick?
  - Is it within its expected interval?

Used by the orchestrator's HOT block to surface an `alive: ...` line so
every STATE assembly tells the LLM whether the body is breathing.
"""

from __future__ import annotations

import json
from contextlib import closing
from typing import Dict, Any, List

from data.db import get_connection


# Expected max interval (seconds) before a loop is considered stale.
# Generous — covers cold starts, sqlite locks, GIL stalls.
EXPECTED_MAX = {
    "meditate": 30.0,    # 2s tick → 30s tolerant
    "coma":     180.0,   # 60s tick
    "tasks":    60.0,    # 10s tick
}


def loop_status() -> List[Dict[str, Any]]:
    """Per-loop liveness rows. Empty if the table doesn't exist yet."""
    try:
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                """
                SELECT loop, last_ts, last_payload, ticks, errors,
                       (julianday('now') - julianday(last_ts)) * 86400.0 AS age_s
                FROM loop_heartbeat
                ORDER BY loop
                """
            ).fetchall()
    except Exception:
        return []

    out = []
    for r in rows:
        loop = r["loop"]
        age = float(r["age_s"] or 0.0)
        max_ok = EXPECTED_MAX.get(loop, 300.0)
        alive = age <= max_ok
        try:
            payload = json.loads(r["last_payload"] or "{}")
        except Exception:
            payload = {}
        out.append({
            "loop": loop,
            "alive": alive,
            "age_s": round(age, 1),
            "max_ok_s": max_ok,
            "ticks": int(r["ticks"] or 0),
            "errors": int(r["errors"] or 0),
            "last_ts": r["last_ts"],
            "payload": payload,
        })
    return out


def alive_summary() -> str:
    """One-line summary suitable for HOT block / banners.

    Examples:
      "all loops alive (meditate 1.8s/126t, coma 12s/4t, tasks 4s/12t)"
      "DEAD: meditate stale 14m, tasks ok 5s"
      "no supervisor running (loop_heartbeat empty)"
    """
    rows = loop_status()
    if not rows:
        return "no supervisor running (loop_heartbeat empty)"

    parts = []
    any_dead = False
    for r in rows:
        flag = "" if r["alive"] else "STALE!"
        if not r["alive"]:
            any_dead = True
        age = r["age_s"]
        if age < 60:
            age_str = f"{age:.0f}s"
        elif age < 3600:
            age_str = f"{age/60:.0f}m"
        else:
            age_str = f"{age/3600:.1f}h"
        parts.append(f"{r['loop']} {age_str}/{r['ticks']}t{flag}")

    prefix = "DEAD" if any_dead else "alive"
    return f"{prefix}: " + ", ".join(parts)


def is_alive() -> bool:
    rows = loop_status()
    if not rows:
        return False
    return all(r["alive"] for r in rows)


__all__ = ["loop_status", "alive_summary", "is_alive"]
