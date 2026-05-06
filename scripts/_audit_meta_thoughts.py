"""Audit: are meta_thoughts keeping up with what we've been doing?"""
from contextlib import closing
from data.db import get_connection

with closing(get_connection(readonly=True)) as conn:
    # Schema
    cols = [r[1] for r in conn.execute("PRAGMA table_info(reflex_meta_thoughts)").fetchall()]
    print("reflex_meta_thoughts columns:", cols)

    # Total + by kind
    print("\n=== by kind, all-time ===")
    for r in conn.execute("SELECT kind, COUNT(*) c FROM reflex_meta_thoughts GROUP BY kind ORDER BY c DESC"):
        print(f"  {r['kind']:30s}  {r['c']}")

    # Last 7 days by kind
    print("\n=== last 7 days ===")
    rows = conn.execute("""
        SELECT kind, COUNT(*) c
        FROM reflex_meta_thoughts
        WHERE created_at >= datetime('now', '-7 days')
        GROUP BY kind ORDER BY c DESC
    """).fetchall()
    for r in rows:
        print(f"  {r['kind']:30s}  {r['c']}")
    if not rows:
        print("  (NONE — that's the problem)")

    # Last 24h sample
    print("\n=== last 24h, most recent 15 ===")
    for r in conn.execute("""
        SELECT id, kind, weight, created_at, substr(content,1,120) AS preview
        FROM reflex_meta_thoughts
        WHERE created_at >= datetime('now','-1 day')
        ORDER BY id DESC LIMIT 15
    """):
        print(f"  #{r['id']} [{r['kind']}] w={r['weight']} {r['created_at']}")
        print(f"     {r['preview']}")

    # Count meta_thoughts vs unified_events velocity in last 24h
    ev = conn.execute("""
        SELECT COUNT(*) c FROM unified_events WHERE timestamp >= datetime('now','-1 day')
    """).fetchone()
    mt = conn.execute("""
        SELECT COUNT(*) c FROM reflex_meta_thoughts WHERE created_at >= datetime('now','-1 day')
    """).fetchone()
    print(f"\nlast 24h: events={ev['c']}  meta_thoughts={mt['c']}")

    # Did meditation/coma emit anything?
    print("\n=== does coma/meditation actually emit meta_thoughts? ===")
    src = conn.execute("""
        SELECT source, COUNT(*) c
        FROM reflex_meta_thoughts
        WHERE created_at >= datetime('now','-30 days')
        GROUP BY source ORDER BY c DESC
    """).fetchall()
    for r in src:
        print(f"  {r['source']:30s}  {r['c']}")
