"""
scripts/audit_goals.py — One-shot goal triage.

Purpose: reclassify existing goals with the new status taxonomy
(in_progress/paused/blocked/completed) and assign urgency scores (0-100)
based on what the system actually knows about each goal.

Also captures a new Email Autonomy v1 goal as a high-urgency anchor.

Safe to re-run. Status/urgency updates are idempotent.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.subconscious.loops.goals import (  # noqa: E402
    _ensure_goals_table,
    propose_goal,
    resolve_goal,
    set_goal_urgency,
)


# ─────────────────────────────────────────────────────────────
# Reclassification plan — decided from what the system actually
# knows about each goal, not guessing.
#
# Format: goal_id -> (new_status, urgency_0_to_100, reason)
# ─────────────────────────────────────────────────────────────
RECLASSIFY: dict[int, tuple[str, int, str]] = {
    # #7: SMS bridge. Redundant with working ntfy — phone push is live and
    # bidirectional via aios notify. Dismissing.
    7: ("dismissed", 0,
        "ntfy covers this; bidirectional phone alerts working since commit 5683593"),

    # #8: VS Code Remote on AIOS VM. Still open; user asked for it explicitly.
    # Unblocked now that we have vm_sync.sh + Ollama cloud working.
    8: ("in_progress", 65,
        "Remote-SSH extension path is clear; vm_sync.sh exists. Medium urgency."),

    # #9: state-vs-bare eval. Actually ran today: n=7, 5/7 passed, win=0.71,
    # personalization=0.57. Completed.
    9: ("completed", 100,
        "Ran 2026-04-22: state_vs_bare_2d19bab7.json, 5/7 passed, win 0.71"),

    # #10: self-teaching Q&A loop from commits/docs/turns. Approved earlier,
    # never started. Parks cleanly as paused because it's valuable but not
    # blocking the email-autonomy flagship goal.
    10: ("paused", 40,
         "Valuable but not blocking; revisit after Email Autonomy Phase 1."),

    # #11: TEST goal-add chime. Was literally a smoke test; hook verified.
    11: ("completed", 100,
         "goal#11 chimed mac + pushed phone 2026-04-22 — hook verified"),

    # #12: relocate research/ artifacts to workspace/. Low friction, high
    # payoff (surfaces hebbian/sae stats in STATE). Raising urgency a bit.
    12: ("approved", 55,
         "Small lift; closes loop between research/ and agent STATE."),
}


def main() -> int:
    _ensure_goals_table()

    print("=== goal audit start ===")
    for gid, (status, urgency, reason) in RECLASSIFY.items():
        ok_s = resolve_goal(gid, status=status)
        ok_u = set_goal_urgency(gid, urgency)
        tag = "OK" if (ok_s and ok_u) else "FAIL"
        print(f"  [{tag}] goal#{gid} -> {status}  urgency={urgency}")
        print(f"         reason: {reason}")

    # Capture Email Autonomy v1 as the new flagship goal.
    email_goal = (
        "Email Autonomy v1 — triage inbox, draft replies, "
        "escalate only the ~2% that actually need me"
    )
    email_rationale = (
        "4-phase plan. Phase 1: inbox_triage loop classifies "
        "{ignore,file,draft,escalate} and fires ntfy only on escalate; "
        "2-week observation period generates free labeled training data. "
        "Phase 2: draft replies into a 'Nola drafts' IMAP folder; every "
        "user edit is a training diff. Phase 3: auto-send gated on >90% "
        "accuracy for 4 weeks in a category + 5-min STOP window. Phase 4: "
        "proactive outbound tied to open goals. Generalizes to calendar, "
        "Slack, GitHub, SMS, payments — all (source, content) -> action."
    )
    new_id = propose_goal(
        goal=email_goal,
        rationale=email_rationale,
        priority="high",
        sources=["user_vscode", "audit_goals.py"],
    )
    if new_id:
        set_goal_urgency(new_id, 85)
        print(f"\n  [OK] NEW goal#{new_id} stored: Email Autonomy v1  urgency=85")
    else:
        print("\n  [FAIL] could not store Email Autonomy v1")

    # Summary print so the user can eyeball the result.
    from contextlib import closing
    from data.db import get_connection
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute(
            "SELECT id, status, priority, urgency, substr(goal,1,70) "
            "FROM proposed_goals ORDER BY "
            "  CASE status "
            "    WHEN 'in_progress' THEN 0 "
            "    WHEN 'pending' THEN 1 "
            "    WHEN 'approved' THEN 2 "
            "    WHEN 'blocked' THEN 3 "
            "    WHEN 'paused' THEN 4 "
            "    WHEN 'completed' THEN 5 "
            "    WHEN 'dismissed' THEN 6 "
            "    WHEN 'rejected' THEN 7 "
            "    ELSE 8 END, "
            "  COALESCE(urgency, 0) DESC, id DESC"
        ).fetchall()
    print("\n=== after audit ===")
    print(f"  {'id':<4}{'status':<13}{'pri':<8}{'urg':<5}goal")
    for r in rows:
        urg = str(r[3]) if r[3] is not None else "-"
        print(f"  #{r[0]:<3}{r[1]:<13}{r[2]:<8}{urg:<5}{r[4]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
