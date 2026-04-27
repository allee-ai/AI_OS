"""
Prune noise from state.db.

Rules (all read-only by default; pass --apply to actually delete):

1. concept_links: length(concept_a) > 40 OR length(concept_b) > 40
   → glued/compound junk concepts ('sync_loop_function_user.general.fact...')

2. concept_links: strength < 0.1 AND fire_count = 1
   → noise floor (singletons that fired once at near-zero strength)

3. temp_facts: COALESCE(confidence_score, 0) = 0 AND hier_key IS NULL
   → zero-confidence orphans ('Ready for promotion', 'Trimmed text', dup 'User likes coffee')

4. temp_facts: source = 'thought_loop'
   → LLM-generated loop suggestions (NOT extracted facts; loop will regenerate)

5. thought_log: ALL ROWS
   → all rows are LLM-generated suggestions, not facts; loop regenerates fresh

6. temp_facts: status = 'rejected'
   → already marked as bad by extractor or human review; keeping them around
     just inflates the temp_facts count and confuses dedup logic

7. temp_facts: hier_key IN ('SOURCE_DATA','Assistant','First message','0')
   → extraction artifacts where the LLM emitted a header/role label as a key
     instead of a real category (no semantic value)

8. temp_facts: text starts with 'User:' or 'Assistant:'
   → extractor misfires that captured an entire conversation block as a fact

9. temp_facts: duplicate excess copies (keep oldest id per unique text)
   → one prompt template appears 485 times, another 151 times, etc.
     run LAST so it dedupes whatever survives rules 6-8

All deletions logged as ONE unified_events row (event_type='prune') so the
timeline records what was cleaned.

Usage:
  python scripts/_prune_noise.py            # dry run (default)
  python scripts/_prune_noise.py --apply    # actually delete + VACUUM
"""
import argparse
import json
import sys
from contextlib import closing
from datetime import datetime, timezone

# Allow `python scripts/_prune_noise.py` from project root
sys.path.insert(0, ".")
from data.db import get_connection
from agent.threads.log.schema import log_event


RULES = [
    {
        "id": "compound_junk_links",
        "table": "concept_links",
        "where": "length(concept_a) > 40 OR length(concept_b) > 40",
        "describe": "concept_links with compound/glued concept names (>40 chars)",
        "sample_query": "SELECT concept_a, concept_b, strength, fire_count FROM concept_links WHERE length(concept_a) > 40 OR length(concept_b) > 40 ORDER BY RANDOM() LIMIT 5",
    },
    {
        "id": "noise_floor_links",
        "table": "concept_links",
        "where": "strength < 0.1 AND fire_count = 1",
        "describe": "concept_links at noise floor (s<0.1 AND fired once)",
        "sample_query": "SELECT concept_a, concept_b, strength, fire_count FROM concept_links WHERE strength < 0.1 AND fire_count = 1 ORDER BY RANDOM() LIMIT 5",
    },
    {
        "id": "zero_confidence_temp_facts",
        "table": "temp_facts",
        "where": "COALESCE(confidence_score, 0) = 0 AND hier_key IS NULL",
        "describe": "temp_facts with zero confidence AND no hier_key (orphan junk)",
        "sample_query": "SELECT id, text, source FROM temp_facts WHERE COALESCE(confidence_score, 0) = 0 AND hier_key IS NULL ORDER BY RANDOM() LIMIT 5",
    },
    {
        "id": "thought_loop_temp_facts",
        "table": "temp_facts",
        "where": "source = 'thought_loop'",
        "describe": "temp_facts from thought_loop (LLM suggestions, not extracted)",
        "sample_query": "SELECT id, text FROM temp_facts WHERE source = 'thought_loop' ORDER BY RANDOM() LIMIT 5",
    },
    {
        "id": "thought_log_all",
        "table": "thought_log",
        "where": "1=1",
        "describe": "thought_log (entire table — all are LLM-generated suggestions)",
        "sample_query": "SELECT id, category, substr(thought, 1, 100) FROM thought_log ORDER BY RANDOM() LIMIT 5",
    },
    {
        "id": "rejected_temp_facts",
        "table": "temp_facts",
        "where": "status = 'rejected'",
        "describe": "temp_facts already marked rejected (extractor or human review said no)",
        "sample_query": "SELECT id, substr(text, 1, 80), source FROM temp_facts WHERE status='rejected' ORDER BY RANDOM() LIMIT 5",
    },
    {
        "id": "extraction_artifact_keys",
        "table": "temp_facts",
        "where": "hier_key IN ('SOURCE_DATA','Assistant','First message','0')",
        "describe": "temp_facts where hier_key is a header/role label, not a category",
        "sample_query": "SELECT id, hier_key, substr(text, 1, 80) FROM temp_facts WHERE hier_key IN ('SOURCE_DATA','Assistant','First message','0') ORDER BY RANDOM() LIMIT 5",
    },
    {
        "id": "conversation_block_extractions",
        "table": "temp_facts",
        "where": "text LIKE 'User:%' OR text LIKE 'Assistant:%'",
        "describe": "temp_facts that are raw conversation blocks (extractor misfires)",
        "sample_query": "SELECT id, substr(text, 1, 100), source FROM temp_facts WHERE text LIKE 'User:%' OR text LIKE 'Assistant:%' ORDER BY RANDOM() LIMIT 5",
    },
    {
        "id": "duplicate_excess_temp_facts",
        "table": "temp_facts",
        "where": "id NOT IN (SELECT MIN(id) FROM temp_facts GROUP BY text)",
        "describe": "duplicate temp_facts (keeps oldest copy of each unique text)",
        "sample_query": "SELECT id, substr(text, 1, 80), source FROM temp_facts WHERE id NOT IN (SELECT MIN(id) FROM temp_facts GROUP BY text) ORDER BY RANDOM() LIMIT 5",
    },
]

