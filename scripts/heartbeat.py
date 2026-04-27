#!/usr/bin/env python3
"""
scripts/heartbeat.py — autopilot stall detector + transition pinger.

Runs from cron / launchd every N minutes.  Two jobs:

  1. STALL DETECTION: fires alert if state is stale or queue is empty.
  2. TRANSITION PINGS: fires alert when something *changed* since the
     last heartbeat — new commit, outreach status moved, goal #46
     status moved.  Both Cade and the next agent turn see it.

State tracked in data/heartbeat.state.json.  First run is baseline-
only; transitions never fire on a cold cache.

Never raises.  Safe to run repeatedly.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOG_PATH = ROOT / "data" / "heartbeat.log"
STATE_PATH = ROOT / "data" / "heartbeat.state.json"
MARKER = ROOT / "data" / ".last_state_read"

DEFAULT_STALE_MINUTES = 90
DEFAULT_PINNED_GOAL_ID = 46


# ── Filesystem / time helpers ─────────────────────────────────────────

def _now_ts() -> float:
    return time.time()


def _age_minutes(path: Path) -> float | None:
    if not path.exists():
        return None
    try:
        return (_now_ts() - path.stat().st_mtime) / 60.0
    except Exception:
        return None


# ── DB queries ────────────────────────────────────────────────────────

def _last_event_age_minutes() -> float | None:
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
            dt = datetime.fromisoformat(str(ts).replace(" ", "T"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).total_seconds() / 60.0
    except Exception:
        return None


def _goal_status(goal_id: int) -> str | None:
    try:
        from data.db import get_connection
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.execute(
                "SELECT status FROM proposed_goals WHERE id=?", (goal_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return row["status"] if hasattr(row, "keys") else row[0]
    except Exception:
        return None


def _pinned_goal_open(goal_id: int) -> bool | None:
    OPEN = {"pending", "approved", "in_progress", "paused"}
    s = _goal_status(goal_id)
    if s is None:
        return None
    return s in OPEN


def _outreach_counts() -> dict:
    out = {"drafted": 0, "approved": 0, "sent": 0, "failed": 0, "rejected": 0}
    try:
        from data.db import get_connection
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.execute(
                "SELECT status, COUNT(*) AS n FROM outreach_queue GROUP BY status"
            )
            for row in cur.fetchall():
                k = row["status"] if hasattr(row, "keys") else row[0]
                v = row["n"] if hasattr(row, "keys") else row[1]
                if k in out:
                    out[k] = int(v or 0)
    except Exception:
        pass
    return out


# ── Git helpers ──────────────────────────────────────────────────────

def _git_head() -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, timeout=5,
        )
        return out.decode().strip()
    except Exception:
        return ""


def _git_subject(sha: str) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(ROOT), "log", "-1", "--format=%s", sha],
            stderr=subprocess.DEVNULL, timeout=5,
        )
        return out.decode().strip()
    except Exception:
        return ""


# ── State persistence ────────────────────────────────────────────────

def _read_prev_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {}


def _write_prev_state(d: dict) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(d, indent=2))
    except Exception:
        pass


def _detect_transitions(prev: dict, curr: dict, goal_id: int) -> list[str]:
    lines: list[str] = []
    if not prev:
        return lines  # baseline — never fire on first run

    if prev.get("git_head") and curr.get("git_head") \
            and prev["git_head"] != curr["git_head"]:
        subject = _git_subject(curr["git_head"])
        lines.append(f"commit {curr['git_head']}: {subject[:80]}")

    p_oc = prev.get("outreach", {}) or {}
    c_oc = curr.get("outreach", {}) or {}
    for status in ("approved", "sent", "failed"):
        delta = c_oc.get(status, 0) - p_oc.get(status, 0)
        if delta > 0:
            lines.append(f"outreach +{delta} {status}")
    # Drafted is informational: only flag *new* drafts (positive delta)
    delta_d = c_oc.get("drafted", 0) - p_oc.get("drafted", 0)
    if delta_d > 0:
        lines.append(f"outreach +{delta_d} drafted")

    if prev.get("goal_status") and curr.get("goal_status") \
            and prev["goal_status"] != curr["goal_status"]:
        lines.append(
            f"goal #{goal_id}: {prev['goal_status']} → {curr['goal_status']}"
        )

    return lines


# ── Output ────────────────────────────────────────────────────────────

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


# ── Main ─────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Autopilot heartbeat / transition pinger.")
    ap.add_argument("--stale-minutes", type=float, default=DEFAULT_STALE_MINUTES)
    ap.add_argument("--goal-id", type=int, default=DEFAULT_PINNED_GOAL_ID)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    state_age = _age_minutes(MARKER)
    event_age = _last_event_age_minutes()
    goal_status = _goal_status(args.goal_id)
    goal_open = goal_status in {"pending", "approved", "in_progress", "paused"} \
        if goal_status else None
    git_head = _git_head()
    outreach = _outreach_counts()

    issues: list[str] = []
    if state_age is None:
        issues.append("turn_start marker missing")
    elif state_age > args.stale_minutes:
        issues.append(f"state_age={state_age:.0f}m (>{args.stale_minutes:.0f})")

    if event_age is not None and event_age > args.stale_minutes:
        issues.append(f"no events {event_age:.0f}m")

    if goal_open is False:
        issues.append(f"goal #{args.goal_id} closed ({goal_status})")
    elif goal_open is None:
        issues.append(f"goal #{args.goal_id} not found")

    prev = _read_prev_state()
    curr = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_head": git_head,
        "outreach": outreach,
        "goal_status": goal_status,
    }
    transitions = _detect_transitions(prev, curr, args.goal_id)

    record = {
        **curr,
        "state_age_min": round(state_age, 1) if state_age is not None else None,
        "event_age_min": round(event_age, 1) if event_age is not None else None,
        "goal_pinned_open": goal_open,
        "issues": issues,
        "transitions": transitions,
    }
    _append_log(record)
    _write_prev_state(curr)

    if not args.quiet:
        print(json.dumps(record))

    # Stall alerts
    if issues:
        _alert(
            "heartbeat stall: " + "; ".join(issues)
            + f" | q={outreach.get('drafted',0)}d/{outreach.get('approved',0)}a/{outreach.get('sent',0)}s",
            priority="high",
        )
    elif sum(outreach.values()) == 0:
        _alert(
            "heartbeat: outreach queue empty — no drafts, no approved, no sent",
            priority="normal",
        )

    # Transition pings (the new behavior — Cade asked for this)
    if transitions:
        _alert("heartbeat Δ: " + " | ".join(transitions), priority="normal")

    return 0


if __name__ == "__main__":
    sys.exit(main())
