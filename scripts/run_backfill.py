#!/usr/bin/env python3
"""
Run the ConvoConceptLoop backfill until all conversations are processed.

This uses the system's own ConvoConceptLoop to process all imported
conversations into the concept graph.

Usage:
    python3 scripts/run_backfill.py [--reset] [--batch-size 20] [--llm]
    
    --llm   Enable LLM fact extraction (calls model per conversation,
            stages new facts in temp_facts, saves training data to
            finetune/auto_generated/concept_extractions.jsonl)
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def run_backfill(reset: bool = False, batch_size: int = 20, use_llm: bool = False):
    from agent.subconscious.loops.convo_concepts import ConvoConceptLoop
    from data.db import get_connection
    from contextlib import closing
    
    loop = ConvoConceptLoop(batch_size=batch_size, use_llm=use_llm)
    
    if use_llm:
        print(f"LLM extraction ENABLED — model: {loop.model}, provider: {loop.provider}")
    
    if reset:
        # Reset progress marker to reprocess everything
        with closing(get_connection()) as conn:
            conn.execute(
                "DELETE FROM memory_loop_state WHERE key = 'convo_concepts_last_id'"
            )
            conn.commit()
        print("Reset backfill progress to 0")
    
    # Get total conversations to process
    with closing(get_connection(readonly=True)) as conn:
        total = conn.execute("SELECT COUNT(*) FROM convos").fetchone()[0]
        last_id = loop._get_progress()
        remaining = conn.execute(
            "SELECT COUNT(*) FROM convos WHERE id > ?", (last_id,)
        ).fetchone()[0]
    
    print(f"Total conversations: {total}")
    print(f"Already processed up to ID: {last_id}")
    print(f"Remaining to process: {remaining}")
    
    if remaining == 0:
        print("Nothing to process!")
        return
    
    start_time = time.time()
    batch_num = 0
    
    while True:
        before_stats = dict(loop.stats)
        
        # Run one batch
        loop._process_batch()
        
        after_stats = loop.stats
        batch_num += 1
        
        new_processed = after_stats["total_processed"] - before_stats.get("total_processed", 0)
        
        elapsed = time.time() - start_time
        print(
            f"  Batch {batch_num}: "
            f"+{new_processed} convos, "
            f"total {after_stats['total_processed']} processed, "
            f"{after_stats['total_concepts']} concepts, "
            f"{after_stats['total_links']} links "
            f"({elapsed:.1f}s)"
        )
        
        if new_processed == 0:
            # All caught up
            break
    
    elapsed = time.time() - start_time
    
    # Final stats from DB
    with closing(get_connection(readonly=True)) as conn:
        cl_count = conn.execute("SELECT COUNT(*) FROM concept_links").fetchone()[0]
        kc_count = conn.execute("SELECT COUNT(*) FROM key_cooccurrence").fetchone()[0]
        avg_str = conn.execute("SELECT AVG(strength) FROM concept_links").fetchone()[0] or 0
        top_concepts = conn.execute(
            "SELECT concept_a, COUNT(*) as cnt FROM concept_links GROUP BY concept_a ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
    
    print(f"\n{'='*60}")
    print(f"BACKFILL COMPLETE")
    print(f"  Mode: {'LLM extraction' if use_llm else 'entity matching'}")
    print(f"  Processed: {after_stats['total_processed']} conversations")
    print(f"  Concepts extracted: {after_stats['total_concepts']}")
    print(f"  Links created: {after_stats['total_links']}")
    if use_llm:
        print(f"  Facts discovered: {after_stats.get('total_facts_extracted', 0)}")
    print(f"  Total links in graph: {cl_count}")
    print(f"  Co-occurrences: {kc_count}")
    print(f"  Avg link strength: {avg_str:.4f}")
    print(f"  Time: {elapsed:.1f}s")
    if use_llm:
        training_file = PROJECT_ROOT / "finetune" / "auto_generated" / "concept_extractions.jsonl"
        if training_file.exists():
            line_count = sum(1 for _ in open(training_file))
            print(f"  Training examples: {line_count} (in {training_file})")
    print(f"\n  Top concepts:")
    for concept, count in top_concepts:
        print(f"    {concept}: {count} links")
    print(f"{'='*60}")


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    use_llm = "--llm" in sys.argv
    batch_size = 20
    for i, arg in enumerate(sys.argv):
        if arg == "--batch-size" and i + 1 < len(sys.argv):
            batch_size = int(sys.argv[i + 1])
    
    run_backfill(reset=reset, batch_size=batch_size, use_llm=use_llm)
