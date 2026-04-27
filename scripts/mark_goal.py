"""Mark goals completed (or other status). One-shot helper since
the audit-goal pipeline used --mark-done baked into run_goal.py
but for goals being completed here in chat we need a tiny CLI."""
import sys, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contextlib import closing
from data.db import get_connection, set_demo_mode

set_demo_mode(False)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--status", default="completed",
                   choices=["completed", "in_progress", "dismissed", "archived", "approved"])
    p.add_argument("--note", default=None,
                   help="Append a one-line note onto rationale describing how it was completed.")
    a = p.parse_args()

    with closing(get_connection()) as c:
        row = c.execute(
            "SELECT id, goal, status, rationale FROM proposed_goals WHERE id=?",
            (a.id,),
        ).fetchone()
        if not row:
            print(f"goal #{a.id} not found", file=sys.stderr)
            return 1
        new_rationale = row["rationale"] or ""
        if a.note:
            stamp = f"\n[completed in-chat] {a.note}"
            new_rationale = (new_rationale + stamp)[:4000]
        c.execute(
            "UPDATE proposed_goals SET status=?, rationale=?, resolved_at=datetime('now') WHERE id=?",
            (a.status, new_rationale, a.id),
        )
        c.commit()
    print(f"goal #{a.id}: {row['status']} → {a.status}")
    print(f"  goal: {row['goal'][:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
