"""
scripts/morning_brief.py — JARVIS-style personalized morning briefing.

Reads STATE the same way the live agent does, plus git log, then composes
a warm, specific greeting that names what happened overnight, what's open,
and what to focus on.

Designed so the brief is itself a fact about the system: it shows the user
that the system actually knows them.

Usage:
    .venv/bin/python scripts/morning_brief.py             # print + ping
    .venv/bin/python scripts/morning_brief.py --print     # print only
    .venv/bin/python scripts/morning_brief.py --speak     # also TTS via `say`
    .venv/bin/python scripts/morning_brief.py --json      # raw data dump
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def _now_local() -> datetime:
    return datetime.now()


def _greeting_for_hour(h: int) -> str:
    if 4 <= h < 11:
        return "Good morning"
    if 11 <= h < 14:
        return "Late morning"
    if 14 <= h < 18:
        return "Good afternoon"
    if 18 <= h < 22:
        return "Good evening"
    return "Late night"


def _humanize_delta(secs: float) -> str:
    secs = int(secs)
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m"
    if secs < 86400:
        h = secs // 3600
        m = (secs % 3600) // 60
        return f"{h}h{m}m" if m else f"{h}h"
    d = secs // 86400
    return f"{d}d"


# ---------------------------------------------------------------------------
# Data collectors (each returns dict, never raises)
# ---------------------------------------------------------------------------

def _identity() -> Dict[str, str]:
    """Resolve user + agent names with multiple fallbacks."""
    out = {"user_name": "you", "agent_name": "Nola"}

    # Try the convenience helpers first
    try:
        from agent.threads.identity import get_user_name, get_agent_name
        u = get_user_name()
        a = get_agent_name()
        if u and u != "User":
            out["user_name"] = u
        if a and a != "Agent":
            out["agent_name"] = a
    except Exception:
        pass

    # Fallback: scan profiles for the actual stored names
    if out["user_name"] in ("you", "User"):
        try:
            from agent.threads.identity.schema import pull_profile_facts
            for pid in ("primary_user", "user.primary", "self.user", "user"):
                facts = pull_profile_facts(profile_id=pid, limit=10)
                for f in facts:
                    if f.get("key") == "name" and f.get("l1_value"):
                        full = f["l1_value"].strip()
                        # Take first word as conversational name
                        out["user_name"] = full.split()[0] if " " not in full else \
                            (full.split()[1] if len(full.split()) > 1 else full.split()[0])
                        break
                if out["user_name"] not in ("you", "User"):
                    break
        except Exception:
            pass

    # Special: this user goes by "Cade" (middle name); detect that pattern
    if out["user_name"] == "Allee":
        out["user_name"] = "Cade"

    return out


def _git_overnight(since_hours: int = 12) -> List[Dict[str, str]]:
    """Commits in the last N hours."""
    try:
        out = subprocess.run(
            ["git", "log", f"--since={since_hours} hours ago",
             "--pretty=format:%h\t%cr\t%s", "--no-merges"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        return []
    commits = []
    for line in out.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            commits.append({"sha": parts[0], "when": parts[1], "subject": parts[2]})
    return commits


def _open_goals(limit: int = 5) -> List[Dict[str, Any]]:
    try:
        from data.db import get_connection
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute("""
                SELECT id, goal, priority, urgency, status
                FROM proposed_goals
                WHERE status IN ('open', 'in_progress', 'proposed')
                ORDER BY COALESCE(priority,0) DESC, COALESCE(urgency,0) DESC, id DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def _recent_events(limit: int = 8) -> List[Dict[str, Any]]:
    try:
        from data.db import get_connection
        with closing(get_connection(readonly=True)) as conn:
            for tbl in ("unified_events", "log_events", "events"):
                try:
                    rows = conn.execute(
                        f"SELECT * FROM {tbl} ORDER BY id DESC LIMIT ?", (limit,)
                    ).fetchall()
                    if rows:
                        return [dict(r) for r in rows]
                except Exception:
                    continue
    except Exception:
        pass
    return []


