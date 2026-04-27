"""Inventory of what runs without LLM or user input."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from contextlib import closing
from data.db import get_connection

print("=" * 70)
print("AUTONOMY INVENTORY — what runs without LLM or user")
print("=" * 70)

with closing(get_connection(readonly=True)) as conn:
    c = conn.cursor()

    print("\n[CRONS / TRIGGERS] — fully autonomic, mostly no LLM")
    rows = c.execute("""
        SELECT id, name, trigger_type, cron_expression, poll_interval,
               tool_name, enabled, execution_count
        FROM reflex_triggers ORDER BY id
    """).fetchall()
    for r in rows:
        en = "ON " if r["enabled"] else "off"
        sched = r["cron_expression"] or (f"poll={r['poll_interval']}s" if r["poll_interval"] else "-")
        print(f"  #{r['id']:>3} [{en}] {r['name']:<32} {r['trigger_type']:<10} {sched:<18} -> {r['tool_name']}  fires={r['execution_count']}")

    print("\n[BACKGROUND LOOPS]")
    loop_dir = "agent/subconscious/loops"
    if os.path.isdir(loop_dir):
        for f in sorted(os.listdir(loop_dir)):
            if f.endswith(".py") and not f.startswith("_"):
                print(f"  {f}")

    print("\n[REFLEX META-THOUGHTS] — by kind")
    for r in c.execute("SELECT kind, COUNT(*) n FROM reflex_meta_thoughts GROUP BY kind ORDER BY n DESC"):
        print(f"  {r['kind']:<25} {r['n']}")
    g = c.execute("SELECT COUNT(*) FROM reflex_meta_thoughts WHERE graded=1").fetchone()[0]
    t = c.execute("SELECT COUNT(*) FROM reflex_meta_thoughts").fetchone()[0]
    print(f"  graded: {g}/{t}")

    print("\n[LINKING_CORE]")
    n = c.execute("SELECT COUNT(*) FROM concept_links").fetchone()[0]
    lp = c.execute("SELECT COUNT(*) FROM concept_links WHERE potentiation > 0").fetchone()[0]
    avg = c.execute("SELECT AVG(strength) FROM concept_links").fetchone()[0]
    print(f"  links: {n}  potentiated: {lp}  avg_strength: {avg:.3f}")

    print("\n[TASK QUEUE]")
    for r in c.execute("SELECT status, COUNT(*) n FROM tasks GROUP BY status"):
        print(f"  {r['status']:<15} {r['n']}")
    rows = c.execute("SELECT id, goal, source FROM tasks WHERE status='pending' ORDER BY created_at LIMIT 5").fetchall()
    if rows:
        print("  oldest pending:")
        for r in rows:
            print(f"    #{r['id']}  {(r['goal'] or '')[:60]:<60}  src={r['source']}")
