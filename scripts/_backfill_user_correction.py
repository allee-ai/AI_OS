#!/usr/bin/env python3
"""One-shot backfill: promote specific copilot notes to user_correction.

These are notes where Cade explicitly pushed back / corrected me, but
the note was logged via copilot_note.py before --from-user existed.
After this runs, scripts/confidence.py user_correction_alignment signal
has actual rows to score against.

Run once. Idempotent: if source is already user_correction, no-op.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.db import get_connection

# (note_id, why) — explicit allow-list, no fuzzy matching.
BACKFILL = [
    (233, "Cade pushed back on hub-key stoplist: 'why are we pruning hubs?'"),
]


def main() -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        promoted = []
        skipped = []
        for nid, why in BACKFILL:
            row = cur.execute(
                "SELECT id, kind, source, weight FROM reflex_meta_thoughts WHERE id = ?",
                (nid,),
            ).fetchone()
            if row is None:
                skipped.append((nid, "missing"))
                continue
            if row["source"] == "user_correction":
                skipped.append((nid, "already user_correction"))
                continue
            cur.execute(
                "UPDATE reflex_meta_thoughts "
                "SET source = 'user_correction', weight = MAX(weight, 0.95) "
                "WHERE id = ?",
                (nid,),
            )
            promoted.append((nid, row["source"], row["weight"], why))
        conn.commit()

    for nid, src, w, why in promoted:
        print(f"  promoted #{nid}: {src} w={w:.2f} -> user_correction w=0.95")
        print(f"    why: {why}")
    for nid, reason in skipped:
        print(f"  skipped #{nid}: {reason}")
    print(f"total promoted: {len(promoted)}  skipped: {len(skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
