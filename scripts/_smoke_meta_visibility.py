"""Smoke: meta-thought visibility + shift emit."""
import json
from agent.subconscious import meditation
from agent.subconscious.orchestrator import get_subconscious

# Force shift detection (lower threshold, ignore rate-limit)
print("=== detect_session_shift (forced) ===")
mt_id = meditation.detect_session_shift(min_facts=1)
print(f"emitted: {mt_id}")

# Reset rate limit so the tick attempts emission too
from contextlib import closing
from data.db import get_connection
with closing(get_connection()) as conn:
    conn.execute("UPDATE meditation_meta SET v='0' WHERE k='last_shift_emit_at'")
    conn.execute("UPDATE meditation_meta SET v='1970-01-01 00:00:00' WHERE k='last_shift_fact_ts'")
    conn.commit()

print("\n=== meditation tick (with shift emit) ===")
s = meditation.tick()
print(f"tick: elapsed={s['elapsed_ms']}ms  readiness={s.get('readiness')}  shift_id={s.get('shift_meta_id')}")

print("\n=== HOT block now (should include meta-thoughts) ===")
sub = get_subconscious()
state = sub.get_state(query="what have you noticed recently")
in_hot = False
shown = 0
for ln in state.split("\n")[:80]:
    if "== HOT" in ln:
        in_hot = True
    if in_hot:
        print(ln)
        shown += 1
        if "recent meta-thoughts" in ln.lower() or shown > 50:
            # keep going a bit past the heading
            if shown > 60:
                break

print("\nOK")
