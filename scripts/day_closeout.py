"""
scripts/day_closeout.py — generate a short markdown summary of a given
calendar day (or the day before today), used as the rollover banner
payload when aios forwards into a fresh VS Code session.

Pulls from whatever adapters exist. Everything is best-effort: each
source is wrapped in try/except so a missing table can't break the
banner. The output cap is ~1500 chars so it fits comfortably in the
Copilot chat input.

Usage (standalone):
    .venv/bin/python scripts/day_closeout.py            # yesterday
    .venv/bin/python scripts/day_closeout.py 2026-04-21 # explicit date
"""

from __future__ import annotations

import sys
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

# Allow running as a standalone script: add repo root to sys.path so
# `from data.db import get_connection` resolves when invoked directly.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _default_day() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def _count_and_head(conn, sql: str, params: tuple, limit: int = 5) -> List[tuple]:
    try:
        return conn.execute(sql, params).fetchall()[:limit]
    except Exception:
        return []


def _goals_section(conn, day: str) -> str:
    opened = _count_and_head(
        conn,
        "SELECT id, goal, priority, urgency FROM proposed_goals "
        "WHERE date(created_at) = ? ORDER BY id DESC",
        (day,),
    )
    closed = _count_and_head(
        conn,
        "SELECT id, goal, status FROM proposed_goals "
        "WHERE date(resolved_at) = ? ORDER BY id DESC",
        (day,),
    )
    lines = []
    if opened:
        lines.append(f"opened {len(opened)}:")
        for row in opened[:3]:
            gid, goal, pri, urg = row[0], row[1], row[2], row[3] if len(row) > 3 else None
            u = f" u{urg}" if urg is not None else ""
            lines.append(f"  #{gid} [{pri}{u}] {str(goal)[:80]}")
    if closed:
        lines.append(f"closed {len(closed)}:")
        for row in closed[:3]:
            gid, goal, status = row[0], row[1], row[2]
            lines.append(f"  #{gid} [{status}] {str(goal)[:80]}")
    if not lines:
        return ""
    return "goals:\n" + "\n".join(lines)


def _events_section(conn, day: str) -> str:
    try:
        rows = conn.execute(
            "SELECT event_type, COUNT(*) c FROM unified_events "
            "WHERE date(timestamp) = ? GROUP BY event_type "
            "ORDER BY c DESC LIMIT 5",
            (day,),
        ).fetchall()
    except Exception:
        rows = []
    if not rows:
        return ""
    parts = [f"{row[0]}×{row[1]}" for row in rows]
    return "events: " + ", ".join(parts)


def _pings_section(conn, day: str) -> str:
    try:
        rows = conn.execute(
            "SELECT data FROM unified_events "
            "WHERE event_type LIKE 'alert%' AND date(timestamp) = ? "
            "ORDER BY id DESC LIMIT 3",
            (day,),
        ).fetchall()
    except Exception:
        rows = []
    if not rows:
        return ""
    tails = []
    for (data,) in rows:
        if data:
            tails.append(str(data)[:90])
    return "pings:\n  " + "\n  ".join(tails) if tails else ""


def _thoughts_section(conn, day: str) -> str:
    try:
        rows = conn.execute(
            "SELECT thought FROM thought_log "
            "WHERE date(created_at) = ? "
            "ORDER BY id DESC LIMIT 3",
            (day,),
        ).fetchall()
    except Exception:
        rows = []
    if not rows:
        return ""
    tails = [str(r[0])[:110] for r in rows if r[0]]
    return "thoughts:\n  " + "\n  ".join(tails) if tails else ""


def _commits_section(day: str) -> str:
    import subprocess
    try:
        start = f"{day} 00:00"
        end = f"{day} 23:59"
        out = subprocess.run(
            ["git", "log", f"--since={start}", f"--until={end}",
             "--pretty=format:%h %s"],
            capture_output=True, text=True, timeout=5,
            cwd=str(__import__('pathlib').Path(__file__).resolve().parents[1]),
        )
        if out.returncode != 0 or not out.stdout.strip():
            return ""
        lines = out.stdout.strip().splitlines()[:6]
        return "commits:\n  " + "\n  ".join(lines)
    except Exception:
        return ""


def build_closeout(day: Optional[str] = None) -> str:
    """Return a compact markdown closeout for the given YYYY-MM-DD (default yesterday)."""
    if not day:
        day = _default_day()

    sections: List[str] = [f"closeout {day}"]

    try:
        from data.db import get_connection
        with closing(get_connection(readonly=True)) as conn:
            for fn in (_goals_section, _events_section, _pings_section, _thoughts_section):
                try:
                    out = fn(conn, day)
                    if out:
                        sections.append(out)
                except Exception:
                    continue
    except Exception as e:
        sections.append(f"[state.db unavailable: {e}]")

    commits = _commits_section(day)
    if commits:
        sections.append(commits)

    joined = "\n\n".join(sections)
    cap = 1500
    if len(joined) > cap:
        joined = joined[:cap] + "\n[truncated]"
    return joined


def main() -> int:
    day = sys.argv[1] if len(sys.argv) > 1 else None
    print(build_closeout(day))
    return 0


if __name__ == "__main__":
    sys.exit(main())
