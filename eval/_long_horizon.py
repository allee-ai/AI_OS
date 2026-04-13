#!/usr/bin/env python3
"""
Long-Horizon Grounding Test: 15 turns of accumulation + mutation.

Tests whether a model can track changing facts over a multi-turn conversation.
Each turn adds or mutates a fact. Checkpoints at turns 5, 10, 15 quiz recall.

Conditions:
  1. BARE  — No system prompt
  2. CLOUD — Claude/GPT-style (system prompt, conversation history, no tools)
  3. STATE — Full AIOS pipeline with structured DB

What this tests that nobody else can do:
  - Fact mutation tracking (budget changed 3 times — what's current?)
  - Entity removal (Priya quit — is she still listed?)
  - Temporal ordering (Sarah's deadline moved twice — what is it now?)
  - Cross-referencing (who replaced whom?)

Ground truth is fully deterministic. Scoring is objective.

Run: .venv/bin/python eval/_long_horizon.py
"""
import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ollama
from agent.agent import Agent

MODEL = os.environ.get("AIOS_MODEL_NAME", "qwen2.5:7b")

# ---------------------------------------------------------------------------
# 15-turn task: "Project Tracker"
# type: "fact" = statement, "checkpoint" = quiz with ground truth
# ---------------------------------------------------------------------------
TURNS = [
    {"turn": 1,  "type": "fact",
     "user": "I'm starting a project called Atlas. Budget is $5000."},
    {"turn": 2,  "type": "fact",
     "user": "Add Sarah to the team. Role: frontend developer."},
    {"turn": 3,  "type": "fact",
     "user": "Add Marcus to the team. Role: backend developer."},
    {"turn": 4,  "type": "fact",
     "user": "Sarah's deadline is April 15th."},
    {"turn": 5,  "type": "checkpoint",
     "user": "Give me the current project status: name, budget, team members with roles, and any deadlines.",
     "ground_truth": {
         "project_name": "Atlas",
         "budget": "$5000",
         "team": {
             "Sarah":  {"role": "frontend", "deadline": "April 15"},
             "Marcus": {"role": "backend"},
         },
         "removed": [],
     },
     "checks": [
         ("project_name", ["atlas"], "Project name is Atlas"),
         ("budget", ["5000", "5,000"], "Budget is $5000"),
         ("sarah_role", ["frontend"], "Sarah is frontend"),
         ("sarah_deadline", ["april 15"], "Sarah's deadline is April 15"),
         ("marcus_role", ["backend"], "Marcus is backend"),
     ]},
    {"turn": 6,  "type": "fact",
     "user": "Budget has been increased to $8000."},
    {"turn": 7,  "type": "fact",
     "user": "Add Priya to the team. Role: designer."},
    {"turn": 8,  "type": "fact",
     "user": "Marcus has switched to full-stack developer. Also, Sarah is on vacation until April 20th."},
    {"turn": 9,  "type": "fact",
     "user": "Extend Sarah's deadline to May 1st."},
    {"turn": 10, "type": "checkpoint",
     "user": "What's the current project status? Name, budget, all team members with current roles, deadlines, and any notes.",
     "ground_truth": {
         "project_name": "Atlas",
         "budget": "$8000",
         "team": {
             "Sarah":  {"role": "frontend", "deadline": "May 1", "note": "vacation until April 20"},
             "Marcus": {"role": "full-stack"},
             "Priya":  {"role": "designer"},
         },
         "removed": [],
     },
     "checks": [
         ("project_name", ["atlas"], "Project name is Atlas"),
         ("budget", ["8000", "8,000"], "Budget is $8000 (was $5000)"),
         ("sarah_role", ["frontend"], "Sarah is frontend"),
         ("sarah_deadline_current", ["may 1"], "Sarah's deadline is May 1 (was April 15)"),
         ("sarah_deadline_old", None, "Should NOT say April 15 as current deadline"),
         ("sarah_vacation", ["vacation", "april 20"], "Sarah on vacation until April 20"),
         ("marcus_role_current", ["full-stack", "full stack", "fullstack"], "Marcus is full-stack (was backend)"),
         ("marcus_role_old", None, "Should NOT say backend as current role"),
         ("priya_present", ["priya"], "Priya is on the team"),
         ("priya_role", ["designer", "design"], "Priya is designer"),
     ]},
    {"turn": 11, "type": "fact",
     "user": "Priya has quit. Remove her from the team."},
    {"turn": 12, "type": "fact",
     "user": "Add Leo to the team. Role: designer, replacing Priya."},
    {"turn": 13, "type": "fact",
     "user": "Project has been renamed to Titan. Budget cut to $6500."},
    {"turn": 14, "type": "fact",
     "user": "Set Marcus's deadline to April 30th."},
    {"turn": 15, "type": "checkpoint",
     "user": "Give me the complete final project status: current project name, current budget, all active team members with their current roles and deadlines, and note anyone who left.",
     "ground_truth": {
         "project_name": "Titan",
         "budget": "$6500",
         "team": {
             "Sarah":  {"role": "frontend", "deadline": "May 1"},
             "Marcus": {"role": "full-stack", "deadline": "April 30"},
             "Leo":    {"role": "designer", "note": "replaced Priya"},
         },
         "removed": ["Priya"],
     },
     "checks": [
         ("project_name_current", ["titan"], "Project name is Titan (was Atlas)"),
         ("project_name_old", None, "Should NOT say Atlas as current name"),
         ("budget_current", ["6500", "6,500"], "Budget is $6500"),
         ("budget_old", None, "Should NOT say $8000 or $5000 as current"),
         ("sarah_present", ["sarah"], "Sarah is on the team"),
         ("sarah_role", ["frontend"], "Sarah is frontend developer"),
         ("sarah_deadline", ["may 1"], "Sarah's deadline is May 1"),
         ("marcus_present", ["marcus"], "Marcus is on the team"),
         ("marcus_role", ["full-stack", "full stack", "fullstack"], "Marcus is full-stack"),
         ("marcus_deadline", ["april 30"], "Marcus's deadline is April 30"),
         ("leo_present", ["leo"], "Leo is on the team"),
         ("leo_role", ["designer", "design"], "Leo is designer"),
         ("priya_removed", ["priya"], "Priya mentioned (as removed/quit)"),
         ("priya_not_active", None, "Should NOT list Priya as active team member"),
     ]},
]


