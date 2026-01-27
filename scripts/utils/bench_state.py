#!/usr/bin/env python3
"""Benchmark state building latency."""
import time
from agent.subconscious.orchestrator import get_subconscious, build_state

sub = get_subconscious()
query = 'who are you and what do you remember about our conversations'

# Warm up
_ = sub.score(query)

# Benchmark score()
times = []
for _ in range(5):
    start = time.perf_counter()
    scores = sub.score(query)
    times.append(time.perf_counter() - start)
print(f'score():       {sum(times)/len(times)*1000:.1f}ms avg')

# Benchmark build_state()
times = []
for _ in range(5):
    start = time.perf_counter()
    state = sub.build_state(scores, query)
    times.append(time.perf_counter() - start)
print(f'build_state(): {sum(times)/len(times)*1000:.1f}ms avg')

# Full pipeline
times = []
for _ in range(5):
    start = time.perf_counter()
    state = build_state(query)
    times.append(time.perf_counter() - start)
print(f'full pipeline: {sum(times)/len(times)*1000:.1f}ms avg')
print(f'State size: {len(state)} chars')
