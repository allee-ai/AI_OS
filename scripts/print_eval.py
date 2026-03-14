#!/usr/bin/env python3
"""Pretty-print eval results from stdin JSON."""
import sys, json

data = json.load(sys.stdin)
results = data.get('results', [])
summary = data.get('summary', {})

for r in results:
    name = r.get('eval_name', '?')
    status = r.get('status', '?')
    score = r.get('score', 0)
    passed = r.get('passed', 0)
    total = r.get('total', 0)
    run_id = r.get('run_id', '')
    icon = '✓' if status in ('passed', 'pass') else '✗'
    filled = int(score * 20)
    bar = '█' * filled + '░' * (20 - filled)
    print(f'  {icon} {name:25s}  {bar}  {passed}/{total}  ({score:.0%})  [{run_id[:8]}]')
    for d in r.get('details', []):
        dp = '✓' if d.get('passed') else '✗'
        prompt = d.get('prompt', '')[:55]
        ms = d.get('duration_ms', 0)
        print(f'      {dp} {prompt:55s} {ms:>8.0f}ms')

print()
tp = summary.get('passed', 0)
tt = summary.get('total', 0)
avg = summary.get('average_score', 0)
print(f'  Summary: {tp}/{tt} pass  avg={avg:.1%}')
