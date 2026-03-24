"""Quick DB audit — fact counts, loop outputs, etc."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db import get_connection
from contextlib import closing

with closing(get_connection(readonly=True)) as conn:
    conn.row_factory = None
    cur = conn.cursor()

    # temp_facts
    cur.execute("SELECT status, COUNT(*) FROM temp_facts GROUP BY status")
    print("=== temp_facts ===")
    total = 0
    for row in cur.fetchall():
        print(f"  {row[0]:20s} {row[1]:,}")
        total += row[1]
    print(f"  {'TOTAL':20s} {total:,}")

    # profile_facts
    print()
    try:
        cur.execute("SELECT COUNT(*) FROM profile_facts")
        pf = cur.fetchone()[0]
        print(f"=== profile_facts === {pf:,}")
        cur.execute("SELECT COUNT(DISTINCT hier_key) FROM profile_facts WHERE hier_key IS NOT NULL")
        hk = cur.fetchone()[0]
        print(f"  distinct hier_keys: {hk}")
        # Sample some
        cur.execute("SELECT hier_key, text FROM profile_facts ORDER BY RANDOM() LIMIT 8")
        for row in cur.fetchall():
            print(f"  [{row[0]}] {str(row[1])[:80]}")
    except Exception as e:
        print(f"profile_facts: {e}")

    # thought_log
    print()
    try:
        cur.execute("SELECT COUNT(*) FROM thought_log")
        print(f"=== thought_log === {cur.fetchone()[0]:,}")
        cur.execute("SELECT content FROM thought_log ORDER BY id DESC LIMIT 2")
        for row in cur.fetchall():
            print(f"  {str(row[0])[:120]}")
    except Exception as e:
        print(f"thought_log: {e}")

    # tasks
    print()
    try:
        cur.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
        print("=== tasks ===")
        for row in cur.fetchall():
            print(f"  {row[0]:20s} {row[1]:,}")
    except Exception as e:
        print(f"tasks: {e}")

    # proposed_goals
    print()
    try:
        cur.execute("SELECT status, COUNT(*) FROM proposed_goals GROUP BY status")
        print("=== proposed_goals ===")
        for row in cur.fetchall():
            print(f"  {str(row[0]):20s} {row[1]:,}")
    except Exception as e:
        print(f"proposed_goals: {e}")

    # proposed_improvements
    print()
    try:
        cur.execute("SELECT status, COUNT(*) FROM proposed_improvements GROUP BY status")
        print("=== proposed_improvements ===")
        for row in cur.fetchall():
            print(f"  {str(row[0]):20s} {row[1]:,}")
    except Exception as e:
        print(f"proposed_improvements: {e}")
