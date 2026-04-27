"""
Data audit — see what's actually in the high-volume tables.

Goal: find where signal is being lost between raw convo → curated fact.
The funnel from convo_turns (8251) → temp_facts (10327) → profile_facts (34)
suggests extraction is permissive and curation is ~nonexistent.
"""

from __future__ import annotations

import sqlite3
import json
from collections import Counter
from pathlib import Path

DB = Path("/Users/cade/Desktop/AI_OS/data/db/state.db")


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main() -> None:
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ── temp_facts: the suspected noise floor ─────────────────────────
    section("temp_facts (10,327 rows) — schema & sample")
    cur.execute("PRAGMA table_info(temp_facts)")
    cols = [r["name"] for r in cur.fetchall()]
    print("columns:", cols)
    cur.execute("SELECT * FROM temp_facts ORDER BY ROWID DESC LIMIT 8")
    for i, row in enumerate(cur.fetchall()):
        d = dict(row)
        # truncate long fields
        for k, v in d.items():
            if isinstance(v, str) and len(v) > 200:
                d[k] = v[:200] + "..."
        print(f"  [{i}] {d}")

    # Distribution by some likely status/source column
    for col in ("source", "status", "promoted", "kind", "type", "thread", "fact_type"):
        if col in cols:
            cur.execute(f"SELECT {col}, COUNT(*) c FROM temp_facts GROUP BY {col} ORDER BY c DESC LIMIT 10")
            print(f"\n  by {col}:")
            for r in cur.fetchall():
                print(f"    {r[col]!r}: {r['c']}")

    # ── profile_facts: the curated tier ──────────────────────────────
    section("profile_facts (34 rows) — the curated bar")
    cur.execute("PRAGMA table_info(profile_facts)")
    cols_pf = [r["name"] for r in cur.fetchall()]
    print("columns:", cols_pf)
    cur.execute("SELECT * FROM profile_facts ORDER BY ROWID LIMIT 20")
    for r in cur.fetchall():
        d = dict(r)
        for k, v in d.items():
            if isinstance(v, str) and len(v) > 120:
                d[k] = v[:120] + "..."
        print(f"  {d}")

    # ── concept_links: distribution of strength ──────────────────────
    section("concept_links (653,496 rows) — strength distribution")
    cur.execute("""
        SELECT
            COUNT(*) total,
            AVG(strength) avg_s,
            MIN(strength) min_s,
            MAX(strength) max_s
        FROM concept_links
    """)
    r = cur.fetchone()
    print(f"  total={r['total']}  avg={r['avg_s']:.3f}  min={r['min_s']:.3f}  max={r['max_s']:.3f}")

    # Buckets
    cur.execute("""
        SELECT
            CASE
                WHEN strength < 0.1 THEN '< 0.1 (noise)'
                WHEN strength < 0.3 THEN '0.1-0.3'
                WHEN strength < 0.5 THEN '0.3-0.5'
                WHEN strength < 0.7 THEN '0.5-0.7'
                WHEN strength < 0.9 THEN '0.7-0.9'
                ELSE '0.9+'
            END bucket,
            COUNT(*) c
        FROM concept_links
        GROUP BY bucket
        ORDER BY MIN(strength)
    """)
    for r in cur.fetchall():
        print(f"  {r['bucket']:<18} {r['c']:>8}")

    # Fire counts
    cur.execute("""
        SELECT
            CASE
                WHEN fire_count = 1 THEN '1 (singleton)'
                WHEN fire_count <= 3 THEN '2-3'
                WHEN fire_count <= 10 THEN '4-10'
                WHEN fire_count <= 50 THEN '11-50'
                ELSE '50+'
            END bucket,
            COUNT(*) c
        FROM concept_links
        GROUP BY bucket
        ORDER BY MIN(fire_count)
    """)
    print("\n  fire_count distribution (singletons = noise candidates):")
    for r in cur.fetchall():
        print(f"  {r['bucket']:<18} {r['c']:>8}")

    # Sample of weakest links
    cur.execute("""
        SELECT concept_a, concept_b, strength, fire_count
        FROM concept_links
        WHERE strength < 0.15 AND fire_count = 1
        ORDER BY RANDOM()
        LIMIT 10
    """)
    print("\n  10 random weak singletons (probably junk):")
    for r in cur.fetchall():
        print(f"    {r['concept_a']!r} ↔ {r['concept_b']!r}  s={r['strength']:.2f} f={r['fire_count']}")

    # Sample of strongest links
    cur.execute("""
        SELECT concept_a, concept_b, strength, fire_count
        FROM concept_links
        WHERE strength > 0.85
        ORDER BY fire_count DESC
        LIMIT 15
    """)
    print("\n  15 strongest+most-fired (the real signal):")
    for r in cur.fetchall():
        print(f"    {r['concept_a']!r} ↔ {r['concept_b']!r}  s={r['strength']:.2f} f={r['fire_count']}")

    # ── convo_turns: source of truth ─────────────────────────────────
    section("convo_turns (8,251 rows) — source quality sample")
    cur.execute("PRAGMA table_info(convo_turns)")
    print("columns:", [r["name"] for r in cur.fetchall()])
    cur.execute("""
        SELECT user_message, assistant_message, length(user_message) ulen
        FROM convo_turns
        WHERE length(user_message) > 100 AND length(user_message) < 400
        ORDER BY ROWID DESC
        LIMIT 5
    """)
    print("\n  recent user turns (medium length):")
    for r in cur.fetchall():
        print(f"  >>> USER: {r['user_message'][:300]}")
        print()

    # ── thought_log ────────────────────────────────────────────────
    section("thought_log (2,454 rows) — sample")
    cur.execute("PRAGMA table_info(thought_log)")
    print("columns:", [r["name"] for r in cur.fetchall()])
    cur.execute("SELECT * FROM thought_log ORDER BY ROWID DESC LIMIT 5")
    for r in cur.fetchall():
        d = dict(r)
        for k, v in d.items():
            if isinstance(v, str) and len(v) > 200:
                d[k] = v[:200] + "..."
        print(f"  {d}")

    # ── reflex_meta_thoughts ─────────────────────────────────────────
    section("reflex_meta_thoughts (166 rows) — sample")
    cur.execute("PRAGMA table_info(reflex_meta_thoughts)")
    print("columns:", [r["name"] for r in cur.fetchall()])
    cur.execute("SELECT * FROM reflex_meta_thoughts ORDER BY ROWID DESC LIMIT 4")
    for r in cur.fetchall():
        d = dict(r)
        for k, v in d.items():
            if isinstance(v, str) and len(v) > 200:
                d[k] = v[:200] + "..."
        print(f"  {d}")

    conn.close()


if __name__ == "__main__":
    main()
