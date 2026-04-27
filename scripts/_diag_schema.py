"""Quick diagnostic for goal #46 + convo_turns schema."""
from contextlib import closing
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.db import get_connection

with closing(get_connection(readonly=True)) as conn:
    cur = conn.execute("SELECT id, status, priority, goal FROM proposed_goals WHERE id=46")
    row = cur.fetchone()
    print("goal#46 ->", dict(row) if row else None)

    cur = conn.execute("PRAGMA table_info(convo_turns)")
    print("\nconvo_turns columns:")
    for r in cur.fetchall():
        print(" ", r["name"], r["type"])

    cur = conn.execute("SELECT COUNT(*) AS n FROM convo_turns")
    print("\nconvo_turns row count:", cur.fetchone()["n"])

    cur = conn.execute("SELECT * FROM convo_turns ORDER BY id DESC LIMIT 1")
    last = cur.fetchone()
    if last:
        print("\nlast convo_turn keys:", list(last.keys()))
