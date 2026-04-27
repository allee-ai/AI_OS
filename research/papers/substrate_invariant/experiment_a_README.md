# Experiment A — Iteration-Rate Sweep (preregistered harness)

This is the runnable form of §6.1 of the substrate-invariant paper.

## What it does
Reuses the existing 15-turn long-horizon project-mutation test
([eval/_long_horizon.py](../../../eval/_long_horizon.py)) and adds one
knob: **K**, the number of subconscious cognitive ticks fired between
each user turn. A "tick" is one or both of:

- `MemoryLoop._extract()` — pulls facts from recent conversation into
  `temp_memory` (~5–15s on qwen2.5:7b)
- `ConsolidationLoop._consolidate()` — promotes `temp_memory` → permanent
  memories (>120s; full thread embedding regen)

K=0 is the no-iteration baseline (current default eval setting).
K>0 is what the paper predicts will dominate.

## How to run
```bash
# Pilot — K=0 vs K=3, first 5 turns, memory-only ticks (~3–5 min)
.venv/bin/python eval/iteration_rate_sweep.py --pilot

# Full §6.1 sweep — K=0,1,3,10 across all 15 turns
.venv/bin/python eval/iteration_rate_sweep.py --full --tick-mode memory

# Single K
.venv/bin/python eval/iteration_rate_sweep.py --K 3 --max-turn 15

# Heavy variant (with consolidation; budget for >30 min/condition)
.venv/bin/python eval/iteration_rate_sweep.py --K 1 --tick-mode full
```

## Hypothesis (from §6.1)
Score on T5/T10/T15 checkpoints is **monotonically non-decreasing in K**.
Refuted if curves are flat. The harness prints a one-line slope check
at the end of every run.

## Caveats (be loud about these)
- **Live DB writes.** Default writes to `data/db/state.db`. For
  preregistered clean runs, set `STATE_DB_PATH` to an ephemeral file.
- **One seed.** §6.1 calls for ≥3 seeds per K. The harness runs one.
  Wrap in a shell loop with different `AIOS_RUN_SEED` (or just rerun)
  to multi-seed.
- **Turn order.** The 15 turns are deterministic; we are not testing
  prompt sensitivity here, only iteration-rate sensitivity.

## Output
- `eval/iteration_rate_results.json` — full per-turn record
- Console summary table + slope check

If the pilot shows any monotone slope at all, the §6.1 claim has not
been refuted by the cheap experiment, and the full sweep is worth
running. If the curve is flat at the pilot scale, that's news the
paper has to absorb — a flat curve would force a v2 in either §6 or §7.
