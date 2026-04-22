"""
Goal Generation Loop
====================
Reads recurring concepts from linking_core, values from philosophy,
and recent activity from log to propose candidate goals.

Goals are stored in temp_memory with source="goal_loop" for human approval
before being promoted to active tasks.
"""

import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from .base import BackgroundLoop, LoopConfig


# ─────────────────────────────────────────────────────────────
# Goal DB helpers
# ─────────────────────────────────────────────────────────────

def _ensure_goals_table() -> None:
    """Create proposed_goals table if it doesn't exist."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS proposed_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal TEXT NOT NULL,
                    rationale TEXT NOT NULL DEFAULT '',
                    priority TEXT NOT NULL DEFAULT 'medium',
                    sources TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    resolved_at TEXT
                )
            """)
            conn.commit()
    except Exception as e:
        print(f"[GoalLoop] Failed to create table: {e}")


def propose_goal(goal: str, rationale: str = "", priority: str = "medium",
                 sources: Optional[List[str]] = None) -> int:
    """Store a proposed goal for human review. Returns goal ID."""
    _ensure_goals_table()
    # Compute risk tier up front so faculties / UI see it immediately.
    try:
        from agent.subconscious.faculties import (
            classify_goal_risk, _ensure_risk_column,
        )
        _ensure_risk_column()
        risk = classify_goal_risk(goal, rationale)
    except Exception:
        risk = "medium"
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "INSERT INTO proposed_goals "
                    "(goal, rationale, priority, sources, risk) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (goal, rationale, priority,
                     json.dumps(sources or []), risk)
                )
            except Exception:
                # Column may not exist yet in older DBs
                cur.execute(
                    "INSERT INTO proposed_goals (goal, rationale, priority, sources) VALUES (?, ?, ?, ?)",
                    (goal, rationale, priority, json.dumps(sources or []))
                )
            conn.commit()
            new_id = cur.lastrowid or 0
        # Mirror → shared meta bus (source='system', kind='expected').
        try:
            from agent.subconscious.meta_mirror import mirror_to_meta
            w = {"urgent": 0.9, "high": 0.8, "medium": 0.7, "low": 0.5}.get(
                (priority or "medium").lower(), 0.7
            )
            content = goal if not rationale else f"{goal} — {rationale}"
            mirror_to_meta(
                kind_hint="goal",
                content=content,
                weight=w,
                confidence=0.6,
            )
        except Exception:
            pass
        return new_id
    except Exception as e:
        print(f"[GoalLoop] Failed to propose goal: {e}")
        return 0


def get_proposed_goals(status: str = "pending", limit: int = 20) -> List[Dict[str, Any]]:
    """Get proposed goals filtered by status."""
    _ensure_goals_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, goal, rationale, priority, sources, status, created_at, resolved_at "
                "FROM proposed_goals WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status, limit)
            )
            return [
                {
                    "id": r[0], "goal": r[1], "rationale": r[2],
                    "priority": r[3], "sources": json.loads(r[4]),
                    "status": r[5], "created_at": r[6], "resolved_at": r[7],
                }
                for r in cur.fetchall()
            ]
    except Exception:
        return []


def resolve_goal(goal_id: int, status: str = "approved") -> bool:
    """Approve, reject, or dismiss a proposed goal."""
    if status not in ("approved", "rejected", "dismissed"):
        return False
    _ensure_goals_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute(
                "UPDATE proposed_goals SET status = ?, resolved_at = datetime('now') WHERE id = ?",
                (status, goal_id)
            )
            conn.commit()
            return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# Context gathering
# ─────────────────────────────────────────────────────────────

def _get_recurring_concepts(limit: int = 10) -> List[Dict[str, Any]]:
    """Get high-weight concepts from linking_core focus + concept graph."""
    results = []
    try:
        from agent.threads.linking_core.schema import get_focus
        focus = get_focus(limit=limit)
        for topic, weight in focus.items():
            results.append({"concept": topic, "weight": weight, "source": "focus"})
    except Exception:
        pass
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT concept, weight FROM concepts ORDER BY weight DESC LIMIT ?",
                (limit,)
            )
            for r in cur.fetchall():
                results.append({"concept": r[0], "weight": r[1], "source": "graph"})
    except Exception:
        pass
    return results


