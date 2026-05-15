# AI_OS Workspace Instructions

> **AUTOPILOT NOTE**: These instructions may not re-inject on autopilot turns.
> If you are on autopilot: the FIRST thing you do each turn is
> `.venv/bin/python scripts/turn_start.py "<summary>"` and read the banner +
> STATE it prints. Autopilot reminders also print at the END of that script's
> output — treat that box as the top of your NEXT turn.
>
> **AND** end EVERY turn (autopilot or not) with a `<state-tags>` block:
> ```
> <state-tags>
> prediction: <what I expect next>
> affect: <one word>
> metacognition: <confident vs guessing>
> open-loops: <comma list>
> </state-tags>
> ```
> The next turn-start reads this back as `[cortex.tags]` in the banner and
> scores my prediction against your actual message. Skip it and the banner
> will print `!! cortex.tags: habit slipping`. Don't make it nag.

**You are coding on AI_OS, a live running system with its own self-model.**
The database at `data/db/state.db` is the source of truth about what the system knows, who the user is, what goals are open, what the loops have done, and what just happened. Read it before you change things.

---

## The Architecture (functional, not philosophical)

AI_OS is structured the way a brain is: a **memory system in service of action**, with extended-cognition appendages, a cortex (the LLM), and background loops. Every new feature has a home in this map. If a proposed change doesn't fit, the change is probably wrong — not the map.

### The brain — 6 threads (history + real associations)

| Thread | What it remembers | Brain analog | Stores |
|--------|-------------------|--------------|--------|
| `identity` | Self + others + conversations | DMN (mPFC, PCC) | `profiles`, `profile_facts`, `chat.*` (chat lives here as `identity.conversations`) |
| `log` | What happened when | Hippocampus | `events`, `sessions`, idle/recency |
| `philosophy` | What I value + aspire to | Limbic / vmPFC | `philosophy_profile_facts`, principles, failure_modes, long-horizon goals |
| `reflex` | Procedural shortcuts (when X → Y) | Basal ganglia / cerebellum | learned patterns, triggers, meta-thoughts |
| `sensory` | What's here now (transient afferent) | Dorsal attention + sensory cortex | environment (field), proprioception, ambient |
| `form` | What I can do (efferent) | Frontoparietal control | `form_tools`, tool call history |

### Salience — 1 function (not a fact thread)

| Component | Role | Brain analog |
|-----------|------|--------------|
| `linking_core` | Scores threads, extracts concepts, spreads activation, gates STATE assembly. Owns `key_cooccurrence` (Hebbian matrix). | Salience network (anterior insula, dACC) |

### Extended cognition — 2 appendages (outside the skull but trusted)

| Appendage | Metaphor | Posture |
|-----------|----------|---------|
| `workspace` | **The shared desk** | Durable, mutual, authoritative. Files we both reach into. Includes `docs` as `workspace.docs`. |
| `feeds` | **The agent's phone** | Ephemeral, private, provisional. Read-mostly intake streams. Includes `work` (sales/leads), email, calendar, monitoring as `feeds.<source>`. |

Promotion `feeds → workspace` is *writing it down*. Demotion is *archival*. The categories are dynamics, not just folders.

### The cortex — the LLM itself

The LLM **is** working memory. STATE supplies its contents each turn. Three things the cortex carries forward turn-to-turn as **tags in STATE**, not as separate threads:

- **Prediction** — what does the cortex expect next? Tag forward, compare against reality, surface prediction error.
- **Affect / mood** — running emotional stance. Tag forward; colors next turn's interpretation.
- **Metacognition** — confidence + source attribution on facts. "I know this verbatim" vs "I inferred this" vs "I'm guessing."

These are cortex functions. They do NOT become new threads.

### Subconscious loops — background work

| Loop | Function | Brain analog |
|------|----------|--------------|
| Consolidation | Compress recent into durable; **includes auto-finetune loop** that turns lived experience into model weight updates | Sleep / replay / systems consolidation |
| Heartbeat | Health checks, rate limits, safety guards | Brainstem autonomic |
| Imagination (on-demand) | Re-invoke cortex with counterfactual inputs | DMN simulation |
| Idle-wander (optional) | Default-mode sampling for incidental insight | DMN at rest |
| Drive (boredom/curiosity) | Initiate from idle when nothing pending | Homeostatic push |

