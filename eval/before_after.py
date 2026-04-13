#!/usr/bin/env python3
"""
Before/After Behavioral Eval — Closing the Loop
================================================
Runs all 8 behavioral evals against both the base model and fine-tuned model,
then prints a comparison table showing the training delta.

Base model:  qwen2.5:1.5b via Ollama (port 11434)
Fine-tuned:  Qwen2.5-1.5B + behavioral LoRA via mlx_lm server (port 8899)

Usage:
    python eval/before_after.py
"""

import json
import sys
import time
import os
from typing import Dict, Any, List, Tuple

# ── Chat helpers ──

def chat_ollama(model: str, system: str, user: str) -> str:
    """Call Ollama API."""
    import ollama
    r = ollama.chat(model=model, messages=[
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ])
    return r["message"]["content"]


def chat_mlx(system: str, user: str, port: int = 8899) -> str:
    """Call MLX server (OpenAI-compatible API)."""
    import urllib.request
    data = json.dumps({
        "model": "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 1024,
        "temperature": 0.7,
    }).encode()
    req = urllib.request.Request(
        f"http://localhost:{port}/v1/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read())
    return result["choices"][0]["message"]["content"]


# ── Import eval modules ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re

from eval.priority_triage import (
    SCENARIOS as PT_SCENARIOS,
    condition_state as pt_state,
    extract_task_order, kendall_tau_distance,
)
from eval.delegation_refusal import (
    QUERIES as DR_QUERIES,
    condition_state as dr_state,
    HEDGING_PATTERNS as DR_HEDGING,
)
from eval.uncertainty_calibration import (
    QUERIES as UC_QUERIES,
    condition_state as uc_state,
    HEDGE_PATTERNS as UC_HEDGE,
    count_hedges,
)
from eval.context_management import (
    PROMPTS as CM_PROMPTS,
    condition_state as cm_state,
)
from eval.resource_regulation import (
    PROMPTS as RR_PROMPTS,
    condition_state_loose as rr_state_loose,
    condition_state_tight as rr_state_tight,
)
from eval.repetition_avoidance import (
    TOPIC_GROUPS as RA_TOPICS,
    word_overlap, ngram_overlap,
)
from eval.tone_matching import (
    PROMPTS as TM_PROMPTS,
    condition_state as tm_state,
    score_register,
)
from eval.tool_selection import (
    QUERIES as TS_QUERIES,
    condition_state as ts_state,
    extract_tool_choice,
)


# ── Eval functions (STATE condition only — that's what we trained on) ──

def eval_priority_triage(chat_fn) -> Dict[str, Any]:
    """Returns: top_correct_rate, avg_tau"""
    results = []
    for scenario in PT_SCENARIOS:
        cond = pt_state(scenario)
        try:
            response = chat_fn(cond["system"], cond["user"])
        except Exception as e:
            response = f"ERROR: {e}"
        task_names = [t["name"] for t in scenario["tasks"]]
        actual = extract_task_order(response, task_names)
        expected = scenario["expected_order"]
        tau = kendall_tau_distance(actual, expected)
        top_ok = actual[0] == expected[0] if actual else False
        results.append({"tau": tau, "top_correct": top_ok})
    
    top_rate = sum(1 for r in results if r["top_correct"]) / len(results) if results else 0
    avg_tau = sum(r["tau"] for r in results) / len(results) if results else 1.0
    return {"top_correct_pct": round(top_rate * 100, 1), "avg_tau": round(avg_tau, 3)}


def eval_delegation_refusal(chat_fn) -> Dict[str, Any]:
    """Returns: accuracy, answer_acc, refusal_acc"""
    correct = 0
    total = 0
    answer_correct = 0
    answer_total = 0
    refusal_correct = 0
    refusal_total = 0

    for q in DR_QUERIES:
        cond = dr_state(q["prompt"])
        try:
            response = chat_fn(cond["system"], cond["user"])
        except Exception as e:
            response = f"ERROR: {e}"

        refused = any(re.search(p, response, re.I) for p in DR_HEDGING)
        should_answer = q["should_answer"]

        if should_answer:
            answer_total += 1
            if not refused:
                correct += 1
                answer_correct += 1
        else:
            refusal_total += 1
            if refused:
                correct += 1
                refusal_correct += 1
        total += 1

    return {
        "accuracy_pct": round(correct / total * 100, 1) if total else 0,
        "answer_acc_pct": round(answer_correct / answer_total * 100, 1) if answer_total else 0,
        "refusal_acc_pct": round(refusal_correct / refusal_total * 100, 1) if refusal_total else 0,
    }


def eval_uncertainty_calibration(chat_fn) -> Dict[str, Any]:
    """Returns: accuracy, calibration_delta"""
    correct = 0
    total = 0
    high_hedges = []
    low_hedges = []

    for q in UC_QUERIES:
        cond = uc_state(q["prompt"], q["topic"], q["confidence"])
        try:
            response = chat_fn(cond["system"], cond["user"])
        except Exception as e:
            response = f"ERROR: {e}"

        hedge_count = count_hedges(response)
        hedged = hedge_count >= 2
        expect_hedge = q.get("expect_hedge", False)

        if expect_hedge:
            low_hedges.append(hedge_count)
            if hedged:
                correct += 1
        else:
            high_hedges.append(hedge_count)
            if not hedged:
                correct += 1
        total += 1

    avg_low = sum(low_hedges) / len(low_hedges) if low_hedges else 0
    avg_high = sum(high_hedges) / len(high_hedges) if high_hedges else 0
    delta = avg_low - avg_high

    return {
        "accuracy_pct": round(correct / total * 100, 1) if total else 0,
        "calibration_delta": round(delta, 2),
    }


def eval_context_management(chat_fn) -> Dict[str, Any]:
    """Returns: compression_ratio (lower = better), low_avg_tokens, high_avg_tokens"""
    low_tokens = []
    high_tokens = []

    for prompt_text in CM_PROMPTS:
        for capacity in ["low", "high"]:
            cond = cm_state(prompt_text, capacity)
            try:
                response = chat_fn(cond["system"], cond["user"])
            except Exception as e:
                response = f"ERROR: {e}"

            words = response.split()
            approx_tokens = max(1, int(len(words) * 1.3))

            if capacity == "low":
                low_tokens.append(approx_tokens)
            else:
                high_tokens.append(approx_tokens)
    
    avg_low = sum(low_tokens) / len(low_tokens) if low_tokens else 1
    avg_high = sum(high_tokens) / len(high_tokens) if high_tokens else 1
    ratio = avg_low / avg_high if avg_high > 0 else 1.0
    
    return {
        "compression_ratio": round(ratio, 3),
        "low_avg_tokens": round(avg_low, 1),
        "high_avg_tokens": round(avg_high, 1),
    }


def eval_resource_regulation(chat_fn) -> Dict[str, Any]:
    """Returns: tight/loose ratio, avg tokens, consistency (CoV)"""
    loose_tokens = []
    tight_tokens = []

    for prompt_text in RR_PROMPTS:
        # Loose condition
        cond = rr_state_loose(prompt_text)
        try:
            response = chat_fn(cond["system"], cond["user"])
        except Exception as e:
            response = f"ERROR: {e}"
        loose_tokens.append(max(1, int(len(response.split()) * 1.3)))

        # Tight condition
        cond = rr_state_tight(prompt_text)
        try:
            response = chat_fn(cond["system"], cond["user"])
        except Exception as e:
            response = f"ERROR: {e}"
        tight_tokens.append(max(1, int(len(response.split()) * 1.3)))

    avg_loose = sum(loose_tokens) / len(loose_tokens) if loose_tokens else 0
    avg_tight = sum(tight_tokens) / len(tight_tokens) if tight_tokens else 0

    all_tokens = loose_tokens + tight_tokens
    avg_all = sum(all_tokens) / len(all_tokens) if all_tokens else 0
    std_all = (sum((t - avg_all) ** 2 for t in all_tokens) / len(all_tokens)) ** 0.5 if all_tokens else 0
    cov = std_all / avg_all if avg_all > 0 else 0

    ratio = avg_tight / avg_loose if avg_loose > 0 else 1.0

    return {
        "tight_loose_ratio": round(ratio, 3),
        "avg_loose_tokens": round(avg_loose, 1),
        "avg_tight_tokens": round(avg_tight, 1),
        "consistency_cov": round(cov, 3),
    }


def eval_repetition_avoidance(chat_fn) -> Dict[str, Any]:
    """Multi-turn: ask same topic 3 ways, measure overlap between responses."""
    all_word_overlaps = []
    all_ngram_overlaps = []

    for group in RA_TOPICS:
        topic = group["topic"]
        prompts = group["prompts"]
        responses = []
        for i, prompt in enumerate(prompts):
            covered = ", ".join(f'"{p}"' for p in prompts[:i]) if i > 0 else "none"
            system = f"""== STATE ==
identity.name = Assistant
session.topic = {topic}
session.turn = {i + 1}
session.topics_covered = [{covered}]
session.prior_response_count = {i}
session.repetition_score = {"n/a" if i == 0 else "monitor"}
== END STATE ==

You are Assistant. Your STATE is your source of truth. You have already covered the topics listed in session.topics_covered. Add NEW information only — do not restate what was covered."""

            try:
                response = chat_fn(system, prompt)
            except Exception as e:
                response = f"ERROR: {e}"
            responses.append(response)

        for j in range(len(responses) - 1):
            wo = word_overlap(responses[j], responses[j + 1])
            no = ngram_overlap(responses[j], responses[j + 1])
            all_word_overlaps.append(wo)
            all_ngram_overlaps.append(no)

    return {
        "word_overlap": round(sum(all_word_overlaps) / len(all_word_overlaps), 3) if all_word_overlaps else 0,
        "ngram_3_overlap": round(sum(all_ngram_overlaps) / len(all_ngram_overlaps), 3) if all_ngram_overlaps else 0,
    }


def eval_tone_matching(chat_fn) -> Dict[str, Any]:
    """Returns: accuracy_pct using score_register from the module."""
    correct = 0
    total = 0

    for prompt_group in TM_PROMPTS:
        for register in ["formal", "casual", "technical"]:
            prompt_text = prompt_group[register]
            cond = tm_state(prompt_text, register)
            try:
                response = chat_fn(cond["system"], cond["user"])
            except Exception as e:
                response = f"ERROR: {e}"

            scores = score_register(response, register)
            if scores["match"]:
                correct += 1
            total += 1

    return {"accuracy_pct": round(correct / total * 100, 1) if total else 0}


def eval_tool_selection(chat_fn) -> Dict[str, Any]:
    """Returns: optimal_pct, adequate_pct"""
    optimal_correct = 0
    adequate_correct = 0
    total = 0

    for q in TS_QUERIES:
        cond = ts_state(q["prompt"])
        try:
            response = chat_fn(cond["system"], cond["user"])
        except Exception as e:
            response = f"ERROR: {e}"

        chosen = extract_tool_choice(response)
        if chosen == q["optimal"]:
            optimal_correct += 1
        if chosen in q["adequate"]:
            adequate_correct += 1
        total += 1

    return {
        "optimal_pct": round(optimal_correct / total * 100, 1) if total else 0,
        "adequate_pct": round(adequate_correct / total * 100, 1) if total else 0,
    }


# ── Main runner ──

EVALS = [
    ("Priority Triage", eval_priority_triage),
    ("Delegation/Refusal", eval_delegation_refusal),
    ("Uncertainty Calibration", eval_uncertainty_calibration),
    ("Context Management", eval_context_management),
    ("Resource Regulation", eval_resource_regulation),
    ("Repetition Avoidance", eval_repetition_avoidance),
    ("Tone Matching", eval_tone_matching),
    ("Tool Selection", eval_tool_selection),
]


def run_all(chat_fn, label: str) -> Dict[str, Dict]:
    """Run all evals with the given chat function."""
    results = {}
    for name, fn in EVALS:
        print(f"  {label} | {name}...", end="", flush=True)
        start = time.time()
        try:
            result = fn(chat_fn)
            duration = time.time() - start
            print(f" done ({duration:.1f}s)")
            results[name] = result
        except Exception as e:
            duration = time.time() - start
            print(f" ERROR: {e} ({duration:.1f}s)")
            results[name] = {"error": str(e)}
    return results


def print_comparison(base_results: Dict, ft_results: Dict):
    """Print a formatted comparison table."""
    print("\n" + "=" * 80)
    print("BEFORE/AFTER COMPARISON — Behavioral STATE-Obedience Training")
    print("=" * 80)
    print(f"{'Eval':<25} {'Metric':<22} {'Base':<12} {'Fine-tuned':<12} {'Delta':<10}")
    print("-" * 80)
    
    for eval_name in [name for name, _ in EVALS]:
        base = base_results.get(eval_name, {})
        ft = ft_results.get(eval_name, {})
        
        if "error" in base or "error" in ft:
            err = base.get("error", ft.get("error", "?"))
            print(f"{eval_name:<25} {'ERROR':<22} {err}")
            continue
        
        first_row = True
        for metric in base:
            bval = base[metric]
            fval = ft.get(metric, "?")

            display_name = eval_name if first_row else ""
            first_row = False
            
            if isinstance(bval, (int, float)) and isinstance(fval, (int, float)):
                delta = fval - bval
                lower_better = metric in (
                    "consistency_cov", "word_overlap", "ngram_3_overlap",
                    "avg_tau", "compression_ratio", "tight_loose_ratio",
                )
                sign = "↓" if delta < 0 else "↑"
                if abs(delta) < 0.001:
                    color = " ─"
                elif lower_better:
                    color = " ✓" if delta < 0 else " ✗"
                else:
                    color = " ✓" if delta > 0 else " ✗"
                
                delta_str = f"{sign}{abs(delta):.1f}{color}"
                print(f"{display_name:<25} {metric:<22} {bval:<12} {fval:<12} {delta_str}")
            else:
                print(f"{display_name:<25} {metric:<22} {str(bval):<12} {str(fval):<12}")
    
    print("=" * 80)


def main():
    print("=" * 60)
    print("BEHAVIORAL BEFORE/AFTER EVAL")
    print("Base: qwen2.5:1.5b (Ollama)")
    print("Fine-tuned: Qwen2.5-1.5B + behavioral LoRA (MLX)")
    print("=" * 60)
    
    # Verify both endpoints
    try:
        import ollama
        ollama.chat(model="qwen2.5:1.5b", messages=[{"role": "user", "content": "hi"}])
        print("✓ Ollama base model ready")
    except Exception as e:
        print(f"✗ Ollama error: {e}")
        sys.exit(1)
    
    try:
        chat_mlx("test", "hi")
        print("✓ MLX fine-tuned model ready")
    except Exception as e:
        print(f"✗ MLX server error: {e}")
        sys.exit(1)
    
    # Run base model evals
    print("\n── BASE MODEL (qwen2.5:1.5b) ──")
    base_fn = lambda s, u: chat_ollama("qwen2.5:1.5b", s, u)
    base_results = run_all(base_fn, "BASE")
    
    # Run fine-tuned model evals
    print("\n── FINE-TUNED MODEL (behavioral LoRA) ──")
    ft_fn = lambda s, u: chat_mlx(s, u)
    ft_results = run_all(ft_fn, "FT")
    
    # Print comparison
    print_comparison(base_results, ft_results)
    
    # Save raw results
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "base_model": "qwen2.5:1.5b",
        "finetuned_model": "Qwen2.5-1.5B-Instruct-4bit + behavioral LoRA",
        "training_examples": 45,
        "training_iters": 700,
        "val_loss_start": 3.105,
        "val_loss_end": 1.802,
        "base_results": base_results,
        "finetuned_results": ft_results,
    }
    
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                           "experiments", "runs", "before_after_behavioral.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
