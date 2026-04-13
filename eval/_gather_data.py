#!/usr/bin/env python3
"""Temporary script to gather all eval data for dashboard update."""
import json, os

# Training logs
for run_id in ['nola-2f58ee32', 'nola-f911a41e']:
    for phase in ['phase1_repeat', 'phase2_understand']:
        path = f'experiments/runs/{run_id}/{phase}/train_log.json'
        if os.path.exists(path):
            d = json.load(open(path))
            entries = d if isinstance(d, list) else d.get('entries', [d])
            print(f'{run_id}/{phase}: {len(entries)} entries')
            if entries:
                print(f'  first: {json.dumps(entries[0], default=str)[:300]}')
                print(f'  last:  {json.dumps(entries[-1], default=str)[:300]}')
        config_path = f'experiments/runs/{run_id}/{phase}/config.json'
        if os.path.exists(config_path):
            cfg = json.load(open(config_path))
            print(f'  config: {json.dumps(cfg, default=str)[:300]}')

    # Check final
    final_cfg = f'experiments/runs/{run_id}/final/config.json'
    if os.path.exists(final_cfg):
        cfg = json.load(open(final_cfg))
        print(f'{run_id}/final config: {json.dumps(cfg, default=str)[:300]}')

print()
print('=== Resource eval variants ===')
import glob
for f in sorted(glob.glob('experiments/runs/resource_eval_qwen*.json')):
    d = json.load(open(f))
    s = d.get('summary', {})
    print(f'{os.path.basename(f)}: {json.dumps(s, indent=2)[:400]}')

print()
print('=== 3b results ===')
for f in sorted(glob.glob('eval/*3b*.json') + glob.glob('experiments/runs/*3b*.json')):
    print(f'Found: {f}')
    d = json.load(open(f))
    print(f'  keys: {list(d.keys())[:10]}')