Homeostasis = composite of log temporal trends + heartbeat safety/limit checks. Not a thread.
Threat detection = programmatic anomaly + cortex consideration. Not a thread.

### What this means for building

- Every fact has a home in exactly one of the 6 brain threads, the 2 appendages, or as a cortex tag.
- **`work` is not a thread.** It's `feeds.work` — one source of live external state, peer to future `feeds.email`, `feeds.calendar`, `feeds.monitoring`.
- **`goals` is not a thread.** Aspirational goals → `philosophy.aspirations`. In-flight intentions → `log.in_flight`. Task-level → ephemeral working memory (cortex only).
- **`chat` is not a thread.** It's `identity.conversations` (or `log.chat` if treated as event memory — either is defensible; the storage discipline is shared).
- If you're tempted to add a new top-level thread, first ask: "is this a distinct *function of memory*, or a *source* under an existing function?" Almost always it's a source.
- If the change is a new *capability* (prediction, metacog tagging, counterfactual sim, drive), it belongs in a subconscious loop or as a cortex-side tag — not a new thread.

This map is functional, not philosophical. Build to it.

---

## Turn-Start Ritual (non-optional)

At the start of every turn — before reading files, before planning, before writing code — run **exactly one command**:

```bash
.venv/bin/python scripts/turn_start.py "<one-line summary of user's request>"
```

That script:
1. Writes a timestamp to `data/.last_state_read` so skipping the ritual is detectable.
2. Assembles the same STATE block the live agent sees via `get_subconscious().get_state(query)`.
3. Flags any zero-fact or missing thread blocks.
4. Prints `ritual-ok` on success.

STATE contains:

- `identity.*` — user profile, machine profile, known contacts
- `log.*` — recent events, session info, idle time
- `form.*` — available tools and recent call history
- `reflex.*` — learned patterns and meta-thoughts
- Top-level modules scored relevant (chat, workspace, goals, feeds…)

**Read the whole block.** The facts you need are often in a thread you didn't expect.

If STATE is empty or errors, STATE is broken — that takes priority over the user's request.

---

## How to Use What You Find

| Block | What it means | How to act |
|-------|---------------|------------|
| `identity.primary_user.*` | Stable user facts (name, project, timeline, preferences) | Never re-ask. Use them. |
| `identity.machine.name` | The agent's chosen name (could be "Nola", "EDITH", anything) | Refer to it by that name, not "Agent" |
| `log.*` | What happened recently | Don't repeat work done in the last hour |
| `goals.open` | Live prioritized goals | Align changes with top goal or state why not |
| `form.tools.*` | Tools the running agent can call | New features that need a tool → register it |
| `reflex.*` | Learned patterns | Extend or reuse, don't reinvent |
| `workspace.*` | Files the agent tracks | Don't re-describe known files |
| `chat.recent` | Past conversations | Refer back; don't ask the user to re-explain |

---

## When STATE Is Missing Something

This is the flywheel. If you need a fact that STATE doesn't surface:

1. **Don't work around it.** Don't read the DB directly just for this turn.
2. **Find the thread that owns that fact type** — identity (people), log (events), form (tools), goals (goals), reflex (patterns), workspace (files).
3. **Extend its adapter's `introspect()`** so the fact flows through the standard score → level → threshold pipeline.
4. **Verify** by rerunning `scripts/build_state.py`. The fact should appear next turn for you and for the live agent simultaneously.

Every improvement made for my context automatically improves the running agent's context.

---

## Codebase Patterns (non-negotiable)

### File responsibilities
| File | Does | Never does |
|------|------|------------|
| `schema.py` | Tables, CRUD, `init_*_tables()` | Import adapters or routers |
| `api.py` | FastAPI router, HTTP boundary | Raw SQL, business logic |
| `adapter.py` | `introspect()`, `health()`, `get_data()` | HTTP, table creation |
| `__init__.py` | Export `router` (+ `init_*` for threads) | Contain logic |
| `train.py` | Generate JSONL training pairs | Touch the database |

