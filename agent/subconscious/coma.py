"""
Coma-mode programmatic substrate.
=================================

The system breathing without thinking.

Every heartbeat tick this module runs.  Zero LLM calls.  Pure SQL +
arithmetic.  Lets STATE evolve when every loop is gated.

What it does each tick:
  - touch_graph_from_events   — recent events bump linking_core edges
                                 between mentioned tokens (entity-only,
                                 no fabrication).  The graph evolves
                                 from observation alone.
  - tally_outcomes (every 6th tick) — read thought_log.acted_on,
                                 proposed_goals.status, task_queue.status,
                                 and prediction_error tags over 14d window.
                                 Write as a reflex compression meta-thought
                                 so STATE picks it up without new schema.
  - update_self_facts         — write agent uptime / heartbeats /
                                 events_last_24h / last_llm_age into
                                 the machine profile so identity STATE
                                 always reflects current self-state.
  - maybe_decay_links         — once per ~6h: linking_core soft forget.
  - maybe_decay_facts         — once per ~24h: identity.decay_learned_facts
                                 (curated facts protected).

In-process state (boot time, heartbeat count, last touch event id) is
intentional — restarting resets to a known clean baseline, like
rate_gate.  All persistent state lives in the DB.
"""

from __future__ import annotations

import time
from contextlib import closing
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional

from data.db import get_connection


# ─────────────────────────────────────────────────────────────────────
# In-process counters
# ─────────────────────────────────────────────────────────────────────

_BOOT_TIME = time.time()
_HEARTBEAT_COUNT = 0
_LAST_TOUCH_EVENT_ID = 0
_LAST_GRAPH_DECAY_AT = 0.0
_LAST_FACT_DECAY_AT = 0.0
_LAST_RUN_SUMMARY: Dict[str, Any] = {}
_LAST_STATE_FINGERPRINT: Optional[str] = None


def _now() -> float:
    return time.time()


# ─────────────────────────────────────────────────────────────────────
# Graph touch — programmatic linking_core feeding
# ─────────────────────────────────────────────────────────────────────

