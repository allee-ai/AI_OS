#!/usr/bin/env python3
"""
Eval: Tool Selection Efficiency
=================================
Tests whether STATE-visible tool costs produce more efficient
tool selection than instruction-based "use tools wisely."

Three conditions:
  A) INSTRUCTION: "Use the most appropriate tool"
  B) EXPLICIT:    "search is expensive, file_read is cheap"
  C) STATE:       tools.search.cost = high, tools.file_read.cost = low

Measurement: does the model pick the cheapest adequate tool?
"""

import json
import os
import sys
import time
import re
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TOOLS = {
    "file_read": {"cost": "low", "description": "Read a local file"},
    "file_write": {"cost": "low", "description": "Write to a local file"},
    "memory_lookup": {"cost": "low", "description": "Query local memory store"},
    "web_search": {"cost": "high", "description": "Search the internet"},
    "browse_page": {"cost": "high", "description": "Load and read a webpage"},
    "llm_call": {"cost": "high", "description": "Call another LLM for analysis"},
    "database_query": {"cost": "medium", "description": "Query the local database"},
}

QUERIES = [
    # Should prefer cheap tools
    {"prompt": "What's in my config.json file?", "optimal": "file_read", "adequate": ["file_read"]},
    {"prompt": "Save this note: 'meeting at 3pm'", "optimal": "file_write", "adequate": ["file_write", "memory_lookup"]},
    {"prompt": "What did I tell you about my coffee preference?", "optimal": "memory_lookup", "adequate": ["memory_lookup", "database_query"]},
    {"prompt": "Read the README.md in my project.", "optimal": "file_read", "adequate": ["file_read"]},
    {"prompt": "Look up what I said about the architecture last week.", "optimal": "memory_lookup", "adequate": ["memory_lookup", "database_query"]},
    # Legitimately needs expensive tools
    {"prompt": "What's the latest news about Python 3.14?", "optimal": "web_search", "adequate": ["web_search", "browse_page"]},
    {"prompt": "Go to github.com and check my repo stars.", "optimal": "browse_page", "adequate": ["browse_page"]},
    {"prompt": "Search the web for MLX benchmarks.", "optimal": "web_search", "adequate": ["web_search"]},
    # Ambiguous — cheap should be preferred
    {"prompt": "Find information about my project structure.", "optimal": "file_read", "adequate": ["file_read", "database_query"]},
    {"prompt": "What do I usually work on?", "optimal": "memory_lookup", "adequate": ["memory_lookup", "database_query"]},
]

TOOL_NAMES = list(TOOLS.keys())


def extract_tool_choice(response: str) -> str:
    """Extract which tool the model chose from its response."""
    response_lower = response.lower()
    # Look for explicit tool mentions
    found = []
    for tool in TOOL_NAMES:
        patterns = [
            rf'\b{tool}\b',
            rf'`{tool}`',
            rf"'{tool}'",
            rf'"{tool}"',
            tool.replace("_", " "),
        ]
        for p in patterns:
            if re.search(p, response_lower):
                found.append(tool)
                break

    # Also check for action descriptions
    action_map = {
        "file_read": [r"read (the |a |your )?file", r"open (the |a )?file", r"check (the |your )?file"],
        "file_write": [r"write (to |a )?file", r"save (to |a |the )?file", r"create (a )?file"],
        "memory_lookup": [r"check (my |the )?memory", r"look (up |in ).*(memory|store)", r"recall", r"remember"],
        "web_search": [r"search (the )?(web|internet|online)", r"google", r"look (it )?up online"],
        "browse_page": [r"visit (the |a )?(page|website|url)", r"navigate to", r"open (the |a )?(page|url|website)"],
        "llm_call": [r"(call|use|invoke) (another |a |the )?llm", r"ask (another |a )?model"],
        "database_query": [r"query (the |a )?database", r"check (the |a )?database", r"sql"],
    }
    for tool, patterns in action_map.items():
        for p in patterns:
            if re.search(p, response_lower) and tool not in found:
                found.append(tool)

    return found[0] if found else "unknown"


def condition_instruction(prompt: str) -> Dict[str, str]:
    tool_list = ", ".join(TOOL_NAMES)
    return {
        "system": f"You are a helpful assistant with access to these tools: {tool_list}. Use the most appropriate tool for each request. State which tool you would use and why. Respond with the tool name first.",
        "user": prompt,
        "label": "A_instruction",
    }


