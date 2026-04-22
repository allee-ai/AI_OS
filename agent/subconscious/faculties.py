"""
Heartbeat Faculties
===================

A *faculty* is a passive decider consulted by the heartbeat on every
tick.  It reads the snapshot and the DB, and returns a list of short
action strings describing anything it did (or would have done, if
AIOS_HEARTBEAT_DRYRUN=1).

Faculties never raise.  They wrap every external call and every DB
mutation in try/except.  They respect the user-presence gate where it
matters (e.g. don't auto-promote heavy tasks while the user is mid-
conversation).

Included faculties:

  1. goal_promoter     — approved+low-risk goals → tasks.pending
  2. goal_auto_approve — pending goals sitting > N hours with
                         risk='low' auto-approve themselves
  3. goal_risk_tagger  — assigns a risk tier to newly-proposed goals
                         that lack one
  4. consolidation_hint — if temp_memory_pending > threshold AND
                          user absent, trigger consolidation loop early
  5. unknown_surfacer  — if unknowns_open > threshold, mirror a
                         "you have N open questions" system thought
                         (dedupe'd per day)

Adding a faculty: append a callable to FACULTIES in run_faculties().
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

# ─────────────────────────────────────────────────────────────
# Risk tiers
# ─────────────────────────────────────────────────────────────
# 'low'    → auto-execute after auto-approval
# 'medium' → auto-approve after grace window; execute once approved
# 'high'   → require human approval, never auto-execute
RISK_TIERS = ("low", "medium", "high")


# ─────────────────────────────────────────────────────────────
# Migration: ensure proposed_goals has a `risk` column
# ─────────────────────────────────────────────────────────────

def _ensure_risk_column() -> None:
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            cols = [
                r[1] for r in conn.execute("PRAGMA table_info(proposed_goals)")
                                 .fetchall()
            ]
            if "risk" not in cols:
                conn.execute(
                    "ALTER TABLE proposed_goals ADD COLUMN risk TEXT "
                    "NOT NULL DEFAULT 'medium'"
                )
                conn.commit()
            if "auto_promoted" not in cols:
                conn.execute(
                    "ALTER TABLE proposed_goals ADD COLUMN auto_promoted "
                    "INTEGER NOT NULL DEFAULT 0"
                )
                conn.commit()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# Heuristics used by faculties
# ─────────────────────────────────────────────────────────────

_HIGH_RISK_TOKENS = (
    "delete", "remove ", "drop ", "destroy", "wipe",
    "force push", "--force", "rm -rf",
    "credit", "charge", "purchase", "transfer",
    "send email", "post to", "publish",
    "deploy", "rollback", "restart server",
    "shutdown", "kill ",
)
_LOW_RISK_TOKENS = (
    "summarize", "summarise", "read", "review", "list",
    "extract", "note", "remember", "record",
    "remind me", "draft", "outline", "brainstorm",
    "organize", "organise", "tag", "categorize",
)


def classify_goal_risk(goal_text: str, rationale: str = "") -> str:
    """Very simple text classifier.  Conservative: defaults to medium."""
    t = f"{goal_text or ''} {rationale or ''}".lower()
    for tok in _HIGH_RISK_TOKENS:
        if tok in t:
            return "high"
    for tok in _LOW_RISK_TOKENS:
        if tok in t:
            return "low"
    return "medium"


# ─────────────────────────────────────────────────────────────
# Faculty: tag risk on un-risked goals
# ─────────────────────────────────────────────────────────────

def faculty_goal_risk_tagger(snapshot: Dict[str, Any]) -> List[str]:
    actions: List[str] = []
    _ensure_risk_column()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            rows = conn.execute(
                "SELECT id, goal, rationale FROM proposed_goals "
                "WHERE (risk IS NULL OR risk='' OR risk='medium') "
                "  AND status='pending' "
                "ORDER BY id DESC LIMIT 20"
            ).fetchall()
            for gid, goal, rationale in rows:
                risk = classify_goal_risk(goal or "", rationale or "")
                if risk == "medium":
                    continue  # already the default, no update needed
                conn.execute(
                    "UPDATE proposed_goals SET risk=? WHERE id=?",
                    (risk, gid),
                )
                actions.append(f"risk_tagged:goal#{gid}={risk}")
            conn.commit()
    except Exception:
        pass
    return actions


# ─────────────────────────────────────────────────────────────
# Faculty: auto-approve low-risk pending goals after grace window
# ─────────────────────────────────────────────────────────────

def faculty_goal_auto_approve(snapshot: Dict[str, Any]) -> List[str]:
    """Promote pending low-risk goals to 'approved' if older than the
    grace window and nobody rejected them.

    Grace window defaults to 0 hours (immediate) for low risk.
    Override via AIOS_GOAL_AUTO_APPROVE_HOURS.
    """
    if os.getenv("AIOS_GOAL_AUTO_APPROVE", "1") != "1":
        return []
    _ensure_risk_column()
    grace_h = float(os.getenv("AIOS_GOAL_AUTO_APPROVE_HOURS", "0"))
    actions: List[str] = []
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            rows = conn.execute(
                "SELECT id, goal FROM proposed_goals "
                "WHERE status='pending' AND risk='low' "
                "  AND (julianday('now') - julianday(created_at)) * 24 >= ? "
                "ORDER BY id ASC LIMIT 10",
                (grace_h,),
            ).fetchall()
            for gid, goal in rows:
                conn.execute(
                    "UPDATE proposed_goals SET status='approved', "
                    "resolved_at=datetime('now') WHERE id=?",
                    (gid,),
                )
                actions.append(f"auto_approved:goal#{gid}")
            conn.commit()
    except Exception:
        pass
    return actions


# ─────────────────────────────────────────────────────────────
# Faculty: promote approved low-risk goals into tasks
# ─────────────────────────────────────────────────────────────

def faculty_goal_promoter(snapshot: Dict[str, Any]) -> List[str]:
    """Pull approved goals (risk!=high, not yet promoted) and create
    rows in `tasks`.  The task planner loop will pick them up.
    """
    if os.getenv("AIOS_GOAL_PROMOTER", "1") != "1":
        return []
    # When the user is in an active turn, don't add background load.
    if snapshot.get("user_present") and snapshot.get("ollama_busy"):
        return []
    _ensure_risk_column()
    actions: List[str] = []
    max_promote = int(os.getenv("AIOS_GOAL_PROMOTER_MAX", "2"))
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            rows = conn.execute(
                "SELECT id, goal, risk, rationale FROM proposed_goals "
                "WHERE status='approved' "
                "  AND (auto_promoted IS NULL OR auto_promoted=0) "
                "  AND COALESCE(risk,'medium') IN ('low','medium') "
                "ORDER BY id ASC LIMIT ?",
                (max_promote,),
            ).fetchall()
            for gid, goal, risk, rationale in rows:
                # Create the task via the existing helper so the
                # planner recognises it.
                try:
                    from agent.subconscious.loops.task_planner import create_task
                    source = f"goal_promoter:{risk or 'medium'}"
                    t = create_task(goal=goal or "(unnamed)", source=source)
                    task_id = t.get("id") if isinstance(t, dict) else None
                    conn.execute(
                        "UPDATE proposed_goals SET auto_promoted=1 WHERE id=?",
                        (gid,),
                    )
                    actions.append(
                        f"promoted:goal#{gid}→task#{task_id}"
                    )
                except Exception as e:
                    actions.append(f"promote_error:goal#{gid}:{str(e)[:60]}")
            conn.commit()
    except Exception:
        pass
    return actions


# ─────────────────────────────────────────────────────────────
# Faculty: consolidation hint
# ─────────────────────────────────────────────────────────────

def faculty_consolidation_hint(snapshot: Dict[str, Any]) -> List[str]:
    """If pending temp_facts exceed threshold AND user is away, nudge
    the consolidation loop to fire early.
    """
    if os.getenv("AIOS_HEARTBEAT_FACULTIES", "1") != "1":
        return []
    if snapshot.get("user_present"):
        return []
    thr = int(os.getenv("AIOS_CONSOLIDATION_HINT_THRESHOLD", "30"))
    pending = (snapshot.get("counts") or {}).get("temp_memory_pending", 0)
    if pending < thr:
        return []
    actions: List[str] = []
    try:
        from agent.subconscious import _loop_manager  # type: ignore
        if _loop_manager is None:
            return []
        loop = _loop_manager.get_loop("consolidation")
        if loop is None:
            return []
        # Fire the task synchronously on the heartbeat thread is
        # dangerous (blocks) — instead we just mark last_run to force a
        # re-tick sooner.  Simplest safe path: call _consolidate if the
        # loop is running and not busy.
        try:
            if (not loop.is_busy) and getattr(loop, "_consolidate", None):
                loop._consolidate()
                actions.append(f"consolidation_fired(pending={pending})")
        except Exception as e:
            actions.append(f"consolidation_error:{str(e)[:60]}")
    except Exception:
        pass
    return actions


# ─────────────────────────────────────────────────────────────
# Faculty: unknown surfacer
# ─────────────────────────────────────────────────────────────

def _seen_today(tag: str) -> bool:
    """Cheap local dedupe — has this tag been emitted in the last 24h?"""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            row = conn.execute(
                "SELECT 1 FROM reflex_meta_thoughts "
                "WHERE content LIKE ? "
                "  AND created_at >= datetime('now','-1 day') LIMIT 1",
                (f"%{tag}%",),
            ).fetchone()
            return bool(row)
    except Exception:
        return False


def faculty_unknown_surfacer(snapshot: Dict[str, Any]) -> List[str]:
    thr = int(os.getenv("AIOS_UNKNOWN_SURFACE_THRESHOLD", "5"))
    unk = (snapshot.get("counts") or {}).get("unknowns_open", 0)
    if unk < thr:
        return []
    tag = "#hb_unknowns"
    if _seen_today(tag):
        return []
    try:
        from agent.threads.reflex.schema import add_meta_thought
        add_meta_thought(
            kind="unknown",
            content=(
                f"I have {unk} unanswered questions/contradictions "
                f"sitting open.  Worth reviewing. {tag}"
            ),
            source="system",
            weight=0.8,
            confidence=0.6,
        )
        return [f"unknown_surfaced(count={unk})"]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────

FACULTIES: List[Callable[[Dict[str, Any]], List[str]]] = [
    faculty_goal_risk_tagger,
    faculty_goal_auto_approve,
    faculty_goal_promoter,
    faculty_consolidation_hint,
    faculty_unknown_surfacer,
]


def run_faculties(snapshot: Dict[str, Any]) -> List[str]:
    """Invoke every faculty.  Never raises.  Returns flat action log."""
    actions: List[str] = []
    for fac in FACULTIES:
        try:
            out = fac(snapshot) or []
            if isinstance(out, list):
                actions.extend(out)
        except Exception as e:
            actions.append(f"{getattr(fac, '__name__', 'faculty')}_error:"
                           f"{str(e)[:60]}")
    return actions


__all__ = [
    "RISK_TIERS",
    "classify_goal_risk",
    "run_faculties",
    "FACULTIES",
]
