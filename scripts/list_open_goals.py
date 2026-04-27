"""List all open goals so we can decide which to do in-chat."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contextlib import closing
from data.db import get_connection, set_demo_mode

set_demo_mode(False)

with closing(get_connection(readonly=True)) as conn:
    rows = conn.execute("""
        SELECT id, goal, rationale, status, priority, urgency, sources, risk, created_at
        FROM proposed_goals
        WHERE status NOT IN ('completed', 'rejected', 'archived', 'failed')
        ORDER BY 
          CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
          id DESC
        LIMIT 80
    """).fetchall()

print(f"open goals: {len(rows)}\n")
for r in rows:
    goal_text = r["goal"][:150]
    rationale = (r["rationale"] or "")[:200].replace("\n", " ")
    sources = (r["sources"] or "")[:80].replace("\n", " ")
    print(f"#{r['id']:>3} [{r['priority'] or '-':6}] [{r['status']:9}] [risk={r['risk'] or '-':4}] {goal_text}")
    if rationale:
        print(f"      why: {rationale}")
    if sources:
        print(f"      src: {sources}")
