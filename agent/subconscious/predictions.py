"""
Predictive reflex
=================

The pulse layer.  Each heartbeat we ask: "what should be true right now?"
and emit prediction-error events when it isn't.

Design rules (per overlap principle):
  - Predictions live in reflex (closest existing semantics — "patterns I expect")
  - Violations write to log (because they ARE events)
  - High-weight violations also drop a meta-thought (so they surface in STATE)
  - No LLM calls.  Pure SQL.  Cheap to run on heartbeat.

A Prediction is just a callable that returns either:
  - None / ""           → expectation holds, no violation
  - str (description)   → violation; write event + meta-thought

Each Prediction has a `name`, `owner_thread`, and `severity` (low/med/high).
Severity controls weight + whether it forwards as a meta-thought.

Built-ins are seeded at import time.  Other code can register more via
`register(Prediction(...))`.
"""

from __future__ import annotations

import os
import time
import threading
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional, Dict, Any

from data.db import get_connection


# ─────────────────────────────────────────────────────────────────────
# Types
# ─────────────────────────────────────────────────────────────────────

CheckFn = Callable[[], Optional[str]]


@dataclass
class Prediction:
    name: str                      # unique key e.g. "goals.stale_in_progress"
    owner_thread: str              # which thread owns the expectation
    check: CheckFn                 # returns None=ok, str=violation description
    severity: str = "medium"       # "low" | "medium" | "high"
    description: str = ""          # human-readable expectation


@dataclass
class Violation:
    prediction: str
    owner: str
    severity: str
    detail: str
    at: float = field(default_factory=time.time)


# ─────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────

_registry: Dict[str, Prediction] = {}
_lock = threading.RLock()
_last_violations: List[Violation] = []  # cache last tick's results for STATE


def register(p: Prediction) -> None:
    with _lock:
        _registry[p.name] = p


def list_predictions() -> List[Prediction]:
    with _lock:
        return list(_registry.values())


def last_violations() -> List[Violation]:
    with _lock:
        return list(_last_violations)


# ─────────────────────────────────────────────────────────────────────
# Heartbeat tick
# ─────────────────────────────────────────────────────────────────────

_SEVERITY_WEIGHT = {"low": 0.4, "medium": 0.65, "high": 0.85}


def check_all(*, emit_events: bool = True) -> List[Violation]:
    """
    Run every registered prediction.  For each violation:
      - log_event(event_type='system:prediction_error', ...)  [if emit_events]
      - add_meta_thought(kind='expected', graded=1, ...) for medium/high

    Returns the list of violations (empty if all expectations held).
    """
    global _last_violations
    violations: List[Violation] = []

    with _lock:
        preds = list(_registry.values())

    for p in preds:
        try:
            result = p.check()
        except Exception as e:  # never let one prediction break the heartbeat
            result = f"[prediction errored: {e}]"
        if not result:
            continue
        v = Violation(
            prediction=p.name,
            owner=p.owner_thread,
            severity=p.severity,
            detail=str(result)[:500],
        )
        violations.append(v)

        if emit_events:
            _emit(v, p)

    with _lock:
        _last_violations = violations
    return violations


def _emit(v: Violation, p: Prediction) -> None:
    # 1. Always: log to unified_events
    try:
        from agent.threads.log import log_event
        log_event(
            event_type="system:prediction_error",
            data=f"{v.prediction}: {v.detail}",
            metadata={
                "prediction": v.prediction,
                "owner": v.owner,
                "severity": v.severity,
                "expectation": p.description,
            },
            source="system",
            thread_subject="predictions",
            tags=["prediction_error", v.owner, v.severity],
        )
    except Exception:
        pass

    # 2. Medium/high: also drop a meta-thought so it surfaces in STATE
    if v.severity in ("medium", "high"):
        try:
            from agent.threads.reflex.schema import add_meta_thought
            add_meta_thought(
                kind="expected",
                content=f"{p.description or p.name} → violated: {v.detail}",
                source="system",
                confidence=0.9,
                weight=_SEVERITY_WEIGHT.get(v.severity, 0.6),
            )
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────
# Built-in predictions
# ─────────────────────────────────────────────────────────────────────
#
# Each one is a small SQL probe.  Add only checks that are CHEAP and
# yield actionable signal.  If a check needs an LLM, it does not belong
# here — promote it to a loop instead.


