"""Analyze training data content."""
import json, collections, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

data = []
with open('finetune/aios_combined.jsonl') as f:
    for line in f:
        data.append(json.loads(line))

print(f'Total examples: {len(data)}')

has_state = 0
identity_names = collections.Counter()
state_facts = collections.Counter()
for ex in data:
    msgs = ex.get('messages', [])
    sys_msg = next((m['content'] for m in msgs if m['role'] == 'system'), '')
    if 'STATE' in sys_msg or 'identity' in sys_msg.lower():
        has_state += 1
    for line in sys_msg.split('\n'):
        if 'name:' in line.lower():
            name = line.split(':',1)[1].strip() if ':' in line else ''
            if name:
                identity_names[name] += 1
        for thread in ['identity', 'philosophy', 'log', 'form', 'reflex', 'linking', 'subconscious']:
            if thread in line.lower():
                state_facts[thread] += 1

print(f'Examples with STATE/identity in system: {has_state}')
print(f'\nIdentity names in training data:')
for name, count in identity_names.most_common(10):
    print(f'  {name}: {count}')
print(f'\nThread mentions in system prompts:')
for thread, count in state_facts.most_common():
    print(f'  {thread}: {count}')

key_terms = collections.Counter()
for ex in data:
    msgs = ex.get('messages', [])
    asst = next((m['content'] for m in msgs if m['role'] == 'assistant'), '').lower()
    for term in ['nola', 'agent', 'ai os', 'aios', 'thread', 'state', 'subconscious',
                 'identity', 'philosophy', 'form', 'reflex', 'linking', 'consolidat',
                 'hebbian', 'spread activation', 'profile_fact', 'l1', 'l2', 'l3']:
        if term in asst:
            key_terms[term] += 1

print(f'\nKey terms in assistant responses:')
for term, count in key_terms.most_common():
    print(f'  {term}: {count}')

# Count user question categories
categories = collections.Counter()
for ex in data:
    msgs = ex.get('messages', [])
    user = next((m['content'] for m in msgs if m['role'] == 'user'), '').lower()
    if 'name' in user: categories['identity/name'] += 1
    elif 'thread' in user: categories['architecture/threads'] += 1
    elif 'tool' in user or 'form' in user: categories['tools/form'] += 1
    elif 'value' in user or 'philosophy' in user: categories['philosophy'] += 1
    elif 'state' in user: categories['STATE'] += 1
    elif 'api' in user or 'endpoint' in user: categories['API'] += 1
    elif 'memory' in user or 'remember' in user: categories['memory'] += 1
    elif any(w in user for w in ['how', 'what', 'why', 'explain']): categories['general_qa'] += 1
    else: categories['other'] += 1

print(f'\nUser question categories:')
for cat, count in categories.most_common():
    print(f'  {cat}: {count}')
