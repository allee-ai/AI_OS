"""
Reflex Schedule Loop
====================
Evaluates cron-expression triggers on a background tick.

Uses the BackgroundLoop infrastructure for error recovery, backoff, and
graceful shutdown.

Flow:
  1. Every *interval_seconds* the loop queries reflex_triggers where
     trigger_type='schedule' AND cron_expression IS NOT NULL AND enabled=1.
  2. For each trigger it checks whether the cron expression matches the
     current minute (wall-clock time, local timezone).
  3. Matching triggers are dispatched through the normal executor flow
     (which now respects response_mode: tool / agent / notify).

Cron format (5-field):
  minute  hour  day-of-month  month  day-of-week
  Supports: *, */N, N, N-M, comma-separated lists.
  e.g. "30 8 * * 1-5" → 08:30 on weekdays.
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional

from .schema import get_triggers, record_trigger_execution


# ---------------------------------------------------------------------------
# Lightweight cron matcher (no external dependency)
# ---------------------------------------------------------------------------

def _cron_field_matches(field_spec: str, value: int, min_val: int, max_val: int) -> bool:
    """Check if *value* matches a single cron field specification."""
    for part in field_spec.split(","):
        part = part.strip()
        if part == "*":
            return True

        # */N  — every N
        if part.startswith("*/"):
            try:
                step = int(part[2:])
                if step > 0 and value % step == 0:
                    return True
            except ValueError:
                pass
            continue

        # N-M  — range
        if "-" in part:
            try:
                lo, hi = part.split("-", 1)
                if int(lo) <= value <= int(hi):
                    return True
            except ValueError:
                pass
            continue

        # Exact match
        try:
            if int(part) == value:
                return True
        except ValueError:
            pass

    return False


def cron_matches_now(cron_expression: str, now: Optional[datetime] = None) -> bool:
    """Return True if *cron_expression* matches the current (or given) minute.

    Accepts standard 5-field cron: minute hour dom month dow.
    """
    if not cron_expression or not cron_expression.strip():
        return False

    fields = cron_expression.strip().split()
    if len(fields) != 5:
        return False

    now = now or datetime.now()
    minute, hour, dom, month, dow = fields

    if not _cron_field_matches(minute, now.minute, 0, 59):
        return False
    if not _cron_field_matches(hour, now.hour, 0, 23):
        return False
    if not _cron_field_matches(dom, now.day, 1, 31):
        return False
    if not _cron_field_matches(month, now.month, 1, 12):
        return False
    # isoweekday: Mon=1..Sun=7 → cron uses 0=Sun..6=Sat
    cron_dow = now.weekday()  # Mon=0..Sun=6  — close enough for standard cron 1-5
    # Map: cron 0=Sun,1=Mon..6=Sat ↔ Python weekday() Mon=0..Sun=6
    # We store cron-compatible: 0=Sun, 1=Mon … 6=Sat
    py_dow = (now.weekday() + 1) % 7  # Mon→1, Sun→0
    if not _cron_field_matches(dow, py_dow, 0, 6):
        return False

    return True


# ---------------------------------------------------------------------------
# Tick function — called by BackgroundLoop on each interval
# ---------------------------------------------------------------------------

def _schedule_tick() -> None:
    """Check all schedule triggers against current time and fire matches."""
    triggers = get_triggers(enabled_only=True)
    schedule_triggers = [
        t for t in triggers
        if t.get("trigger_type") == "schedule" and t.get("cron_expression")
    ]

    if not schedule_triggers:
        return

    now = datetime.now()
    fired: List[str] = []

    for trigger in schedule_triggers:
        cron_expr = trigger["cron_expression"]
        if not cron_matches_now(cron_expr, now):
            continue

        # Guard: don't fire if already fired this same minute
        last_exec = trigger.get("last_executed")
        if last_exec:
            try:
                last_dt = datetime.fromisoformat(last_exec)
                if (last_dt.year == now.year and last_dt.month == now.month
                        and last_dt.day == now.day and last_dt.hour == now.hour
                        and last_dt.minute == now.minute):
                    continue
            except Exception:
                pass

        # Dispatch through executor (which branches on response_mode)
        _fire_trigger(trigger)
        fired.append(trigger.get("name", str(trigger["id"])))

    if fired:
        print(f"[SCHEDULE] Fired {len(fired)} trigger(s): {', '.join(fired)}")


def _fire_trigger(trigger: Dict[str, Any]) -> None:
    """Execute a single schedule trigger through the reflex executor."""
    from .executor import execute_matching_triggers  # avoid circular at module level

    trigger_id = trigger["id"]
    payload: Dict[str, Any] = {
        "scheduled": True,
        "cron_expression": trigger.get("cron_expression"),
        "fired_at": datetime.now().isoformat(),
    }

    # Build a synthetic event payload and call the matching-triggers path
    # We call the per-trigger branch directly to avoid re-querying.
    async def _run():
        from .executor import (
            check_condition,
            execute_tool_action,
            _escalate_to_agent,
            _notify_only,
        )
        import json as _json

        condition = trigger.get("condition") or trigger.get("condition_json")
        if isinstance(condition, str):
            try:
                condition = _json.loads(condition)
            except Exception:
                condition = None

        # condition check still honoured (e.g. "only on weekdays")
        if not check_condition(condition, payload):
            return

        response_mode = trigger.get("response_mode", "tool")
        tool_params = trigger.get("tool_params") or trigger.get("tool_params_json")
        if isinstance(tool_params, str):
            try:
                tool_params = _json.loads(tool_params)
            except Exception:
                tool_params = {}

        if response_mode == "agent":
            result = await _escalate_to_agent(
                trigger, payload,
                trigger.get("feed_name", "schedule"),
                trigger.get("event_type", "cron_fired"),
            )
        elif response_mode == "notify":
            result = _notify_only(
                trigger, payload,
                trigger.get("feed_name", "schedule"),
                trigger.get("event_type", "cron_fired"),
            )
        else:
            result = await execute_tool_action(
                tool_name=trigger.get("tool_name", ""),
                tool_action=trigger.get("tool_action", ""),
                tool_params=tool_params,
                event_payload=payload,
            )

        record_trigger_execution(
            trigger_id=trigger_id,
            success=result.get("success", False),
            error=result.get("error"),
        )

        # Log
        try:
            from agent.threads.log.schema import log_event
            log_event(
                event_type="trigger",
                data=f"Schedule trigger '{trigger.get('name')}' fired ({response_mode})",
                metadata={
                    "trigger_id": trigger_id,
                    "cron_expression": trigger.get("cron_expression"),
                    "response_mode": response_mode,
                    "success": result.get("success", False),
                },
                source="reflex",
            )
        except Exception:
            pass

    # Run the async dispatch
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_run())
        else:
            loop.run_until_complete(_run())
    except RuntimeError:
        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Public start / stop / status helpers (mirror Feeds/polling.py pattern)
# ---------------------------------------------------------------------------

_loop_instance = None


def start_schedule_loop(interval_seconds: int = 60) -> None:
    """Start the cron schedule loop (called once from server.py)."""
    global _loop_instance
    if _loop_instance is not None:
        return  # already running

    try:
        from agent.subconscious.loops import BackgroundLoop, LoopConfig

        config = LoopConfig(
            interval_seconds=interval_seconds,
            name="reflex_schedule",
            enabled=True,
            max_errors=5,
            error_backoff=2.0,
        )
        _loop_instance = BackgroundLoop(config, _schedule_tick)
        _loop_instance.start()
        print(f"⏰ Reflex schedule loop started (every {interval_seconds}s)")
    except ImportError:
        print("[SCHEDULE] BackgroundLoop not available — schedule loop disabled")


def stop_schedule_loop() -> None:
    """Stop the schedule loop."""
    global _loop_instance
    if _loop_instance:
        _loop_instance.stop()
        _loop_instance = None


def get_schedule_status() -> Dict[str, Any]:
    """Return current schedule loop status."""
    if _loop_instance is None:
        return {"status": "stopped"}
    return _loop_instance.stats
