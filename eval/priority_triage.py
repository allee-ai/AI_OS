#!/usr/bin/env python3
"""
Eval: Priority Triage
=======================
Tests whether STATE-visible task priorities produce better
triage ordering than instruction-based "handle the most urgent first."

Three conditions:
  A) INSTRUCTION: "Address the most urgent item first"
  B) EXPLICIT:    "Task X is high priority, Task Y is low priority"
  C) STATE:       tasks.0.priority = critical, tasks.1.priority = low

Measurement: does response ordering match priority ordering?
"""

import json
import os
import sys
import time
import re
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCENARIOS = [
    {
        "id": "mixed_severity",
        "tasks": [
            {"name": "server_crash", "desc": "Production server is down, customers can't access the app", "priority": "critical"},
            {"name": "button_color", "desc": "The 'About' page button color should be blue not green", "priority": "low"},
            {"name": "password_reset", "desc": "Password reset emails are delayed by 30 minutes", "priority": "high"},
            {"name": "docs_typo", "desc": "There's a typo in the API documentation", "priority": "low"},
        ],
        "expected_order": ["server_crash", "password_reset", "button_color", "docs_typo"],
    },
    {
        "id": "deadline_pressure",
        "tasks": [
            {"name": "quarterly_report", "desc": "Q4 financial report due to board tomorrow morning", "priority": "critical"},
            {"name": "team_lunch", "desc": "Organize next week's team lunch outing", "priority": "low"},
            {"name": "client_proposal", "desc": "Client proposal draft needs final review, meeting in 2 days", "priority": "high"},
            {"name": "desk_cleanup", "desc": "Clean up shared workspace desk area", "priority": "low"},
            {"name": "budget_approval", "desc": "Approve department budget for next quarter, CFO waiting", "priority": "high"},
        ],
        "expected_order": ["quarterly_report", "client_proposal", "budget_approval", "team_lunch", "desk_cleanup"],
    },
    {
        "id": "technical_backlog",
        "tasks": [
            {"name": "security_patch", "desc": "Apply critical CVE patch to authentication service", "priority": "critical"},
            {"name": "code_style", "desc": "Update linting rules to match new style guide", "priority": "low"},
            {"name": "memory_leak", "desc": "Investigate memory leak causing OOM crashes every 12 hours", "priority": "high"},
            {"name": "upgrade_react", "desc": "Upgrade React from 17 to 18", "priority": "medium"},
            {"name": "add_favicon", "desc": "Add favicon to the admin dashboard", "priority": "low"},
        ],
        "expected_order": ["security_patch", "memory_leak", "upgrade_react", "code_style", "add_favicon"],
    },
    {
        "id": "customer_support",
        "tasks": [
            {"name": "data_breach", "desc": "Customer reports unauthorized access to their account", "priority": "critical"},
            {"name": "feature_request", "desc": "Customer wants dark mode support", "priority": "low"},
            {"name": "billing_error", "desc": "Customer charged twice for monthly subscription", "priority": "high"},
            {"name": "slow_page", "desc": "Dashboard page loads in 4 seconds instead of 2", "priority": "medium"},
        ],
        "expected_order": ["data_breach", "billing_error", "slow_page", "feature_request"],
    },
]

PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def extract_task_order(response: str, task_names: List[str]) -> List[str]:
    """Extract the order in which tasks appear in the response."""
    response_lower = response.lower()
    positions = []
    for name in task_names:
        # Search for task name or its description keywords
        readable = name.replace("_", " ")
        pos = response_lower.find(readable)
        if pos == -1:
            pos = response_lower.find(name)
        if pos == -1:
            pos = 999999  # not found = last
        positions.append((pos, name))
    positions.sort()
    return [name for _, name in positions]


def kendall_tau_distance(actual: List[str], expected: List[str]) -> float:
    """Normalized Kendall tau distance (0 = perfect, 1 = reversed)."""
    n = len(expected)
    if n <= 1:
        return 0.0
    # Count discordant pairs
    rank_actual = {v: i for i, v in enumerate(actual)}
    rank_expected = {v: i for i, v in enumerate(expected)}
    discordant = 0
    pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            a = expected[i]
            b = expected[j]
            if a in rank_actual and b in rank_actual:
                pairs += 1
                if (rank_actual[a] - rank_actual[b]) * (rank_expected[a] - rank_expected[b]) < 0:
                    discordant += 1
    return round(discordant / pairs, 3) if pairs else 0.0


def condition_instruction(scenario: Dict) -> Dict[str, str]:
    task_list = "\n".join(f"- {t['desc']}" for t in scenario["tasks"])
    return {
        "system": "You are a helpful assistant. When given multiple tasks, address the most urgent and important items first. Present your recommended order clearly.",
        "user": f"I have these tasks to handle. What order should I tackle them?\n\n{task_list}",
        "label": "A_instruction",
    }


