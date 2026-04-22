# Shadow Executor

Two-container sandbox for safely testing self-modification.

## What it does

When AIOS proposes to modify its own code (via the evolve loop or an
approved self-improvement), we need somewhere to run it *first* that
isn't the live process the user is talking to.

This folder is that somewhere.  `docker-compose.yml` defines two
containers built from the same image:

| service | port | DB file | role |
|---------|------|---------|------|
| `aios_prod` | 8000 | `state.db` | the one the user talks to |
| `aios_shadow` | 8001 | `state.shadow.db` | scratch copy for tests |

The shadow has `AIOS_HUMAN_META=0`, `AIOS_GOAL_PROMOTER=0`, and
`AIOS_EVOLVE=0` so nothing it does echoes back into production.

## Running a shadow test

```bash
./shadow/run_shadow_test.sh
```

That script:
1. Copies `state.db` → `state.shadow.db`.
2. Boots `aios_shadow` via `docker compose up -d`.
3. Waits for `/api/subconscious/heartbeat` on :8001.
4. Runs `tmp/verify_write_bus.py` inside the shadow.
5. Returns pass/fail.

## Integration hook

`agent/subconscious/loops/evolve.py` currently writes directly to disk
and commits.  The safe flow:

1. Evolve writes the proposed change to a `git worktree` inside the
   shadow container (not live).
2. `run_shadow_test.sh` runs in that worktree.
3. Only if the shadow stays green does the change get promoted to a
   real commit on the live repo and the prod container gets a SIGHUP
   to reload.

This hook is not wired yet — the current evolve loop is unchanged.
The shadow folder is the scaffolding for that next step.
