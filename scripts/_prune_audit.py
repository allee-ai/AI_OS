"""Pre-prune audit — count exactly what each rule would delete, show samples."""
from contextlib import closing
from data.db import get_connection

def main():
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()

        # ── Compound-junk vocab tokens ───────────────────────────────
        # Find vocab table name + structure
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%vocab%' OR name LIKE '%concept%'")
        candidates = [r[0] for r in cur.fetchall()]
        print(f"vocab/concept tables: {candidates}")

        # ── concept_links structure ──────────────────────────────────
        cur.execute("PRAGMA table_info(concept_links)")
        cols = [r[1] for r in cur.fetchall()]
        print(f"\nconcept_links cols: {cols}")
        cur.execute("SELECT * FROM concept_links LIMIT 1")
        print(f"sample row: {dict(cur.fetchone())}")

        # ── Compound-junk concept names ──────────────────────────────
        # Extract unique concept names from concept_links (col_a, col_b)
        # Find which two cols hold the names
        # Likely: concept_a, concept_b OR src, dst
        name_cols = [c for c in cols if any(k in c.lower() for k in ['concept', 'src', 'dst', 'a', 'b', 'from', 'to'])]
        print(f"name candidate cols: {name_cols}")

def show(query, label):
    with closing(get_connection(readonly=True)) as conn:
        n = conn.execute(query).fetchone()[0]
        print(f"  {label}: {n}")

if __name__ == "__main__":
    main()
    print("\n── target tables row counts ──")
    queries = [
        ("SELECT COUNT(*) FROM concept_links", "concept_links total"),
        ("SELECT COUNT(*) FROM concept_links WHERE strength < 0.1", "  strength<0.1"),
        ("SELECT COUNT(*) FROM concept_links WHERE fire_count = 1", "  fire_count=1"),
        ("SELECT COUNT(*) FROM concept_links WHERE strength < 0.1 AND fire_count = 1", "  BOTH (noise floor)"),
        ("SELECT COUNT(*) FROM temp_facts", "temp_facts total"),
        ("SELECT COUNT(*) FROM temp_facts WHERE status='approved'", "  approved"),
        ("SELECT COUNT(*) FROM temp_facts WHERE status='approved' AND length(text)<30", "  approved & short<30"),
        ("SELECT COUNT(*) FROM temp_facts WHERE status='approved' AND hier_key IS NULL", "  approved & no hier_key"),
        ("SELECT COUNT(*) FROM temp_facts WHERE source='thought_loop'", "  source=thought_loop"),
        ("SELECT COUNT(*) FROM temp_facts WHERE confidence_score < 0.7", "  confidence<0.7"),
        ("SELECT COUNT(*) FROM thought_log", "thought_log total"),
        ("SELECT COUNT(*) FROM convo_turns", "convo_turns (PROTECTED)"),
        ("SELECT COUNT(*) FROM convos", "convos (PROTECTED)"),
        ("SELECT COUNT(*) FROM profile_facts", "profile_facts (PROTECTED)"),
    ]
    for q, lbl in queries:
        try:
            show(q, lbl)
        except Exception as e:
            print(f"  {lbl}: ERR {e}")

    # Check for training-related tables
    print("\n── all training/prompt tables ──")
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%train%' OR name LIKE '%prompt%' OR name LIKE '%pair%')")
        for (t,) in cur.fetchall():
            try:
                cur.execute(f'SELECT COUNT(*) FROM "{t}"')
                print(f"  {t}: {cur.fetchone()[0]}")
            except Exception:
                pass
