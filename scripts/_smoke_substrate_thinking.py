"""Smoke all four meditation extensions together."""
import json, time
from agent.subconscious import meditation, salience_overlay
from agent.subconscious.orchestrator import get_subconscious

# Warm meditation a bit
print("=== warming meditation (8 ticks) ===")
elapsed = []
ready_track = []
for i in range(8):
    s = meditation.tick()
    elapsed.append(s["elapsed_ms"])
    ready_track.append(s.get("readiness", 0))
print(f"avg tick: {sum(elapsed)/len(elapsed):.1f}ms  readiness traj: {[round(r,2) for r in ready_track]}")

print("\n=== goal_salience (top 5) ===")
gs = salience_overlay.goal_salience(limit=5)
for g in gs:
    print(f"  #{g['id']}  sal={g['salience']:.3f}  lift={g['lift']:.3f}  "
          f"({g['priority']}/{g['urgency'] or 0}, {g['status']})  {g['goal'][:80]}")
if not gs:
    print("  (no open goals)")

print("\n=== readiness ===")
r = salience_overlay.readiness()
print(json.dumps(r, indent=2))

print("\n=== self_trigger dry-run ===")
tid = salience_overlay.maybe_self_trigger(threshold=0.0, dry_run=True)
print(f"would queue task: {tid}")

print("\n=== STATE w/ HOT block (preview) ===")
sub = get_subconscious()
state = sub.get_state(query="what's on your mind right now")
# Print just the HOT block + first thread block to keep output bounded
lines = state.split("\n")
in_hot = False
shown = 0
for ln in lines[:80]:
    if "== HOT" in ln:
        in_hot = True
    if in_hot:
        print(ln)
        shown += 1
        if shown > 30:
            break

print("\nOK")
