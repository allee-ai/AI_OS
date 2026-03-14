"""
Eval Module — Human Judge
=========================
Interactive human evaluation: user votes on responses turn-by-turn.

Usage (CLI):
    eval judge <run_id>     — judge a saved eval run
    eval judge --live       — judge live model responses to prompts

Future: integrate as a UI component with side-by-side comparison.
"""

import json
from typing import Dict, Any, List, Optional

from .schema import get_run, update_run, save_run


def judge_run_interactive(run_id: str) -> Dict[str, Any]:
    """
    Load a saved eval run and let the human score each case.
    Returns updated run with human_scores in details.
    """
    run = get_run(run_id)
    if not run:
        return {"error": f"Run {run_id} not found"}

    details = run.get("details", [])
    if not details:
        # Try parsing from details_json
        raw = run.get("details_json", "[]")
        if isinstance(raw, str):
            details = json.loads(raw)

    if not details:
        return {"error": "No details to judge"}

    print(f"\n  Judging run {run_id}: {run.get('eval_name', '?')} ({len(details)} cases)")
    print(f"  Model: {run.get('model', '?')}\n")
    print("  For each case, rate: [1] Good  [2] Acceptable  [3] Bad  [s] Skip\n")

    scores = []
    for i, case in enumerate(details):
        prompt = case.get("prompt", "(no prompt)")
        response = case.get("response_preview", "(no response)")
        auto_pass = case.get("passed", None)

        print(f"  ── Case {i+1}/{len(details)} ──")
        print(f"  Prompt:   {prompt}")
        print(f"  Response: {response}")
        if auto_pass is not None:
            print(f"  Auto:     {'✓ pass' if auto_pass else '✗ fail'}")

        while True:
            vote = input("  Score [1/2/3/s]: ").strip().lower()
            if vote in ("1", "2", "3", "s"):
                break
            print("  Invalid. Enter 1, 2, 3, or s.")

        if vote == "s":
            scores.append(None)
        else:
            scores.append(int(vote))
            case["human_score"] = int(vote)
        print()

    # Compute human agreement with automated eval
    auto_results = [d.get("passed") for d in details]
    valid_scores = [(s, a) for s, a in zip(scores, auto_results) if s is not None and a is not None]

    agreement = 0
    for human, auto in valid_scores:
        # Human 1=good aligns with auto pass, human 3=bad aligns with auto fail
        if (human <= 2 and auto) or (human == 3 and not auto):
            agreement += 1

    agreement_pct = (agreement / len(valid_scores) * 100) if valid_scores else 0

    human_good = sum(1 for s in scores if s == 1)
    human_ok = sum(1 for s in scores if s == 2)
    human_bad = sum(1 for s in scores if s == 3)
    skipped = sum(1 for s in scores if s is None)

    summary = {
        "human_good": human_good,
        "human_acceptable": human_ok,
        "human_bad": human_bad,
        "skipped": skipped,
        "agreement_with_auto": round(agreement_pct, 1),
    }

    # Update the run with human scores
    update_run(run_id, details=details)

    return {"run_id": run_id, "summary": summary, "details": details}


def judge_live(prompts: List[str], model: str = "nola") -> Dict[str, Any]:
    """
    Run prompts live and have human judge each response.
    Returns scores without saving unless explicitly requested.
    """
    from .runner import run_prompt

    print(f"\n  Live judging: {len(prompts)} prompts against {model}")
    print("  For each response, rate: [1] Good  [2] Acceptable  [3] Bad  [s] Skip\n")

    results = []
    for i, prompt in enumerate(prompts):
        print(f"  ── Prompt {i+1}/{len(prompts)} ──")
        print(f"  {prompt}")
        print("  Running...")

        r = run_prompt(model, prompt, with_state=True)
        response = r.get("response", "(error)")
        print(f"  Response: {response[:300]}")

        while True:
            vote = input("  Score [1/2/3/s]: ").strip().lower()
            if vote in ("1", "2", "3", "s"):
                break
            print("  Invalid. Enter 1, 2, 3, or s.")

        results.append({
            "prompt": prompt,
            "response_preview": response[:200],
            "human_score": int(vote) if vote != "s" else None,
            "duration_ms": r.get("duration_ms", 0),
        })
        print()

    valid = [r for r in results if r["human_score"] is not None]
    avg = sum(r["human_score"] for r in valid) / len(valid) if valid else 0

    return {
        "model": model,
        "total": len(prompts),
        "judged": len(valid),
        "average_score": round(avg, 2),
        "results": results,
    }
