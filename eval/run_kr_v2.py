"""Run knowledge_retention eval: T0 base, V1 adapter, V2 adapter (final + best checkpoint)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.evals import run_eval

models = [
    ("T0: Base Qwen 1.5B", "mlx:Qwen2.5-1.5B-Instruct-4bit"),
    ("V1: 700 iters, 1377 examples", "mlx:Qwen2.5-1.5B-Instruct-4bit+finetune/runs/base-v1/adapters"),
    ("V2-final: 1400 iters, 2335 examples", "mlx:Qwen2.5-1.5B-Instruct-4bit+finetune/runs/base-v2/adapters"),
]

results = []
for label, model in models:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  model: {model}")
    print(f"{'='*60}")

    result = run_eval('knowledge_retention', save=True, model=model)
    print(f"Score: {result['score']} ({result['passed']}/{result['total']})  {result['status'].upper()}")
    print(f"Run ID: {result.get('run_id', 'N/A')}")
    for d in result['details']:
        mark = 'Y' if d['passed'] else 'N'
        print(f"  {mark} {d['prompt'][:50]} -- hits: {d['keyword_hits']}/{d['min_required']}")
    results.append((label, result))

print(f"\n{'='*60}")
print("  COMPARISON")
print(f"{'='*60}")
for label, r in results:
    print(f"  {label}: {r['score']:.0%} ({r['passed']}/{r['total']})  {r['status'].upper()}")
