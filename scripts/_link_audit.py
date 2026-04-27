"""Diagnose concept_links quality. Read-only."""
import sys
sys.path.insert(0, ".")
from contextlib import closing
from data.db import get_connection


def section(title):
    print("\n" + "─" * 8 + " " + title + " " + "─" * (60 - len(title)))


with closing(get_connection(readonly=True)) as conn:
    cur = conn.cursor()

    section("strength distribution (after phase-1 prune)")
    cur.execute("""
        SELECT
          CASE
            WHEN strength < 0.1 THEN '<0.1'
            WHEN strength < 0.2 THEN '0.1-0.2'
            WHEN strength < 0.3 THEN '0.2-0.3'
            WHEN strength < 0.5 THEN '0.3-0.5'
            WHEN strength < 0.7 THEN '0.5-0.7'
            WHEN strength < 0.9 THEN '0.7-0.9'
            ELSE '>=0.9'
          END as bucket,
          COUNT(*),
          AVG(fire_count),
          MAX(fire_count)
        FROM concept_links
        GROUP BY bucket ORDER BY MIN(strength)
    """)
    print(f"  {'bucket':<10} {'count':>8} {'avg_fire':>10} {'max_fire':>10}")
    for r in cur.fetchall():
        print(f"  {r[0]:<10} {r[1]:>8} {r[2]:>10.2f} {r[3]:>10}")

    section("fire_count distribution")
    cur.execute("""
        SELECT
          CASE
            WHEN fire_count = 1 THEN '1'
            WHEN fire_count = 2 THEN '2'
            WHEN fire_count <= 5 THEN '3-5'
            WHEN fire_count <= 10 THEN '6-10'
            WHEN fire_count <= 50 THEN '11-50'
            ELSE '>50'
          END as bucket,
          COUNT(*),
          AVG(strength)
        FROM concept_links
        GROUP BY bucket ORDER BY MIN(fire_count)
    """)
    print(f"  {'fires':<8} {'count':>8} {'avg_strength':>14}")
    for r in cur.fetchall():
        print(f"  {r[0]:<8} {r[1]:>8} {r[2]:>14.3f}")

    section("top 15 highest-fired links")
    cur.execute("""
        SELECT concept_a, concept_b, strength, fire_count
        FROM concept_links ORDER BY fire_count DESC LIMIT 15
    """)
    for r in cur.fetchall():
        print(f"  fires={r[3]:>5} s={r[2]:.2f}  {r[0]:<35} <-> {r[1]}")

    section("top 15 strongest links")
    cur.execute("""
        SELECT concept_a, concept_b, strength, fire_count
        FROM concept_links WHERE fire_count >= 3
        ORDER BY strength DESC LIMIT 15
    """)
    for r in cur.fetchall():
        print(f"  s={r[2]:.2f} fires={r[3]:>4}  {r[0]:<35} <-> {r[1]}")

    section("concept length distribution (post-prune, should be tighter)")
    cur.execute("""
        SELECT
          CASE
            WHEN MAX(length(concept_a), length(concept_b)) <= 10 THEN '1-10'
            WHEN MAX(length(concept_a), length(concept_b)) <= 20 THEN '11-20'
            WHEN MAX(length(concept_a), length(concept_b)) <= 30 THEN '21-30'
            WHEN MAX(length(concept_a), length(concept_b)) <= 40 THEN '31-40'
            ELSE '>40'
          END as bucket,
          COUNT(*)
        FROM concept_links
        GROUP BY bucket ORDER BY MIN(length(concept_a))
    """)
    for r in cur.fetchall():
        print(f"  {r[0]:<10} {r[1]}")

    section("how connected is each concept (degree)")
    cur.execute("""
        WITH degrees AS (
          SELECT concept_a as c FROM concept_links
          UNION ALL
          SELECT concept_b as c FROM concept_links
        )
        SELECT c, COUNT(*) as deg FROM degrees GROUP BY c
        ORDER BY deg DESC LIMIT 15
    """)
    print("  most-connected concepts (high degree = central hub):")
    for r in cur.fetchall():
        print(f"  deg={r[1]:>5}  {r[0]}")

    cur.execute("""
        WITH degrees AS (
          SELECT concept_a as c FROM concept_links
          UNION ALL
          SELECT concept_b as c FROM concept_links
        ),
        per_concept AS (SELECT c, COUNT(*) deg FROM degrees GROUP BY c)
        SELECT
          CASE
            WHEN deg = 1 THEN '1'
            WHEN deg <= 5 THEN '2-5'
            WHEN deg <= 20 THEN '6-20'
            WHEN deg <= 100 THEN '21-100'
            WHEN deg <= 500 THEN '101-500'
            ELSE '>500'
          END as bucket,
          COUNT(*) n_concepts
        FROM per_concept GROUP BY bucket ORDER BY MIN(deg)
    """)
    print("\n  degree distribution across all concepts:")
    for r in cur.fetchall():
        print(f"  deg={r[0]:<10} {r[1]} concepts")

    section("hapax legomena (singletons)")
    cur.execute("SELECT COUNT(*) FROM concept_links WHERE fire_count = 1")
    print(f"  links fired exactly once: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM concept_links WHERE fire_count = 1 AND strength >= 0.1")
    print(f"  ... with strength >= 0.1 (passed phase-1 floor): {cur.fetchone()[0]}")

    section("concept namespace patterns")
    cur.execute("""
        SELECT
          CASE
            WHEN concept_a LIKE '%.%' THEN 'dotted'
            WHEN concept_a LIKE '% %' THEN 'multiword'
            ELSE 'single_token'
          END as kind,
          COUNT(*)
        FROM concept_links GROUP BY kind
    """)
    for r in cur.fetchall():
        print(f"  {r[0]:<15} {r[1]}")

    section("link symmetry check")
    cur.execute("""
        SELECT COUNT(*) FROM concept_links a
        WHERE EXISTS (
          SELECT 1 FROM concept_links b
          WHERE b.concept_a = a.concept_b AND b.concept_b = a.concept_a
        )
    """)
    print(f"  links with reverse pair also present: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(DISTINCT concept_a||'<->'||concept_b) FROM concept_links")
    print(f"  total distinct ordered pairs: {cur.fetchone()[0]}")
