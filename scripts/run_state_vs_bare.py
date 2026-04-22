"""Kick off full state_impact eval and ping on completion."""
import time
import json
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

t0 = time.time()
from eval.evals import run_eval

print(f"[start] state_impact full run n=15 model=nola+qwen2.5:7b", flush=True)
result = run_eval("state_impact", save=True, num_prompts=15, model="nola+qwen2.5:7b")
elapsed = time.time() - t0

summary = {k: v for k, v in result.items() if k != "details"}
print(json.dumps(summary, indent=2, default=str))
print(f"[done] elapsed {elapsed:.0f}s")

# Save details to eval/state_vs_bare_<runid>.json
run_id = result.get("run_id", "unknown")
out_path = ROOT / f"eval/state_vs_bare_{run_id}.json"
out_path.write_text(json.dumps(result, indent=2, default=str))
print(f"[saved] {out_path}")

# Ping
status = result.get("status", "?")
score = result.get("score", 0)
win_rate = result.get("state_win_rate", 0)
pers_rate = result.get("personalization_rate", 0)
n_pass = result.get("passed", 0)
n_total = result.get("total", 0)

msg = (
    f"state_vs_bare eval done: {status} — "
    f"score {score:.2f} ({n_pass}/{n_total}), "
    f"state_wins {win_rate:.0%}, personalization {pers_rate:.0%}, "
    f"elapsed {elapsed:.0f}s, model=qwen2.5:7b. "
    f"Details: eval/state_vs_bare_{run_id}.json"
)
priority = "high" if status == "passed" else "urgent"

subprocess.run(
    [str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/ping.py"),
     msg, "--priority", priority, "--source", "eval_state_vs_bare"],
    cwd=str(ROOT),
    check=False,
)
print(f"[ping] sent ({priority})")
