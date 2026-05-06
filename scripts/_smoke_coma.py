"""Smoke test coma-mode: one tick, then state."""
from agent.subconscious import coma

print("--- coma.run_once() #1 ---")
s1 = coma.run_once()
import json
print(json.dumps({k: v for k, v in s1.items() if k != "tally"}, indent=2, default=str))
if s1.get("tally"):
    print("tally keys:", list(s1["tally"].keys()))
    for tk, tv in s1["tally"].items():
        print(f"  {tk}: {tv}")

print("\n--- run #2 (should touch fewer events; counters bumped) ---")
s2 = coma.run_once()
print(f"events_touched={s2['events_touched']}, edges_touched={s2['edges_touched']}, hb={s2['self']['heartbeats']}, uptime_h={s2['self']['uptime_h']}")

print("\n--- last_summary readback ---")
ls = coma.last_summary()
print(f"hb={ls['self']['heartbeats']} events_24h={ls['self']['events_24h']} last_llm_age_h={ls['self'].get('last_llm_age_h')}")

print("\n--- check identity facts written ---")
from agent.threads.identity.schema import pull_profile_facts
facts = pull_profile_facts(profile_id="machine", limit=20)
for f in facts:
    if f["key"] in ("uptime_h", "heartbeats_session", "events_24h", "last_llm_age_h"):
        print(f"  machine.{f['key']} = {f.get('l1_value')!r} (weight={f.get('weight')})")

print("\nOK")
