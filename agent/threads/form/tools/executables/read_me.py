"""
read_me — Self-introspection sense
===================================

The system's own fingertips for examining itself.

This is a *sense*, not a limb: every action is read-only. It exists so the
model can ask focused questions about its own state on demand, without
bloating STATE with everything-all-the-time.

STATE shows the skin (passive low-res awareness).
read_me lets the model bring a fingertip to a specific spot.

Actions
-------
    services    — what loops are running, last heartbeat, recent errors
    tools       — full tool catalog with allowed/enabled flags
    threads     — each thread's health() + counts
    recent      — last N events from the log (filterable by event_type)
    self        — full identity at L3: name, user, machine, current affect
    goals       — open goals + statuses
    errors      — recent errors across all threads
    surface     — top-level project layout: directories, file counts

All output is plain text capped at ~6KB so the result fits in the next
turn's context comfortably.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List

WORKSPACE_ROOT = Path(__file__).resolve().parents[5]  # → AI_OS/
MAX_OUTPUT = 8000


def run(action: str, params: dict) -> str:
    """Dispatch read_me actions.  Returns a plain-text summary."""
    actions = {
        "services": _services,
        "tools":    _tools,
        "threads":  _threads,
        "recent":   _recent,
        "self":     _self,
        "goals":    _goals,
        "errors":   _errors,
        "surface":  _surface,
    }
    fn = actions.get(action)
    if not fn:
        return (
            f"Unknown action: {action}. Available: {', '.join(actions)}\n"
            "All read-only.  Each summarizes a slice of my own running state."
        )
    try:
        out = fn(params or {})
    except Exception as e:
        return f"read_me.{action} failed: {type(e).__name__}: {e}"
    return _truncate(out)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + f"\n\n... [truncated, {len(text)} chars total]"


def _conn():
    from data.db import get_connection
    return get_connection(readonly=True)


def _try_query(sql: str, params: tuple = ()) -> List[sqlite3.Row]:
    """Read-only query.  Returns [] on any error."""
    try:
        with closing(_conn()) as conn:
            return list(conn.execute(sql, params).fetchall())
    except Exception:
        return []


def _age(ts: str | None) -> str:
    """Compact age string for an ISO timestamp."""
    if not ts:
        return "never"
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = (datetime.now(timezone.utc) - dt).total_seconds()
        if secs < 60:    return f"{int(secs)}s ago"
        if secs < 3600:  return f"{int(secs/60)}m ago"
        if secs < 86400: return f"{int(secs/3600)}h ago"
        return f"{int(secs/86400)}d ago"
    except Exception:
        return "?"


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def _services(params: dict) -> str:
    """Loops, heartbeat, and recent service events."""
    lines: List[str] = ["[services]"]

    # Heartbeat state
    hb_path = WORKSPACE_ROOT / "data" / "heartbeat.state.json"
    if hb_path.exists():
        try:
            data = json.loads(hb_path.read_text())
            ts = data.get("ts") or data.get("timestamp")
            lines.append(f"  heartbeat.last_run: {_age(ts)}")
            for k in ("commit", "outreach_queued", "goal_46_status"):
                if k in data:
                    lines.append(f"  heartbeat.{k}: {data[k]}")
        except Exception as e:
            lines.append(f"  heartbeat.error: {e}")
    else:
        lines.append("  heartbeat: not running (no state file)")

    # Loop heartbeats from unified_events (event_type starts with 'loop:')
    loop_rows = _try_query(
        "SELECT event_type, MAX(timestamp) as last_ts, COUNT(*) as n "
        "FROM unified_events WHERE event_type LIKE 'loop:%' "
        "GROUP BY event_type ORDER BY event_type"
    )
    if loop_rows:
        lines.append("  loops:")
        for r in loop_rows:
            lines.append(f"    {r['event_type']:30}  last={_age(r['last_ts'])}  total={r['n']}")
    else:
        lines.append("  loops: no loop events recorded")

    # Recent service-level errors
    err_rows = _try_query(
        "SELECT event_type, data, timestamp FROM unified_events "
        "WHERE event_type LIKE 'error:%' OR event_type LIKE 'warn:%' "
        "ORDER BY timestamp DESC LIMIT 5"
    )
    if err_rows:
        lines.append("  recent_errors:")
        for r in err_rows:
            d = (r["data"] or "")[:80].replace("\n", " ")
            lines.append(f"    [{_age(r['timestamp']):>6}] {r['event_type']}: {d}")

    return "\n".join(lines)


def _tools(params: dict) -> str:
    """Tool catalog with gate status."""
    rows = _try_query(
        "SELECT name, description, category, actions, enabled, allowed, "
        "requires_env FROM form_tools ORDER BY category, name"
    )
    if not rows:
        return "[tools] form_tools table empty or unavailable"

    lines = [f"[tools] {len(rows)} registered"]
    current_cat = None
    for r in rows:
        cat = r["category"] or "uncat"
        if cat != current_cat:
            lines.append(f"  {cat}:")
            current_cat = cat
        gate = []
        if not r["enabled"]: gate.append("disabled")
        if not r["allowed"]: gate.append("locked")
        try:
            envs = json.loads(r["requires_env"] or "[]")
        except Exception:
            envs = []
        missing_env = [e for e in envs if not os.getenv(e)]
        if missing_env:
            gate.append(f"missing_env={','.join(missing_env)}")
        gate_str = f" [{', '.join(gate)}]" if gate else ""
        try:
            actions = json.loads(r["actions"] or "[]")
        except Exception:
            actions = []
        a_str = f" ({', '.join(actions[:4])}{'...' if len(actions) > 4 else ''})" if actions else ""
        lines.append(f"    {r['name']}{gate_str}: {r['description']}{a_str}")
    return "\n".join(lines)


def _threads(params: dict) -> str:
    """Each thread's health, counts, and module list."""
    lines = ["[threads]"]
    try:
        from agent.threads import get_all_threads
        threads = get_all_threads()
    except Exception as e:
        return f"[threads] could not load thread registry: {e}"

    for adapter in sorted(threads, key=lambda a: getattr(a, "name", "") or ""):
        name = getattr(adapter, "name", None) or adapter.__class__.__name__
        try:
            health = adapter.health().to_dict() if hasattr(adapter, "health") else {}
        except Exception as e:
            health = {"status": "error", "message": str(e)[:80]}
        status = health.get("status", "?")
        msg = (health.get("message") or "")[:60]
        modules = []
        try:
            modules = adapter.get_modules() or []
        except Exception:
            pass
        lines.append(f"  {name:14} [{status}] {msg}")
        if modules:
            lines.append(f"    modules: {', '.join(modules)}")
    return "\n".join(lines)


