"""
Smoke test: does graph_attention produce different head priorities for
different queries? If yes, elasticity has signal. If no, the heads are
not semantically distinct enough or the encoder isn't seeding well.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from agent.threads.linking_core.attention import get_graph_attention


PROBES = [
    {"id": "factual_recall", "query": "what's my name and python version?",
     "concepts": ["name", "python", "version", "user"]},
    {"id": "judgement",      "query": "should i go to bed?",
     "concepts": ["sleep", "bed", "schedule"]},
    {"id": "self_reference", "query": "explain linking_core",
     "concepts": ["linking_core", "concept", "graph", "spread"]},
    {"id": "tool_use",       "query": "search the web for ai_os papers",
     "concepts": ["search", "web", "tool", "form"]},
    {"id": "value",          "query": "what do you believe in?",
     "concepts": ["philosophy", "belief", "value"]},
]


def main() -> int:
    ga = get_graph_attention()
    if not ga.available:
        print("graph_attention not available — assets missing")
        return 1

    print(f"loaded: {ga.num_heads} heads, vocab={ga.vocab_size}")
    print()
    print(f"{'probe':<18} | {'identity':>9} {'log':>9} {'form':>9} {'philo':>9} {'reflex':>9} {'assoc':>9} | seeds | ms")
    print("-" * 110)

    for p in PROBES:
        r = ga.shape_state(query=p["query"], extracted_concepts=p["concepts"])
        h = r.head_priorities
        print(
            f"{p['id']:<18} |"
            f" {h.get('identity', 0):>9.3f}"
            f" {h.get('log', 0):>9.3f}"
            f" {h.get('form', 0):>9.3f}"
            f" {h.get('philosophy', 0):>9.3f}"
            f" {h.get('reflex', 0):>9.3f}"
            f" {h.get('association', 0):>9.3f}"
            f" | {r.query_concept_count:>5}"
            f" | {r.elapsed_ms:>5.1f}"
        )

    print()
    print("== top concepts per head, last probe ==")
    last = ga.shape_state(query=PROBES[-1]["query"], extracted_concepts=PROBES[-1]["concepts"])
    for head, top in last.top_concepts_per_head.items():
        if not top:
            continue
        sample = ", ".join(f"{c}({a:.2f})" for c, a in top[:5])
        print(f"  {head:<14} → {sample}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
