#!/usr/bin/env python3
"""
Eval: Repetition Avoidance
===========================
Tests whether STATE-visible conversation history produces less
repetition than instruction-based "don't repeat yourself."

Three conditions (multi-turn: same topic asked 3 ways):
  A) INSTRUCTION: "Don't repeat information you've already shared"
  B) EXPLICIT:    Prior answers listed in system prompt
  C) STATE:       session.topics_covered = [...] in STATE block

Measurement: semantic overlap between responses (lower = less repetition).
"""

import json
import os
import sys
import time
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Each topic has 3 prompts that ask about the same thing differently
TOPIC_GROUPS = [
    {
        "topic": "python_lists",
        "prompts": [
            "What is a Python list?",
            "How do lists work in Python?",
            "Explain Python lists to me.",
        ],
    },
    {
        "topic": "http",
        "prompts": [
            "What is HTTP?",
            "Explain the HTTP protocol.",
            "How does HTTP work?",
        ],
    },
    {
        "topic": "git",
        "prompts": [
            "What is Git?",
            "How does Git version control work?",
            "Explain Git to me.",
        ],
    },
    {
        "topic": "recursion",
        "prompts": [
            "What is recursion in programming?",
            "Explain how recursion works.",
            "How does a recursive function work?",
        ],
    },
]


def word_overlap(text1: str, text2: str) -> float:
    """Calculate Jaccard word overlap between two texts."""
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union)


def ngram_overlap(text1: str, text2: str, n: int = 3) -> float:
    """Calculate n-gram overlap between two texts."""
    words1 = text1.lower().split()
    words2 = text2.lower().split()
    if len(words1) < n or len(words2) < n:
        return 0.0
    ngrams1 = set(tuple(words1[i:i+n]) for i in range(len(words1) - n + 1))
    ngrams2 = set(tuple(words2[i:i+n]) for i in range(len(words2) - n + 1))
    if not ngrams1 or not ngrams2:
        return 0.0
    intersection = ngrams1 & ngrams2
    union = ngrams1 | ngrams2
    return len(intersection) / len(union)


def run_topic_group(model: str, topic: str, prompts: List[str], ollama_mod) -> Dict[str, List]:
    """Run all 3 prompts under each condition for one topic group."""
    results = {"A_instruction": [], "B_explicit": [], "C_state": []}

    for cond_label in ["A", "B", "C"]:
        prior_responses = []
        for i, prompt in enumerate(prompts):
            if cond_label == "A":
                system = "You are a helpful assistant. Don't repeat information you've already shared in this conversation. If you've already explained something, refer to it briefly and add new information."
            elif cond_label == "B":
                if prior_responses:
                    prior_text = "\n---\n".join(f"[Previous answer {j+1}]: {r}" for j, r in enumerate(prior_responses))
                    system = f"You are a helpful assistant. You have already given these answers:\n{prior_text}\n\nDo NOT repeat information from your previous answers. Only add new, different information."
                else:
                    system = "You are a helpful assistant. Provide a clear, focused answer."
            else:  # C_state
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

            label = {"A": "A_instruction", "B": "B_explicit", "C": "C_state"}[cond_label]

            start = time.time()
            try:
                r = ollama_mod.chat(model=model, messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ])
                response = r["message"]["content"]
            except Exception as e:
                response = f"ERROR: {e}"

            duration = time.time() - start
            prior_responses.append(response)

            results[label].append({
                "prompt": prompt,
                "topic": topic,
                "turn": i + 1,
                "response": response,
                "word_count": len(response.split()),
                "duration_s": round(duration, 2),
            })

    return results


def run_eval(model: str = "qwen2.5:7b") -> Dict[str, Any]:
    try:
        import ollama
    except ImportError:
        print("ERROR: ollama required"); sys.exit(1)

    all_results = {"A_instruction": [], "B_explicit": [], "C_state": []}
    total_groups = len(TOPIC_GROUPS)

    for gi, group in enumerate(TOPIC_GROUPS):
        print(f"\n  Topic {gi+1}/{total_groups}: {group['topic']}")
        group_results = run_topic_group(model, group["topic"], group["prompts"], ollama)

        for label in all_results:
            entries = group_results[label]
            for e in entries:
                print(f"    {label} turn {e['turn']}: {e['word_count']} words ({e['duration_s']:.1f}s)")
            all_results[label].extend(entries)

    return all_results


def analyze(results: Dict[str, List]) -> Dict[str, Any]:
    summary = {}
    for label, entries in results.items():
        # Group by topic
        topics = {}
        for e in entries:
            topics.setdefault(e["topic"], []).append(e)

        word_overlaps = []
        ngram_overlaps = []
        for topic, topic_entries in topics.items():
            responses = [e["response"] for e in sorted(topic_entries, key=lambda x: x["turn"])]
            for i in range(len(responses)):
                for j in range(i + 1, len(responses)):
                    word_overlaps.append(word_overlap(responses[i], responses[j]))
                    ngram_overlaps.append(ngram_overlap(responses[i], responses[j]))

        avg_word = sum(word_overlaps) / len(word_overlaps) if word_overlaps else 0
        avg_ngram = sum(ngram_overlaps) / len(ngram_overlaps) if ngram_overlaps else 0

        summary[label] = {
            "avg_word_overlap": round(avg_word, 3),
            "avg_ngram_overlap": round(avg_ngram, 3),
            "total_entries": len(entries),
        }
    return summary


def print_report(summary: Dict[str, Any]):
    print("\n" + "=" * 70)
    print("REPETITION AVOIDANCE EVAL")
    print("=" * 70)
    print(f"{'Condition':<20} {'Word Overlap':<15} {'3-gram Overlap':<15}")
    print("-" * 70)

    for label in ["A_instruction", "B_explicit", "C_state"]:
        s = summary[label]
        name = {"A_instruction": "Instruction", "B_explicit": "Explicit History", "C_state": "STATE Block"}[label]
        print(f"{name:<20} {s['avg_word_overlap']:<15.3f} {s['avg_ngram_overlap']:<15.3f}")

    print("-" * 70)
    print("Lower overlap = less repetition = better")
    print("=" * 70)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Repetition Avoidance Eval")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    print(f"Repetition Avoidance Eval")
    print(f"  Model: {args.model}")
    print(f"  Topic groups: {len(TOPIC_GROUPS)} (3 prompts each)")
    print(f"  Conditions: 3")
    print(f"  Total calls: {len(TOPIC_GROUPS) * 3 * 3}")

    results = run_eval(model=args.model)
    summary = analyze(results)
    print_report(summary)

    out_path = args.output or os.path.join(
        os.path.dirname(__file__), "..", "experiments", "runs",
        f"repetition_eval_{args.model.replace(':', '_')}_{int(time.time())}.json"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"config": vars(args), "summary": summary, "results": results}, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
