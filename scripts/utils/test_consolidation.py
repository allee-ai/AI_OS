#!/usr/bin/env python3
"""Test thread summary generation and embedding-based scoring."""
import time

# Test summary generation
print("=== Testing Thread Summary Generation ===\n")

from agent.subconscious.loops import ConsolidationLoop

loop = ConsolidationLoop(interval=300)
print("Running _update_thread_summaries()...")
start = time.perf_counter()
loop._update_thread_summaries()
elapsed = (time.perf_counter() - start) * 1000
print(f"Done in {elapsed:.0f}ms\n")

# Check what summaries were generated
from agent.threads.linking_core.scoring import get_thread_summary_stats, get_thread_summary

stats = get_thread_summary_stats()
print(f"Threads with summaries: {stats['summary_count']}")
print(f"  {stats['threads_with_summaries']}")
print(f"Threads with embeddings: {len(stats['threads_with_embeddings'])}")
print(f"  {stats['threads_with_embeddings']}\n")

# Show a summary
if stats['threads_with_summaries']:
    thread = stats['threads_with_summaries'][0]
    summary = get_thread_summary(thread)
    print(f"Sample summary ({thread}):")
    print(f"  {summary[:200]}..." if len(summary) > 200 else f"  {summary}")
    print()

# Test embedding-based scoring
print("=== Testing Embedding-Based Thread Scoring ===\n")

from agent.threads.linking_core.scoring import score_threads_by_embedding

queries = [
    "who are you and what's your name?",
    "what did we talk about recently?",
    "what do you believe in?",
    "can you help me build something?",
]

for query in queries:
    start = time.perf_counter()
    scores = score_threads_by_embedding(query)
    elapsed = (time.perf_counter() - start) * 1000
    
    if scores:
        # Sort by score
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top3 = sorted_scores[:3]
        print(f"Query: '{query[:40]}...'")
        print(f"  Top threads: {', '.join(f'{t}={s:.1f}' for t,s in top3)} ({elapsed:.0f}ms)")
    else:
        print(f"Query: '{query[:40]}...'")
        print(f"  No embedding scores available (Ollama not running?)")
    print()
