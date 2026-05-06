"""Jarvis-gap inventory. What's running, what's not, what's wired in."""
from contextlib import closing
from data.db import get_connection
import os, subprocess, time

def q(sql, args=()):
    with closing(get_connection(readonly=True)) as conn:
        return conn.execute(sql, args).fetchall()

print("=" * 72)
print("ALIVE = RUNNING")
print("=" * 72)

# Is the meditator daemon actually running?
try:
    out = subprocess.run(["pgrep", "-fa", "run_meditator"], capture_output=True, text=True)
    print(f"\nmeditator daemon: {'RUNNING' if out.stdout.strip() else 'NOT RUNNING'}")
    if out.stdout.strip():
        print(f"  {out.stdout.strip()}")
except Exception as e:
    print(f"meditator: {e}")

# Server?
try:
    out = subprocess.run(["pgrep", "-fa", "scripts/server.py"], capture_output=True, text=True)
    print(f"\nserver:           {'RUNNING' if out.stdout.strip() else 'NOT RUNNING'}")
except Exception:
    pass

# Coma loop?
try:
    out = subprocess.run(["pgrep", "-fa", "coma|heartbeat"], capture_output=True, text=True)
    print(f"\ncoma/heartbeat:   {'RUNNING' if out.stdout.strip() else 'NOT RUNNING'}")
except Exception:
    pass

# When did we last actually tick?
print("\n--- last meditation tick (from meditation_meta) ---")
try:
    rows = q("SELECT k, v FROM meditation_meta")
    for r in rows:
        print(f"  {r['k']:30s} = {r['v']}")
except Exception as e:
    print(f"  err: {e}")

# Was there any unified_event in the last hour?
n_recent = q("SELECT COUNT(*) c FROM unified_events WHERE timestamp >= datetime('now','-1 hour')")[0]['c']
n_today = q("SELECT COUNT(*) c FROM unified_events WHERE timestamp >= datetime('now','-1 day')")[0]['c']
print(f"\nevents last 1h:   {n_recent}")
print(f"events last 24h:  {n_today}")

print("\n" + "=" * 72)
print("THINKING = UPDATING (DB-only cognition)")
print("=" * 72)

# concept_activation pulse?
try:
    r = q("SELECT COUNT(*) c, MAX(activation) mx, AVG(activation) av FROM concept_activation")[0]
    print(f"\nconcept_activation: {r['c']} concepts active, max={r['mx']}, avg={r['av']:.3f if r['av'] else 0}")
except Exception as e:
    print(f"  concept_activation: NOT WIRED -- {e}")

# state_cache fresh?
try:
    r = q("SELECT COUNT(*) c, MAX(updated_at) mx FROM state_cache")[0]
    print(f"state_cache: {r['c']} rows, last update {r['mx']}")
except Exception as e:
    print(f"  state_cache: NOT WIRED -- {e}")

# Predictions firing?
try:
    r = q("SELECT COUNT(*) c FROM unified_events WHERE event_type='prediction_violation' AND timestamp >= datetime('now','-7 days')")[0]
    print(f"prediction_violations 7d: {r['c']}")
except Exception as e:
    print(f"  predictions: {e}")

# Sequences mined?
try:
    r = q("SELECT COUNT(*) c, MAX(updated_at) mx FROM sequences")[0] if q("SELECT name FROM sqlite_master WHERE name='sequences'") else None
    if r:
        print(f"sequences mined: {r['c']}, last {r['mx']}")
except Exception:
    print("  sequences: not present")

# Goals in pipeline?
gs = q("SELECT status, COUNT(*) c FROM proposed_goals GROUP BY status")
print(f"\ngoals by status:")
for r in gs:
    print(f"  {r['status']:15s} {r['c']}")

# task_queue
try:
    r = q("SELECT status, COUNT(*) c FROM task_queue GROUP BY status")
    print(f"\ntask_queue:")
    for x in r:
        print(f"  {x['status']:15s} {x['c']}")
except Exception:
    pass

# Self-triggered tasks?
try:
    r = q("SELECT COUNT(*) c FROM task_queue WHERE requested_by='meditator'")[0]
    print(f"\nself-triggered tasks (kind=self_reflect, requested_by=meditator): {r['c']}")
except Exception:
    pass

# Meta-thoughts pulse
mt = q("SELECT kind, COUNT(*) c FROM reflex_meta_thoughts WHERE created_at >= datetime('now','-1 day') GROUP BY kind")
print(f"\nmeta_thoughts last 24h: {sum(r['c'] for r in mt)} total")
for r in mt:
    print(f"  {r['kind']:20s} {r['c']}")

# Contradictions ever emitted?
try:
    r = q("SELECT COUNT(*) c FROM reflex_meta_thoughts WHERE kind='contradiction'")[0]
    print(f"contradictions emitted (all-time): {r['c']}")
except Exception:
    pass

print("\n" + "=" * 72)
print("PROCESSING = LLM (call frequency, surface coverage)")
print("=" * 72)

# Last LLM call?
try:
    r = q("""SELECT timestamp, event_type, json_extract(data, '$.role') as role
            FROM unified_events
            WHERE event_type LIKE 'llm%' OR event_type='convo' OR event_type='agent_turn'
            ORDER BY id DESC LIMIT 5""")
    print("\nrecent LLM-shaped events:")
    for x in r:
        print(f"  {x['timestamp']}  {x['event_type']:20s}  {x['role']}")
except Exception as e:
    print(f"  err: {e}")

# How many distinct surfaces (sensory feeds)?
try:
    r = q("SELECT type, enabled, COUNT(*) c FROM sensory_feeds GROUP BY type, enabled")
    print("\nsensory feeds:")
    for x in r:
        print(f"  {x['type']:20s} enabled={x['enabled']}  ({x['c']})")
except Exception as e:
    print(f"  sensory_feeds: {e}")

# Email feed actually pulling?
try:
    r = q("""SELECT COUNT(*) c, MAX(timestamp) mx FROM unified_events
             WHERE event_type='sensory' AND json_extract(data, '$.source')='email'
             AND timestamp >= datetime('now','-1 day')""")[0]
    print(f"\nemail events 24h: {r['c']}, last {r['mx']}")
except Exception:
    pass

print("\n" + "=" * 72)
print("MOTOR / OUTPUT (the 'mouth' side of Jarvis)")
print("=" * 72)

# Tools registered (form thread)
try:
    r = q("SELECT COUNT(*) c FROM form_tools WHERE active=1")[0]
    print(f"\nactive tools: {r['c']}")
    rows = q("SELECT name FROM form_tools WHERE active=1 ORDER BY name")
    for x in rows[:30]:
        print(f"  {x['name']}")
    if len(rows) > 30:
        print(f"  ... +{len(rows)-30} more")
except Exception as e:
    print(f"  form_tools: {e}")

# Outbound surfaces (ways the system can speak)
print("\n--- output surfaces (how can the system SAY something?) ---")
try:
    r = q("""SELECT DISTINCT event_type, COUNT(*) c FROM unified_events
             WHERE event_type IN ('email_sent','message_sent','sms_sent','tool_call','agent_turn','self_reflect','convo')
             AND timestamp >= datetime('now','-7 days')
             GROUP BY event_type ORDER BY c DESC""")
    for x in r:
        print(f"  {x['event_type']:25s} {x['c']}/7d")
except Exception:
    pass
