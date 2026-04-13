#!/usr/bin/env python3
"""
Eval: Context Self-Management
================================
Tests whether STATE-visible context window utilization produces
better compression/conciseness behavior than instruction-based limits.

Three conditions:
  A) INSTRUCTION: "Be concise, we're running low on space"
  B) EXPLICIT:    "You have 200 tokens remaining"
  C) STATE:       context.tokens_used = 3800/4096, context.remaining = 296

Measurement: response length calibration (does the model compress
when capacity is low, expand when capacity is high?)
"""

import json
import math
import os
import sys
import time
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROMPTS = [
    "Explain what a neural network is.",
    "How does garbage collection work in Python?",
    "What are the main differences between SQL and NoSQL databases?",
    "Describe how HTTPS keeps data secure.",
    "What is the difference between a process and a thread?",
    "Explain how hash tables work.",
    "What is dependency injection?",
    "How does DNS resolution work?",
    "What are design patterns and why are they useful?",
    "Explain the CAP theorem.",
]

# Two capacity levels to test
CAPACITY_LEVELS = {
    "low": {
        "tokens_used": 3800,
        "tokens_max": 4096,
        "remaining": 296,
        "pct_used": 0.93,
    },
    "high": {
        "tokens_used": 800,
        "tokens_max": 4096,
        "remaining": 3296,
        "pct_used": 0.20,
    },
}


def approx_tokens(text: str) -> int:
    return max(1, int(len(text.split()) * 1.3))


def condition_instruction(prompt: str, capacity: str) -> Dict[str, str]:
    cap = CAPACITY_LEVELS[capacity]
    if capacity == "low":
        sys_msg = "You are a helpful assistant. Be very concise — we're running low on space. Keep your answer brief and to the point."
    else:
        sys_msg = "You are a helpful assistant. You have plenty of space. Feel free to give a thorough, detailed explanation."
    return {
        "system": sys_msg,
        "user": prompt,
        "label": f"A_instruction_{capacity}",
    }


def condition_explicit(prompt: str, capacity: str) -> Dict[str, str]:
    cap = CAPACITY_LEVELS[capacity]
    return {
        "system": f"You are a helpful assistant. You have approximately {cap['remaining']} tokens remaining in this conversation ({cap['pct_used']:.0%} of context used). Calibrate your response length to fit within the available space.",
        "user": prompt,
        "label": f"B_explicit_{capacity}",
    }


def condition_state(prompt: str, capacity: str) -> Dict[str, str]:
    cap = CAPACITY_LEVELS[capacity]
    return {
        "system": f"""== STATE ==
identity.name = Assistant
context.tokens_used = {cap['tokens_used']}
context.tokens_max = {cap['tokens_max']}
context.tokens_remaining = {cap['remaining']}
context.utilization_pct = {cap['pct_used']:.2f}
context.pressure = {"high" if capacity == "low" else "low"}
session.turn_count = {"12" if capacity == "low" else "2"}
== END STATE ==

You are Assistant. Your STATE is your source of truth. Calibrate your response length to the available context capacity. When capacity is low, compress. When capacity is high, elaborate.""",
        "user": prompt,
        "label": f"C_state_{capacity}",
    }


def run_eval(model: str = "qwen2.5:7b") -> Dict[str, Any]:
    try:
        import ollama
    except ImportError:
        print("ERROR: ollama required"); sys.exit(1)

    labels = []
    for cap in ["low", "high"]:
        for prefix in ["A_instruction", "B_explicit", "C_state"]:
            labels.append(f"{prefix}_{cap}")

    results = {l: [] for l in labels}
    conditions = [condition_instruction, condition_explicit, condition_state]
    capacities = ["low", "high"]
    total = len(PROMPTS) * len(capacities) * len(conditions)
    done = 0

    for prompt in PROMPTS:
        for cap in capacities:
            for cond_fn in conditions:
                cond = cond_fn(prompt, cap)
                done += 1
                print(f"  [{done}/{total}] {cond['label']} | {prompt[:40]}...", end="", flush=True)

                start = time.time()
                try:
                    r = ollama.chat(model=model, messages=[
                        {"role": "system", "content": cond["system"]},
                        {"role": "user", "content": cond["user"]},
                    ])
                    response = r["message"]["content"]
                except Exception as e:
                    response = f"ERROR: {e}"

                duration = time.time() - start
                tokens = approx_tokens(response)
                words = len(response.split())

                print(f" → {tokens} tokens, {words} words ({duration:.1f}s)")

                results[cond["label"]].append({
                    "prompt": prompt,
                    "capacity": cap,
                    "tokens": tokens,
                    "words": words,
                    "response": response,
                    "duration_s": round(duration, 2),
                })

    return results


