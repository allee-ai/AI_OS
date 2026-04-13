#!/usr/bin/env python3
"""Inspect existing self-knowledge training data."""
import json, os

files = [
    "identity_train", "philosophy_train", "form_train", "log_train",
    "reflex_train", "linking_core_train", "chat_train", "docs_train",
    "reasoning_train",
]

total = 0
for f in files:
    path = f"finetune/{f}.jsonl"
    if not os.path.exists(path):
        print(f"{f}: NOT FOUND")
        continue
    with open(path) as fh:
        lines = [json.loads(l) for l in fh]
    total += len(lines)
    print(f"{f}: {len(lines)} examples, keys={list(lines[0].keys()) if lines else '?'}")
    if lines:
        ex = lines[0]
        if "messages" in ex:
            for m in ex["messages"][:2]:
                print(f"  {m['role']}: {m['content'][:100]}")
        elif "text" in ex:
            print(f"  text: {ex['text'][:120]}")
    print()

print(f"TOTAL self-knowledge examples: {total}")

# Also check gold_examples
print("\n--- gold_examples.py ---")
try:
    from finetune.gold_examples import get_reasoning_examples, get_reasoning_stats
    stats = get_reasoning_stats()
    print(f"Gold example stats: {stats}")
    examples = get_reasoning_examples()
    print(f"Total gold examples: {len(examples)}")
    if examples:
        ex = examples[0]
        print(f"First example keys: {list(ex.keys())}")
        if "messages" in ex:
            for m in ex["messages"][:2]:
                print(f"  {m['role']}: {m['content'][:100]}")
except Exception as e:
    print(f"Error loading gold_examples: {e}")