def _get_values(limit: int = 10) -> List[str]:
    """Get current philosophy/value statements."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT content FROM facts WHERE thread = 'philosophy' AND status = 'approved' "
                "ORDER BY updated_at DESC LIMIT ?",
                (limit,)
            )
            return [r[0] for r in cur.fetchall()]
    except Exception:
        return []


def _get_recent_activity(limit: int = 10) -> List[str]:
    """Get recent log events for activity awareness."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT data FROM events ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            return [r[0] for r in cur.fetchall()]
    except Exception:
        return []


def _get_existing_goals() -> List[str]:
    """Get currently pending/approved goals to avoid duplicates."""
    existing = get_proposed_goals("pending", limit=50)
    existing += get_proposed_goals("approved", limit=50)
    return [g["goal"] for g in existing]


# ─────────────────────────────────────────────────────────────
# Goal generation
# ─────────────────────────────────────────────────────────────

GOAL_PROMPT = """You are the goal-generation module of a personal AI assistant.

Your job: given the user's recurring interests, stated values, and recent activity,
propose 0-3 concrete, actionable goals the agent should pursue.

RULES:
- Each goal must be specific enough to become a task (not vague aspirations)
- Goals should align with the user's values and recent interests
- Do NOT propose goals that duplicate existing ones
- If nothing warrants a new goal, return an empty list
- Include a brief rationale for each goal
- Assign priority: low, medium, or high

Respond with ONLY a JSON array:
[{"goal": "...", "rationale": "...", "priority": "medium"}]
Return [] if no goals are warranted.

CURRENT CONTEXT:
Recurring concepts: {concepts}
Values: {values}
Recent activity: {activity}
Existing goals (do not duplicate): {existing}"""


def _generate_goals(prompt_template: str = GOAL_PROMPT) -> str:
    """Run one cycle of goal generation. Returns summary."""
    concepts = _get_recurring_concepts()
    values = _get_values()
    activity = _get_recent_activity()
    existing = _get_existing_goals()

    # Skip if there's nothing to work with
    if not concepts and not values:
        return "No concepts or values to generate goals from"

    prompt = prompt_template.format(
        concepts=json.dumps(concepts[:10], default=str),
        values=json.dumps(values[:10]),
        activity=json.dumps(activity[:10]),
        existing=json.dumps(existing[:20]),
    )

    try:
        from agent.services.llm import generate
        response = generate(prompt, role="GOAL", max_tokens=1024)
    except Exception as e:
        print(f"[GoalLoop] LLM call failed: {e}")
        return f"LLM call failed: {e}"

    # Parse response — lazy parse: try JSON, fall back to raw text
    try:
        text = response.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            return f"[raw output - no JSON array found]\n{text[:2000]}"
        goals = json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError):
        return f"[raw output - JSON parse failed]\n{response.strip()[:2000]}"

    if not isinstance(goals, list):
        return f"[raw output - not a list]\n{response.strip()[:2000]}"

    proposed = []
    for g in goals:
        if not isinstance(g, dict) or "goal" not in g:
            continue
        goal_text = str(g["goal"]).strip()
        if not goal_text:
            continue
        # Skip if too similar to existing
        if any(goal_text.lower() in ex.lower() or ex.lower() in goal_text.lower()
               for ex in existing):
            continue
        propose_goal(
            goal=goal_text,
            rationale=str(g.get("rationale", "")),
            priority=str(g.get("priority", "medium")),
            sources=["linking_core", "philosophy", "log"],
        )
        proposed.append(f"[{g.get('priority', 'medium')}] {goal_text}")

    if proposed:
        return f"Proposed {len(proposed)} goals:\n" + "\n".join(proposed)
    return "No new goals proposed this cycle"


# ─────────────────────────────────────────────────────────────
# Loop class
# ─────────────────────────────────────────────────────────────

class GoalLoop(BackgroundLoop):
    """
    Periodically proposes goals based on recurring interests, values,
    and recent activity. Goals go to proposed_goals for human review.
    """

    def __init__(self, interval: float = 600, enabled: bool = True):
        config = LoopConfig(
            interval_seconds=interval,
            name="goal_generation",
            enabled=enabled,
            max_errors=3,
            error_backoff=2.0,
            context_aware=False,
        )
        super().__init__(config, task=self._run)
        self._prompts: Dict[str, str] = {"generate": GOAL_PROMPT}

    def _run(self) -> str:
        return _generate_goals(self._prompts.get("generate", GOAL_PROMPT))

    @property
    def stats(self) -> Dict[str, Any]:
        base = super().stats
        base["prompts"] = dict(self._prompts)
        return base
