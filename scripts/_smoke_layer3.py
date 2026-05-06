"""Smoke: slots + contradictions + sequence-driven predictions + coma."""
import json
from agent.subconscious import slots, seq_predictions, coma
from agent.threads.philosophy import contradictions

print("=== slots ===")
n = slots.refresh_slots()
print(f"refreshed: {n}")
print(f"stats: {slots.slot_stats()}")
silent = slots.threads_silent_for(hours=72)
for s in silent[:5]:
    print(f"  silent: {s['thread']} (last={s['last_ts']}, n={s['total_events']})")

print("\n=== philosophy.contradictions ===")
beliefs = contradictions.top_beliefs(min_weight=0.6, limit=5)
print(f"top beliefs: {len(beliefs)}")
for b in beliefs[:3]:
    print(f"  {b['profile_id']}.{b['key']} = {(b['value'] or '')[:50]} (w={b['weight']})")
contras = contradictions.find_contradictions(min_weight=0.4)
print(f"contradictions: {len(contras)}")
for c in contras[:5]:
    va = (c['value_a'] or '')[:35]
    vb = (c['value_b'] or '')[:35]
    print(f"  {c['key']}: {c['profile_a']}={va!r} vs {c['profile_b']}={vb!r} (tension={c['tension']})")
emitted = contradictions.emit_contradiction_meta_thoughts(limit=3)
print(f"emitted meta-thoughts: {emitted}")
print(f"summary: {contradictions.contradictions_summary()}")

print("\n=== seq_predictions ===")
added = seq_predictions.mine_and_register()
print(f"newly registered: {added}")
print(f"all registered seq predictions: {seq_predictions.registered_seq_predictions()}")

print("\n=== predictions.check_all (with new seq predictions) ===")
from agent.subconscious import predictions
violations = predictions.check_all(emit_events=False)
print(f"violations: {len(violations)}")
for v in violations[:5]:
    print(f"  [{v.severity}] {v.prediction}: {v.detail[:100]}")

print("\n=== coma.run_once full pass ===")
s = coma.run_once()
keep = {k: v for k, v in s.items() if k != "tally"}
print(json.dumps(keep, indent=2, default=str))

print("\nOK")
