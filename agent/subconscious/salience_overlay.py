"""
salience_overlay — derive live priority/readiness from meditation state.
========================================================================

Two functions, both pure SQL + no LLM:

  goal_salience()    — for each open goal, compute a salience score
                       combining text-priority + activation flow over the
                       goal's tokens. Returns ranked list. Used by the
                       goal-loop to decide what to surface or work on.

  readiness()        — single-number readiness signal (0..1) for whether
                       the substrate is "ready to speak" — blends max
                       activation, salience volatility (current vs prev),
                       and time-since-last-llm-call. When this crosses a
                       threshold the system can self-trigger an LLM
                       response without external prompting.

Both are O(N_goals * 1) and run in milliseconds. Designed to be called
each meditation tick or whenever a surface needs to ask "what now?".
"""

from __future__ import annotations

import time
from contextlib import closing
from typing import List, Dict, Any, Optional

from data.db import get_connection


# In-process state for readiness volatility tracking.
_LAST_TOP_SALIENCE: float = 0.0
_LAST_READINESS_AT: float = 0.0
_LAST_READINESS: float = 0.0


_PRIORITY_BASE = {"high": 0.8, "medium": 0.5, "low": 0.25}


def goal_salience(limit: int = 20) -> List[Dict[str, Any]]:
    """Live-priority list of open goals.

    salience = priority_base + 0.4 * (urgency/100) + 0.3 * activation_lift

    activation_lift is the max activation of any concept whose token
    appears in the goal text. Goals about currently-hot topics rise
    automatically without any LLM in the loop.
    """
    try:
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                """
                SELECT
                    g.id, g.goal, g.priority, g.urgency, g.status,
                    COALESCE((
                        SELECT MAX(ca.activation)
                        FROM concept_activation ca
                        WHERE INSTR(LOWER(g.goal), ca.concept) > 0
                    ), 0.0) AS lift
                FROM proposed_goals g
                WHERE g.status IN ('pending','approved','in_progress')
                ORDER BY g.id DESC
                LIMIT 200
                """
            ).fetchall()
    except Exception:
        return []

    out: List[Dict[str, Any]] = []
    for r in rows:
        pri = _PRIORITY_BASE.get((r["priority"] or "medium").lower(), 0.5)
        urg = float(r["urgency"] or 0) / 100.0
        lift = float(r["lift"] or 0.0)
        sal = pri + 0.4 * urg + 0.3 * lift
        out.append({
            "id": int(r["id"]),
            "goal": r["goal"],
            "priority": r["priority"],
            "urgency": r["urgency"],
            "status": r["status"],
            "lift": round(lift, 3),
            "salience": round(sal, 3),
        })
    out.sort(key=lambda d: d["salience"], reverse=True)
    return out[: int(limit)]


def readiness() -> Dict[str, Any]:
    """Single-number readiness signal in [0, 1].

    Combines:
      a) max activation in concept_activation (proxy for 'thinking
         intensity')
      b) salience volatility — how much top salience moved since last
         call (proxy for 'something changed worth speaking about')
      c) time-since-last-llm-call recency — suppresses repeat-fire

    Returns a dict with the score + components so callers can decide.
    """
    global _LAST_TOP_SALIENCE, _LAST_READINESS_AT, _LAST_READINESS
    try:
        with closing(get_connection(readonly=True)) as conn:
            act = conn.execute(
                "SELECT COALESCE(MAX(activation), 0.0) AS mx, COUNT(*) AS n "
                "FROM concept_activation"
            ).fetchone()
            sal = conn.execute(
                "SELECT COALESCE(MAX(salience), 0.0) AS mx FROM state_cache"
            ).fetchone()
            last_llm = conn.execute(
                """
                SELECT (julianday('now') - julianday(MAX(timestamp))) * 24.0 * 60.0 AS m
                FROM unified_events
                WHERE event_type IN ('llm_call','llm_response','convo')
                """
            ).fetchone()
    except Exception:
        return {"score": 0.0, "ready": False, "error": "db"}

    max_act = float(act["mx"] or 0.0)
    n_act = int(act["n"] or 0)
    cur_top_sal = float(sal["mx"] or 0.0)
    last_llm_min = float(last_llm["m"] or 0.0) if last_llm else 1e6

    # a) Intensity: clamp activation 0..1
    intensity = min(1.0, max_act)

    # b) Volatility: |Δ top_salience| / max(prev, 1.0), clamped
    if _LAST_TOP_SALIENCE > 0:
        delta = abs(cur_top_sal - _LAST_TOP_SALIENCE) / max(_LAST_TOP_SALIENCE, 1.0)
    else:
        delta = 0.0
    volatility = min(1.0, delta * 2.0)
    _LAST_TOP_SALIENCE = cur_top_sal

    # c) Recency gate: no fire within 10 min of last LLM event
    if last_llm_min < 10.0:
        recency = 0.0
    elif last_llm_min < 60.0:
        recency = (last_llm_min - 10.0) / 50.0
    else:
        recency = 1.0

    score = (
        0.4 * intensity
        + 0.4 * volatility
        + 0.2 * recency
    )
    score = max(0.0, min(1.0, score))
    ready = score >= 0.6 and intensity >= 0.4

    _LAST_READINESS = score
    _LAST_READINESS_AT = time.time()

    return {
        "score": round(score, 3),
        "ready": bool(ready),
        "intensity": round(intensity, 3),
        "volatility": round(volatility, 3),
        "recency": round(recency, 3),
        "max_activation": round(max_act, 3),
        "active_concepts": n_act,
        "top_salience": round(cur_top_sal, 3),
        "last_llm_min": round(last_llm_min, 1),
    }


def maybe_self_trigger(threshold: float = 0.7, dry_run: bool = False) -> Optional[int]:
    """If readiness exceeds threshold, queue a 'reflective' task.

    Returns the queued task_id, or None if not ready / dry_run.
    The substrate decides on its own that it has something to say.
    """
    r = readiness()
    if not r.get("ready") or r["score"] < threshold:
        return None
    if dry_run:
        return -1

    try:
        from agent.threads.log.schema import enqueue_task
    except Exception:
        return None

    try:
        from agent.subconscious.meditation import top_salient, hot_concepts
    except Exception:
        return None

    top = top_salient(limit=8)
    hot = hot_concepts(limit=8)
    fact_lines = "\n".join(
        f"- {(t.get('value') or '')[:140]} (sal={t['salience']:.2f})"
        for t in top
    )
    hot_terms = ", ".join(f"{h['concept']}" for h in hot[:6])
    prompt = (
        f"Substrate self-triggered at readiness={r['score']:.2f} "
        f"(intensity={r['intensity']}, volatility={r['volatility']}).\n\n"
        f"On-mind: {hot_terms}\n\n"
        f"Top-salient facts:\n{fact_lines}\n\n"
        f"In one paragraph, what — if anything — is worth saying right now? "
        f"If nothing actionable, return EMPTY."
    )

    try:
        return int(enqueue_task(
            kind="self_reflect",
            prompt=prompt,
            role="THOUGHT",
            requested_by="meditator",
            params={"max_tokens": 400, "readiness": r["score"]},
        ))
    except Exception:
        return None


__all__ = ["goal_salience", "readiness", "maybe_self_trigger"]
