"""Run knowledge_retention eval through the registry against base + v1 adapter."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.evals import run_eval

models = [
    ("T0: Base Qwen 1.5B", "mlx:Qwen2.5-1.5B-Instruct-4bit"),
    ("T1: V1 Adapter", "mlx:Qwen2.5-1.5B-Instruct-4bit+finetune/runs/base-v1/adapters"),
]

for label, model in models:
    print(f"\n{'='*60}")
    print(f"  {label}  ({model})")
    print(f"{'='*60}")

    result = run_eval('knowledge_retention', save=True, model=model)
    print(f"Score: {result['score']} ({result['passed']}/{result['total']})  {result['status'].upper()}")
    print(f"Run ID: {result.get('run_id', 'N/A')}")
    for d in result['details']:
        mark = 'Y' if d['passed'] else 'N'
        print(f"  {mark} {d['prompt'][:50]} -- hits: {d['keyword_hits']}/{d['min_required']}")
