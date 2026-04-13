#!/usr/bin/env python3
"""Analyze baseline comparison failures."""
import json

with open("eval/baseline_comparison_results.json") as f:
    data = json.load(f)

print("=" * 70)
print("STATE IDENTITY FAILURES (why STATE lost to STATIC)")
print("=" * 70)
for t in data["identity"]["state"]["turns"]:
    if not t["passed"]:
        print(f"\n[{t['turn']}] [{t['category']}] {t['prompt']}")
        print(f"  has_identity={t['has_identity']}  adopted_foreign={t['adopted_foreign']}  resists={t['actively_resists']}")
        print(f"  RESPONSE: {t['response'][:500]}")

print("\n\n" + "=" * 70)
print("STATIC IDENTITY FAILURES (for comparison)")
print("=" * 70)
for t in data["identity"]["static"]["turns"]:
    if not t["passed"]:
        print(f"\n[{t['turn']}] [{t['category']}] {t['prompt']}")
        print(f"  has_identity={t['has_identity']}  adopted_foreign={t['adopted_foreign']}  resists={t['actively_resists']}")
        print(f"  RESPONSE: {t['response'][:500]}")

print("\n\n" + "=" * 70)
print("STATE MEMORY FAILURES")
print("=" * 70)
for t in data["memory"]["state"]["turns"]:
    if not t["passed"]:
        print(f"\n[{t['turn']}] [{t['category']}] {t['prompt']}")
        print(f"  required_hits={t['required_hits']} (of {t['required_total']} required keywords)")
        print(f"  RESPONSE: {t['response'][:500]}")

print("\n\n" + "=" * 70)
print("STATIC+FACTS MEMORY FAILURES (for comparison)")
print("=" * 70)
for t in data["memory"]["static_with_facts"]["turns"]:
    if not t["passed"]:
        print(f"\n[{t['turn']}] [{t['category']}] {t['prompt']}")
        print(f"  required_hits={t['required_hits']} (of {t['required_total']} required keywords)")
        print(f"  RESPONSE: {t['response'][:500]}")

print("\n\n" + "=" * 70)
print("MEMORY SIDE-BY-SIDE (STATE vs STATIC+FACTS)")
print("=" * 70)
for i in range(len(data["memory"]["state"]["turns"])):
    st = data["memory"]["state"]["turns"][i]
    sf = data["memory"]["static_with_facts"]["turns"][i]
    s_st = "PASS" if st["passed"] else "FAIL"
    s_sf = "PASS" if sf["passed"] else "FAIL"
    print(f"\n[{i+1}] [{st['category']}] {st['prompt']}")
    print(f"  STATE:        {s_st}  hits={st['required_hits']}  detail={st.get('detail_score',0):.2f}")
    print(f"  STATIC+FACTS: {s_sf}  hits={sf['required_hits']}  detail={sf.get('detail_score',0):.2f}")
