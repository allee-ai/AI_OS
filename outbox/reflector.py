"""
reflector — slow background "thought" motor.

Every N minutes (default 300s = 5min) the supervisor calls
``tick_once()``. We:

  1. Pull the same STATE block the live agent / turn_start sees.
  2. Hand it to a cloud LLM with a tight prompt: "given this state,
     produce ONE short thought — observation, question, suggestion,
     or contradiction noticed."
  3. Write the thought to ``workspace/_aios_thoughts/NNNN.md`` AND
     drop a low-priority notifications row so phone + turn_start
     surface it.

This is the minimum viable cognition loop:
    state mutates  →  thought emitted  →  observable

No outbox card, no approval flow, no DB mutation of identity. We're
practicing the loop before adding teeth. Once thoughts look honest
and grounded, we can promote the motor to write meta_thoughts /
propose facts / open goals.

Hard-pinned to ``provider='ollama'`` + ``AIOS_REFLECT_MODEL`` (default
gpt-oss:120b-cloud) so it never accidentally bills a paid provider.
"""

from __future__ import annotations

import json
import os
import re
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from data.db import get_connection

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT / "workspace"
THOUGHTS_DIR = WORKSPACE / "_aios_thoughts"

# ── Tunables ────────────────────────────────────────────────────────

REFLECT_ENABLED = os.getenv("AIOS_REFLECT_ENABLED", "1") == "1"
REFLECT_MODEL = os.getenv("AIOS_REFLECT_MODEL", "gpt-oss:120b-cloud")
# Token budget — one thought, not an essay. 600 leaves room for ~5
# sentences without truncation; smoke #1 hit the 240 cap mid-word.
REFLECT_MAX_TOKENS = int(os.getenv("AIOS_REFLECT_MAX_TOKENS", "600"))
REFLECT_TEMP = float(os.getenv("AIOS_REFLECT_TEMP", "0.6"))
# Optional query the subconscious uses to bias which threads score
# relevant. Empty = the default "what's going on right now" assembly.
REFLECT_QUERY = os.getenv("AIOS_REFLECT_QUERY", "")

PROMPT_TEMPLATE = """You are the reflective layer of AIOS, an always-on personal AI operating system whose primary user is Cade.

Below is the current STATE block — the facts, recent events, open goals, and tracked threads the live system is aware of right now. This is real data; ground every claim in it.

Produce exactly ONE short thought (max ~5 sentences). Pick whichever of these is most useful given what you see:
  - an OBSERVATION about a pattern or shift in recent activity
  - a QUESTION worth raising back to Cade (something the state implies but doesn't resolve)
  - a SUGGESTION for a next move that's clearly aligned with the top open goal
  - a CONTRADICTION you notice between two facts in state

Rules:
  - If state is sparse or you genuinely have nothing grounded to say, output exactly: "(no grounded thought this tick)"
  - Do NOT invent facts, names, projects, or numbers that aren't in state.
  - Do NOT restate the state back. Reference specific items briefly.
  - Plain prose. No headers, no lists, no preamble like "Here's a thought:".
  - First-person voice ("I notice...", "I wonder...", "It looks like...") is fine.

STATE:
---
{state}
---

ONE thought:"""


def _next_seq() -> int:
    THOUGHTS_DIR.mkdir(parents=True, exist_ok=True)
    nums = []
    for p in THOUGHTS_DIR.glob("*.md"):
        m = re.match(r"(\d+)", p.name)
        if m:
            try:
                nums.append(int(m.group(1)))
            except ValueError:
                pass
    return (max(nums) + 1) if nums else 1


def _emit_notification(thought: str, path: str) -> None:
    """Drop a low-priority row in notifications so phone + turn_start
    surface the thought without spamming."""
    try:
        snippet = thought.strip().replace("\n", " ")
        if len(snippet) > 180:
            snippet = snippet[:177] + "..."
        ctx = json.dumps({"path": path, "source": "reflector"})
        with closing(get_connection()) as conn:
            conn.execute(
                """INSERT INTO notifications
                   (type, message, priority, context, created_at)
                   VALUES (?, ?, ?, ?, datetime('now'))""",
                ("aios_thought", snippet, 0.3, ctx),
            )
            conn.commit()
    except Exception:
        # Don't fail a tick over notification plumbing.
        pass


def _generate_thought(state: str) -> str:
    """Cloud-grounded one-thought call. Returns stripped text."""
    from agent.services.llm import generate

    prompt = PROMPT_TEMPLATE.format(state=state[:18000])  # cap input
    raw = generate(
        prompt,
        provider="ollama",
        model=REFLECT_MODEL,
        max_tokens=REFLECT_MAX_TOKENS,
        temperature=REFLECT_TEMP,
    )
    return (raw or "").strip()


def tick_once() -> Dict[str, Any]:
    """Run a single reflector pass. Safe to call from supervisor.

    Returns a small dict the supervisor can log:
      {"emitted": 0|1, "skipped_disabled": bool, "elapsed_s": float,
       "path": str|None, "error": str|None}
    """
    if not REFLECT_ENABLED:
        return {"emitted": 0, "skipped_disabled": True, "elapsed_s": 0.0,
                "path": None, "error": None}

    t0 = time.monotonic()
    out: Dict[str, Any] = {"emitted": 0, "skipped_disabled": False,
                           "elapsed_s": 0.0, "path": None, "error": None}
    try:
        # Lazy import to keep run_loops light if the module is disabled.
        from agent.subconscious.orchestrator import get_subconscious
        sc = get_subconscious()
        state = sc.get_state(query=REFLECT_QUERY) or ""
        if not state.strip():
            out["error"] = "empty_state"
            out["elapsed_s"] = round(time.monotonic() - t0, 3)
            return out

        thought = _generate_thought(state)
        if not thought or thought == "(no grounded thought this tick)":
            out["elapsed_s"] = round(time.monotonic() - t0, 3)
            out["error"] = "no_grounded_thought" if not thought else None
            out["skipped_no_thought"] = True
            return out

        # Persist
        seq = _next_seq()
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        fname = f"{seq:04d}-{ts.replace(':','').replace('-','')}.md"
        path = THOUGHTS_DIR / fname
        body = (
            f"# AIOS thought #{seq}\n"
            f"_emitted {ts} • model {REFLECT_MODEL}_\n\n"
            f"{thought}\n"
        )
        path.write_text(body, encoding="utf-8")

        rel = str(path.relative_to(ROOT))
        _emit_notification(thought, rel)

        out["emitted"] = 1
        out["path"] = rel
        out["elapsed_s"] = round(time.monotonic() - t0, 3)
        return out
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
        out["elapsed_s"] = round(time.monotonic() - t0, 3)
        return out
