"""Refocus STATE on vre-construction reconstruction company.

What this does:
1. Adds a high-priority focus goal for today's 5pm reconstruction launch.
2. Closes goal #61 (site migration via Caddy) — that was completed today.
3. Marks the stale Jake ping (#62, 2026-04-28) as read so it stops being
   the 'latest' high-priority ping surfacing in STATE.
4. Logs a focus directive event so the agent's recent log centers on
   reconstruction-company work.

Jake-financial-crisis goals (#51, #52, #57, etc.) are left intact — those
are live life-concerns, just not today's work focus.
"""
from __future__ import annotations

import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.subconscious.loops.goals import propose_goal  # noqa: E402
from agent.threads.log.schema import log_event  # noqa: E402
from data.db import get_connection  # noqa: E402


def main() -> None:
    actions: list[str] = []

    # 1. Top-priority focus goal for today's reconstruction launch.
    focus_goal_id = propose_goal(
        goal=(
            "Reconstruction company (vre-construction.com) launch — site is "
            "live, marketing assets due by 5pm 2026-05-14. Today's primary "
            "focus. Sub-tasks: (a) validate /contact-submit end-to-end "
            "delivers Proton email; (b) SEO basics — sitemap.xml, "
            "robots.txt, schema.org LocalBusiness, OpenGraph; (c) marketing "
            "assets — Google Business profile copy, Facebook/Nextdoor post "
            "drafts, flyer; (d) refine sales/investor-onepager.md and "
            "sales/cold-call-cheatsheet.md."
        ),
        rationale=(
            "User explicit focus 2026-05-14: 'were focusing on the "
            "reconstruction company'. 5pm deadline. Site at "
            "https://vre-construction.com is live with HTTPS 200, TLS "
            "issued. Everything else (jake elements, engineering goals) "
            "is deprioritized for the rest of today."
        ),
        priority="urgent",
        sources=["user", "user_vscode"],
    )
    actions.append(f"new focus goal #{focus_goal_id}")

    # 2. Close goal #61 — migration to droplet via Caddy is done.
    with closing(get_connection()) as conn:
        cur = conn.execute(
            "SELECT id, status, substr(goal, 1, 80) AS g "
            "FROM proposed_goals WHERE id = 61"
        )
        row = cur.fetchone()
        if row and row["status"] != "completed":
            conn.execute(
                "UPDATE proposed_goals SET status = 'completed', "
                "resolved_at = CURRENT_TIMESTAMP WHERE id = 61"
            )
            actions.append("closed goal #61 (Caddy migration — done today)")

        # 3. Mark Jake ping #62 as read (stale from 2026-04-28).
        cur = conn.execute("SELECT id, read FROM notifications WHERE id = 62")
        row = cur.fetchone()
        if row and not row["read"]:
            conn.execute(
                "UPDATE notifications SET read = 1, "
                "response = 'acknowledged 2026-05-14: not today''s focus; "
                "reconstruction launch + marketing is the 5pm priority' "
                "WHERE id = 62"
            )
            actions.append("acknowledged Jake ping #62")

        conn.commit()

    # 4. Focus directive event — anchors STATE's recent log on the right topic.
    eid = log_event(
        "system",
        "FOCUS DIRECTIVE 2026-05-14: Reconstruction company "
        "(vre-construction.com) is the active work for the rest of today. "
        "Site is live. Remaining: contact-form e2e test, SEO basics, "
        "marketing assets (GBP copy, social posts, flyer), sales-asset "
        "refinement. Jake/business-dashboard work is paused until after "
        "5pm. Engineering goals (#13 email autonomy, #63 secrets, #65 "
        "facts pipeline) are not the focus today.",
        thread_subject="vre_construction_launch",
        tags=["focus", "directive", "reconstruction", "vre_construction",
              "marketing", "today"],
    )
    actions.append(f"logged focus directive event #{eid}")

    for a in actions:
        print(f"  {a}")


if __name__ == "__main__":
    main()