def _check_goal_staleness() -> Optional[str]:
    """
    Expectation: a goal in_progress shows up in events within the last 7 days.
    Violation: any in_progress goal silent for >7 days.
    """
    try:
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                """
                SELECT pg.id, pg.goal AS title
                FROM proposed_goals pg
                WHERE pg.status = 'in_progress'
                  AND julianday('now') - julianday(pg.created_at) > 7
                  AND NOT EXISTS (
                      SELECT 1 FROM unified_events ue
                      WHERE ue.related_table = 'proposed_goals'
                        AND ue.related_key = CAST(pg.id AS TEXT)
                        AND julianday('now') - julianday(ue.timestamp) < 7
                  )
                LIMIT 5
                """,
            ).fetchall()
        if not rows:
            return None
        names = ", ".join(f"#{r['id']} '{(r['title'] or '')[:40]}'" for r in rows)
        return f"{len(rows)} in_progress goal(s) silent >7d: {names}"
    except Exception:
        return None


def _check_task_backlog() -> Optional[str]:
    """
    Expectation: pending task_queue rows stay below 20.
    Violation: more than that means the worker isn't draining.
    """
    threshold = int(os.getenv("AIOS_PRED_TASK_BACKLOG", "20"))
    try:
        with closing(get_connection(readonly=True)) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM task_queue WHERE status = 'pending'"
            ).fetchone()
        n = int(row["n"]) if row else 0
        if n > threshold:
            return f"task_queue has {n} pending (>{threshold})"
        return None
    except Exception:
        return None


def _check_trigger_silence() -> Optional[str]:
    """
    Expectation: enabled poll-triggers fire within 3x their poll_interval.
    Violation: any trigger overdue by more than 3x.
    """
    try:
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                """
                SELECT id, name, poll_interval, last_polled
                FROM reflex_triggers
                WHERE enabled = 1
                  AND poll_interval IS NOT NULL
                  AND poll_interval > 0
                  AND last_polled IS NOT NULL
                """,
            ).fetchall()
        offenders: List[str] = []
        for r in rows:
            interval = int(r["poll_interval"] or 0)
            if interval <= 0:
                continue
            try:
                last = datetime.fromisoformat(str(r["last_polled"]).replace("Z", ""))
            except Exception:
                continue
            elapsed = (datetime.utcnow() - last).total_seconds()
            if elapsed > 3 * interval:
                offenders.append(
                    f"#{r['id']} {r['name']} ({int(elapsed)}s elapsed vs {interval}s)"
                )
        if not offenders:
            return None
        return f"{len(offenders)} trigger(s) overdue: " + "; ".join(offenders[:5])
    except Exception:
        return None


def _check_loop_error_streak() -> Optional[str]:
    """
    Expectation: most recent run of every loop is not an ERROR.
    Violation: any loop whose last_result starts with 'ERROR' or 'Health check error'.
    """
    try:
        from agent.subconscious.core import get_core
        mgr = get_core().loop_manager
        if not mgr:
            return None
        bad: List[str] = []
        for loop in mgr.list_loops():
            lr = (loop._last_result or "").strip()
            if not lr:
                continue
            head = lr[:80].lower()
            if head.startswith("error") or "exception" in head or "traceback" in head:
                bad.append(f"{loop.config.name}: {lr[:60]}")
        if not bad:
            return None
        return f"{len(bad)} loop(s) erroring: " + " | ".join(bad[:3])
    except Exception:
        return None


def _check_disk_pressure() -> Optional[str]:
    """
    Expectation: state.db stays under a soft cap.
    Violation: file size exceeds AIOS_PRED_DB_MB_SOFT (default 2048 MB).
    """
    cap_mb = float(os.getenv("AIOS_PRED_DB_MB_SOFT", "2048"))
    try:
        path = os.path.join("data", "db", "state.db")
        if not os.path.exists(path):
            return None
        mb = os.path.getsize(path) / (1024 * 1024)
        if mb > cap_mb:
            return f"state.db is {mb:.1f}MB (>{cap_mb:.0f}MB soft cap)"
        return None
    except Exception:
        return None


# Seed registry at import time
register(Prediction(
    name="goals.stale_in_progress",
    owner_thread="goals",
    severity="medium",
    description="every in_progress goal touches an event within 7 days",
    check=_check_goal_staleness,
))
register(Prediction(
    name="tasks.backlog",
    owner_thread="log",
    severity="medium",
    description="task_queue pending count stays below soft cap",
    check=_check_task_backlog,
))
register(Prediction(
    name="triggers.silence",
    owner_thread="reflex",
    severity="medium",
    description="enabled poll-triggers fire within 3x their poll_interval",
    check=_check_trigger_silence,
))
register(Prediction(
    name="loops.error_streak",
    owner_thread="form",
    severity="high",
    description="loops do not leave their last run in an ERROR state",
    check=_check_loop_error_streak,
))
register(Prediction(
    name="storage.db_size",
    owner_thread="log",
    severity="low",
    description="state.db stays under soft size cap",
    check=_check_disk_pressure,
))


__all__ = [
    "Prediction",
    "Violation",
    "register",
    "list_predictions",
    "last_violations",
    "check_all",
]
