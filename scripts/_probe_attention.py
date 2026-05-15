"""Probe: does the attention matrix actually update in real time, and does it discriminate by query?

Tests:
  1. Score discrimination: do different queries score threads differently?
  2. Real-time write: does building STATE actually increment key_cooccurrence?
  3. Concept extraction: do query tokens map to existing entity-keys?
  4. Cross-thread retrieval: when query=dad, do facts from identity AND log AND chat surface?
  5. Hebbian asymptote: does link_concepts() actually move strength?
"""
from contextlib import closing
import time
from data.db import get_connection
from agent.subconscious import get_subconscious

sub = get_subconscious()

print("=" * 70)
print("TEST 1: Score discrimination across queries")
print("=" * 70)
queries = [
    "what do you know about dad",
    "tell me about leads and sales calls",
    "what tools can you use",
    "summarize philosophy and values",
    "show me workspace files",
]
score_matrix = {}
for q in queries:
    s = sub.score(q)
    score_matrix[q] = s

# Print as matrix
all_sources = sorted({k for s in score_matrix.values() for k in s})
print(f"\n{'source':<18}", end="")
for q in queries:
    print(f"{q[:14]:<16}", end="")
print()
print("-" * (18 + 16 * len(queries)))
for src in all_sources:
    print(f"{src:<18}", end="")
    for q in queries:
        v = score_matrix[q].get(src, 0)
        print(f"{v:<16.2f}", end="")
    print()

# Variance check
print("\nDiscrimination test (per-source variance across queries):")
for src in all_sources:
    vals = [score_matrix[q].get(src, 0) for q in queries]
    lo, hi = min(vals), max(vals)
    spread = hi - lo
    flag = "MOVES" if spread > 0.5 else "FLAT"
    print(f"  {src:<18} lo={lo:.2f} hi={hi:.2f} spread={spread:.2f}  {flag}")


print("\n" + "=" * 70)
print("TEST 2: Real-time cooccurrence writes")
print("=" * 70)
with closing(get_connection(readonly=True)) as conn:
    before = conn.execute("SELECT COUNT(*), SUM(count) FROM key_cooccurrence").fetchone()
print(f"Before build_state: rows={before[0]}, total_count={before[1]}")

t0 = time.perf_counter()
_ = sub.get_state("what do you know about dad")
t_ms = int((time.perf_counter() - t0) * 1000)

with closing(get_connection(readonly=True)) as conn:
    after = conn.execute("SELECT COUNT(*), SUM(count) FROM key_cooccurrence").fetchone()
print(f"After  build_state: rows={after[0]}, total_count={after[1]}  ({t_ms}ms)")
print(f"Delta rows: +{after[0] - before[0]}   Delta count: +{(after[1] or 0) - (before[1] or 0)}")


print("\n" + "=" * 70)
print("TEST 3: Concept extraction from query → entity-registry hits")
print("=" * 70)
from agent.threads.linking_core.schema import extract_concepts_from_text
for q in queries:
    c = extract_concepts_from_text(q)
    print(f"  '{q}'")
    print(f"     -> {len(c)} concepts: {c[:8]}")


print("\n" + "=" * 70)
print("TEST 4: Cross-thread retrieval for 'dad'")
print("=" * 70)
from agent.threads.linking_core.schema import spread_activate
concepts = extract_concepts_from_text("what do you know about dad")
print(f"Seed concepts: {concepts}")
if concepts:
    act = spread_activate(concepts, activation_threshold=0.05, max_hops=2, limit=20)
    print(f"Spread activation found {len(act)} concepts:")
    for a in act[:15]:
        c = a.get("concept", "")
        s = a.get("strength", a.get("activation", 0))
        print(f"   {c:<50} strength={s:.3f}")


print("\n" + "=" * 70)
print("TEST 5: Hebbian update — does strength actually move?")
print("=" * 70)
from agent.threads.linking_core.schema import link_concepts
test_a, test_b = "__probe_test_a__", "__probe_test_b__"
# Clean
with closing(get_connection()) as conn:
    conn.execute("DELETE FROM concept_links WHERE concept_a IN (?,?) OR concept_b IN (?,?)",
                 (test_a, test_b, test_a, test_b))
    conn.commit()
print(f"Initial: no link")
for i in range(8):
    s = link_concepts(test_a, test_b, learning_rate=0.2)
    print(f"  fire {i+1}: strength = {s:.4f}")
# cleanup
with closing(get_connection()) as conn:
    conn.execute("DELETE FROM concept_links WHERE concept_a IN (?,?) OR concept_b IN (?,?)",
                 (test_a, test_b, test_a, test_b))
    conn.commit()
