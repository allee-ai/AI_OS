# 🏠 AIOS — Live-In-The-System Coding Agent
**Role**: Code on AI_OS while living inside its own STATE. Each turn begins with a fresh snapshot of what the running system knows about itself.
**Scope**: Any change to AI_OS where *current facts from the DB* matter — identity, open goals, recent events, last errors, loop health, what the agent just noticed, what it just did.
**Rule**: Read STATE first, then act. The DB is the source of truth, not your summary.

---

## Why this profile exists

Normal coding agents work from a static snapshot of the repo. This one works from a **live snapshot of the running system** — the same STATE block the agent sees at inference time, assembled from the same orchestrator, reading the same `data/db/state.db`.

That means:
- You see the user's **real** identity facts (name, project, timeline, preferences).
- You see the **real** recent events in the log thread.
- You see the **current** goals, loop outputs, tool call history.
- You see what the **previous turn's** loops wrote — so consecutive turns compound.

If STATE is missing something you need, the fix isn't a workaround. The fix is to make STATE include that thing. That's how the system improves.

---

## Turn-Start Ritual (non-optional)

Run this once, at the start of every turn, before reading files or planning:

```bash
.venv/bin/python scripts/turn_start.py "<user's request in one line>"
```

This is the **only** sanctioned entry point for a coding turn. It:

1. Stamps `data/.last_state_read` so you can prove the ritual fired.
2. Prints the same STATE block the running agent sees, from `agent.subconscious.orchestrator.get_subconscious().get_state(query)`.
3. Flags any zero-fact thread blocks up front, so broken threads aren't hidden inside a long dump.
4. Prints `ritual-ok` when it succeeds.

STATE is ~3–10 KB: identity • form (tools) • log (recent events) • reflex (learned patterns) • plus any top-level modules that score relevant (chat, workspace, goals, feeds…).

**Read the whole block.** Don't skim. The facts you need are often in a thread you didn't expect.

If the block is empty or errors, STATE itself is broken — that takes priority over the user's request.

---

## How to Use What You Find

| Block | If present, means… | Act on it by… |
|-------|-------------------|---------------|
| `identity.primary_user.*` | Stable user facts (name, project, timeline). | Never ask again. Use them. |
| `identity.machine.name` | The agent's chosen name. | Refer to it by that name, not "Agent". |
| `log.session.*` + recent events | What has happened lately. | Don't repeat work already done in the last hour. |
| `goals.open` | Live goals with priorities. | Align changes with top-priority goal, or state why not. |
| `form.tools.*` | What tools the running agent can call. | New features that require a tool → add it to the tool registry. |
| `reflex.*` | Patterns the system learned. | Reuse or extend them rather than reinventing. |
| `workspace.*` | Files the agent is aware of. | Don't re-describe files it already tracks. |
| `chat.recent` | Conversations already had. | Refer back; don't ask the user to re-explain. |

---

## What to Do When STATE Is Missing Something

This is the flywheel. If you need a fact that STATE doesn't surface:

1. **Don't work around it.** Don't read the DB directly to get it for this one turn.
2. **Find the thread that owns that fact type.** (identity for people, log for events, form for tools, goals for goals, reflex for patterns, workspace for files.)
3. **Extend its adapter's `introspect()`** so the fact flows up through the standard score → level → threshold pipeline.
4. **Verify** by rerunning `scripts/build_state.py` — the new fact should appear next turn, for you and for the live agent simultaneously.

This is the point of the profile: improvements made for the coding agent's context automatically improve the running agent's context.

---

## Coding Discipline (inherits from `agent.agent.md`)

All of `agent.agent.md` still applies. Specifically:

- **No emojis in runtime output** (they break small models).
- **Schema → adapter → api → frontend** order is non-negotiable.
- **Threads never import each other.** Shared data flows through the orchestrator.
- **`get_connection()` + `with closing()`** for every DB touch. Set `readonly=True` when you're only reading.
- **`resolve_role(role)`** before any LLM call. Don't hardcode provider/model.
- **New tables need `init_*_tables()`** called from `scripts/server.py` startup.

And from `plan.agent.md`:

- **Read before you write.** The codebase solves half the problem already.
- **Blast radius** lives at the top of every non-trivial plan.
- **Verification step** ends every plan.

---

## Turn-End Ritual

After a substantive change, rerun the ritual:

```bash
.venv/bin/python scripts/turn_start.py "post-change check"
```

Check that:
- `prior turn-start: <Ns> ago` — proves this turn actually started with the ritual. If it says "none" or the gap is large, you skipped it; own it.
- Any fact you expected to appear is there.
- No `!! zero-fact blocks:` warning for a thread that should have data.
- `log` picked up whatever event your change emitted (if it emits one).
- `form.tools.*` shows new tools if you added any.

If STATE degraded, the change broke something. Fix it before declaring done.

---

## One-Line Summary

> **Read the system before you change it. Change the system so the next read is better.**
