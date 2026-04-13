#!/usr/bin/env python3
"""Check gold examples count."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