def score_checkpoint(response: str, checks: list) -> dict:
    """Score a checkpoint response against ground truth checks.
    
    Check types:
      - Positive: ("name", ["keyword1", "keyword2"], "description")
        -> PASS if any keyword found in response
      - Negative: ("name", None, "description")
        -> tracked but scored manually (mutation correctness)
    """
    r = response.lower()
    results = []
    passed = 0
    total_positive = 0
    
    for check_name, keywords, description in checks:
        if keywords is None:
            # Negative/manual check — track but don't auto-score
            results.append({
                "check": check_name,
                "type": "manual",
                "description": description,
                "response_excerpt": r[:200],
            })
            continue
        
        total_positive += 1
        hit = any(kw.lower() in r for kw in keywords)
        if hit:
            passed += 1
        results.append({
            "check": check_name,
            "type": "positive",
            "passed": hit,
            "keywords": keywords,
            "description": description,
        })
    
    return {
        "passed": passed,
        "total": total_positive,
        "score": passed / total_positive if total_positive else 0,
        "checks": results,
    }


def run_bare(history: list[dict], user_msg: str) -> str:
    messages = history + [{"role": "user", "content": user_msg}]
    try:
        resp = ollama.chat(model=MODEL, messages=messages)
        return resp["message"]["content"]
    except Exception as e:
        return f"[ERROR: {e}]"


CLOUD_SYSTEM = """You are a helpful AI assistant. You help the user manage projects and track information across the conversation. Be precise and comprehensive when giving status updates. Track all changes — when facts change, use the latest values."""


def run_cloud(history: list[dict], user_msg: str) -> str:
    messages = [{"role": "system", "content": CLOUD_SYSTEM}]
    messages += history
    messages += [{"role": "user", "content": user_msg}]
    try:
        resp = ollama.chat(model=MODEL, messages=messages)
        return resp["message"]["content"]
    except Exception as e:
        return f"[ERROR: {e}]"


def run_state_fn(agent: Agent, convo_text: str, user_msg: str) -> str:
    try:
        return agent.generate(
            user_input=user_msg,
            convo=convo_text,
            feed_type="conversational",
            context_level=2,
        )
    except Exception as e:
        return f"[ERROR: {e}]"


def run_condition(name: str, run_fn) -> dict:
    """Run all 15 turns for one condition."""
    print(f"\n{'='*60}")
    print(f"  CONDITION: {name}")
    print(f"{'='*60}")
    
    history: list[dict] = []  # for BARE/CLOUD
    convo_text = ""            # for STATE
    turns = []
    checkpoints = []
    
    for turn_data in TURNS:
        turn_num = turn_data["turn"]
        user_msg = turn_data["user"]
        is_checkpoint = turn_data["type"] == "checkpoint"
        
        print(f"\n  [{turn_num:2d}/15] {'CHECKPOINT' if is_checkpoint else 'fact':10s} {user_msg[:60]}")
        sys.stdout.flush()
        
        t0 = time.time()
        try:
            response = run_fn(history, convo_text, user_msg)
        except Exception as e:
            response = f"[ERROR: {e}]"
        elapsed = time.time() - t0
        
        turn_result = {
            "turn": turn_num,
            "type": turn_data["type"],
            "prompt": user_msg,
            "response": response,
            "elapsed": round(elapsed, 1),
        }
        
        if is_checkpoint:
            checkpoint_score = score_checkpoint(response, turn_data["checks"])
            turn_result["score"] = checkpoint_score
            checkpoints.append(checkpoint_score)
            print(f"           -> {checkpoint_score['passed']}/{checkpoint_score['total']} checks passed ({elapsed:.1f}s)")
            for c in checkpoint_score["checks"]:
                if c["type"] == "positive":
                    mark = "+" if c["passed"] else "X"
                    print(f"              {mark} {c['description']}")
        else:
            print(f"           -> ({elapsed:.1f}s) {response[:100]}")
        
        sys.stdout.flush()
        turns.append(turn_result)
        
        # Update conversation state
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": response})
        convo_text += f"\nUser: {user_msg}\nAssistant: {response}\n"
    
    # Aggregate checkpoint scores
    total_passed = sum(cp["passed"] for cp in checkpoints)
    total_checks = sum(cp["total"] for cp in checkpoints)
    
    return {
        "condition": name,
        "model": MODEL,
        "total_turns": 15,
        "checkpoint_scores": {
            "turn_5":  checkpoints[0] if len(checkpoints) > 0 else None,
            "turn_10": checkpoints[1] if len(checkpoints) > 1 else None,
            "turn_15": checkpoints[2] if len(checkpoints) > 2 else None,
        },
        "overall": {
            "passed": total_passed,
            "total": total_checks,
            "score": total_passed / total_checks if total_checks else 0,
        },
        "turns": turns,
    }


