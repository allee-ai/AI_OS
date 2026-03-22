#!/usr/bin/env python3
"""Analyze the training data distribution."""
import json

cats = {}
avg_lens = {}

for line in open('finetune/aios_combined.jsonl'):
    d = json.loads(line)
    msgs = d['messages']
    sys_msg = msgs[0]['content'] if msgs[0]['role'] == 'system' else ''
    user_msg = msgs[1]['content'] if len(msgs) > 1 else ''
    asst_msg = msgs[-1]['content'] if msgs[-1]['role'] == 'assistant' else ''

    if 'STATE' in sys_msg and 'Association' in sys_msg:
        cat = 'association_recall'
    elif 'STATE' in sys_msg and 'self.' in sys_msg:
        cat = 'state_with_self_dot'
    elif 'STATE' in sys_msg:
        cat = 'state_other'
    elif any(k in user_msg.lower() for k in ['identity', 'who are you', 'your name', 'what are you']):
        cat = 'identity'
    elif any(k in user_msg.lower() for k in ['tool', 'function', 'command']):
        cat = 'tool_use'
    elif any(k in sys_msg.lower() for k in ['philosophy', 'reflex']):
        cat = 'philosophy'
    else:
        cat = 'other'

    cats.setdefault(cat, []).append(1)
    avg_lens.setdefault(cat, []).append(len(asst_msg))

print("=== Training Data Distribution ===\n")
for k, v in sorted(cats.items(), key=lambda x: -len(x[1])):
    avg = sum(avg_lens[k]) / len(avg_lens[k])
    print(f"  {k:30s} {len(v):5d} examples  (avg response: {avg:.0f} chars)")
print(f"\n  {'TOTAL':30s} {sum(len(v) for v in cats.values()):5d}")

# Show some examples of state_with_self_dot
print("\n=== Sample state_with_self_dot examples ===\n")
count = 0
for line in open('finetune/aios_combined.jsonl'):
    d = json.loads(line)
    msgs = d['messages']
    sys_msg = msgs[0]['content'] if msgs[0]['role'] == 'system' else ''
    if 'STATE' in sys_msg and 'self.' in sys_msg:
        count += 1
        if count <= 3:
            print(f"--- Example {count} ---")
            print(f"SYSTEM: {sys_msg[:300]}")
            print(f"USER: {msgs[1]['content'][:200]}")
            print(f"ASSISTANT: {msgs[-1]['content'][:300]}")
            print()