def condition_explicit(scenario: Dict) -> Dict[str, str]:
    task_list = "\n".join(f"- {t['desc']} (Priority: {t['priority'].upper()})" for t in scenario["tasks"])
    return {
        "system": "You are a helpful assistant. Tasks have explicit priority levels: CRITICAL > HIGH > MEDIUM > LOW. Always recommend handling tasks in priority order.",
        "user": f"I have these tasks to handle. What order should I tackle them?\n\n{task_list}",
        "label": "B_explicit",
    }


def condition_state(scenario: Dict) -> Dict[str, str]:
    task_state = "\n".join(
        f"tasks.{i}.name = {t['name']}\ntasks.{i}.description = {t['desc']}\ntasks.{i}.priority = {t['priority']}\ntasks.{i}.status = pending"
        for i, t in enumerate(scenario["tasks"])
    )
    task_list = "\n".join(f"- {t['desc']}" for t in scenario["tasks"])
    return {
        "system": f"""== STATE ==
identity.name = Assistant
{task_state}
triage.sort_by = priority
triage.priority_order = critical > high > medium > low
== END STATE ==

You are Assistant. Your STATE is your source of truth. Use the priority metadata to recommend the optimal task ordering.""",
        "user": f"I have these tasks to handle. What order should I tackle them?\n\n{task_list}",
        "label": "C_state",
    }


def run_eval(model: str = "qwen2.5:7b") -> Dict[str, Any]:
    try:
        import ollama
    except ImportError:
        print("ERROR: ollama required"); sys.exit(1)

    results = {"A_instruction": [], "B_explicit": [], "C_state": []}
    conditions = [condition_instruction, condition_explicit, condition_state]
    total = len(SCENARIOS) * 3
    done = 0

    for scenario in SCENARIOS:
        task_names = [t["name"] for t in scenario["tasks"]]
        for cond_fn in conditions:
            cond = cond_fn(scenario)
            done += 1
            print(f"  [{done}/{total}] {cond['label']} | {scenario['id']}", end="", flush=True)

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
            actual_order = extract_task_order(response, task_names)
            expected_order = scenario["expected_order"]
            tau = kendall_tau_distance(actual_order, expected_order)
            top_correct = actual_order[0] == expected_order[0] if actual_order else False
            top_mark = "✓" if top_correct else "✗"

            print(f" → tau={tau:.2f}, top={actual_order[0] if actual_order else '?'} {top_mark} ({duration:.1f}s)")

            results[cond["label"]].append({
                "scenario": scenario["id"],
                "expected_order": expected_order,
                "actual_order": actual_order,
                "kendall_tau": tau,
                "top_correct": top_correct,
                "response": response,
                "duration_s": round(duration, 2),
            })

    return results


def analyze(results: Dict[str, List]) -> Dict[str, Any]:
    summary = {}
    for label, entries in results.items():
        total = len(entries)
        avg_tau = sum(e["kendall_tau"] for e in entries) / total if total else 0
        top_correct = sum(1 for e in entries if e["top_correct"])
        perfect = sum(1 for e in entries if e["kendall_tau"] == 0)

        summary[label] = {
            "avg_kendall_tau": round(avg_tau, 3),
            "top_correct_rate": round(top_correct / total, 3) if total else 0,
            "perfect_ordering_rate": round(perfect / total, 3) if total else 0,
            "top_correct": top_correct,
            "perfect": perfect,
            "total": total,
        }
    return summary


def print_report(summary: Dict[str, Any]):
    print("\n" + "=" * 70)
    print("PRIORITY TRIAGE EVAL")
    print("=" * 70)
    print(f"{'Condition':<20} {'Avg τ dist':<14} {'Top Correct':<14} {'Perfect':<10}")
    print("-" * 70)

    for label in ["A_instruction", "B_explicit", "C_state"]:
        s = summary[label]
        name = {"A_instruction": "Instruction", "B_explicit": "Explicit Priority", "C_state": "STATE Block"}[label]
        print(f"{name:<20} {s['avg_kendall_tau']:<14.3f} {s['top_correct_rate']:<14.1%} {s['perfect_ordering_rate']:<10.1%}")

    print("-" * 70)
    print("Kendall τ distance: 0 = perfect ordering, 1 = fully reversed")
    print("=" * 70)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Priority Triage Eval")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    print(f"Priority Triage Eval")
    print(f"  Model: {args.model}")
    print(f"  Scenarios: {len(SCENARIOS)}")
    print(f"  Total calls: {len(SCENARIOS) * 3}")
    print()

    results = run_eval(model=args.model)
    summary = analyze(results)
    print_report(summary)

    out_path = args.output or os.path.join(
        os.path.dirname(__file__), "..", "experiments", "runs",
        f"priority_triage_eval_{args.model.replace(':', '_')}_{int(time.time())}.json"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"config": vars(args), "summary": summary, "results": results}, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
