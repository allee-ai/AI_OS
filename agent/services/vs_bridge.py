"""
VS Code Chat Bridge
===================
Forward a message into the active VS Code Copilot Chat window on this Mac,
with a once-per-day ritual banner that injects yesterday's closeout so the
Copilot side always knows where we left off.

Used by:
  - agent/services/llm.VSCodeKeyboardProvider (phone chat → Copilot)
  - agent/subconscious/loops/goals.propose_goal (phone goal → Copilot)
  - any other code that wants to type into this Copilot chat

Date-roll model: we stay in the same VS Code chat (no Cmd+N). When the
date changes, we prepend a divider + yesterday's summary to the next
forwarded message. Simpler, 100% reliable, and the scrollback itself
becomes the long-running session log.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SEND_SCRIPT = _REPO_ROOT / "scripts" / "send_to_vs.py"
_STATE_FILE = _REPO_ROOT / "data" / ".last_vs_session_date"


def _read_last_date() -> Optional[str]:
    try:
        return _STATE_FILE.read_text().strip() or None
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _write_last_date(day: str) -> None:
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(day + "\n")
    except Exception:
        pass


def _build_rollover_banner(today: str, previous: Optional[str]) -> str:
    """Ritual banner prepended to the first forward of a new day."""
    try:
        from scripts.day_closeout import build_closeout
        summary = build_closeout(previous)
    except Exception as e:
        summary = f"[closeout generator failed: {e}]"

    prev_line = previous or "(none on record)"
    return (
        f"─── aios session roll → {today} ───\n"
        f"previous session: {prev_line}\n\n"
        f"{summary}\n\n"
        f"─── run ritual then continue ───\n\n"
    )


def forward(text: str, source: str = "unknown", submit: bool = True) -> bool:
    """Forward text into VS Code Copilot Chat on this Mac.

    On a new calendar day, prepends a rollover banner with yesterday's
    closeout summary. Updates the date state file after a successful send.

    Returns True on successful keystroke dispatch, False otherwise. Never
    raises — callers shouldn't care if the keyboard bridge is unavailable.
    """
    if not text or not text.strip():
        return False
    if not _SEND_SCRIPT.exists():
        return False

    today = date.today().isoformat()
    last = _read_last_date()
    if last != today:
        banner = _build_rollover_banner(today, last)
        text = banner + text

    max_chars = int(os.getenv("AIOS_KEYBOARD_MAX_CHARS", "8000"))
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[truncated at {max_chars} chars]"

    cmd = [sys.executable, str(_SEND_SCRIPT), text, "--idle-seconds", "0"]
    if not submit:
        cmd.append("--no-submit")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception:
        return False

    if proc.returncode != 0:
        return False

    _write_last_date(today)
    try:
        from agent.threads.log.schema import log_event
        log_event(
            event_type="vs_bridge:forward",
            data=f"[{source}] {text[:120]}",
            metadata={"source": source, "chars": len(text), "rolled": last != today},
            source="vs_bridge",
        )
    except Exception:
        pass
    return True
