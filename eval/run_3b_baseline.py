"""Baseline eval: Qwen 3B raw vs 1.5B raw, then we train 3B."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.evals import run_eval
from eval.runner import clear_mlx_cache

models = [
    ("T0: Base Qwen 1.5B", "mlx:Qwen2.5-1.5B-Instruct-4bit"),
    ("T0: Base Qwen 3B", "mlx:Qwen2.5-3B-Instruct-4bit"),
]

results = []
for label, model in models:
    clear_mlx_cache()
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    result = run_eval('knowledge_retention', save=True, model=model)
    print(f"Score: {result['score']} ({result['passed']}/{result['total']})  {result['status'].upper()}")
    print(f"Run ID: {result.get('run_id', 'N/A')}")
    for d in result['details']:
        mark = 'Y' if d['passed'] else 'N'
        print(f"  {mark} {d['prompt'][:50]} -- hits: {d['keyword_hits']}/{d['min_required']}")
        print(f"      {d['response_preview'][:150]}")
    results.append((label, result))

print(f"\n{'='*60}")
print("  COMPARISON")
print(f"{'='*60}")
for label, r in results:
    print(f"  {label}: {r['score']:.0%} ({r['passed']}/{r['total']})")