def _field_status() -> Dict[str, Any]:
    try:
        from agent.threads.field import schema as fs
        stats = fs.get_stats()
        alerts = fs.list_alerts(unack_only=True, limit=3)
        strangers = fs.detect_persistent_strangers(min_envs=2, min_days=2)
        return {
            "stats": stats,
            "alerts": alerts,
            "strangers_count": len(strangers),
        }
    except Exception:
        return {}


def _unread_pings(limit: int = 5) -> List[Dict[str, Any]]:
    try:
        from data.db import get_connection
        with closing(get_connection(readonly=True)) as conn:
            rows = conn.execute("""
                SELECT id, message, priority, created_at
                FROM notifications
                WHERE read = 0 AND dismissed = 0
                ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def _last_chat_topic() -> Optional[str]:
    try:
        from data.db import get_connection
        with closing(get_connection(readonly=True)) as conn:
            for tbl, col in (("convo_turns", "user_msg"), ("conversation_turns", "user_msg"),
                             ("chat_turns", "user_message")):
                try:
                    row = conn.execute(
                        f"SELECT {col} FROM {tbl} ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    if row and row[0]:
                        text = row[0].strip().split("\n")[0]
                        return text[:120]
                except Exception:
                    continue
    except Exception:
        pass
    return None


def _philosophy_anchor() -> Optional[str]:
    """Pick a philosophy fact at random from the high-weight set, biased toward
    those captured most recently. The agent should be able to quote itself."""
    try:
        from agent.threads.philosophy.schema import pull_philosophy_profile_facts
        facts = pull_philosophy_profile_facts(
            profile_id="value_system.machine", min_weight=0.85, limit=20
        )
        if not facts:
            return None
        # Bias toward most recent by reversing list (pull_ returns newest-first
        # in most schemas, but this is defensive)
        import random
        chosen = random.choice(facts[:8])
        return chosen.get("l1_value") or chosen.get("l2_value")
    except Exception:
        return None


def _state_summary() -> Dict[str, Any]:
    try:
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        state = sub.get_state(query="morning brief")
        if isinstance(state, dict):
            return {
                "blocks": list(state.get("blocks", state).keys())
                if isinstance(state.get("blocks", state), dict) else [],
                "fact_count": state.get("fact_count", 0),
            }
        return {"raw_chars": len(str(state))}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Composer
# ---------------------------------------------------------------------------

def compose_brief() -> Dict[str, Any]:
    now = _now_local()
    ident = _identity()
    commits = _git_overnight(since_hours=12)
    goals = _open_goals(limit=5)
    field = _field_status()
    pings = _unread_pings(limit=5)
    last_topic = _last_chat_topic()
    anchor = _philosophy_anchor()
    state = _state_summary()

    user = ident.get("user_name", "you")
    agent = ident.get("agent_name", "Agent")
    greeting = _greeting_for_hour(now.hour)

    # ----- compose lines -----
    lines: List[str] = []
    lines.append(f"{greeting}, {user}. {agent} here.")
    lines.append("")

    # Overnight summary
    if commits:
        lines.append(f"Overnight I shipped {len(commits)} commit{'s' if len(commits) != 1 else ''}:")
        for c in commits[:6]:
            subj = c["subject"]
            if len(subj) > 90:
                subj = subj[:87] + "..."
            lines.append(f"  • {subj}  ({c['when']})")
        if len(commits) > 6:
            lines.append(f"  • ...and {len(commits) - 6} more.")
        lines.append("")

    # State health
    if state.get("blocks"):
        lines.append(f"STATE assembled cleanly — {len(state['blocks'])} thread blocks active.")
        lines.append("")

    # Field
    fstats = field.get("stats", {})
    if fstats.get("field_environments", 0):
        unack = fstats.get("unack_alerts", 0)
        strangers = field.get("strangers_count", 0)
        if unack or strangers:
            lines.append(
                f"Field: {fstats['field_environments']} env(s), "
                f"{strangers} persistent stranger(s), {unack} unacknowledged alert(s)."
            )
        else:
            lines.append(f"Field: {fstats['field_environments']} env(s) tracked, all clear.")
        lines.append("")

    # Goals
    if goals:
        lines.append(f"Top open goal{'s' if len(goals) > 1 else ''}:")
        for g in goals[:3]:
            pri = g.get("priority")
            tag = ""
            if pri is not None:
                tag = f"[{pri}] " if isinstance(pri, str) else f"[p{pri}] "
            lines.append(f"  • #{g['id']} {tag}{g['goal'][:90]}")
        lines.append("")

    # Pings (already-pending notifications)
    if pings:
        lines.append(f"You have {len(pings)} unread ping(s). Most recent:")
        for p in pings[:2]:
            msg = p["message"]
            if len(msg) > 100:
                msg = msg[:97] + "..."
            lines.append(f"  • [{p.get('priority', 'normal')}] {msg}")
        lines.append("")

    # Memory of last conversation
    if last_topic:
        lines.append(f"We were last discussing: \"{last_topic}\"")
        lines.append("")

    # Anchor — quote a value back
    if anchor:
        lines.append(f"From your value system, anchored today: {anchor}")
        lines.append("")

    # Frame for the day
    lines.append("Today: ship one thing that proves the operator framing — "
                 "concrete, narrow, irreversible.")
    lines.append("")
    lines.append(f"— {agent}")

    text = "\n".join(lines).strip()

    return {
        "text": text,
        "generated_at": now.isoformat(),
        "data": {
            "identity": ident,
            "commits": commits,
            "goals": goals,
            "field": field,
            "pings": pings,
            "last_topic": last_topic,
            "anchor": anchor,
            "state": state,
        },
    }


# ---------------------------------------------------------------------------
# Side effects
# ---------------------------------------------------------------------------

def send_as_ping(text: str) -> None:
    """Send the brief as a high-priority ping so it shows on dashboard + ntfy."""
    try:
        from data.db import get_connection
        with closing(get_connection()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL DEFAULT 'alert',
                    message TEXT NOT NULL,
                    priority TEXT NOT NULL DEFAULT 'normal',
                    context TEXT NOT NULL DEFAULT '{}',
                    read INTEGER NOT NULL DEFAULT 0,
                    dismissed INTEGER NOT NULL DEFAULT 0,
                    response TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            cur = conn.execute(
                "INSERT INTO notifications (type, message, priority, context) VALUES (?, ?, ?, ?)",
                ("morning_brief", text, "high",
                 json.dumps({"source": "morning_brief", "len": len(text)})),
            )
            conn.commit()
            nid = cur.lastrowid
        try:
            from agent.services.alerts import fire_alerts
            fire_alerts(text[:240], "high", nid=nid, source="morning_brief")
        except Exception:
            pass
    except Exception as e:
        print(f"[ping send failed] {e}", file=sys.stderr)


def speak(text: str) -> None:
    """macOS `say` — best-effort. Truncated for sanity."""
    if sys.platform != "darwin":
        return
    try:
        clean = text.replace("•", "").replace("—", ",")
        # Cap at 800 chars so it doesn't drone on
        clean = clean[:800]
        subprocess.Popen(["say", "-r", "180", clean])
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print", action="store_true",
                        help="Just print, don't send a ping")
    parser.add_argument("--speak", action="store_true",
                        help="Also TTS via macOS `say`")
    parser.add_argument("--json", action="store_true",
                        help="Dump raw composer data as JSON")
    args = parser.parse_args()

    brief = compose_brief()

    if args.json:
        print(json.dumps(brief, indent=2, default=str))
        return 0

    print(brief["text"])
    if args.speak:
        speak(brief["text"])
    if not args.print:
        send_as_ping(brief["text"])
        print("\n[ping sent: morning_brief, priority=high]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
