#!/usr/bin/env python3
"""Run all evals sequentially and save results.

Usage:
    python3 eval/run_all_save.py          # run all
    python3 eval/run_all_save.py kr       # run just knowledge_retention
"""
import sys, os, time, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.evals import run_eval, list_evals

RESULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "all_results.json")

# Evals to skip (need cloud models or special setup)
SKIP_EVALS = {"tool_calling_direct"}  # needs kimi-k2:1t-cloud

# Only run specific evals if specified (comma-separated or single)
filter_name = sys.argv[1] if len(sys.argv) > 1 else None

all_results = {}
evals = list_evals()

if filter_name:
    # Support comma-separated: "fact_recall,hallucination,retrieval"
    filters = [f.strip() for f in filter_name.split(",")]
    evals = [e for e in evals if any(f in e["name"] for f in filters)]

print(f"{'='*60}", flush=True)
print(f"Running {len(evals)} evals (skipping: {SKIP_EVALS})", flush=True)
print(f"{'='*60}\n", flush=True)

for i, ev in enumerate(evals, 1):
    name = ev["name"]
    if name in SKIP_EVALS:
        print(f"[{i}/{len(evals)}] SKIP {name}", flush=True)
        continue

    print(f"[{i}/{len(evals)}] Running: {name}...", flush=True)
    start = time.time()
    try:
        result = run_eval(name, save=True)
        elapsed = time.time() - start
        score = result.get("score", 0)
        status = result.get("status", "unknown")
        passed = result.get("passed", 0)
        total = result.get("total", 0)
        print(f"  -> {status} | score={score} | {passed}/{total} | {elapsed:.1f}s", flush=True)
        all_results[name] = result
    except Exception as e:
        elapsed = time.time() - start
        print(f"  -> ERROR: {e} ({elapsed:.1f}s)", flush=True)
        all_results[name] = {"status": "error", "error": str(e)}

# Save combined results
with open(RESULTS_FILE, "w") as f:
    json.dump(all_results, f, indent=2, default=str)

print(f"\n{'='*60}", flush=True)
print(f"All results saved to {RESULTS_FILE}", flush=True)
print(f"{'='*60}", flush=True)

# Summary
print("\nSummary:", flush=True)
for name, r in all_results.items():
    status = r.get("status", "error")
    score = r.get("score", "N/A")
    print(f"  {name:30s}  {status:8s}  score={score}", flush=True)