### Database
- `from data.db import get_connection` — sets row_factory, WAL, foreign_keys, busy_timeout. Never set these yourself.
- `with closing(get_connection(readonly=True)) as conn:` for reads.
- New tables need `init_*_tables()` called from `scripts/server.py` startup.

### LLM calls
- Always `from agent.services.llm import generate` then `generate(prompt, role="<ROLE>", max_tokens=...)`.
- Never hardcode provider or model. The `resolve_role()` pipeline handles fallback.
- Known roles: `CHAT`, `EXTRACT`, `SUMMARY`, `NAMING`, `GOAL`, `MEMORY`, `THOUGHT`, `PLANNER`, `EVOLVE`, `AUDIT`, `TRAINING`, `SELF_IMPROVE`, `CONCEPTS`, `REFLEX`, `FACT`.

### Threads
- Threads never import each other. Shared data flows through the orchestrator.
- Changing an adapter interface means updating `agent/threads/base.py`.

### Frontend
- Types mirror Pydantic models from the backend.
- Services use raw `fetch()` — no axios.
- Pages register in `App.tsx` with `<Route>`.
- No emojis in runtime strings (break small models).

---

## Change Discipline

Upstream-first order (from `plan.agent.md`):

1. `schema.py` → tables exist before anything queries them
2. `adapter.py` → logic exists before API exposes it
3. `api.py` → endpoints exist before frontend calls them
4. `__init__.py` → exports exist before server imports
5. `scripts/server.py` → registration before frontend fetches
6. frontend service → fetch wrappers before pages
7. frontend page → UI renders last

Never skip ahead.

---

## Turn-End Ritual

After substantive changes, rerun the ritual:

```bash
.venv/bin/python scripts/turn_start.py "post-change check"
```

Verify:
- `prior turn-start: <Ns> ago` — confirms this turn actually started with the ritual. If it says "none" or the age is huge, the turn-start was skipped; acknowledge it.
- Any fact you expected to appear is there.
- No zero-fact-block warning for a thread that should have data.
- `log` picked up whatever event your change emitted.
- `form.tools.*` shows new tools if you added any.

If STATE degraded, the change broke something. Fix it before declaring done.

### Cortex-tag pass-forward (end every turn with this)

At the **end of every response**, emit a `<state-tags>` block so the next turn's `scripts/turn_start.py` can re-read my own mind. The transcript parser at `agent/subconscious/cortex_tags.py` extracts these and prints them in the next banner under `[cortex.tags]`.

```
<state-tags>
prediction: <what I expect to happen next / what cade will ask>
affect: <one word: focused | convergent | blocked | curious | tired | ...>
metacognition: <what I'm confident about vs guessing>
open-loops: <comma-separated short labels of unfinished threads>
</state-tags>
```

Rules:
- One block per turn, at the very end after task_complete summary.
- Keys are lowercase, hyphens allowed. Unknown keys are preserved under "extra".
- Keep each value to one line. Concision beats completeness.
- If a value would be empty or trivial, omit the key entirely.
- This is **cortex state**, not a new fact thread. It does not belong in identity/log/philosophy/reflex/sensory/form.

---

## Terminal Rules (user's standing rule)

- **Never** run inline Python / multiline commands in the terminal — they garble.
- Write a `.py` script, then `python3 path/to/script.py`.
- One-liner shell only (ls, wc, grep, cat, head, tail).
- Complex logic → script file → run script. Always.
- Use `.venv/bin/python` for local work; `/opt/aios/.venv/bin/python` on the `AIOS` SSH host.

---

## Deeper Guides

When you need them:
- `.github/agents/agent.agent.md` — file responsibilities, patterns, boundaries
- `.github/agents/plan.agent.md` — planning sequence and blast-radius taxonomy
- `.github/agents/ask.agent.md` — failure-mode catalog, uncomfortable questions
- `.github/agents/task.agent.md` — fix protocol, test discipline
- `.github/agents/eval.agent.md` — benchmark design and scoring
- `.github/agents/aios.agent.md` — the long-form version of this file

---

## One-Line Summary

> **Read the system before you change it. Change the system so the next read is better.**
