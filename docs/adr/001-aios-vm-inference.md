# ADR 001 — AIOS VM inference strategy

**Status:** accepted  **Date:** 2026-04-23  **Context:** rot item #3

## Problem

The AIOS VM at `ssh AIOS` (`/opt/aios/`) has only **961 MiB RAM**. That's
below the floor for running any useful local Ollama model (smallest
quantized 1.5B needs ~1.5 GB; 7B needs 6+ GB). This has meant:

- `ollama run <model>` on the VM either fails to load or swaps to death
- All inference on the VM has to go through **Ollama cloud** (kimi-k2:1t-cloud,
  etc.), which requires an active signin and works but costs per-token
- The Mac can run local Ollama fine (qwen2.5:7b on M4 Air 16 GB is the
  current hardware baseline)

Two assessments (2026-04-22 and 2026-04-23) flagged this as open rot.
It isn't rot in the "broken code" sense — it's a hardware gap.

## Options considered

1. **Upgrade the VM.** Real RAM costs real money. Cloud VMs with ≥ 8 GB
   RAM run $20–80/mo depending on provider. Not justifiable until there's
   a product surface that needs always-on inference separate from the Mac.
2. **Ditch the VM, run everything on the Mac.** Works today for Cade's
   personal use. Fails the moment the agent needs to act while the Mac is
   closed/away, or when the public demo needs inference without touching
   the owner's machine.
3. **Keep the VM for non-inference services, route inference to Ollama
   cloud or back to the Mac.** Pragmatic split: the VM is a
   control plane + data plane; the Mac (or cloud) is the GPU.

## Decision

**Option 3.** The VM stays as:

- webhook / inbound endpoint target (ntfy, email forwarders, scrapers)
- cron-y background tasks that don't need a model (`goals_watcher`,
  `feed_pollers`, `sync_jobs`)
- readonly mirror of the state DB for offline inspection
- the `vm_sync.sh` destination

Inference routing (in order of preference):

1. **Mac Ollama** when reachable (`http://mac:11434`) — preferred for
   personal queries because context already lives there.
2. **Ollama cloud** (`kimi-k2:1t-cloud`) for heavy lifting (training_gen,
   eval, big SUMMARY) — already the default for `TRAINING_GEN` role.
3. **Provider fallback** (Groq / Together / OpenAI) for roles configured
   that way — the `resolve_role()` pipeline already handles this.

## Consequences

- **Good:** no hardware spend, existing tooling keeps working, the VM
  keeps its useful role (off-site compute that isn't inference-heavy).
- **Good:** the "inference is network-routable" invariant is already
  what `agent/services/llm.py` models — this ADR just documents it.
- **Bad:** when the Mac is unreachable and cloud quota is exhausted,
  the VM can't self-serve. That's the gap. We accept it until we have
  a reason to close it.
- **Not done:** if/when we need the agent to answer voice prompts while
  Cade is fully off-LAN (not "at laptop" or "on wifi"), revisit this.
  Cloudflare Tunnel + cloud Ollama is probably the path.

## Retirement of this rot item

This is no longer "rot" — it's a documented design trade-off. Future
assessments should not re-flag it. If the decision changes, supersede
this ADR with another.

---

_See also: `docs/assessments/ASSESSMENT_2026-04-22.md` and
`docs/assessments/ASSESSMENT_2026-04-23.md`._
