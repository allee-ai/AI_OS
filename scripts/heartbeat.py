#!/usr/bin/env python3
"""
scripts/heartbeat.py — autopilot stall detector.

Runs from cron / launchd every N minutes.  Checks:
  - is data/.last_state_read fresh?
  - is the live agent still emitting events?
  - is goal #46 still open?

If anything looks stalled, fires an alert via agent.services.alerts so
Cade gets a phone push.  Also writes a one-line status to
data/heartbeat.log so we have a paper trail.

Designed to be safe to run repeatedly.  Never raises.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOG_PATH = ROOT / "data" / "heartbeat.log"
MARKER = ROOT / "data" / ".last_state_read"

DEFAULT_STALE_MINUTES = 90
DEFAULT_PINNED_GOAL_ID = 46


def _now() -> float:
    return time.time()


def _age_minutes(path: Path) -> float | None:
    if not path.exists():
        return None
    try:
        m = path.stat().st_mtime
        return (_now() - m) / 60.0
    except Exception:
        return None


def _last_event_age_minutes() -> float | None:
    """Approximate idle time using the most recent unified_events row."""
    try:
        from data.db import get_connection
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.execute(
                "SELECT created_at FROM unified_events ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                return None
            ts = row["created_at"] if hasattr(row, "keys") else row[0]
            # SQLite stores 'YYYY-MM-DD HH:MM:SS'
            dt = datetime.fromisoformat(str(ts).replace(" ", "T"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).total_seconds() / 60.0
    except Exception:
        return None


def _pinned_goal_open(goal_id: int) -> bool | None:
    """Open = anything not in a terminal state."""
    OPEN = {"pending", "approved", "in_progress", "paused"}
    try:
        from data.db import get_connection
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.execute(
                "SELECT status FROM proposed_goals WHERE id=?", (goal_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            status = row["status"] if hasattr(row, "keys") else row[0]
            return status in OPEN
    except Exception:
        return None


def _approved_count() -> int:
    try:
        from data.db import get_connection
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM outreach_queue WHERE status='approved'"
            )
            row = cur.fetchone()
            return int((row[0] if not hasattr(row, "keys") else row[0]) or 0)
    except Exception:
        return 0


def _drafted_count() -> int:
    try:
        from data.db import get_connection
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM outreach_queue WHERE status='drafted'"
            )
            row = cur.fetchone()
            return int((row[0] if not hasattr(row, "keys") else row[0]) or 0)
    except Exception:
        return 0


def _alert(msg: str, priority: str = "normal") -> None:
    try:
        from agent.services.alerts import fire_alerts
        fire_alerts(message=msg, priority=priority, source="heartbeat")
    except Exception:
        pass


def _append_log(record: dict) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Autopilot heartbeat / stall detector.")
    ap.add_argument("--stale-minutes", type=float, default=DEFAULT_STALE_MINUTES)
    ap.add_argument("--goal-id", type=int, default=DEFAULT_PINNED_GOAL_ID)
    ap.add_argument("--quiet", action="store_true", help="suppress stdout output")
    args = ap.parse_args(argv)

    state_age = _age_minutes(MARKER)
    event_age = _last_event_age_minutes()
    goal_open = _pinned_goal_open(args.goal_id)
    approved = _approved_count()
    drafted = _drafted_count()

    issues: list[str] = []
    if state_age is None:
        issues.append("turn_start marker missing")
    elif state_age > args.stale_minutes:
        issues.append(f"turn_start marker {state_age:.0f}m old (>{args.stale_minutes:.0f})")

    if event_age is not None and event_age > args.stale_minutes:
        issues.append(f"no events for {event_age:.0f}m")

    if goal_open is False:
        issues.append(f"goal #{args.goal_id} no longer pending")
    elif goal_open is None:
        issues.append(f"goal #{args.goal_id} not found")

    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "state_age_min": round(state_age, 1) if state_age is not None else None,
        "event_age_min": round(event_age, 1) if event_age is not None else None,
        "goal_pinned_open": goal_open,
        "approved_outreach": approved,
        "drafted_outreach": drafted,
        "issues": issues,
    }
    _append_log(record)

    if not args.quiet:
        print(json.dumps(record))

    if issues:
        msg = (f"heartbeat: {len(issues)} issue(s) — " + "; ".join(issues)
               + f" | drafts={drafted} approved={approved}")
        _alert(msg, priority="high")
    elif drafted == 0 and approved == 0:
        # Soft nudge: nothing in the queue at all
        _alert(
            "heartbeat: outreach queue empty — no drafts, no approved sends",
            priority="normal",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
