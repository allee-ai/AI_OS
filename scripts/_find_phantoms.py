"""Identify phantom concepts: high-degree in graph but absent from real text.

Real text = convo_turns user_message OR assistant_message OR temp_facts.text
       OR profile_facts.l1_value/l2_value/l3_value.

Outputs the phantom list to data/phantom_concepts.json so the prune rule
can reference it deterministically.
"""
import json
import sys
import time
from contextlib import closing
from pathlib import Path

sys.path.insert(0, ".")
from data.db import get_connection


DEGREE_THRESHOLD = 100   # everything above this is suspicious
MIN_REAL_OCCURRENCES = 1  # appearing once in real data is enough to keep


def main():
    out_path = Path("data/phantom_concepts.json")
    started = time.time()

    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()

        cur.execute("""
            WITH degrees AS (
              SELECT concept_a c FROM concept_links
              UNION ALL
              SELECT concept_b c FROM concept_links
            )
            SELECT c, COUNT(*) deg FROM degrees GROUP BY c
            HAVING deg >= ?
            ORDER BY deg DESC
        """, (DEGREE_THRESHOLD,))
        candidates = cur.fetchall()
        print(f"checking {len(candidates)} concepts with degree >= {DEGREE_THRESHOLD}...")

        phantoms = []
        kept = []
        for i, (concept, deg) in enumerate(candidates):
            if i % 100 == 0 and i:
                print(f"  ...{i}/{len(candidates)}")
            patt = f"%{concept}%"
            cur.execute(
                "SELECT (SELECT COUNT(*) FROM convo_turns WHERE user_message LIKE ? OR assistant_message LIKE ?) "
                "+ (SELECT COUNT(*) FROM temp_facts WHERE text LIKE ?) "
                "+ (SELECT COUNT(*) FROM profile_facts WHERE l1_value LIKE ? OR l2_value LIKE ? OR l3_value LIKE ?)",
                (patt, patt, patt, patt, patt, patt),
            )
            n_real = cur.fetchone()[0]
            if n_real < MIN_REAL_OCCURRENCES:
                phantoms.append({"concept": concept, "degree": deg, "real_occurrences": n_real})
            else:
                kept.append({"concept": concept, "degree": deg, "real_occurrences": n_real})

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "threshold_degree": DEGREE_THRESHOLD,
        "min_real_occurrences": MIN_REAL_OCCURRENCES,
        "phantoms": phantoms,
        "kept": kept,
    }, indent=2))

    elapsed = time.time() - started
    print()
    print(f"done in {elapsed:.1f}s  →  {out_path}")
    print(f"  phantoms (degree >= {DEGREE_THRESHOLD}, real_occ < {MIN_REAL_OCCURRENCES}): {len(phantoms)}")
    print(f"  kept (real signal):                                                       {len(kept)}")
    print()
    print("── 25 worst phantoms (highest degree, zero real occurrences) ──")
    for p in phantoms[:25]:
        print(f"  deg={p['degree']:>5}  occ={p['real_occurrences']}  {p['concept']}")
    print()
    print("── 25 highest-degree REAL concepts (kept) ──")
    for k in kept[:25]:
        print(f"  deg={k['degree']:>5}  occ={k['real_occurrences']}  {k['concept']}")


if __name__ == "__main__":
    main()