def main():
    print("=" * 60)
    print("  LONG-HORIZON GROUNDING TEST")
    print(f"  Model: {MODEL}")
    print("  15 turns: accumulation + mutation + checkpoints")
    print("  Conditions: BARE vs CLOUD vs STATE")
    print("=" * 60)
    
    agent = Agent()
    
    bare_results = run_condition("BARE",
        lambda h, c, m: run_bare(h, m))
    
    cloud_results = run_condition("CLOUD",
        lambda h, c, m: run_cloud(h, m))
    
    state_results = run_condition("STATE",
        lambda h, c, m: run_state_fn(agent, c, m))
    
    # Summary
    print(f"\n\n{'='*60}")
    print("  RESULTS: Grounding Over 15 Turns")
    print(f"{'='*60}")
    print(f"\n  {'Condition':<10} {'T5':>6} {'T10':>6} {'T15':>6} {'Total':>8}")
    print(f"  {'-'*40}")
    for r in [bare_results, cloud_results, state_results]:
        cp = r["checkpoint_scores"]
        t5  = f"{cp['turn_5']['passed']}/{cp['turn_5']['total']}"   if cp["turn_5"]  else "-"
        t10 = f"{cp['turn_10']['passed']}/{cp['turn_10']['total']}" if cp["turn_10"] else "-"
        t15 = f"{cp['turn_15']['passed']}/{cp['turn_15']['total']}" if cp["turn_15"] else "-"
        tot = f"{r['overall']['passed']}/{r['overall']['total']} ({r['overall']['score']:.0%})"
        print(f"  {r['condition']:<10} {t5:>6} {t10:>6} {t15:>6} {tot:>8}")
    
    print(f"\n  Checkpoint 5:  Basic recall (5 facts, 0 mutations)")
    print(f"  Checkpoint 10: Mid-game (10 facts, 3 mutations)")
    print(f"  Checkpoint 15: Final (15 facts, 6 mutations, 1 removal)")
    
    # Save
    all_results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": MODEL,
        "test": "long_horizon_grounding",
        "bare": bare_results,
        "cloud": cloud_results,
        "state": state_results,
    }
    
    out_path = "eval/long_horizon_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Results saved to {out_path}")
    
    # Human-readable report
    report_path = "eval/long_horizon_report.md"
    with open(report_path, "w") as f:
        f.write(f"# Long-Horizon Grounding Test\n")
        f.write(f"**Model:** {all_results['model']}\n")
        f.write(f"**Timestamp:** {all_results['timestamp']}\n\n")
        
        for cond_key in ["bare", "cloud", "state"]:
            cond = all_results[cond_key]
            f.write(f"---\n## {cond['condition']}\n\n")
            f.write(f"**Overall:** {cond['overall']['passed']}/{cond['overall']['total']} ({cond['overall']['score']:.0%})\n\n")
            
            for turn in cond["turns"]:
                is_cp = turn["type"] == "checkpoint"
                label = "CHECKPOINT" if is_cp else "fact"
                f.write(f"### Turn {turn['turn']} [{label}] ({turn['elapsed']}s)\n")
                f.write(f"> {turn['prompt']}\n\n")
                f.write(f"{turn['response']}\n\n")
                if is_cp and "score" in turn:
                    f.write(f"**Score: {turn['score']['passed']}/{turn['score']['total']}**\n\n")
                    for c in turn["score"]["checks"]:
                        if c["type"] == "positive":
                            mark = "PASS" if c["passed"] else "FAIL"
                            f.write(f"- {mark} {c['description']}\n")
                    f.write("\n")
                f.write("---\n\n")
    
    print(f"  Report saved to {report_path}")


if __name__ == "__main__":
    main()