def _recent(params: dict) -> str:
    """Last N events from the log thread."""
    n = int(params.get("n", 20))
    n = max(1, min(n, 50))
    event_type = params.get("event_type", "")
    if event_type:
        rows = _try_query(
            "SELECT event_type, data, source, timestamp FROM unified_events "
            "WHERE event_type LIKE ? ORDER BY timestamp DESC LIMIT ?",
            (f"{event_type}%", n),
        )
        header = f"[recent] last {n} events matching '{event_type}*'"
    else:
        rows = _try_query(
            "SELECT event_type, data, source, timestamp FROM unified_events "
            "ORDER BY timestamp DESC LIMIT ?",
            (n,),
        )
        header = f"[recent] last {n} events"
    if not rows:
        return f"{header}: none"
    lines = [header]
    for r in rows:
        d = (r["data"] or "")[:80].replace("\n", " ")
        src = (r["source"] or "")[:14]
        lines.append(f"  [{_age(r['timestamp']):>6}] {r['event_type']:24} <{src}> {d}")
    return "\n".join(lines)


def _self(params: dict) -> str:
    """Full identity at L3 + current affect, all in one place."""
    lines = ["[self]"]
    rows = _try_query(
        "SELECT profile_id, key, l3_value, l2_value, l1_value, fact_type, weight "
        "FROM profile_facts WHERE weight >= 0.4 "
        "ORDER BY profile_id, weight DESC, key"
    )
    if rows:
        current = None
        for r in rows:
            pid = r["profile_id"]
            if pid != current:
                lines.append(f"  {pid}:")
                current = pid
            value = r["l3_value"] or r["l2_value"] or r["l1_value"] or ""
            value = value.replace("\n", " ")[:140]
            lines.append(f"    {r['key']:24} = {value}")

    # Affect across all threads
    try:
        from agent.services.affect import read_all_affect, import_all_feelings
        import_all_feelings()
        affect = read_all_affect()
    except Exception:
        affect = {}
    if affect:
        lines.append("  affect:")
        for thread in sorted(affect):
            kv = affect[thread]
            if not kv:
                continue
            pairs = ", ".join(f"{k}={v}" for k, v in sorted(kv.items()))
            lines.append(f"    {thread}: {pairs}")
    return "\n".join(lines)


