#!/usr/bin/env python3
"""Run the fixed evals."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.evals import run_eval

for name in ["retrieval_precision", "tier_comparison"]:
    print(f"Running {name}...", flush=True)
    r = run_eval(name, save=True)
    print(f"  {r['status']} score={r['score']} {r['passed']}/{r['total']}", flush=True)
print("Done.", flush=True)
