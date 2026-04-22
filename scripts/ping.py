#!/usr/bin/env python3
"""
scripts/ping.py — Send a low-overhead notification to the user's dashboard.

Writes into the existing `notifications` table used by the notify tool and
served by /api/subconscious/notifications, so the existing dashboard panel
picks it up with zero new infrastructure.

Usage:
    .venv/bin/python scripts/ping.py "I finished goal #9, results in eval/"
    .venv/bin/python scripts/ping.py "blocked on X" --priority high
    .venv/bin/python scripts/ping.py --list            # show recent
    .venv/bin/python scripts/ping.py --unread          # show unread only

By default, pings also get mirrored into today's vscode_copilot chat session
so they appear in the chat window as a short assistant note ("pings" feed
type). Pass --no-mirror to skip.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_table() -> None:
    from data.db import get_connection
    from contextlib import closing
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
        conn.commit()


def cmd_send(message: str, priority: str, source: str, mirror: bool) -> int:
    from data.db import get_connection
    from contextlib import closing
    import json

    _ensure_table()
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO notifications (type, message, priority, context) VALUES (?, ?, ?, ?)",
            ("ping", message, priority, json.dumps({"source": source})),
        )
        conn.commit()
        nid = cur.lastrowid

    # Emit log event so the log thread / consequences block see pings.
    try:
        from agent.threads.log.schema import log_event
        log_event(
            event_type="ping_sent",
            data=message,
            metadata={"notification_id": nid, "priority": priority, "source": source},
            source="scripts/ping.py",
        )
    except Exception:
        pass

    # Mirror into today's vscode_copilot chat so the chat window shows it.
    if mirror:
        try:
            from chat.schema import save_conversation, add_turn
            from datetime import datetime as _dt
            today = _dt.now().strftime("%Y-%m-%d")
            session_id = f"vscode_copilot_{today}"
            save_conversation(
                session_id=session_id,
                name=f"VS Code coding — {today}",
                channel="react",
                source="vscode_copilot",
            )
            add_turn(
                session_id=session_id,
                user_message=f"[ping #{nid}] from {source}",
                assistant_message=message,
                feed_type="ping",
                context_level=0,
                metadata={"source": source, "priority": priority, "notification_id": nid},
            )
        except Exception:
            pass

    print(f"ping#{nid} [{priority}] {message}")
    return 0


def cmd_list(unread_only: bool, limit: int) -> int:
    from data.db import get_connection
    from contextlib import closing

    _ensure_table()
    sql = "SELECT id, priority, message, read, dismissed, created_at FROM notifications"
    if unread_only:
        sql += " WHERE read = 0 AND dismissed = 0"
    sql += " ORDER BY id DESC LIMIT ?"
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
    if not rows:
        print("(no notifications)")
        return 0
    for r in rows:
        flag = " " if (r[3] or r[4]) else "•"
        print(f"{flag} #{r[0]:<4} [{r[1]:<6}] {r[5]}  {r[2]}")
    return 0


def cmd_read(nid: int) -> int:
    from data.db import get_connection
    from contextlib import closing
    _ensure_table()
    with closing(get_connection()) as conn:
        conn.execute("UPDATE notifications SET read = 1 WHERE id = ?", (nid,))
        conn.commit()
    print(f"ping#{nid} read")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Low-overhead ping to the AIOS dashboard.")
    p.add_argument("message", nargs="?", help="Message text.")
    p.add_argument("--priority", choices=["low", "normal", "high", "urgent"], default="normal")
    p.add_argument("--source", default="vscode_copilot")
    p.add_argument("--no-mirror", action="store_true", help="Don't mirror to chat.")
    p.add_argument("--list", action="store_true")
    p.add_argument("--unread", action="store_true")
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--read", type=int, help="Mark notification N as read.")
    args = p.parse_args(argv)

    if args.read is not None:
        return cmd_read(args.read)
    if args.list or args.unread:
        return cmd_list(args.unread, args.limit)

    if not args.message:
        p.print_help(sys.stderr)
        return 2
    return cmd_send(args.message, args.priority, args.source, mirror=not args.no_mirror)


if __name__ == "__main__":
    sys.exit(main())