PROTECTED = ["convo_turns", "convos", "profile_facts", "training_pairs", "training_templates"]


def count(conn, rule):
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {rule['table']} WHERE {rule['where']}")
    return cur.fetchone()[0]


def total(conn, table):
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0]


def show_samples(conn, rule):
    cur = conn.cursor()
    cur.execute(rule["sample_query"])
    rows = cur.fetchall()
    return rows


def dry_run():
    print("\n" + "=" * 72)
    print("DRY RUN — no changes will be made")
    print("=" * 72)
    summary = {"rules": [], "protected_table_counts": {}}
    with closing(get_connection(readonly=True)) as conn:
        for rule in RULES:
            n_total = total(conn, rule["table"])
            n_kill = count(conn, rule)
            pct = (n_kill / n_total * 100) if n_total else 0
            print(f"\n[{rule['id']}] {rule['describe']}")
            print(f"  table={rule['table']}  total={n_total}  would_delete={n_kill} ({pct:.1f}%)  keeps={n_total - n_kill}")
            print(f"  WHERE {rule['where']}")
            print("  samples (5 random):")
            for s in show_samples(conn, rule):
                vals = " | ".join(str(v)[:60] for v in s)
                print(f"    | {vals}")
            summary["rules"].append({
                "id": rule["id"],
                "table": rule["table"],
                "would_delete": n_kill,
                "total_before": n_total,
            })

        print("\n── PROTECTED tables (untouched) ──")
        for t in PROTECTED:
            try:
                n = total(conn, t)
                summary["protected_table_counts"][t] = n
                print(f"  {t}: {n}")
            except Exception as e:
                print(f"  {t}: ERR {e}")

    print("\n" + "=" * 72)
    print("To apply these deletions: python scripts/_prune_noise.py --apply")
    print("=" * 72)
    return summary


def apply():
    print("\n" + "=" * 72)
    print("APPLYING — deletions are PERMANENT (backup at ~/Desktop/state.db.pre-prune.*)")
    print("=" * 72)

    deleted: dict = {}
    started = datetime.now(timezone.utc).isoformat()

    with closing(get_connection()) as conn:
        cur = conn.cursor()
        # Foreign keys off so deletes don't trip on cascading constraints.
        cur.execute("PRAGMA foreign_keys = OFF")
        for rule in RULES:
            n_before = count(conn, rule)
            print(f"\n[{rule['id']}] deleting {n_before} rows from {rule['table']}...")
            cur.execute(f"DELETE FROM {rule['table']} WHERE {rule['where']}")
            deleted[rule["id"]] = cur.rowcount
            print(f"  deleted: {cur.rowcount}")
        conn.commit()
        cur.execute("PRAGMA foreign_keys = ON")

    print("\nVACUUM (reclaiming space)...")
    with closing(get_connection()) as conn:
        # VACUUM cannot run inside a transaction
        conn.isolation_level = None
        conn.execute("VACUUM")

    finished = datetime.now(timezone.utc).isoformat()

    # Final counts for verification
    with closing(get_connection(readonly=True)) as conn:
        protected_after = {t: total(conn, t) for t in PROTECTED if _table_exists(conn, t)}
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM concept_links")
        cl_after = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM temp_facts")
        tf_after = cur.fetchone()[0]

    summary = {
        "started_at": started,
        "finished_at": finished,
        "deleted": deleted,
        "total_deleted": sum(deleted.values()),
        "after": {
            "concept_links": cl_after,
            "temp_facts": tf_after,
            **{f"protected.{k}": v for k, v in protected_after.items()},
        },
    }

    headline = (
        f"[ok] pruned {summary['total_deleted']} rows: "
        + ", ".join(f"{k}={v}" for k, v in deleted.items())
    )
    log_event(
        event_type="prune",
        data=headline,
        metadata=summary,
        source="scripts._prune_noise",
    )

    print("\n" + "=" * 72)
    print("DONE")
    print(json.dumps(summary, indent=2))
    print("=" * 72)


def _table_exists(conn, name):
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (name,))
    return cur.fetchone() is not None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="actually delete")
    args = parser.parse_args()
    if args.apply:
        apply()
    else:
        dry_run()
