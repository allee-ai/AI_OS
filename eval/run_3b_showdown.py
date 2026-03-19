"""The big comparison: all models, full responses visible."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.evals import run_eval
from eval.runner import clear_mlx_cache

models = [
    ("T0: Raw 3B",         "mlx:Qwen2.5-3B-Instruct-4bit"),
    ("3B-v1: 800 iters",   "mlx:Qwen2.5-3B-Instruct-4bit+finetune/runs/3b-v1/adapters"),
    ("1.5B-v1: best (v2@800)", "mlx:Qwen2.5-1.5B-Instruct-4bit+finetune/runs/base-v2-best"),
]

results = []
for label, model in models:
    clear_mlx_cache()
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")

    result = run_eval('knowledge_retention', save=True, model=model)
    print(f"  Score: {result['score']} ({result['passed']}/{result['total']})  {result['status'].upper()}")
    print(f"  Run ID: {result.get('run_id', 'N/A')}")
    for d in result['details']:
        mark = 'Y' if d['passed'] else 'N'
        print(f"\n  [{mark}] {d['prompt']}")
        print(f"      hits: {d['keyword_hits']}/{d['min_required']}")
        resp = d.get('response_preview', '')[:250]
        print(f"      {resp}")
    results.append((label, result))

print(f"\n{'='*70}")
print("  FINAL COMPARISON")
print(f"{'='*70}")
for label, r in results:
    print(f"  {label}: {r['score']:.0%} ({r['passed']}/{r['total']})  {r['status'].upper()}")
