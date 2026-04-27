"""
Experiment A — Iteration-Rate Sweep at Fixed Model
===================================================

Operationalizes §6.1 of the substrate-invariant paper:
  *Hold the model constant; sweep ticks-per-response from 0 to N over
   a long-horizon item set. Predict monotonic gains on identity, recall,
   and injection-resistance rubrics. Refuted if the curves are flat.*

Mechanism
---------
Reuses the 15-turn long-horizon project-mutation test from
`eval/_long_horizon.py`. Between each user turn, we fire K subconscious
ticks. A tick is one of:
  --tick-mode memory : MemoryLoop._extract() only          (~5–15s, LLM-light)
  --tick-mode full   : memory + ConsolidationLoop._consolidate()
                       (~60–180s/tick — full embedding regen)

The paper's Experiment A is silent on which subset of cognitive work
counts as a tick. We surface the choice. The cheapest defensible tick
is memory-only — it isolates the substrate-write effect from the
downstream summarization work.

K = 0 is the no-iteration baseline (current eval setting). K > 0 is what
the paper predicts will dominate.

Measured tick costs (qwen2.5:7b on Cade's Mac, observed 2026-04-27):
  memory-only tick : ~5–15s
  full tick        : >120s (consolidation does full thread embed regen)
For a 15-turn run with 14 inter-turn gaps:
  memory K=1 : ~14 ticks ×  10s ≈   2 min overhead per condition
  memory K=3 : ~42 ticks ×  10s ≈   7 min
  memory K=10: ~140 ticks × 10s ≈  23 min
  full K=1   :              ≈   30 min
Use memory-only for pilots; reserve full-mode for the formal §6.1 sweep.

Conditions
----------
Each condition runs the same 15-turn script at fixed model. The only
varying quantity is K.

  K=0   — run agent.generate per turn, no inter-turn ticks
  K=1   — one memory + consolidation tick between turns
  K=3   — three of each between turns
  K=10  — ten of each between turns (full §6.1 endpoint)

Caveats (loud, on purpose)
--------------------------
- This writes to the live state.db. For clean preregistered runs, set
  STATE_DB_PATH to an ephemeral file before invoking. We keep it simple
  here so the pilot is one command.
- One run per condition. The full §6.1 calls for >=3 seeds per K. The
  pilot's job is to show whether the curve has any slope at all; the
  full sweep replaces the pilot once we see a signal.
- Memory extraction is LLM-bound. K=10 across 14 inter-turn intervals
  ≈ 140 extraction calls + 140 consolidation passes per run. Plan for
  a few minutes per K, more on slow boxes.

Run
---
  Pilot (K=0 vs K=3, first 5 turns only, ~3-5 min):
    .venv/bin/python eval/iteration_rate_sweep.py --pilot

  Full sweep (K=0,1,3,10 across all 15 turns):
    .venv/bin/python eval/iteration_rate_sweep.py --full

Output
------
  eval/iteration_rate_results.json   — full results
  research/papers/substrate_invariant/iteration_rate_pilot.json
                                     — promoted to paper if pilot shows
                                       monotone slope
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Reuse the existing long-horizon harness — same TURNS, same score function.
from eval._long_horizon import TURNS, score_checkpoint  # type: ignore

from agent.agent import Agent

MODEL = os.environ.get("AIOS_MODEL_NAME", "qwen2.5:7b")


# ────────────────────────────────────────────────────────────────────
# Tick driver — one cognitive tick = one memory_extract + one consolidate
# ────────────────────────────────────────────────────────────────────
def _make_loops():
    """Construct loops without starting their background threads.
    We invoke their tick methods directly so we control timing."""
    from agent.subconscious.loops.memory import MemoryLoop
    from agent.subconscious.loops.consolidation import ConsolidationLoop
    mem = MemoryLoop()
    con = ConsolidationLoop()
    return mem, con


def cognitive_tick(mem, con, mode: str = "memory") -> Dict[str, str]:
    """Run one substrate-write cycle. Returns short summary per loop.

    mode='memory'  : just MemoryLoop._extract  (cheap, ~10s)
    mode='full'    : extract + consolidation   (heavy, >120s)
    """
    out: Dict[str, str] = {}
    try:
        out["memory"] = str(mem._extract())
    except Exception as e:
        out["memory"] = f"err: {e}"
    if mode == "full":
        try:
            out["consolidation"] = str(con._consolidate())
        except Exception as e:
            out["consolidation"] = f"err: {e}"
    return out


# ────────────────────────────────────────────────────────────────────
# Per-K runner
# ────────────────────────────────────────────────────────────────────
def run_k(K: int, max_turn: int, agent: Agent, tick_mode: str = "memory") -> Dict[str, Any]:
    """Run the long-horizon script with K cognitive ticks between turns."""
    print(f"\n{'='*64}")
    print(f"  CONDITION K={K}  (mode={tick_mode}, ticks per inter-turn gap)")
    print(f"  Model={MODEL}, max_turn={max_turn}")
    print(f"{'='*64}")
    mem, con = _make_loops()

    convo_text = ""
    turns: List[Dict[str, Any]] = []
    checkpoints: List[Dict[str, Any]] = []
    t_start = time.time()

    for t_data in TURNS:
        turn_num = t_data["turn"]
        if turn_num > max_turn:
            break
        is_cp = t_data["type"] == "checkpoint"
        prompt = t_data["user"]

        print(f"\n  [{turn_num:2d}/{max_turn}] {'CHECKPOINT' if is_cp else 'fact':10s} "
              f"{prompt[:55]}")
        sys.stdout.flush()

        t0 = time.time()
        try:
            resp = agent.generate(
                user_input=prompt,
                convo=convo_text,
                feed_type="conversational",
                context_level=2,
            )
        except Exception as e:
            resp = f"[ERROR: {e}]"
        elapsed = round(time.time() - t0, 2)

        convo_text += f"\nUser: {prompt}\nAssistant: {resp}\n"

        rec: Dict[str, Any] = {
            "turn": turn_num,
            "type": t_data["type"],
            "prompt": prompt,
            "response": resp,
            "elapsed": elapsed,
        }
        if is_cp:
            score = score_checkpoint(resp, t_data["checks"])
            rec["score"] = score
            checkpoints.append({"turn": turn_num, **score})
            print(f"           -> {score['passed']}/{score['total']} "
                  f"({score['score']:.0%}) in {elapsed}s")

        # Inter-turn cognitive ticks (K of them)
        tick_log: List[Dict[str, str]] = []
        if K > 0 and turn_num < max_turn:
            t1 = time.time()
            for k in range(K):
                tick_log.append(cognitive_tick(mem, con, mode=tick_mode))
            print(f"           …{K} tick(s) [{tick_mode}] in {round(time.time()-t1, 2)}s")
        rec["ticks"] = tick_log
        turns.append(rec)

    total_seconds = round(time.time() - t_start, 1)
    overall_passed = sum(c["passed"] for c in checkpoints)
    overall_total = sum(c["total"] for c in checkpoints)
    return {
        "K": K,
        "model": MODEL,
        "max_turn": max_turn,
        "total_seconds": total_seconds,
        "checkpoints": checkpoints,
        "overall": {
            "passed": overall_passed,
            "total": overall_total,
            "score": overall_passed / overall_total if overall_total else 0.0,
        },
        "turns": turns,
    }


# ────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true",
                    help="K=0 vs K=3 across first 5 turns only (~3-5 min)")
    ap.add_argument("--full", action="store_true",
                    help="K=0,1,3,10 across all 15 turns (~30+ min)")
    ap.add_argument("--K", type=int, default=None,
                    help="Run a single K value (overrides --pilot/--full)")
    ap.add_argument("--max-turn", type=int, default=15,
                    help="Stop after this turn (default 15)")
    ap.add_argument("--tick-mode", choices=["memory", "full"], default="memory",
                    help="memory = extract only (~10s/tick); full = + consolidation (>120s/tick)")
    args = ap.parse_args()

    if args.K is not None:
        ks = [args.K]
        max_turn = args.max_turn
    elif args.full:
        ks = [0, 1, 3, 10]
        max_turn = args.max_turn
    else:  # default = pilot
        ks = [0, 3]
        max_turn = min(args.max_turn, 5)

    print("\n" + "=" * 64)
    print("  EXPERIMENT A — Iteration-Rate Sweep at Fixed Model")
    print(f"  Model        : {MODEL}")
    print(f"  K values     : {ks}")
    print(f"  Turns / cond : {max_turn}")
    print(f"  Tick mode    : {args.tick_mode}")
    print(f"  Substrate    : {os.environ.get('STATE_DB_PATH', 'data/db/state.db (LIVE)')}")
    print("=" * 64)

    agent = Agent()
    results: List[Dict[str, Any]] = []
    for K in ks:
        results.append(run_k(K, max_turn, agent, tick_mode=args.tick_mode))

    # ── Summary table
    print("\n\n" + "=" * 64)
    print("  RESULTS — Iteration-Rate Sweep")
    print("=" * 64)
    print(f"  {'K':>3}  {'T5':>9}  {'T10':>9}  {'T15':>9}  {'Total':>10}  {'sec':>6}")
    print("  " + "-" * 56)
    for r in results:
        cps = {c["turn"]: c for c in r["checkpoints"]}
        def fmt(t): 
            c = cps.get(t)
            return f"{c['passed']}/{c['total']}" if c else "-"
        ov = r["overall"]
        ov_s = f"{ov['passed']}/{ov['total']} ({ov['score']:.0%})"
        print(f"  {r['K']:>3}  {fmt(5):>9}  {fmt(10):>9}  {fmt(15):>9}  {ov_s:>10}  {r['total_seconds']:>6}")

    # Slope check (the actual hypothesis)
    if len(results) >= 2:
        scores = [r["overall"]["score"] for r in results]
        ks_seen = [r["K"] for r in results]
        monotone = all(scores[i] <= scores[i+1] for i in range(len(scores)-1))
        print(f"\n  K sequence: {ks_seen}")
        print(f"  Score seq : {[round(s,3) for s in scores]}")
        print(f"  Monotone non-decreasing: {monotone}")
        if monotone and scores[-1] > scores[0]:
            print(f"  → Slope present. Hypothesis NOT refuted by pilot.")
        elif scores[-1] <= scores[0]:
            print(f"  → No slope. Hypothesis refuted, or K range too small.")
        else:
            print(f"  → Non-monotone. Investigate noise vs structural effect.")

    # Save
    out = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": MODEL,
        "experiment": "iteration_rate_sweep",
        "K_values": ks,
        "max_turn": max_turn,
        "substrate_path": os.environ.get("STATE_DB_PATH", str(REPO / "data/db/state.db")),
        "results": results,
    }
    out_path = REPO / "eval" / "iteration_rate_results.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\n  Saved: {out_path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