def condition_explicit(prompt: str) -> Dict[str, str]:
    tool_list = ", ".join(TOOL_NAMES)
    return {
        "system": f"You are a helpful assistant with access to these tools: {tool_list}. Tool costs: file_read=cheap, file_write=cheap, memory_lookup=cheap, database_query=moderate, web_search=expensive, browse_page=expensive, llm_call=expensive. Always prefer the cheapest tool that can accomplish the task. State which tool you would use first.",
        "user": prompt,
        "label": "B_explicit",
    }


def condition_state(prompt: str) -> Dict[str, str]:
    return {
        "system": """== STATE ==
identity.name = Assistant
tools.file_read.available = true
tools.file_read.cost = low
tools.file_read.latency_ms = 5
tools.file_write.available = true
tools.file_write.cost = low
tools.file_write.latency_ms = 5
tools.memory_lookup.available = true
tools.memory_lookup.cost = low
tools.memory_lookup.latency_ms = 10
tools.database_query.available = true
tools.database_query.cost = medium
tools.database_query.latency_ms = 50
tools.web_search.available = true
tools.web_search.cost = high
tools.web_search.latency_ms = 2000
tools.browse_page.available = true
tools.browse_page.cost = high
tools.browse_page.latency_ms = 3000
tools.llm_call.available = true
tools.llm_call.cost = high
tools.llm_call.latency_ms = 5000
resource.api_budget_remaining = 12
== END STATE ==

You are Assistant. Your STATE is your source of truth. Select the tool with the lowest cost that adequately handles the request. State the tool name first, then explain briefly.""",
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
    total = len(QUERIES) * 3
    done = 0

    for q in QUERIES:
        for cond_fn in conditions:
            cond = cond_fn(q["prompt"])
            done += 1
            print(f"  [{done}/{total}] {cond['label']} | [opt={q['optimal']}] {q['prompt'][:40]}...", end="", flush=True)

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
            chosen = extract_tool_choice(response)
            is_optimal = chosen == q["optimal"]
            is_adequate = chosen in q["adequate"]
            cost = TOOLS.get(chosen, {}).get("cost", "unknown")

            mark = "✓" if is_optimal else ("~" if is_adequate else "✗")
            print(f" → {chosen} ({cost}) {mark} ({duration:.1f}s)")

            results[cond["label"]].append({
                "prompt": q["prompt"],
                "optimal": q["optimal"],
                "adequate": q["adequate"],
                "chosen": chosen,
                "chosen_cost": cost,
                "is_optimal": is_optimal,
                "is_adequate": is_adequate,
                "response": response,
                "duration_s": round(duration, 2),
            })

    return results


def analyze(results: Dict[str, List]) -> Dict[str, Any]:
    summary = {}
    for label, entries in results.items():
        optimal = sum(1 for e in entries if e["is_optimal"])
        adequate = sum(1 for e in entries if e["is_adequate"])
        total = len(entries)

        cost_map = {"low": 1, "medium": 2, "high": 3, "unknown": 4}
        avg_cost = sum(cost_map.get(e["chosen_cost"], 4) for e in entries) / total if total else 0

        summary[label] = {
            "optimal_rate": round(optimal / total, 3) if total else 0,
            "adequate_rate": round(adequate / total, 3) if total else 0,
            "avg_cost_score": round(avg_cost, 2),
            "optimal": optimal,
            "adequate": adequate,
            "total": total,
        }
    return summary


def print_report(summary: Dict[str, Any]):
    print("\n" + "=" * 70)
    print("TOOL SELECTION EFFICIENCY EVAL")
    print("=" * 70)
    print(f"{'Condition':<20} {'Optimal':<12} {'Adequate':<12} {'Avg Cost':<10}")
    print("-" * 70)

    for label in ["A_instruction", "B_explicit", "C_state"]:
        s = summary[label]
        name = {"A_instruction": "Instruction", "B_explicit": "Explicit Costs", "C_state": "STATE Block"}[label]
        print(f"{name:<20} {s['optimal_rate']:<12.1%} {s['adequate_rate']:<12.1%} {s['avg_cost_score']:<10.2f}")

    print("-" * 70)
    print("Cost score: 1=low, 2=medium, 3=high (lower = more efficient)")
    print("=" * 70)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Tool Selection Efficiency Eval")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    print(f"Tool Selection Efficiency Eval")
    print(f"  Model: {args.model}")
    print(f"  Queries: {len(QUERIES)}")
    print(f"  Total calls: {len(QUERIES) * 3}")
    print()

    results = run_eval(model=args.model)
    summary = analyze(results)
    print_report(summary)

    out_path = args.output or os.path.join(
        os.path.dirname(__file__), "..", "experiments", "runs",
        f"tool_selection_eval_{args.model.replace(':', '_')}_{int(time.time())}.json"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"config": vars(args), "summary": summary, "results": results}, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
