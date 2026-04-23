#!/usr/bin/env python3
"""Demo server wrapper.

Boots the same FastAPI app as scripts/server.py, but with the demo DB,
LLM calls disabled, and read-only middleware enforced.

Usage:
    .venv/bin/python scripts/server_demo.py
    PORT=8081 .venv/bin/python scripts/server_demo.py

Env vars set here (cannot be overridden from outside):
    AIOS_MODE=demo          → use state_demo.db
    AIOS_NO_LLM=1           → generate() returns canned reply
    AIOS_READ_ONLY=1        → POST/PUT/PATCH/DELETE on /api/* return 403
                              (with a small allowlist for chat + sensory record)
    AIOS_LOOPS=             → never auto-start background loops on the demo

This is a separate process so the demo deployment can run alongside your
personal instance on the same VM (different port) without any state crossover.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Pin demo behavior BEFORE importing the server module.
# These are not user-overridable from outside the process.
os.environ["AIOS_MODE"] = "demo"
os.environ["AIOS_NO_LLM"] = "1"
os.environ["AIOS_READ_ONLY"] = "1"
os.environ["AIOS_LOOPS"] = ""  # explicit empty — no background loops

# Ensure project root on path so `import scripts.server` works.
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Force-set the mode file so set_demo_mode/is_demo_mode return demo immediately.
from data.db import set_demo_mode  # noqa: E402

set_demo_mode(True)

# Now import server (this triggers app construction with the read-only middleware).
import scripts.server as _server  # noqa: E402

app = _server.app


def main() -> int:
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8081"))

    print("=" * 64)
    print(" AI_OS DEMO SERVICE")
    print("=" * 64)
    print(f" host:        {host}:{port}")
    print(f" db:          state_demo.db")
    print(f" llm:         BLOCKED (AIOS_NO_LLM=1)")
    print(f" writes:      BLOCKED (AIOS_READ_ONLY=1, allowlist applies)")
    print(f" loops:       OFF")
    print("=" * 64)

    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
