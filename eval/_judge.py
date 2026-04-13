#!/usr/bin/env python3
"""Print contested identity + memory prompts for human judging."""
import json

data = json.load(open("eval/baseline_comparison_results.json"))

# ── IDENTITY: show where conditions disagree ──
print("=" * 70)
print("IDENTITY BATTERY — CONTESTED PROMPTS")
print("(Showing prompts where at least one condition failed)")
print("=" * 70)

bare = data["identity"]["bare"]["turns"]
static = data["identity"]["static"]["turns"]
state = data["identity"]["state"]["turns"]

for i in range(20):
    b, s, st = bare[i], static[i], state[i]
    if b["passed"] and s["passed"] and st["passed"]:
        continue  # all pass, skip
    
    tags = []
    if b["passed"] != s["passed"] or s["passed"] != st["passed"]:
        tags.append("DISAGREE")
    
    print(f"\n{'─'*70}")
    print(f"[{i+1}] {b['category'].upper()}  {' '.join(tags)}")
    print(f"Q: {b['prompt']}")
    
    for label, t in [("BARE", b), ("STATIC", s), ("STATE", st)]:
        mark = "PASS" if t["passed"] else "FAIL"
        resp = t["response"].strip().replace("\n", "\n       ")
        print(f"\n  {label} [{mark}]:")
        print(f"       {resp[:400]}")

# ── MEMORY: show where conditions disagree ──
print(f"\n\n{'=' * 70}")
print("MEMORY BATTERY — CONTESTED PROMPTS")
print("(Showing prompts where at least one condition failed)")
print("=" * 70)

bare_m = data["memory"]["bare"]["turns"]
static_m = data["memory"]["static_with_facts"]["turns"]
state_m = data["memory"]["state"]["turns"]

for i in range(10):
    b, s, st = bare_m[i], static_m[i], state_m[i]
    if b["passed"] and s["passed"] and st["passed"]:
        continue
    
    print(f"\n{'─'*70}")
    print(f"[{i+1}] {b['category'].upper()}")
    print(f"Q: {b['prompt']}")
    
    for label, t in [("BARE", b), ("STATIC+FACTS", s), ("STATE", st)]:
        mark = "PASS" if t["passed"] else "FAIL"
        resp = t["response"].strip().replace("\n", "\n       ")
        hits = t.get("required_hits", [])
        print(f"\n  {label} [{mark}] hits={hits}:")
        print(f"       {resp[:400]}")
