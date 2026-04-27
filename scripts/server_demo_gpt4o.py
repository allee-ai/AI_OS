#!/usr/bin/env python3
"""GPT-4o-backed public demo server.

Same FastAPI app as scripts/server.py, but locked down so a public visitor
on the website can talk to Nola via OpenAI gpt-4o while everything else is
disabled.

What's enabled:
    • /api/chat/* sends → gpt-4o (your OPENAI_API_KEY)
    • Reads on every other endpoint (so the UI renders STATE, threads, etc.)

What's blocked:
    • All background LLM roles (memory, consolidation, naming, summary,
      thought, goal, evolve, …) → canned reply, zero token cost
    • All POST/PUT/PATCH/DELETE on /api/* outside the chat allowlist
    • All background loops
    • The owner's real database (uses state_demo.db, sanitized)

Required env (set on the VM, NOT checked in):
    OPENAI_API_KEY=sk-...

Usage:
    .venv/bin/python scripts/server_demo_gpt4o.py
    PORT=8081 .venv/bin/python scripts/server_demo_gpt4o.py

Why this exists:
    • Lets the public website's demo page actually talk to a working Nola
    • Tests the full STATE → context-assembly pipeline against gpt-4o-quality
      generation, which surfaces continuity bugs that a 7B local model masks
    • Costs are bounded: only chat burns tokens, and the read-only middleware
      keeps visitors from triggering loops or writes
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Pin demo behavior BEFORE importing the server module ─────────────
# These are not user-overridable from outside the process.
os.environ["AIOS_MODE"] = "demo"             # use state_demo.db
os.environ["AIOS_READ_ONLY"] = "1"           # POST/PUT/PATCH/DELETE → 403 (chat allowlist applies)
os.environ["AIOS_LOOPS"] = ""                # no background loops

# Allow LLM calls in demo mode (default is to block them entirely).
os.environ["AIOS_DEMO_ALLOW_LLM"] = "1"

# But ONLY for the user-facing chat. Every other role gets a canned reply.
os.environ["AIOS_DEMO_LLM_CHAT_ONLY"] = "1"

# Pin the chat role to OpenAI gpt-4o.
os.environ["AIOS_CHAT_PROVIDER"] = "openai"
os.environ["AIOS_CHAT_MODEL"] = "gpt-4o"

# Sanity check: refuse to start without an OpenAI key.
if not os.getenv("OPENAI_API_KEY", "").strip():
    print("ERROR: OPENAI_API_KEY is not set.")
    print("       This server requires an OpenAI key to back the chat path.")
    print("       Set it in your VM environment before launching:")
    print("           export OPENAI_API_KEY=sk-...")
    sys.exit(2)

# Project root on path for `import scripts.server`
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Force-set the mode file so set_demo_mode/is_demo_mode return demo immediately.
from data.db import set_demo_mode  # noqa: E402

set_demo_mode(True)

# Import the real server (this triggers app construction with read-only middleware).
import scripts.server as _server  # noqa: E402

app = _server.app


def main() -> int:
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8081"))

    # Mask the key for logging.
    key = os.getenv("OPENAI_API_KEY", "")
    masked = (key[:7] + "…" + key[-4:]) if len(key) > 12 else "set"

    print("=" * 64)
    print(" AI_OS PUBLIC DEMO  (GPT-4o-backed chat)")
    print("=" * 64)
    print(f" host:        {host}:{port}")
    print(f" db:          state_demo.db  (sanitized)")
    print(f" chat llm:    openai / gpt-4o  (key {masked})")
    print(f" other llms:  BLOCKED  (canned reply)")
    print(f" writes:      BLOCKED  (chat allowlist only)")
    print(f" loops:       OFF")
    print("=" * 64)
    print(" CORS reminder: configure scripts/server.py CORS origins to")
    print("                allow your public site origin (allee-ai.com,")
    print("                or whatever GitHub Pages host you deploy from).")
    print("=" * 64)

    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
