#!/usr/bin/env python3
"""
Eval: Tone Matching
=====================
Tests whether STATE-visible communication style info produces
better tone adaptation than instruction-based "match the user's tone."

Three conditions:
  A) INSTRUCTION: "Match the user's communication style"
  B) EXPLICIT:    "The user prefers formal/casual/technical language"
  C) STATE:       user.communication_style = formal | casual | technical

Measurement: vocabulary overlap with target register.
"""

import json
import os
import sys
import time
import re
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Register word sets — representative vocabulary
REGISTERS = {
    "formal": {
        "words": {"therefore", "regarding", "furthermore", "consequently", "hereby",
                  "accordingly", "nonetheless", "substantial", "facilitate", "endeavor",
                  "acknowledge", "inquire", "subsequent", "pertaining", "comprehensive",
                  "demonstrate", "pursuant", "constitute", "provision", "stipulate"},
        "patterns": [r"I would", r"please note", r"with respect to", r"in regard",
                     r"I am pleased", r"kindly", r"at your earliest"],
    },
    "casual": {
        "words": {"hey", "yeah", "cool", "awesome", "gonna", "wanna", "kinda",
                  "stuff", "things", "basically", "totally", "honestly", "pretty",
                  "super", "ok", "nah", "yep", "lol", "btw", "imo"},
        "patterns": [r"no worries", r"you know", r"kind of", r"sort of",
                     r"here's the deal", r"let me know", r"hope that helps"],
    },
    "technical": {
        "words": {"implementation", "architecture", "abstraction", "paradigm",
                  "latency", "throughput", "orthogonal", "deterministic", "idempotent",
                  "polymorphism", "concurrency", "serialization", "asynchronous",
                  "refactor", "runtime", "overhead", "pipeline", "modular"},
        "patterns": [r"O\(n", r"trade-?off", r"under the hood", r"boils down to",
                     r"in terms of", r"use case"],
    },
}

PROMPTS = [
    # Each prompt asked in 3 tones
    {
        "topic": "explain_sorting",
        "formal": "Could you please provide a thorough explanation of how sorting algorithms work, particularly with regard to their comparative efficiencies?",
        "casual": "hey can you explain how sorting works? like what's the deal with different sorting algorithms being faster?",
        "technical": "Can you break down the computational complexity of comparison-based sorting algorithms and discuss the lower bound proof?",
    },
    {
        "topic": "debug_help",
        "formal": "I would appreciate your assistance in diagnosing an issue wherein my application produces incorrect output after processing a substantial dataset.",
        "casual": "yo my app is giving me wrong answers when I throw a bunch of data at it, any idea what's going on?",
        "technical": "I'm seeing data corruption in my output after processing batches >10K rows — could be a race condition in the concurrent pipeline or an off-by-one in the buffer allocation.",
    },
    {
        "topic": "learn_python",
        "formal": "I am interested in acquiring proficiency in Python programming. Would you kindly suggest a structured approach to learning the language?",
        "casual": "I wanna learn Python — where should I start? any cool resources?",
        "technical": "What's the optimal path to Python proficiency if I already have experience with compiled languages and want to focus on the runtime model, metaprogramming, and async patterns?",
    },
    {
        "topic": "api_design",
        "formal": "I should like to understand the best practices pertaining to the design of RESTful APIs, particularly regarding versioning and error handling conventions.",
        "casual": "how should I set up my API? like what's the best way to handle errors and versioning?",
        "technical": "What are the trade-offs between URL-based vs header-based API versioning, and how should idempotent error responses be structured for retry-safe clients?",
    },
]


def score_register(response: str, target_register: str) -> Dict[str, float]:
    """Score how well a response matches the target register."""
    response_lower = response.lower()
    words = set(re.findall(r'\b\w+\b', response_lower))

    scores = {}
    for reg_name, reg_data in REGISTERS.items():
        word_hits = len(words & reg_data["words"])
        pattern_hits = sum(1 for p in reg_data["patterns"] if re.search(p, response_lower))
        scores[reg_name] = word_hits + pattern_hits

    total = sum(scores.values()) or 1
    for reg_name in scores:
        scores[reg_name] = round(scores[reg_name] / total, 3)

    return {
        "raw_scores": {k: v for k, v in scores.items()},
        "target_share": scores.get(target_register, 0),
        "dominant": max(scores, key=scores.get),
        "match": max(scores, key=scores.get) == target_register,
    }


def condition_instruction(prompt: str, register: str) -> Dict[str, str]:
    return {
        "system": "You are a helpful assistant. Match the user's communication style in your response. Be natural and responsive.",
        "user": prompt,
        "label": "A_instruction",
    }


