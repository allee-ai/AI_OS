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
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO proposed_goals (goal, rationale, priority, sources) VALUES (?, ?, ?, ?)",
                (goal, rationale, priority, json.dumps(sources or []))
            )
            conn.commit()
            return cur.lastrowid or 0
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


def _generate_goals() -> None:
    """Run one cycle of goal generation."""
    concepts = _get_recurring_concepts()
    values = _get_values()
    activity = _get_recent_activity()
    existing = _get_existing_goals()

    # Skip if there's nothing to work with
    if not concepts and not values:
        return

    prompt = GOAL_PROMPT.format(
        concepts=json.dumps(concepts[:10], default=str),
        values=json.dumps(values[:10]),
        activity=json.dumps(activity[:10]),
        existing=json.dumps(existing[:20]),
    )

    try:
        from agent.services.llm import call_llm
        response = call_llm(prompt, max_tokens=1024)
    except Exception as e:
        print(f"[GoalLoop] LLM call failed: {e}")
        return

    # Parse response
    try:
        # Extract JSON array from response
        text = response.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            return
        goals = json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError):
        return

    if not isinstance(goals, list):
        return

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
        super().__init__(config, task=_generate_goals)
