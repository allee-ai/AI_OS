"""
aios_thoughts — list / read / dismiss thoughts emitted by the reflector.

Operator-side cleanup tool. Reflector pauses when N unresolved thoughts
exist (default 3); use this to clear the backlog so it can keep
ticking.

Usage:
    python scripts/aios_thoughts.py list                 # show unresolved
    python scripts/aios_thoughts.py list --all           # include resolved
    python scripts/aios_thoughts.py read <id> [<id>...]  # mark read
    python scripts/aios_thoughts.py dismiss <id> [<id>...]
    python scripts/aios_thoughts.py read --all           # clear all unread
    python scripts/aios_thoughts.py dismiss --all
    python scripts/aios_thoughts.py count                # unresolved count

Run on the droplet to clear droplet backlog; on laptop to clear local.
"""

from __future__ import annotations

import argparse
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.db import get_connection  # noqa: E402

THOUGHT_TYPE = "aios_thought"


def _list(show_all: bool) -> int:
    sql = ("SELECT id, message, read, dismissed, created_at "
           "FROM notifications WHERE type = ?")
    if not show_all:
        sql += " AND read = 0 AND dismissed = 0"
    sql += " ORDER BY id DESC"
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute(sql, (THOUGHT_TYPE,)).fetchall()
    if not rows:
        print("(no thoughts)")
        return 0
    for r in rows:
        flag = " "
        if r["dismissed"]:
            flag = "X"
        elif r["read"]:
            flag = "."
        msg = r["message"]
        if len(msg) > 110:
            msg = msg[:107] + "..."
        print(f"  [{flag}] #{r['id']:>4} {r['created_at']}  {msg}")
    return 0


def _update(ids: list[int], all_unread: bool, *, field: str) -> int:
    """field is 'read' or 'dismissed'."""
    if field not in ("read", "dismissed"):
        raise ValueError(field)
    with closing(get_connection()) as conn:
        if all_unread:
            cur = conn.execute(
                f"UPDATE notifications SET {field} = 1 "
                "WHERE type = ? AND read = 0 AND dismissed = 0",
                (THOUGHT_TYPE,),
            )
        elif ids:
            placeholders = ",".join("?" * len(ids))
            cur = conn.execute(
                f"UPDATE notifications SET {field} = 1 "
                f"WHERE type = ? AND id IN ({placeholders})",
                (THOUGHT_TYPE, *ids),
            )
        else:
            print(f"need ids or --all", file=sys.stderr)
            return 2
        conn.commit()
        print(f"{field}: {cur.rowcount} row(s) updated")
    return 0


def _count() -> int:
    with closing(get_connection(readonly=True)) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM notifications "
            "WHERE type = ? AND read = 0 AND dismissed = 0",
            (THOUGHT_TYPE,),
        ).fetchone()
    print(int(row["n"]) if row else 0)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list", help="list thoughts")
    pl.add_argument("--all", action="store_true",
                    help="include read/dismissed")

    pr = sub.add_parser("read", help="mark thought(s) as read")
    pr.add_argument("ids", nargs="*", type=int)
    pr.add_argument("--all", action="store_true")

    pd = sub.add_parser("dismiss", help="dismiss thought(s)")
    pd.add_argument("ids", nargs="*", type=int)
    pd.add_argument("--all", action="store_true")

    sub.add_parser("count", help="unresolved count")

    args = p.parse_args()
    if args.cmd == "list":
        return _list(args.all)
    if args.cmd == "read":
        return _update(args.ids, args.all, field="read")
    if args.cmd == "dismiss":
        return _update(args.ids, args.all, field="dismissed")
    if args.cmd == "count":
        return _count()
    return 1


if __name__ == "__main__":
    sys.exit(main())