def condition_explicit(prompt: str, register: str) -> Dict[str, str]:
    desc = {
        "formal": "The user prefers formal, professional language. Use complete sentences, sophisticated vocabulary, and a respectful tone.",
        "casual": "The user prefers casual, friendly language. Be conversational, use contractions, and keep it relaxed.",
        "technical": "The user prefers precise technical language. Use correct terminology, discuss implementation details, and be specific.",
    }
    return {
        "system": f"You are a helpful assistant. {desc[register]}",
        "user": prompt,
        "label": "B_explicit",
    }


def condition_state(prompt: str, register: str) -> Dict[str, str]:
    style_fields = {
        "formal": """user.communication_style = formal
user.vocabulary_level = advanced
user.expects_professional_tone = true""",
        "casual": """user.communication_style = casual
user.vocabulary_level = conversational
user.prefers_contractions = true""",
        "technical": """user.communication_style = technical
user.vocabulary_level = domain_expert
user.expects_precision = true""",
    }
    return {
        "system": f"""== STATE ==
identity.name = Assistant
{style_fields[register]}
session.turn_count = 3
== END STATE ==

You are Assistant. Your STATE is your source of truth. Respond naturally according to the user's communication style as indicated in STATE.""",
        "user": prompt,
        "label": "C_state",
    }


def run_eval(model: str = "qwen2.5:7b") -> Dict[str, Any]:
    try:
        import ollama
    except ImportError:
        print("ERROR: ollama required"); sys.exit(1)

    results = {"A_instruction": [], "B_explicit": [], "C_state": []}
    conditions = [condition_instruction, condition_explicit, condition_state]
    registers = ["formal", "casual", "technical"]
    total = len(PROMPTS) * len(registers) * 3
    done = 0

    for pg in PROMPTS:
        for reg in registers:
            prompt = pg[reg]
            for cond_fn in conditions:
                cond = cond_fn(prompt, reg)
                done += 1
                print(f"  [{done}/{total}] {cond['label']} | {reg} | {pg['topic'][:20]}...", end="", flush=True)

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
                score = score_register(response, reg)
                match_mark = "✓" if score["match"] else "✗"
                print(f" → {score['dominant']} (share={score['target_share']:.0%}) {match_mark} ({duration:.1f}s)")

                results[cond["label"]].append({
                    "topic": pg["topic"],
                    "target_register": reg,
                    "prompt": prompt,
                    "score": score,
                    "response": response,
                    "duration_s": round(duration, 2),
                })

    return results


def analyze(results: Dict[str, List]) -> Dict[str, Any]:
    summary = {}
    for label, entries in results.items():
        correct = sum(1 for e in entries if e["score"]["match"])
        total = len(entries)
        avg_share = sum(e["score"]["target_share"] for e in entries) / total if total else 0

        # Per-register breakdown
        per_reg = {}
        for reg in ["formal", "casual", "technical"]:
            reg_entries = [e for e in entries if e["target_register"] == reg]
            if reg_entries:
                per_reg[reg] = {
                    "match_rate": round(sum(1 for e in reg_entries if e["score"]["match"]) / len(reg_entries), 3),
                    "avg_share": round(sum(e["score"]["target_share"] for e in reg_entries) / len(reg_entries), 3),
                }

        summary[label] = {
            "match_rate": round(correct / total, 3) if total else 0,
            "avg_target_share": round(avg_share, 3),
            "per_register": per_reg,
            "correct": correct,
            "total": total,
        }
    return summary


def print_report(summary: Dict[str, Any]):
    print("\n" + "=" * 70)
    print("TONE MATCHING EVAL")
    print("=" * 70)
    print(f"{'Condition':<20} {'Match Rate':<14} {'Avg Share':<12}")
    print("-" * 70)

    for label in ["A_instruction", "B_explicit", "C_state"]:
        s = summary[label]
        name = {"A_instruction": "Instruction", "B_explicit": "Explicit Style", "C_state": "STATE Block"}[label]
        print(f"{name:<20} {s['match_rate']:<14.1%} {s['avg_target_share']:<12.1%}")

    print()
    for label in ["A_instruction", "B_explicit", "C_state"]:
        s = summary[label]
        name = {"A_instruction": "Instruction", "B_explicit": "Explicit Style", "C_state": "STATE Block"}[label]
        for reg, rd in s["per_register"].items():
            print(f"  {name} / {reg}: match={rd['match_rate']:.0%}, share={rd['avg_share']:.0%}")

    print("=" * 70)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Tone Matching Eval")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    print(f"Tone Matching Eval")
    print(f"  Model: {args.model}")
    print(f"  Prompts: {len(PROMPTS) * 3} (4 topics × 3 registers)")
    print(f"  Total calls: {len(PROMPTS) * 3 * 3}")
    print()

    results = run_eval(model=args.model)
    summary = analyze(results)
    print_report(summary)

    out_path = args.output or os.path.join(
        os.path.dirname(__file__), "..", "experiments", "runs",
        f"tone_matching_eval_{args.model.replace(':', '_')}_{int(time.time())}.json"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"config": vars(args), "summary": summary, "results": results}, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
