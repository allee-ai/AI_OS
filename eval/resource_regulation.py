#!/usr/bin/env python3
"""
Eval: Resource Self-Regulation
==============================
Tests whether STATE-aware resource visibility produces better
self-regulation than instruction-based constraints.

Three conditions (same prompt, same model, different framing):
  A) INSTRUCTION: "Don't write too much, be concise"
  B) BUDGET:      "You have N tokens available for your response"
  C) STATE:       Full STATE block with resource metrics

Measurement: actual token count of response.
Hypothesis: STATE condition produces tightest self-regulation.
"""

import json
import os
import sys
import time
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Test prompts (all require extended answers to tempt verbosity) ──────────

PROMPTS = [
    "Explain how memory works in a computer.",
    "What are the benefits of exercise?",
    "Describe the water cycle.",
    "How does the internet work?",
    "What is machine learning?",
    "Explain how a car engine works.",
    "What causes the seasons to change?",
    "How do vaccines work?",
    "Describe the process of photosynthesis.",
    "What is the stock market and how does it work?",
]

# ── Three conditions ───────────────────────────────────────────────────────

def condition_instruction(prompt: str) -> Dict[str, str]:
    """Condition A: vague instruction to be brief."""
    return {
        "system": "You are a helpful assistant. Don't over-use tokens. Be concise and efficient with your response length.",
        "user": prompt,
        "label": "A_instruction",
    }


def condition_budget(prompt: str, budget: int = 150) -> Dict[str, str]:
    """Condition B: explicit token budget."""
    return {
        "system": f"You are a helpful assistant. You have {budget} tokens available for your response. Do not exceed this budget.",
        "user": prompt,
        "label": "B_budget",
    }


def condition_state_loose(prompt: str, used: int = 340, total: int = 1200, budget: int = 150) -> Dict[str, str]:
    """Condition C: STATE block with plenty of remaining tokens."""
    remaining = total - used
    return {
        "system": f"""== STATE ==
identity.name = Assistant
identity.role = helpful_assistant
resource.tokens_used = {used}
resource.tokens_total = {total}
resource.tokens_remaining = {remaining}
resource.response_budget = {budget}
resource.utilization_pct = {round(used/total*100, 1)}
session.turn_count = 4
session.avg_response_tokens = 89
== END STATE ==

You are Assistant. Your STATE is your source of truth. Respond within your resource.response_budget. Your current utilization is {round(used/total*100, 1)}% — manage your remaining tokens wisely.""",
        "user": prompt,
        "label": "C_state_loose",
    }


def condition_state_tight(prompt: str, budget: int = 150) -> Dict[str, str]:
    """Condition D: STATE block with tight remaining tokens."""
    used = 1020
    total = 1200
    remaining = total - used
    return {
        "system": f"""== STATE ==
identity.name = Assistant
identity.role = helpful_assistant
resource.tokens_used = {used}
resource.tokens_total = {total}
resource.tokens_remaining = {remaining}
resource.response_budget = {budget}
resource.utilization_pct = {round(used/total*100, 1)}
session.turn_count = 12
session.avg_response_tokens = 89
== END STATE ==

You are Assistant. Your STATE is your source of truth. Respond within your resource.response_budget. Your current utilization is {round(used/total*100, 1)}% — manage your remaining tokens wisely.""",
        "user": prompt,
        "label": "D_state_tight",
    }


def count_tokens_approx(text: str) -> int:
    """Approximate token count (words * 1.3 is standard approximation)."""
    return int(len(text.split()) * 1.3)


def run_eval(model: str = "qwen2.5:7b", budget: int = 150, runs_per_prompt: int = 1) -> Dict[str, Any]:
    """Run all three conditions across all prompts."""
    try:
        import ollama
    except ImportError:
        print("ERROR: ollama package required. pip install ollama")
        sys.exit(1)

    results = {"A_instruction": [], "B_budget": [], "C_state_loose": [], "D_state_tight": []}
    conditions = [condition_instruction, condition_budget, condition_state_loose, condition_state_tight]

    total = len(PROMPTS) * len(conditions) * runs_per_prompt
    done = 0

    for prompt in PROMPTS:
        for cond_fn in conditions:
            for run_i in range(runs_per_prompt):
                if cond_fn == condition_budget:
                    cond = cond_fn(prompt, budget)
                elif cond_fn == condition_state_loose:
                    cond = cond_fn(prompt, budget=budget)
                elif cond_fn == condition_state_tight:
                    cond = cond_fn(prompt, budget=budget)
                else:
                    cond = cond_fn(prompt)

                done += 1
                print(f"  [{done}/{total}] {cond['label']} | {prompt[:40]}...", end="", flush=True)

                start = time.time()
                try:
                    r = ollama.chat(
                        model=model,
                        messages=[
                            {"role": "system", "content": cond["system"]},
                            {"role": "user", "content": cond["user"]},
                        ],
                    )
                    response = r["message"]["content"]
                    duration = time.time() - start
                except Exception as e:
                    response = f"ERROR: {e}"
                    duration = time.time() - start

                tok_count = count_tokens_approx(response)
                print(f" → {tok_count} tokens ({duration:.1f}s)")

                results[cond["label"]].append({
                    "prompt": prompt,
                    "response": response,
                    "token_count": tok_count,
                    "word_count": len(response.split()),
                    "char_count": len(response),
                    "duration_s": round(duration, 2),
                    "run": run_i,
                })

    return results


