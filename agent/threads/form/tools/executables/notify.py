"""
notify — Send notifications to the user
========================================

Actions:
    alert(message, priority)           → immediate notification
    remind(message, context)           → contextual reminder
    confirm(question, options)         → request user confirmation

Notifications are stored in a DB table and surfaced via the frontend.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[5]  # → AI_OS/


def _ensure_notifications_table() -> None:
    """Create notifications table if needed."""
    try:
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
    except Exception as e:
        print(f"[notify] Failed to create table: {e}")


def run(action: str, params: dict) -> str:
    """Execute a notify action."""
    actions = {
        "alert": _alert,
        "remind": _remind,
        "confirm": _confirm,
        "list": _list_notifications,
        "dismiss": _dismiss,
    }

    fn = actions.get(action)
    if not fn:
        return f"Unknown action: {action}. Available: {', '.join(actions)}"

    try:
        return fn(params)
    except Exception as e:
        return f"Error: {e}"


def _alert(params: dict) -> str:
    """Send an immediate notification."""
    message = params.get("message", "").strip()
    if not message:
        return "Error: message is required"

    priority = params.get("priority", "normal")
    if priority not in ("low", "normal", "high", "urgent"):
        priority = "normal"

    _ensure_notifications_table()
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO notifications (type, message, priority) VALUES (?, ?, ?)",
            ("alert", message, priority)
        )
        conn.commit()
        nid = cur.lastrowid

    return f"Alert sent (id={nid}, priority={priority}): {message}"


def _remind(params: dict) -> str:
    """Send a contextual reminder."""
    message = params.get("message", "").strip()
    if not message:
        return "Error: message is required"

    context = params.get("context", "")
    _ensure_notifications_table()
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO notifications (type, message, context) VALUES (?, ?, ?)",
            ("reminder", message, json.dumps({"context": context}))
        )
        conn.commit()
        nid = cur.lastrowid

    return f"Reminder created (id={nid}): {message}"


def _confirm(params: dict) -> str:
    """Request user confirmation."""
    question = params.get("question", "").strip()
    if not question:
        return "Error: question is required"

    options = params.get("options", ["yes", "no"])
    if isinstance(options, str):
        options = [o.strip() for o in options.split(",")]

    _ensure_notifications_table()
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO notifications (type, message, priority, context) VALUES (?, ?, ?, ?)",
            ("confirm", question, "high", json.dumps({"options": options}))
        )
        conn.commit()
        nid = cur.lastrowid

    return f"Confirmation requested (id={nid}): {question} [{'/'.join(options)}]"


def _list_notifications(params: dict) -> str:
    """List recent notifications."""
    _ensure_notifications_table()
    limit = int(params.get("limit", 10))
    unread_only = params.get("unread_only", False)

    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        if unread_only:
            cur.execute(
                "SELECT id, type, message, priority, read, created_at FROM notifications "
                "WHERE read = 0 AND dismissed = 0 ORDER BY id DESC LIMIT ?",
                (limit,)
            )
        else:
            cur.execute(
                "SELECT id, type, message, priority, read, created_at FROM notifications "
                "ORDER BY id DESC LIMIT ?",
                (limit,)
            )
        rows = cur.fetchall()

    if not rows:
        return "No notifications"

    lines = []
    for r in rows:
        status = "unread" if not r[4] else "read"
        lines.append(f"[{r[0]}] ({r[1]}/{r[3]}) {r[2]} — {status} — {r[5]}")
    return "\n".join(lines)


def _dismiss(params: dict) -> str:
    """Dismiss a notification by ID."""
    nid = params.get("id")
    if nid is None:
        return "Error: id is required"

    _ensure_notifications_table()
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection()) as conn:
        conn.execute(
            "UPDATE notifications SET dismissed = 1 WHERE id = ?",
            (int(nid),)
        )
        conn.commit()

    return f"Notification {nid} dismissed"
