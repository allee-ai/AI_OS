"""
Full eval suite for SmolLM2-135M fine-tuned model (5e-6 learning rate).
Model: finetune/runs/smol-135m-5e6-final (SFT, 5e-6 LR, val loss 2.452)
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MLX_MODEL = "mlx:finetune/runs/smol-135m-5e6-final"

# ── Quick smoke test: can we load and generate? ──
print("=" * 70)
print("SMOKE TEST: Loading model and generating...")
print("=" * 70)

from eval.runner import run_prompt

smoke = run_prompt(MLX_MODEL, "What is your name?")
print(f"Response: {smoke.get('response', '')[:300]}")
print(f"Duration: {smoke.get('duration_ms', 0):.0f}ms")
if smoke.get("error"):
    print(f"ERROR: {smoke['error']}")
    print("Cannot proceed with evals — model load failed.")
    sys.exit(1)
print(f"\nSmoke test passed. Model loaded successfully.\n")

# ── Run all evals ──
from eval.evals import EVAL_REGISTRY, run_eval, list_evals

# Categorize evals by type
MODEL_EVALS = [
    "knowledge_retention",      # Direct model test, no STATE needed
    "identity_persistence",     # Tests identity claims
    "state_format",             # Tests if model produces STATE notation
    "hallucination",            # Tests grounding (no STATE = tests raw behavior)
    "tool_use",                 # Tests if model invokes tools
    "injection_resistance",     # Tests adversarial robustness
]

INFRASTRUCTURE_EVALS = [
    "state_completeness",       # Tests STATE assembler (model-independent)
    "scoring_quality",          # Tests relevance scoring (model-independent)
    "context_relevance",        # Tests STATE assembly per query
]

PIPELINE_EVALS = [
    "fact_recall",              # Needs seeded facts + STATE
    "state_impact",             # A/B with nola pipeline
    "retrieval_precision",      # Needs seeded facts + STATE
    "state_drift",              # Needs agent pipeline for multi-turn
]

SPECIAL_EVALS = [
    "tier_comparison",          # Needs multiple models (Ollama)
    "tool_calling_direct",      # Needs Ollama
]

all_results = {}
summary = []

def run_and_report(name, **overrides):
    """Run one eval and print results."""
    print(f"\n{'─' * 60}")
    print(f"Running: {name}")
    print(f"{'─' * 60}")
    start = time.time()
    try:
        result = run_eval(name, save=True, **overrides)
        elapsed = time.time() - start
        all_results[name] = result
        
        status = result.get("status", "?")
        score = result.get("score", 0)
        total = result.get("total", 0)
        passed = result.get("passed", 0)
        error = result.get("error", "")
        
        icon = "✓" if status == "passed" else "✗" if status == "failed" else "⚠"
        print(f"  {icon} Status: {status}")
        print(f"  Score: {score:.2f} ({passed}/{total})")
        if error:
            print(f"  Error: {error}")
        print(f"  Time: {elapsed:.1f}s")
        
        # Print per-case details
        for d in result.get("details", [])[:15]:
            p = d.get("prompt", d.get("query", ""))[:50]
            ok = "✓" if d.get("passed") else "✗"
            preview = d.get("response_preview", "")[:80].replace("\n", " ")
            extras = ""
            if "keyword_hits" in d:
                extras = f" (hits: {d['keyword_hits']}/{d['min_required']})"
            elif "held_identity" in d:
                extras = f" (held={d['held_identity']}, leaked={d.get('leaked_identity', '?')})"
            elif "category" in d:
                extras = f" [{d['category']}]"
            print(f"    {ok} {p}{extras}")
            if preview:
                print(f"      → {preview}")
        
        summary.append({
            "name": name, "status": status, "score": score,
            "passed": passed, "total": total, "time": round(elapsed, 1),
            "error": error,
        })
        return result
    except Exception as e:
        elapsed = time.time() - start
        print(f"  EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        summary.append({
            "name": name, "status": "exception", "score": 0,
            "passed": 0, "total": 0, "time": round(elapsed, 1),
            "error": str(e),
        })
        return None


# ── Phase 1: Model-focused evals (most relevant for this test) ──
print("\n" + "=" * 70)
print("PHASE 1: Model-focused evals (testing the fine-tuned model directly)")
print("=" * 70)

for name in MODEL_EVALS:
    run_and_report(name, model=MLX_MODEL)

# ── Phase 2: Infrastructure evals (model-independent, test STATE system) ──
print("\n" + "=" * 70)
print("PHASE 2: Infrastructure evals (STATE assembler / scoring)")
print("=" * 70)

for name in INFRASTRUCTURE_EVALS:
    run_and_report(name)  # These use inspect_state(), no model override needed

# ── Phase 3: Pipeline evals (need agent pipeline — run with MLX override where possible) ──
print("\n" + "=" * 70)
print("PHASE 3: Pipeline evals (require agent pipeline)")
print("=" * 70)

for name in PIPELINE_EVALS:
    run_and_report(name, model=MLX_MODEL)

# ── Phase 4: Special evals (need Ollama/multiple models — skip or adapt) ──
print("\n" + "=" * 70)
print("PHASE 4: Special evals (multi-model / Ollama-dependent)")
print("=" * 70)

# tool_calling_direct needs Ollama — skip for MLX model
print(f"\n{'─' * 60}")
print("Skipping: tool_calling_direct (requires Ollama, not applicable to MLX model)")
summary.append({"name": "tool_calling_direct", "status": "skipped", "score": 0,
                 "passed": 0, "total": 0, "time": 0, "error": "Requires Ollama"})

# tier_comparison needs multiple models — skip
print(f"Skipping: tier_comparison (requires multiple Ollama models)")
summary.append({"name": "tier_comparison", "status": "skipped", "score": 0,
                 "passed": 0, "total": 0, "time": 0, "error": "Requires Ollama models"})


# ── FINAL REPORT ──
print("\n\n" + "=" * 70)
print("FINAL EVALUATION REPORT")
print(f"Model: SmolLM2-135M SFT (5e-6 LR, val loss 2.452)")
print(f"Path: finetune/runs/smol-135m-5e6-final")
print("=" * 70)

print(f"\n{'Eval':<25} {'Status':<10} {'Score':>6} {'Passed':>8} {'Time':>6}")
print(f"{'─' * 25} {'─' * 10} {'─' * 6} {'─' * 8} {'─' * 6}")

total_score = 0
total_evals = 0
for s in summary:
    status_icon = {"passed": "✓", "failed": "✗", "error": "⚠", "exception": "💥", "skipped": "⊘"}.get(s["status"], "?")
    score_str = f"{s['score']:.2f}" if s["status"] not in ("skipped", "exception") else "N/A"
    passed_str = f"{s['passed']}/{s['total']}" if s["total"] > 0 else "N/A"
    print(f"{s['name']:<25} {status_icon} {s['status']:<8} {score_str:>6} {passed_str:>8} {s['time']:>5.1f}s")
    if s["status"] in ("passed", "failed"):
        total_score += s["score"]
        total_evals += 1

if total_evals > 0:
    avg = total_score / total_evals
    print(f"\n{'Average score':<25} {'':>10} {avg:>6.2f}")

print(f"\nRan: {sum(1 for s in summary if s['status'] not in ('skipped',))}/{len(summary)} evals")
print(f"Passed: {sum(1 for s in summary if s['status'] == 'passed')}/{total_evals}")
print(f"Failed: {sum(1 for s in summary if s['status'] == 'failed')}/{total_evals}")
print(f"Errors: {sum(1 for s in summary if s['status'] in ('error', 'exception'))}")
print(f"Skipped: {sum(1 for s in summary if s['status'] == 'skipped')}")

# Save results
results_path = "eval/results_smol135m_5e6_full.json"
with open(results_path, "w") as f:
    json.dump({"summary": summary, "details": {k: v for k, v in all_results.items()}}, f, indent=2, default=str)
print(f"\nFull results saved to: {results_path}")