def touch_graph_from_events(max_events: int = 200) -> Tuple[int, int]:
    """Process events newer than the last seen id; bump cooccurrence +
    concept_link edges between every pair of mentioned tokens.

    Returns (events_processed, edges_touched).
    """
    global _LAST_TOUCH_EVENT_ID

    try:
        from agent.threads.linking_core.schema import (
            extract_concepts_from_text,
            record_cooccurrence_batch,
            link_concepts,
        )
    except Exception:
        return (0, 0)

    try:
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                """
                SELECT id, data, tags_json, thread_subject
                FROM unified_events
                WHERE id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (_LAST_TOUCH_EVENT_ID, max_events),
            ).fetchall()
    except Exception:
        return (0, 0)

    if not rows:
        return (0, 0)

    import json as _json

    edges = 0
    last_id = _LAST_TOUCH_EVENT_ID

    for r in rows:
        last_id = max(last_id, int(r["id"]))
        text = (r["data"] or "")[:1000]

        # Tags + thread_subject as tokens (already-normalized labels)
        labels = []
        if r["tags_json"]:
            try:
                labels = list(_json.loads(r["tags_json"]) or [])
            except Exception:
                labels = []
        if r["thread_subject"]:
            labels.append(r["thread_subject"])

        # Concepts pulled only from the known entity registry — never
        # invents new tokens, so the graph stays bounded.
        try:
            concepts = extract_concepts_from_text(text) if text else []
        except Exception:
            concepts = []

        tokens = list({str(t)[:60] for t in (labels + concepts) if t})
        if len(tokens) < 2:
            continue

        # Bulk cooccurrence (cheap upsert)
        pairs = [
            (tokens[i], tokens[j])
            for i in range(len(tokens))
            for j in range(i + 1, len(tokens))
        ]
        try:
            edges += record_cooccurrence_batch(pairs)
        except Exception:
            pass

        # Concept-only edges go through Hebbian linker (slower learning,
        # higher signal — these are real entity matches not arbitrary tags)
        if len(concepts) >= 2:
            try:
                seen = set()
                for i, a in enumerate(concepts):
                    for b in concepts[i + 1:]:
                        key = tuple(sorted((a, b)))
                        if key in seen:
                            continue
                        seen.add(key)
                        link_concepts(a, b, learning_rate=0.05)
            except Exception:
                pass

    _LAST_TOUCH_EVENT_ID = last_id
    return (len(rows), edges)


# ─────────────────────────────────────────────────────────────────────
# Outcome tally — programmatic reward-PE substrate
# ─────────────────────────────────────────────────────────────────────

def tally_outcomes(window_days: int = 14) -> Dict[str, Any]:
    """Compute hit/total counts across thoughts, goals, tasks, predictions
    over the recent window.  Pure SQL.  Never raises."""
    out: Dict[str, Any] = {
        "thoughts": {}, "goals": {}, "tasks": {}, "predictions": {},
    }
    wd = int(max(1, window_days))
    try:
        with closing(get_connection(readonly=True)) as conn:
            # Thoughts — by category, hit = acted_on=1
            try:
                rows = conn.execute(
                    f"""
                    SELECT category,
                           SUM(CASE WHEN acted_on=1 THEN 1 ELSE 0 END) AS hits,
                           COUNT(*) AS total
                    FROM thought_log
                    WHERE created_at >= datetime('now','-{wd} days')
                    GROUP BY category
                    """
                ).fetchall()
                for r in rows:
                    cat = r["category"] or "unknown"
                    total = int(r["total"] or 0)
                    if total <= 0:
                        continue
                    out["thoughts"][cat] = {
                        "hits": int(r["hits"] or 0),
                        "total": total,
                        "rate": round((r["hits"] or 0) / total, 3),
                    }
            except Exception:
                pass

            # Goals — by priority, hit = completed
            try:
                rows = conn.execute(
                    f"""
                    SELECT priority,
                           SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS hits,
                           SUM(CASE WHEN status IN ('rejected','dismissed') THEN 1 ELSE 0 END) AS misses,
                           COUNT(*) AS total
                    FROM proposed_goals
                    WHERE created_at >= datetime('now','-{wd} days')
                    GROUP BY priority
                    """
                ).fetchall()
                for r in rows:
                    pri = r["priority"] or "unknown"
                    total = int(r["total"] or 0)
                    closed = int(r["hits"] or 0) + int(r["misses"] or 0)
                    out["goals"][pri] = {
                        "hits": int(r["hits"] or 0),
                        "closed": closed,
                        "total": total,
                        "rate": (
                            round((r["hits"] or 0) / closed, 3)
                            if closed else None
                        ),
                    }
            except Exception:
                pass

            # Tasks — status counts
            try:
                rows = conn.execute(
                    f"""
                    SELECT status, COUNT(*) AS n
                    FROM task_queue
                    WHERE created_at >= datetime('now','-{wd} days')
                    GROUP BY status
                    """
                ).fetchall()
                for r in rows:
                    out["tasks"][r["status"]] = int(r["n"])
            except Exception:
                pass

            # Predictions — count violations by prediction name
            try:
                rows = conn.execute(
                    f"""
                    SELECT tags_json, COUNT(*) AS n
                    FROM unified_events
                    WHERE event_type='system:prediction_error'
                      AND timestamp >= datetime('now','-{wd} days')
                    GROUP BY tags_json
                    LIMIT 50
                    """
                ).fetchall()
                import json as _json
                bucket: Dict[str, int] = {}
                for r in rows:
                    try:
                        tags = _json.loads(r["tags_json"] or "[]")
                    except Exception:
                        tags = []
                    name = "unknown"
                    for t in tags:
                        if t and t not in (
                            "prediction_error", "low", "medium", "high"
                        ):
                            name = t
                            break
                    bucket[name] = bucket.get(name, 0) + int(r["n"])
                out["predictions"] = bucket
            except Exception:
                pass
    except Exception:
        return out
    return out


def write_outcome_compression(tally: Dict[str, Any]) -> bool:
    """Surface the tally as a reflex compression meta-thought.  No new schema."""
    try:
        from agent.threads.reflex.schema import add_meta_thought
        parts = []
        t = tally.get("thoughts") or {}
        if t:
            top = sorted(
                t.items(), key=lambda kv: kv[1].get("total", 0), reverse=True
            )[:3]
            parts.append("thoughts " + ", ".join(
                f"{k}:{v['hits']}/{v['total']}" for k, v in top
            ))
        g = tally.get("goals") or {}
        if g:
            parts.append("goals " + ", ".join(
                f"{k}:{v['hits']}/{v['total']}" for k, v in g.items()
            ))
        ts = tally.get("tasks") or {}
        if ts:
            parts.append(
                "tasks " + ", ".join(f"{k}={v}" for k, v in ts.items())
            )
        p = tally.get("predictions") or {}
        if p:
            top = sorted(p.items(), key=lambda kv: -kv[1])[:3]
            parts.append(
                "pred_errs " + ", ".join(f"{k}={v}" for k, v in top)
            )
        if not parts:
            return False
        content = ("outcomes 14d: " + " | ".join(parts))[:500]
        add_meta_thought(
            kind="compression",
            content=content,
            source="system",
            confidence=1.0,
            weight=0.5,
        )
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────
# Self-state — agent writes facts about itself
# ─────────────────────────────────────────────────────────────────────

def update_self_facts() -> Dict[str, Any]:
    """Refresh machine-profile facts with current heartbeat counters.
    Visible in identity STATE so the agent can reason about its own coma."""
    global _HEARTBEAT_COUNT
    _HEARTBEAT_COUNT += 1

    info: Dict[str, Any] = {
        "uptime_h": round((_now() - _BOOT_TIME) / 3600.0, 2),
        "heartbeats": _HEARTBEAT_COUNT,
        "events_24h": 0,
        "last_llm_age_h": None,
    }

    try:
        with closing(get_connection(readonly=True)) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM unified_events "
                "WHERE timestamp >= datetime('now','-24 hours')"
            ).fetchone()
            info["events_24h"] = int(row["n"]) if row else 0

            row = conn.execute(
                "SELECT timestamp FROM unified_events "
                "WHERE event_type IN ('llm_call','llm_response','convo') "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row and row["timestamp"]:
                try:
                    ts = str(row["timestamp"]).replace("T", " ").split(".")[0]
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    age_s = (datetime.now(timezone.utc) - dt).total_seconds()
                    info["last_llm_age_h"] = round(age_s / 3600.0, 2)
                except Exception:
                    pass
    except Exception:
        pass

    try:
        from agent.threads.identity.schema import push_profile_fact

        push_profile_fact(
            "machine", "uptime_h", "learned",
            l1_value=f"{info['uptime_h']:.1f}h",
            l2_value=f"agent has been running {info['uptime_h']:.1f}h since last boot",
            weight=0.4,
        )
        push_profile_fact(
            "machine", "heartbeats_session", "learned",
            l1_value=str(_HEARTBEAT_COUNT),
            l2_value=f"{_HEARTBEAT_COUNT} programmatic heartbeats since boot",
            weight=0.3,
        )
        push_profile_fact(
            "machine", "events_24h", "learned",
            l1_value=str(info["events_24h"]),
            l2_value=f"{info['events_24h']} events recorded in the last 24 hours",
            weight=0.4,
        )
        if info["last_llm_age_h"] is not None:
            push_profile_fact(
                "machine", "last_llm_age_h", "learned",
                l1_value=f"{info['last_llm_age_h']:.1f}h",
                l2_value=f"last LLM-bearing event was {info['last_llm_age_h']:.1f}h ago",
                weight=0.5,
            )
    except Exception:
        pass

    return info


# ─────────────────────────────────────────────────────────────────────
# Decay (throttled — not every tick)
# ─────────────────────────────────────────────────────────────────────

def maybe_decay_links() -> int:
    """Concept-link decay every ~6h.  Returns pruned count."""
    global _LAST_GRAPH_DECAY_AT
    if _now() - _LAST_GRAPH_DECAY_AT < 6 * 3600:
        return 0
    try:
        from agent.threads.linking_core.schema import decay_concept_links
        pruned = decay_concept_links(decay_rate=0.97, min_strength=0.04)
        _LAST_GRAPH_DECAY_AT = _now()
        return pruned
    except Exception:
        return 0


def maybe_decay_facts() -> int:
    """Identity learned-fact decay every ~24h.  Curated facts protected."""
    global _LAST_FACT_DECAY_AT
    if _now() - _LAST_FACT_DECAY_AT < 24 * 3600:
        return 0
    try:
        from agent.threads.identity.schema import decay_learned_facts
        result = decay_learned_facts(dry_run=False)
        _LAST_FACT_DECAY_AT = _now()
        return (
            len(result.get("decayed") or [])
            + len(result.get("pruned") or [])
            + len(result.get("floor_deleted") or [])
        )
    except Exception:
        return 0


# ─────────────────────────────────────────────────────────────────────
# FTS5 recall index — sync new events on the heartbeat
# ─────────────────────────────────────────────────────────────────────

def refresh_recall_index() -> int:
    """Incrementally sync unified_events into the FTS5 recall index."""
    try:
        from agent.threads.log.recall import ensure_fts_index
        return ensure_fts_index()
    except Exception:
        return 0


# ─────────────────────────────────────────────────────────────────────
# Sequence mining — surface habit patterns
# ─────────────────────────────────────────────────────────────────────

def maybe_mine_sequences(every_nth: int = 12) -> bool:
    """Mine event-type n-grams and write a compression meta-thought.

    Runs every Nth heartbeat (default ~1 hour at 5-min cadence).
    """
    if _HEARTBEAT_COUNT == 0 or _HEARTBEAT_COUNT % every_nth != 0:
        return False
    try:
        from agent.subconscious.sequences import (
            mine_sequences, write_sequence_compression,
        )
        result = mine_sequences()
        return write_sequence_compression(result)
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────
# STATE self-similarity — change detection without an LLM
# ─────────────────────────────────────────────────────────────────────

def state_fingerprint() -> str:
    """Cheap deterministic fingerprint of the current high-weight fact set.

    Hashes (profile_id, key, l1_value, weight bucket) for the top
    profile_facts. Tick-over-tick this changes only when content the
    agent considers important changes — a structural derivative.
    """
    import hashlib
    h = hashlib.blake2b(digest_size=12)
    try:
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute(
                """
                SELECT profile_id, key, l1_value, weight
                FROM profile_facts
                WHERE protected = 1 OR weight >= 0.5
                ORDER BY profile_id, key
                LIMIT 200
                """
            ).fetchall()
            for r in rows:
                bucket = round(float(r["weight"] or 0.0) * 10) / 10.0
                h.update(
                    f"{r['profile_id']}|{r['key']}|{(r['l1_value'] or '')[:120]}|{bucket}\n".encode("utf-8", "ignore")
                )
            # Mix in goals open + tasks pending counts so big workflow
            # shifts also flip the fingerprint.
            try:
                gr = conn.execute(
                    "SELECT COUNT(*) AS n FROM proposed_goals "
                    "WHERE status IN ('pending','approved','in_progress')"
                ).fetchone()
                tr = conn.execute(
                    "SELECT COUNT(*) AS n FROM task_queue WHERE status='pending'"
                ).fetchone()
                h.update(f"goals_open={int(gr['n']) if gr else 0}\n".encode())
                h.update(f"tasks_pending={int(tr['n']) if tr else 0}\n".encode())
            except Exception:
                pass
    except Exception:
        return ""
    return h.hexdigest()


def detect_state_change() -> Optional[str]:
    """Compare current fingerprint to previous; on change emit a
    meta-thought and return the new fingerprint. Returns None if same."""
    global _LAST_STATE_FINGERPRINT
    fp = state_fingerprint()
    if not fp:
        return None
    if _LAST_STATE_FINGERPRINT is None:
        _LAST_STATE_FINGERPRINT = fp
        return None  # first run — no prior to compare against
    if fp == _LAST_STATE_FINGERPRINT:
        return None
    prev = _LAST_STATE_FINGERPRINT
    _LAST_STATE_FINGERPRINT = fp
    try:
        from agent.threads.reflex.schema import add_meta_thought
        add_meta_thought(
            kind="compression",
            content=f"state shifted: {prev[:8]} -> {fp[:8]}",
            source="system",
            confidence=1.0,
            weight=0.45,
        )
    except Exception:
        pass
    return fp


# ─────────────────────────────────────────────────────────────────────
# Tick
# ─────────────────────────────────────────────────────────────────────

def run_once() -> Dict[str, Any]:
    """Single coma-mode tick.  Cheap.  Always-callable.  No LLM."""
    global _LAST_RUN_SUMMARY

    summary: Dict[str, Any] = {
        "at": datetime.utcnow().isoformat() + "Z",
    }

    events_n, edges_n = touch_graph_from_events()
    summary["events_touched"] = events_n
    summary["edges_touched"] = edges_n

    # Tally is more expensive — run every 6th tick (every ~30 min on a
    # 5 min heartbeat) plus the very first tick after boot.
    if _HEARTBEAT_COUNT == 0 or _HEARTBEAT_COUNT % 6 == 0:
        tally = tally_outcomes()
        summary["tally"] = tally
        summary["compression_written"] = write_outcome_compression(tally)
    else:
        summary["tally"] = None
        summary["compression_written"] = False

    summary["self"] = update_self_facts()
    summary["graph_pruned"] = maybe_decay_links()
    summary["facts_decayed"] = maybe_decay_facts()
    summary["fts_added"] = refresh_recall_index()
    summary["seq_mined"] = maybe_mine_sequences()
    summary["slots_touched"] = _refresh_slots_safe()
    if _HEARTBEAT_COUNT == 0 or _HEARTBEAT_COUNT % 12 == 0:
        summary["seq_predictions_added"] = _register_seq_predictions_safe()
    else:
        summary["seq_predictions_added"] = 0
    if _HEARTBEAT_COUNT == 0 or _HEARTBEAT_COUNT % 6 == 0:
        summary["contradictions_emitted"] = _emit_contradictions_safe()
    else:
        summary["contradictions_emitted"] = 0
    fp = detect_state_change()
    summary["state_changed"] = bool(fp)
    if fp:
        summary["state_fp"] = fp[:8]

    _LAST_RUN_SUMMARY = summary
    return summary


def _refresh_slots_safe() -> int:
    try:
        from agent.subconscious.slots import refresh_slots
        return refresh_slots()
    except Exception:
        return 0


def _register_seq_predictions_safe() -> int:
    try:
        from agent.subconscious.seq_predictions import mine_and_register
        return mine_and_register()
    except Exception:
        return 0


def _emit_contradictions_safe() -> int:
    try:
        from agent.threads.philosophy.contradictions import (
            emit_contradiction_meta_thoughts,
        )
        return emit_contradiction_meta_thoughts()
    except Exception:
        return 0


def last_summary() -> Dict[str, Any]:
    return dict(_LAST_RUN_SUMMARY)


__all__ = [
    "run_once",
    "last_summary",
    "touch_graph_from_events",
    "tally_outcomes",
    "write_outcome_compression",
    "update_self_facts",
    "maybe_decay_links",
    "maybe_decay_facts",
    "refresh_recall_index",
    "maybe_mine_sequences",
    "state_fingerprint",
    "detect_state_change",
]
