#!/usr/bin/env python3
"""Run key evals with qwen2.5:1.5b as the agent's LLM.

Usage:
    python3 eval/_run_1_5b.py
    
Sets AIOS_MODEL_NAME=qwen2.5:1.5b to route the agent pipeline through
the smaller model, keeping all STATE/HEA infrastructure identical.
"""
import sys, os, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Override the default model
os.environ["AIOS_MODEL_NAME"] = "qwen2.5:1.5b"

from eval.evals import run_eval

# Run the most important evals to show scale independence
EVALS = [
    "state_format",
    "identity_persistence",
    "knowledge_retention",
    "fact_recall",
    "injection_resistance",
    "context_relevance",
]

print(f"Running {len(EVALS)} evals with qwen2.5:1.5b...", flush=True)
print("=" * 60, flush=True)

for i, name in enumerate(EVALS, 1):
    print(f"[{i}/{len(EVALS)}] {name}...", flush=True)
    start = time.time()
    try:
        r = run_eval(name, save=True, model="nola")
        elapsed = time.time() - start
        print(f"  -> {r['status']} score={r['score']} {r['passed']}/{r['total']} ({elapsed:.1f}s)", flush=True)
    except Exception as e:
        elapsed = time.time() - start
        print(f"  -> ERROR: {e} ({elapsed:.1f}s)", flush=True)

print("\nDone.", flush=True)
