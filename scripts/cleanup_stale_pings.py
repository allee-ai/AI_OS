"""Bulk cleanup of stale mobile-test ping goals.

Goals #15-19, #21, #22 are leftover mobile-panel test pings ("ping me if this
shows up", "random 3-digit number"). They were urgent priority but stuck at
pending forever. Strategy:

1. Fire ONE consolidated alert acknowledging the stale pings (so the literal
   intent of the goal text is satisfied — Cade asked to be pinged).
2. Bulk-mark all 7 as completed with a clarifying rationale.
3. Print a summary so it's auditable.
"""

from __future__ import annotations

import sys
from contextlib import closing
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from data.db import get_connection, set_demo_mode  # noqa: E402

STALE_IDS = [15, 16, 17, 18, 19, 21, 22]
RATIONALE_NOTE = (
    "[copilot cleanup] mobile-panel test ping; goal #20 (no optimistic UI) "
    "is what made these pile up. Acknowledged via consolidated alert and "
    "marked completed retroactively."
)


def fire_consolidated_alert(ids: list[int]) -> int | None:
    from agent.threads.form.tools.executables.notify import run as notify_run

    message = (
        f"Retroactive ping for stale test goals #{', #'.join(str(i) for i in ids)} "
        "— Copilot acknowledged and cleared them. Mobile addGoal optimistic UI "
        "is now fixed (goal #20)."
    )
    result = notify_run("alert", {"message": message, "priority": "normal"})
    print(f"[alert] {result}")
    # Result format: "Alert sent (id=N, priority=...): ..."
    if "id=" in result:
        try:
            return int(result.split("id=")[1].split(",")[0])
        except (IndexError, ValueError):
            return None
    return None


def mark_completed(ids: list[int], note: str) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        for gid in ids:
            row = cur.execute(
                "SELECT id, goal, status, rationale FROM proposed_goals WHERE id=?",
                (gid,),
            ).fetchone()
            if not row:
                print(f"  goal #{gid}: NOT FOUND")
                continue
            old_status = row["status"]
            if old_status in ("completed", "dismissed", "archived"):
                print(f"  goal #{gid}: already {old_status}, skipping")
                continue
            new_rationale = (row["rationale"] or "").rstrip()
            new_rationale = (new_rationale + "\n\n" + note).strip()
            cur.execute(
                """
                UPDATE proposed_goals
                SET status = 'completed',
                    rationale = ?,
                    resolved_at = datetime('now')
                WHERE id = ?
                """,
                (new_rationale, gid),
            )
            print(f"  goal #{gid}: {old_status} -> completed | {row['goal'][:60]}")
            rows.append((gid, row["goal"]))
        conn.commit()
    return rows


def main() -> int:
    set_demo_mode(False)
    print(f"=== cleanup stale ping goals: {STALE_IDS} ===\n")
    print("[1/2] firing consolidated alert...")
    alert_id = fire_consolidated_alert(STALE_IDS)
    note = RATIONALE_NOTE
    if alert_id is not None:
        note += f" (alert#{alert_id})"

    print("\n[2/2] marking goals completed...")
    cleared = mark_completed(STALE_IDS, note)

    print(f"\n=== done: {len(cleared)} goals cleared, alert#{alert_id} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