def analyze(results: Dict[str, List]) -> Dict[str, Any]:
    """Compute summary statistics."""
    summary = {}
    for label, entries in results.items():
        tokens = [e["token_count"] for e in entries]
        words = [e["word_count"] for e in entries]
        avg_tok = sum(tokens) / len(tokens) if tokens else 0
        avg_words = sum(words) / len(words) if words else 0
        summary[label] = {
            "avg_tokens": round(avg_tok, 1),
            "avg_words": round(avg_words, 1),
            "min_tokens": min(tokens) if tokens else 0,
            "max_tokens": max(tokens) if tokens else 0,
            "median_tokens": sorted(tokens)[len(tokens)//2] if tokens else 0,
            "std_tokens": round((sum((t - avg_tok)**2 for t in tokens) / len(tokens))**0.5, 1) if tokens else 0,
            "n": len(entries),
        }
    return summary


def print_report(summary: Dict[str, Any], budget: int):
    """Print formatted comparison."""
    print("\n" + "=" * 70)
    print("RESOURCE SELF-REGULATION EVAL")
    print(f"Target budget: {budget} tokens")
    print("=" * 70)
    print(f"{'Condition':<20} {'Avg Tokens':<12} {'Median':<10} {'Min':<8} {'Max':<8} {'StdDev':<8}")
    print("-" * 70)

    for label in ["A_instruction", "B_budget", "C_state_loose", "D_state_tight"]:
        s = summary[label]
        name = {
            "A_instruction": "Instruction",
            "B_budget": "Explicit Budget",
            "C_state_loose": "STATE (loose)",
            "D_state_tight": "STATE (tight)",
        }[label]
        over = "✓" if s["avg_tokens"] <= budget * 1.2 else "✗"
        print(f"{name:<20} {s['avg_tokens']:<12} {s['median_tokens']:<10} {s['min_tokens']:<8} {s['max_tokens']:<8} {s['std_tokens']:<8} {over}")

    print("-" * 70)

    a = summary["A_instruction"]["avg_tokens"]
    b = summary["B_budget"]["avg_tokens"]
    c = summary["C_state_loose"]["avg_tokens"]
    d = summary["D_state_tight"]["avg_tokens"]

    if a > 0:
        print(f"\nBudget vs Instruction:      {((b - a) / a * 100):+.1f}% tokens")
        print(f"STATE loose vs Instruction: {((c - a) / a * 100):+.1f}% tokens")
        print(f"STATE tight vs Instruction: {((d - a) / a * 100):+.1f}% tokens")
    if c > 0 and d > 0:
        print(f"STATE tight vs STATE loose: {((d - c) / c * 100):+.1f}% tokens")
    
    # Coefficient of variation (consistency measure)
    print(f"\nConsistency (CoV = StdDev/Mean, lower = more consistent):")
    for label in ["A_instruction", "B_budget", "C_state_loose", "D_state_tight"]:
        s = summary[label]
        name = {
            "A_instruction": "Instruction",
            "B_budget": "Explicit Budget",
            "C_state_loose": "STATE (loose)",
            "D_state_tight": "STATE (tight)",
        }[label]
        cov = s["std_tokens"] / s["avg_tokens"] if s["avg_tokens"] > 0 else 0
        print(f"  {name:<20} CoV = {cov:.3f}")

    print(f"\nClosest to target ({budget}):")
    deltas = {k: abs(v["avg_tokens"] - budget) for k, v in summary.items()}
    winner = min(deltas, key=deltas.get)
    name = {
        "A_instruction": "Instruction",
        "B_budget": "Explicit Budget",
        "C_state_loose": "STATE (loose)",
        "D_state_tight": "STATE (tight)",
    }[winner]
    print(f"  → {name} (avg {summary[winner]['avg_tokens']} tokens, Δ={deltas[winner]:.0f} from target)")
    print("=" * 70)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Resource Self-Regulation Eval")
    parser.add_argument("--model", default="qwen2.5:7b", help="Ollama model name")
    parser.add_argument("--budget", type=int, default=150, help="Target token budget")
    parser.add_argument("--runs", type=int, default=1, help="Runs per prompt per condition")
    parser.add_argument("--output", default=None, help="Save results JSON to file")
    args = parser.parse_args()

    print(f"Resource Self-Regulation Eval")
    print(f"  Model: {args.model}")
    print(f"  Budget: {args.budget} tokens")
    print(f"  Prompts: {len(PROMPTS)}")
    print(f"  Conditions: 4 (instruction / budget / STATE-loose / STATE-tight)")
    print(f"  Runs per prompt: {args.runs}")
    print(f"  Total calls: {len(PROMPTS) * 4 * args.runs}")
    print()

    results = run_eval(model=args.model, budget=args.budget, runs_per_prompt=args.runs)
    summary = analyze(results)
    print_report(summary, args.budget)

    # Save
    out_path = args.output or os.path.join(
        os.path.dirname(__file__), "..", "experiments", "runs",
        f"resource_eval_{args.model.replace(':', '_')}_{int(time.time())}.json"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"config": vars(args), "summary": summary, "results": results}, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