def _goals(params: dict) -> str:
    """Open and recent goals (from proposed_goals table)."""
    rows = _try_query(
        "SELECT id, status, priority, goal, risk FROM proposed_goals "
        "WHERE status IN ('pending','approved','in_progress','paused') "
        "ORDER BY "
        "  CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 "
        "               WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END, "
        "  id DESC"
    )
    lines = [f"[goals] {len(rows)} open"]
    for r in rows:
        title = (r["goal"] or "")[:80]
        risk = f" risk={r['risk']}" if r["risk"] else ""
        lines.append(f"  #{r['id']} [{r['status']:11}] {r['priority']:6}{risk}: {title}")
    if not rows:
        lines.append("  (none open)")

    closed = _try_query(
        "SELECT id, status, goal FROM proposed_goals "
        "WHERE status IN ('completed','rejected','dismissed') "
        "ORDER BY id DESC LIMIT 5"
    )
    if closed:
        lines.append("  recently closed:")
        for r in closed:
            lines.append(f"    #{r['id']} [{r['status']}] {(r['goal'] or '')[:60]}")
    return "\n".join(lines)


def _errors(params: dict) -> str:
    """Recent error/warn events across the system."""
    n = int(params.get("n", 20))
    n = max(1, min(n, 50))
    rows = _try_query(
        "SELECT event_type, data, source, timestamp FROM unified_events "
        "WHERE event_type LIKE 'error:%' OR event_type LIKE 'warn:%' "
        "OR event_type LIKE 'fail:%' "
        "ORDER BY timestamp DESC LIMIT ?",
        (n,),
    )
    if not rows:
        return f"[errors] no recent errors (last {n} window)"
    lines = [f"[errors] last {len(rows)}"]
    for r in rows:
        d = (r["data"] or "")[:120].replace("\n", " ")
        src = (r["source"] or "")[:14]
        lines.append(f"  [{_age(r['timestamp']):>6}] {r['event_type']:20} <{src}> {d}")
    return "\n".join(lines)


def _surface(params: dict) -> str:
    """Top-level project layout: directories with file counts."""
    lines = ["[surface] workspace structure"]
    try:
        roots = sorted(p for p in WORKSPACE_ROOT.iterdir()
                       if p.is_dir() and not p.name.startswith("."))
    except Exception as e:
        return f"[surface] cannot read workspace: {e}"

    # Directories that aren't modules but matter (data, etc.)
    skip = {"node_modules", "__pycache__", "_archive", ".venv", "venv"}
    for root in roots:
        if root.name in skip:
            continue
        try:
            py = list(root.rglob("*.py"))
            md = list(root.rglob("*.md"))
            py_count = len(py)
            md_count = len(md)
        except Exception:
            py_count = md_count = 0
        # Look for an obvious entry point.
        entries = []
        for candidate in ("__init__.py", "cli.py", "api.py", "schema.py"):
            if (root / candidate).exists():
                entries.append(candidate)
        ent = f" entries={','.join(entries)}" if entries else ""
        lines.append(f"  {root.name}/  py={py_count}  md={md_count}{ent}")

    # Top-level files of interest.
    top_py = sorted(p.name for p in WORKSPACE_ROOT.glob("*.py"))
    if top_py:
        lines.append(f"  toplevel.py: {', '.join(top_py)}")
    return "\n".join(lines)
