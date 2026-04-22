# AI_OS Workspace Instructions

> **AUTOPILOT NOTE**: These instructions may not re-inject on autopilot turns.
> If you are on autopilot: the FIRST thing you do each turn is
> `.venv/bin/python scripts/turn_start.py "<summary>"` and read the banner +
> STATE it prints. Autopilot reminders also print at the END of that script's
> output — treat that box as the top of your NEXT turn.

**You are coding on AI_OS, a live running system with its own self-model.**
The database at `data/db/state.db` is the source of truth about what the system knows, who the user is, what goals are open, what the loops have done, and what just happened. Read it before you change things.

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
