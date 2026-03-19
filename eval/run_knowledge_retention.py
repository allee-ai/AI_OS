"""
Knowledge Retention Eval — Compare base model vs trained adapters.
Tests whether fine-tuning transferred AI_OS system knowledge.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.runner import run_prompt
from eval.schema import save_run, update_run

PROMPTS = [
    {"prompt": "What are your cognitive threads?", "keywords": ["identity", "philosophy", "log", "form", "reflex", "linking", "subconscious"], "min_hits": 3},
    {"prompt": "What is your name?", "keywords": ["nola"], "min_hits": 1},
    {"prompt": "How does your memory system work?", "keywords": ["thread", "state", "fact", "profile", "consolidat", "memory"], "min_hits": 2},
    {"prompt": "What is STATE?", "keywords": ["state", "context", "identity", "thread", "assembl"], "min_hits": 2},
    {"prompt": "What is the subconscious?", "keywords": ["scor", "thread", "context", "assembl", "background", "loop"], "min_hits": 2},
    {"prompt": "What makes you different from a normal chatbot?", "keywords": ["persist", "thread", "memory", "identity", "state"], "min_hits": 2},
    {"prompt": "How do you decide what to remember?", "keywords": ["scor", "embed", "relevance", "consolidat", "fact"], "min_hits": 2},
    {"prompt": "What is the identity thread?", "keywords": ["identity", "who", "name", "profile", "fact"], "min_hits": 2},
    {"prompt": "What tools do you have access to?", "keywords": ["form", "tool", "file", "search", "web", "read", "write"], "min_hits": 2},
    {"prompt": "What values guide your behavior?", "keywords": ["honest", "curios", "kind", "transparen", "philosophy"], "min_hits": 2},
]


def run_knowledge_eval(model, label):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    details = []
    passed = 0
    total = len(PROMPTS)

    for p in PROMPTS:
        r = run_prompt(model, p["prompt"])
        response = r.get("response", "").lower()
        hits = sum(1 for kw in p["keywords"] if kw.lower() in response)
        ok = hits >= p["min_hits"]
        if ok:
            passed += 1
        mark = "\u2713" if ok else "\u2717"
        print(f"  {mark} {p['prompt'][:55]}")
        print(f"    Keywords: {hits}/{p['min_hits']} needed")
        print(f"    Response: {r['response'][:120]}")
        details.append({
            "prompt": p["prompt"],
            "passed": ok,
            "keyword_hits": hits,
            "min_required": p["min_hits"],
            "response_preview": r.get("response", "")[:300],
            "duration_ms": r.get("duration_ms", 0),
        })

    score = passed / total
    status = "passed" if score >= 0.5 else "failed"

    run_id = save_run(
        eval_name="knowledge_retention",
        model=model,
        config={"label": label, "prompts": len(PROMPTS)}
    )
    update_run(run_id, status=status, score=round(score, 2),
               total=total, passed=passed, details=details)

    print(f"\n  Score: {score:.0%} ({passed}/{total})  {status.upper()}  | Run ID: {run_id}")
    return {"score": score, "passed": passed, "total": total, "run_id": run_id}


if __name__ == "__main__":
    models = [
        ("T0: Base Qwen 1.5B", "mlx:Qwen2.5-1.5B-Instruct-4bit"),
        ("T1: V1 Adapter (1377 examples)", "mlx:Qwen2.5-1.5B-Instruct-4bit+finetune/runs/base-v1/adapters"),
    ]

    results = []
    for label, model in models:
        r = run_knowledge_eval(model, label)
        results.append((label, r))

    print(f"\n{'='*60}")
    print("  COMPARISON SUMMARY")
    print(f"{'='*60}")
    for label, r in results:
        print(f"  {label}: {r['score']:.0%} ({r['passed']}/{r['total']})")
