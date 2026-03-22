"""Temporary script to display 3B eval results from DB."""
import sqlite3
from data.db import get_db_path
from eval.evals import EVAL_REGISTRY

conn = sqlite3.connect(get_db_path())
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT eval_name, status, score, total, passed, model, id, created_at "
    "FROM eval_runs WHERE model = 'mlx:finetune/runs/3b-v1-final' "
    "ORDER BY created_at ASC"
).fetchall()
conn.close()

seen = {}
for r in rows:
    seen[r['eval_name']] = dict(r)

print("=" * 76)
print("  3B FUSED MODEL EVAL RESULTS  (mlx:finetune/runs/3b-v1-final)")
print("  Base: mlx-community/Qwen2.5-3B-Instruct-4bit + 800 iter SFT")
print("=" * 76)
print()
print(f"  {'#':<3} {'Eval':<26} {'Status':<9} {'Score':<7} {'Passed':<9} {'Run ID':<10}")
print("  " + "-" * 70)

total_score = 0
total_evals = 0
pass_count = 0
fail_count = 0

for i, name in enumerate(EVAL_REGISTRY, 1):
    if name not in seen:
        print(f"  {i:<3} {name:<26} {'MISSING':<9}")
        continue
    r = seen[name]
    status = r['status']
    if status == 'running':
        status = 'failed'
    score = r['score'] or 0
    total = r['total'] or 0
    passed = r['passed'] or 0
    sym = "PASS" if status in ('pass', 'passed') else "FAIL"
    print(f"  {i:<3} {name:<26} {sym:<9} {score:5.0%}   {passed:>2}/{total:<4}  {r['id'][:8]}")
    total_score += score
    total_evals += 1
    if status in ('pass', 'passed'):
        pass_count += 1
    else:
        fail_count += 1

print("  " + "-" * 70)
avg = total_score / total_evals if total_evals else 0
print(f"  Average score: {avg:.2f} ({avg:.0%})")
print(f"  Passed: {pass_count}/{total_evals}  |  Failed: {fail_count}/{total_evals}  |  Errors: 0")
print()

# Detail breakdown for key evals
print("=" * 76)
print("  PER-EVAL DETAIL (from saved details_json)")
print("=" * 76)

conn2 = sqlite3.connect(get_db_path())
conn2.row_factory = sqlite3.Row
import json
for name in EVAL_REGISTRY:
    if name not in seen:
        continue
    row = conn2.execute(
        "SELECT details_json FROM eval_runs WHERE id = ?", (seen[name]['id'],)
    ).fetchone()
    if not row or not row['details_json']:
        continue
    details = json.loads(row['details_json'])
    if not details:
        continue
    print(f"\n  {name} (score={seen[name]['score']:.0%}):")
    for d in details:
        p = d.get('passed', False)
        prompt = d.get('prompt', '')[:55]
        sym = "+" if p else "-"
        print(f"    {sym} {prompt}")
conn2.close()
print()
