"""Smoke test: FTS recall, sequence mining, STATE fingerprint."""
from agent.threads.log import recall as r
from agent.subconscious import sequences as seq, coma

print("--- FTS index sync ---")
n = r.ensure_fts_index()
print(f"added={n}")
print(f"stats={r.recall_stats()}")

print("\n--- recall: 'predictions' ---")
hits = r.recall("predictions", k=5)
for h in hits:
    print(f"  [{h['score']:.3f}] #{h['id']} ({h['event_type']}, {h['age_h']}h ago) {h['data'][:80]}")

print("\n--- recall: 'goal' ---")
for h in r.recall("goal", k=5):
    print(f"  [{h['score']:.3f}] #{h['id']} ({h['event_type']}) {h['data'][:80]}")

print("\n--- sequence mining ---")
res = seq.mine_sequences()
print(f"events={res['n_events']}")
for b in res["bigrams"][:5]:
    print(f"  bigram: {b['pattern']} ({b['count']})")
for t in res["trigrams"][:3]:
    print(f"  trigram: {t['pattern']} ({t['count']})")

print("\n--- state fingerprint ---")
print("fp1:", coma.state_fingerprint()[:16])
print("fp2:", coma.state_fingerprint()[:16])  # same expected

print("\n--- coma.run_once full pass ---")
s = coma.run_once()
import json
print(json.dumps({k: v for k, v in s.items() if k != "tally"}, indent=2, default=str))

print("\nOK")
