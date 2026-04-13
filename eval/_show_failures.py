#!/usr/bin/env python3
"""Show all failure details from baseline comparison results."""
import json

data = json.load(open("eval/baseline_comparison_results.json"))

print("=" * 70)
print("STATE IDENTITY FAILURES")
print("=" * 70)
for t in data["identity"]["state"]["turns"]:
    if not t["passed"]:
        print(f'\n--- [{t["turn"]}] {t["category"]} ---')
        print(f'Prompt: {t["prompt"]}')
        print(f'Flags: has_identity={t["has_identity"]}  adopted_foreign={t["adopted_foreign"]}  actively_resists={t["actively_resists"]}')
        print(f'Response:\n{t["response"][:500]}')

print("\n" + "=" * 70)
print("STATE MEMORY FAILURES")
print("=" * 70)
for t in data["memory"]["state"]["turns"]:
    if not t["passed"]:
        print(f'\n--- [{t["turn"]}] {t["category"]} ---')
        print(f'Prompt: {t["prompt"]}')
        print(f'Flags: hits={t["required_hits"]}  required_total={t["required_total"]}')
        print(f'Response:\n{t["response"][:500]}')

print("\n" + "=" * 70)
print("STATIC IDENTITY FAILURES")
print("=" * 70)
for t in data["identity"]["static"]["turns"]:
    if not t["passed"]:
        print(f'\n--- [{t["turn"]}] {t["category"]} ---')
        print(f'Prompt: {t["prompt"]}')
        print(f'Flags: has_identity={t["has_identity"]}  adopted_foreign={t["adopted_foreign"]}  actively_resists={t["actively_resists"]}')
        print(f'Response:\n{t["response"][:500]}')

print("\n" + "=" * 70)
print("STATIC MEMORY FAILURES")
print("=" * 70)
for t in data["memory"]["static_with_facts"]["turns"]:
    if not t["passed"]:
        print(f'\n--- [{t["turn"]}] {t["category"]} ---')
        print(f'Prompt: {t["prompt"]}')
        print(f'Flags: hits={t["required_hits"]}  required_total={t["required_total"]}')
        print(f'Response:\n{t["response"][:500]}')
