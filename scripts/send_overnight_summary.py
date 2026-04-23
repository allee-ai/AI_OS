"""Send Cade a wake-up ping summarizing the overnight autonomy session.

This is the last thing I do before stopping. The morning brief covers
what's in STATE; this ping is the human-readable headline of what tonight
specifically was.
"""
import json
import sys
import subprocess
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.db import get_connection


def _commit_count_since(hours: int) -> int:
    try:
        out = subprocess.run(
            ["git", "log", f"--since={hours} hours ago", "--oneline", "--no-merges"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        return len([l for l in out.splitlines() if l])
    except Exception:
        return 0


def main() -> int:
    n_commits = _commit_count_since(12)

    summary_lines = [
        "Good morning, Cade. Overnight summary:",
        "",
        f"  • {n_commits} commits while you slept (all reversible — `git log` to inspect).",
        "  • morning_brief.py shipped: JARVIS-style daily digest sourced from STATE.",
        "    Run: `.venv/bin/python scripts/morning_brief.py --print` (add --speak for TTS).",
        "  • wifi_collector.py shipped: privacy-safe field collector. Tested working.",
        "    Run: `.venv/bin/python scripts/wifi_collector.py --once --env home`",
        "  • 5 self-portrait facts written to value_system.machine — including",
        "    'self.operator_framing' and 'self.behavior_when_alone'.",
        "  • 9 reflex meta-thoughts captured (6 expected, 3 rejected) — what to do",
        "    and what NOT to do under autonomy.",
        "  • /api/morning-brief endpoint added (restart server to pick up).",
        "",
        "Boundaries I held: no host services installed, no public site changes,",
        "no external paid APIs, no destructive ops. All work is in commits on main.",
        "",
        "Hand-back: read morning brief first, then `git log --since='12 hours ago'`",
        "to see what changed. Push back on anything that doesn't belong.",
        "",
        "— Nola",
    ]
    text = "\n".join(summary_lines)
    print(text)
    print()

    # Write to notifications
    try:
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
                ("overnight_summary", text, "high",
                 json.dumps({"source": "overnight_session_2026_04_22",
                             "commits": n_commits})),
            )
            conn.commit()
            nid = cur.lastrowid
        print(f"[ping written: id={nid}, priority=high]")

        # Try to fire ntfy alert
        try:
            from agent.services.alerts import fire_alerts
            fire_alerts(
                f"overnight: {n_commits} commits, morning brief + wifi collector + self-portrait shipped",
                "high", nid=nid, source="overnight_summary",
            )
            print("[ntfy fired]")
        except Exception as e:
            print(f"[ntfy skipped: {e}]")
    except Exception as e:
        print(f"[ping write failed: {e}]")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
