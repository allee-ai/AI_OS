"""Smoke: run meditation ticks and inspect the substrate."""
import json, time
from agent.subconscious import meditation as m

print("=== initial stats ===")
print(json.dumps(m.meditation_stats(), indent=2))

elapsed = []
for i in range(8):
    s = m.tick()
    elapsed.append(s["elapsed_ms"])
    print(f"\ntick {i+1}: elapsed={s['elapsed_ms']}ms  events={s['events_seen']}  "
          f"kicked={s['concepts_kicked']}  spread={s['spread_edges']}  "
          f"decayed={s['decayed_rows']}  cache={s['salience_rows']}")
    if s.get("error"):
        print(f"  ERROR: {s['error']}")

print(f"\n=== timing: avg={sum(elapsed)/len(elapsed):.1f}ms  max={max(elapsed):.1f}ms ===")

print("\n=== hot_concepts (top 10) ===")
for h in m.hot_concepts(limit=10):
    print(f"  {h['activation']:.3f}  {h['concept']}")

print("\n=== top_salient (top 10) ===")
for s in m.top_salient(limit=10):
    val = (s.get('value') or '')[:60]
    print(f"  sal={s['salience']:.3f} w={s['weight']}  {s['profile_id']}.{s['key']}  →  {val}")

print("\n=== final stats ===")
print(json.dumps(m.meditation_stats(), indent=2))

print("\n=== sustained 20 ticks @ 0.25s ===")
t0 = time.time()
for i in range(20):
    m.tick()
    time.sleep(0.25)
total = time.time() - t0
print(f"20 ticks in {total:.2f}s  (target 5.0s)")
print(json.dumps(m.meditation_stats(), indent=2))

print("\nOK")
