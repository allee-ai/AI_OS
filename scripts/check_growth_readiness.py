"""Check: what are open goals, what loops exist, what's their current state?"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contextlib import closing
from data.db import get_connection

print("=== OPEN + RECENT GOALS ===")
with closing(get_connection(readonly=True)) as c:
    rows = c.execute("""
        SELECT id, title, status, priority, source, created_at
        FROM goals
        WHERE status IN ('open','in_progress','active','pending')
           OR created_at > datetime('now','-7 days')
        ORDER BY priority DESC, id DESC
        LIMIT 40
    """).fetchall()
    for r in rows:
        print(f"  #{r['id']:3d} [{r['status']:12s}] pri={r['priority']} src={r['source']:15s} {r['title'][:70]}")

print("\n=== PROPOSED GOALS (pending approval) ===")
with closing(get_connection(readonly=True)) as c:
    try:
        rows = c.execute("""
            SELECT id, title, status, source, created_at
            FROM proposed_goals
            WHERE status='pending'
            ORDER BY id DESC LIMIT 20
        """).fetchall()
        for r in rows:
            print(f"  #{r['id']:3d} [{r['status']:10s}] src={r['source']:12s} {r['title'][:70]}")
    except Exception as e:
        print(f"  (err: {e})")

print("\n=== LOOPS / SUBCONSCIOUS STATE ===")
import os
print(f"  AIOS_LOOPS env: {os.getenv('AIOS_LOOPS', '(unset)')}")
try:
    from agent.subconscious import get_core
    core = get_core()
    print(f"  threads: {core.registry.count()}")
    # threads with loops?
    for tid, t in list(core.registry._threads.items())[:20]:
        has_loop = hasattr(t, 'loop') or hasattr(t, 'tick') or hasattr(t, 'run')
        running = getattr(t, '_loop_running', None) or getattr(t, 'running', None)
        print(f"    {tid:25s} loop={has_loop} running={running}")
except Exception as e:
    print(f"  (core not awakened in this process: {e})")

print("\n=== RECENT LOG EVENTS (last 50) ===")
with closing(get_connection(readonly=True)) as c:
    try:
        rows = c.execute("""
            SELECT event_type, source, created_at
            FROM unified_events
            ORDER BY id DESC LIMIT 50
        """).fetchall()
        from collections import Counter
        types = Counter((r['event_type'], r['source']) for r in rows)
        for (et, src), n in types.most_common(15):
            print(f"  {n:3d} x {et} / {src}")
    except Exception as e:
        print(f"  (err: {e})")

print("\n=== TOOLS AVAILABLE TO AGENT ===")
with closing(get_connection(readonly=True)) as c:
    try:
        rows = c.execute("SELECT name, category FROM tools ORDER BY category, name").fetchall()
        from collections import defaultdict
        by_cat = defaultdict(list)
        for r in rows:
            by_cat[r['category']].append(r['name'])
        for cat, names in by_cat.items():
            print(f"  [{cat}] {', '.join(names[:10])}{'...' if len(names)>10 else ''}")
    except Exception as e:
        print(f"  (err: {e})")

print("\n=== identity: who cares about this project ===")
with closing(get_connection(readonly=True)) as c:
    try:
        rows = c.execute("""
            SELECT key, l1_value FROM identity_profile_facts
            WHERE profile_id='primary_user' AND key LIKE '%project%' OR key LIKE '%business%' OR key LIKE '%website%' OR key LIKE '%brand%' OR key LIKE '%market%'
            LIMIT 20
        """).fetchall()
        for r in rows:
            print(f"  {r['key']}: {r['l1_value'][:100]}")
    except Exception as e:
        print(f"  (err: {e})")
