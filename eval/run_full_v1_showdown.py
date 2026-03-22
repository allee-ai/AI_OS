"""Compare full-v1-best (all data, iter 1800) vs base-v2-best (system only, iter 800) vs base model."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.evals import run_eval
from eval.runner import clear_mlx_cache

MODELS = [
    ("Base (no adapters)", "mlx:Qwen2.5-1.5B-Instruct-4bit"),
    ("base-v2-best (sys only, i800, val 1.127)", "mlx:Qwen2.5-1.5B-Instruct-4bit+finetune/runs/base-v2-best"),
    ("full-v1-best (all data, i1800, val 2.002)", "mlx:Qwen2.5-1.5B-Instruct-4bit+finetune/runs/full-v1-best"),
]

EVALS = ["knowledge_retention", "identity_persistence", "fact_recall"]

all_results = {}

for eval_name in EVALS:
    print(f"\n{'#'*70}")
    print(f"  EVAL: {eval_name}")
    print(f"{'#'*70}")

    eval_results = []
    for label, model in MODELS:
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")

        clear_mlx_cache()

        result = run_eval(eval_name, save=True, model=model)
        print(f"Score: {result['score']} ({result['passed']}/{result['total']})  {result['status'].upper()}")
        print(f"Run ID: {result.get('run_id', 'N/A')}")
        for d in result['details']:
            mark = 'Y' if d['passed'] else 'N'
            detail_str = d.get('prompt', d.get('probe', ''))[:50]
            extra = ""
            if 'keyword_hits' in d:
                extra = f" -- hits: {d['keyword_hits']}/{d['min_required']}"
            print(f"  {mark} {detail_str}{extra}")
        eval_results.append((label, result))

    all_results[eval_name] = eval_results

# ── Summary ──────────────────────────────────────────────────────────────
print(f"\n{'#'*70}")
print("  FINAL COMPARISON")
print(f"{'#'*70}")

header = f"{'Eval':<25}"
for label, _ in MODELS:
    short = label.split('(')[0].strip()
    header += f"  {short:<20}"
print(header)
print("-" * len(header))

for eval_name in EVALS:
    row = f"{eval_name:<25}"
    for label, result in all_results[eval_name]:
        row += f"  {result['score']:.0%} ({result['passed']}/{result['total']}){'':<5}"
    print(row)
