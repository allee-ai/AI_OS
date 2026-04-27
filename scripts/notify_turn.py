#!/usr/bin/env python3
"""
scripts/notify_turn.py — explicit start/finish notifications.

Sends a phone push (via fire_alerts) AND logs an event so STATE shows it
on the next turn-start.  Both Cade and I see every transition.

Usage:
    notify_turn.py start  "<one-line summary>"
    notify_turn.py finish "<one-line summary>" [--ok | --partial | --failed]
    notify_turn.py update "<text>"     # mid-turn ping for long jobs

The start/finish events become the canonical record of "what Copilot
was doing and when it stopped".
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _alert(msg: str, priority: str, nid: str | None) -> None:
    try:
        from agent.services.alerts import fire_alerts
        fire_alerts(message=msg, priority=priority, nid=nid, source="copilot_turn")
    except Exception:
        pass


def _log(event_type: str, data: str, metadata: dict | None = None) -> None:
    try:
        from agent.threads.log.schema import log_event
        log_event(
            event_type=event_type,
            data=data,
            metadata=metadata or {},
            source="scripts/notify_turn.py",
        )
    except Exception:
        pass


def cmd_start(args) -> int:
    text = args.text.strip()[:200]
    msg = f"▶ start: {text}"
    _alert(msg, priority=args.priority, nid="turn:start")
    _log("turn_event", msg, {"phase": "start", "summary": text})
    print(msg)
    return 0


def cmd_finish(args) -> int:
    text = args.text.strip()[:200]
    if args.failed:
        prefix, prio = "✗ failed", "high"
    elif args.partial:
        prefix, prio = "~ partial", "normal"
    else:
        prefix, prio = "✓ done", "normal"
    msg = f"{prefix}: {text}"
    _alert(msg, priority=prio, nid="turn:finish")
    _log("turn_event", msg, {"phase": "finish", "summary": text,
                              "result": prefix.split()[1]})
    print(msg)
    return 0


def cmd_update(args) -> int:
    text = args.text.strip()[:200]
    msg = f"… {text}"
    _alert(msg, priority="low", nid="turn:update")
    _log("turn_event", msg, {"phase": "update", "summary": text})
    print(msg)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("start")
    ps.add_argument("text")
    ps.add_argument("--priority", default="normal",
                    choices=["low", "normal", "high", "urgent"])

    pf = sub.add_parser("finish")
    pf.add_argument("text")
    g = pf.add_mutually_exclusive_group()
    g.add_argument("--ok", action="store_true")
    g.add_argument("--partial", action="store_true")
    g.add_argument("--failed", action="store_true")

    pu = sub.add_parser("update")
    pu.add_argument("text")

    args = ap.parse_args(argv)
    return {"start": cmd_start, "finish": cmd_finish, "update": cmd_update}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
