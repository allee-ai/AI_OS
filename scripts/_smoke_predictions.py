"""Smoke test predictive reflex: import, tick once, print results, then read STATE."""
from agent.subconscious import predictions as p

print(f"registered predictions: {len(p.list_predictions())}")
for pr in p.list_predictions():
    print(f"  - {pr.name} [{pr.severity}] owner={pr.owner_thread}")

print("\n--- check_all (emit=False, dry) ---")
viols = p.check_all(emit_events=False)
if not viols:
    print("no violations (all expectations hold)")
for v in viols:
    print(f"  [{v.severity}] {v.prediction}: {v.detail}")

print("\n--- check_all (emit=True, real) ---")
viols2 = p.check_all(emit_events=True)
print(f"emitted {len(viols2)} violation(s) to log + meta_thoughts")

print("\n--- last_violations cache ---")
for v in p.last_violations():
    print(f"  cached: [{v.severity}] {v.prediction}")
