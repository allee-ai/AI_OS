#!/usr/bin/env python3
"""Run all structured evals inside Docker container and print results."""
import subprocess, json, sys

raw = subprocess.run(
    ["docker", "exec", "ai-os", "python", "-c",
     "import json; from eval.evals import run_all; print(json.dumps(run_all(save=True)))"],
    capture_output=True, text=True, timeout=600
)

if raw.returncode != 0:
    print("STDERR:", raw.stderr, file=sys.stderr)
    sys.exit(1)

results = json.loads(raw.stdout.strip())

for r in results:
    name = r.get('eval_name', '?')
    status = r.get('status', '?')
    score = r.get('score', 0)
    passed = r.get('passed', 0)
    total = r.get('total', 0)
    run_id = r.get('run_id', '')[:8]
    icon = '✓' if status in ('passed', 'pass') else '✗'
    filled = int(score * 20)
    bar = '█' * filled + '░' * (20 - filled)
    print(f'  {icon} {name:25s}  {bar}  {passed}/{total}  ({score:.0%})  [{run_id}]')
    for d in r.get('details', []):
        dp = '✓' if d.get('passed') else '✗'
        prompt = d.get('prompt', '')[:55]
        ms = d.get('duration_ms', 0)
        print(f'      {dp} {prompt:55s} {ms:>8.0f}ms')
    print()

total_pass = sum(1 for r in results if r.get('status') in ('pass', 'passed'))
avg = sum(r.get('score', 0) for r in results) / len(results) if results else 0
print(f'  Summary: {total_pass}/{len(results)} pass  avg={avg:.1%}')
