#!/usr/bin/env python3
"""Deep analysis of training data composition."""
import json

cats = {}

for line in open('finetune/aios_combined.jsonl'):
    d = json.loads(line)
    sys_msg = d['messages'][0]['content'] if d['messages'][0]['role'] == 'system' else ''
    user_msg = d['messages'][1]['content'] if len(d['messages']) > 1 else ''
    asst_msg = d['messages'][-1]['content'] if d['messages'][-1]['role'] == 'assistant' else ''

    if 'Spread activation' in sys_msg or 'Association' in sys_msg:
        continue

    has_state = '== STATE ==' in sys_msg
    has_self_dot = 'self.' in sys_msg

    u = user_msg.lower()
    if 'what comes to mind' in u or 'think about' in u or 'relate to' in u:
        cat = 'spread_activation_style'
    elif 'who are you' in u or 'your name' in u or 'what are you' in u or 'identity' in u:
        cat = 'identity'
    elif 'self.' in asst_msg:
        cat = 'uses_self_dot_in_response'
    elif has_self_dot:
        cat = 'has_self_dot_in_context'
    elif has_state:
        cat = 'has_state_no_self_dot'
    else:
        cat = 'no_state_context'

    cats.setdefault(cat, []).append(len(asst_msg))

print('=== Behavioral examples breakdown ===')
for k, v in sorted(cats.items(), key=lambda x: -len(x[1])):
    avg = sum(v) // len(v)
    print(f'  {k:35s} {len(v):5d}  (avg response: {avg} chars)')
total = sum(len(v) for v in cats.values())
print(f'  {"TOTAL":35s} {total:5d}')

# Now check: how many examples teach the model to USE state in its answer?
print('\n=== Does the assistant reference STATE in its response? ===')
refs_state = 0
refs_self = 0
refs_thread = 0
total_b = 0
for line in open('finetune/aios_combined.jsonl'):
    d = json.loads(line)
    asst = d['messages'][-1]['content'] if d['messages'][-1]['role'] == 'assistant' else ''
    total_b += 1
    if 'self.' in asst:
        refs_self += 1
    if 'thread' in asst.lower():
        refs_thread += 1
    if 'STATE' in asst or 'state' in asst:
        refs_state += 1

print(f'  References self.* in response:  {refs_self}/{total_b}')
print(f'  References thread in response:  {refs_thread}/{total_b}')
print(f'  References STATE in response:   {refs_state}/{total_b}')

# Check the source files
print('\n=== Source file breakdown ===')
for fname in ['identity_train.jsonl', 'chat_train.jsonl', 'docs_train.jsonl',
              'form_train.jsonl', 'log_train.jsonl', 'reasoning_train.jsonl',
              'reflex_train.jsonl', 'philosophy_train.jsonl', 'linking_core_train.jsonl']:
    try:
        lines = open(f'finetune/{fname}').readlines()
        has_state_ctx = 0
        has_self_dot_ctx = 0
        refs_self_resp = 0
        for l in lines:
            d = json.loads(l)
            sys_msg = d['messages'][0]['content'] if d['messages'][0]['role'] == 'system' else ''
            asst = d['messages'][-1]['content'] if d['messages'][-1]['role'] == 'assistant' else ''
            if '== STATE ==' in sys_msg:
                has_state_ctx += 1
            if 'self.' in sys_msg:
                has_self_dot_ctx += 1
            if 'self.' in asst:
                refs_self_resp += 1
        print(f'  {fname:30s} {len(lines):4d} lines | state_ctx: {has_state_ctx} | self_dot_ctx: {has_self_dot_ctx} | self_dot_resp: {refs_self_resp}')
    except FileNotFoundError:
        pass