def analyze(results: Dict[str, List]) -> Dict[str, Any]:
    summary = {}

    for label, entries in results.items():
        total = len(entries)
        tokens = [e["tokens"] for e in entries]
        avg = sum(tokens) / total if total else 0
        variance = sum((t - avg) ** 2 for t in tokens) / total if total else 0
        std = math.sqrt(variance)

        summary[label] = {
            "avg_tokens": round(avg, 1),
            "std_tokens": round(std, 1),
            "min_tokens": min(tokens) if tokens else 0,
            "max_tokens": max(tokens) if tokens else 0,
            "total": total,
        }

    # Compute compression ratios (low/high capacity)
    ratios = {}
    for prefix in ["A_instruction", "B_explicit", "C_state"]:
        low_avg = summary.get(f"{prefix}_low", {}).get("avg_tokens", 1)
        high_avg = summary.get(f"{prefix}_high", {}).get("avg_tokens", 1)
        ratio = round(low_avg / high_avg, 3) if high_avg else 0
        ratios[prefix] = ratio

    summary["compression_ratios"] = ratios
    return summary


def print_report(summary: Dict[str, Any]):
    print("\n" + "=" * 78)
    print("CONTEXT SELF-MANAGEMENT EVAL")
    print("=" * 78)
    print(f"{'Condition':<30} {'Avg Tokens':<14} {'Std':<10} {'Range':<16}")
    print("-" * 78)

    order = [
        ("A_instruction_high", "Instruction (high cap)"),
        ("A_instruction_low", "Instruction (low cap)"),
        ("B_explicit_high", "Explicit (high cap)"),
        ("B_explicit_low", "Explicit (low cap)"),
        ("C_state_high", "STATE (high cap)"),
        ("C_state_low", "STATE (low cap)"),
    ]

    for label, name in order:
        s = summary.get(label, {})
        avg = s.get("avg_tokens", 0)
        std = s.get("std_tokens", 0)
        mn = s.get("min_tokens", 0)
        mx = s.get("max_tokens", 0)
        print(f"{name:<30} {avg:<14.1f} {std:<10.1f} [{mn}-{mx}]")

    print()
    print("Compression ratios (low_cap / high_cap — lower = more compression):")
    ratios = summary.get("compression_ratios", {})
    for prefix in ["A_instruction", "B_explicit", "C_state"]:
        name = {"A_instruction": "Instruction", "B_explicit": "Explicit", "C_state": "STATE"}[prefix]
        r = ratios.get(prefix, 0)
        print(f"  {name:.<24} {r:.3f}")

    print()
    print("Ideal: high compression ratio contrast between low & high capacity")
    print("Best condition = lowest ratio (most responsive to capacity pressure)")
    print("=" * 78)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Context Self-Management Eval")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    print(f"Context Self-Management Eval")
    print(f"  Model: {args.model}")
    print(f"  Prompts: {len(PROMPTS)}")
    print(f"  Total calls: {len(PROMPTS) * 2 * 3}")
    print()

    results = run_eval(model=args.model)
    summary = analyze(results)
    print_report(summary)

    out_path = args.output or os.path.join(
        os.path.dirname(__file__), "..", "experiments", "runs",
        f"context_mgmt_eval_{args.model.replace(':', '_')}_{int(time.time())}.json"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"config": vars(args), "summary": summary, "results": results}, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
