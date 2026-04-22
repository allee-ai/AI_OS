#!/usr/bin/env python3
"""
scripts/send_to_vs.py — Type a message into VS Code's Copilot Chat input.

How it works:
  1. Check HID idle time. If user has been typing/mousing in the last
     --idle-seconds (default 5), abort unless --force. This prevents
     stealing focus mid-keystroke.
  2. Copy message to clipboard via pbcopy.
  3. AppleScript: activate VS Code → focus Copilot Chat panel
     (ctrl+cmd+i is the default Copilot Chat Focus shortcut) →
     Cmd+V (paste) → Return.

Why clipboard paste instead of `keystroke "text"`:
  - keystroke mangles non-ASCII, quote chars, and is slow for long text.
  - Paste is O(1) regardless of message length.

Why ctrl+cmd+i instead of cmd+shift+i:
  - cmd+shift+i has historically been other things (DevTools etc);
    the VS Code default "Copilot Chat: Focus Chat Input" in recent
    releases is ctrl+cmd+i. Configurable via --chat-shortcut.

Dependencies: stdlib only. Requires macOS Accessibility permission for
whatever terminal/VS Code process invokes this.

Exit codes:
  0  — keystrokes dispatched
  2  — aborted due to idle guard
  3  — non-Darwin
  4  — VS Code not running / AppleScript failed
"""
from __future__ import annotations

import argparse
import platform
import re
import shutil
import subprocess
import sys
import time


def _hid_idle_seconds() -> float:
    """Return seconds since last HID (keyboard/mouse) event on macOS."""
    try:
        out = subprocess.check_output(
            ["ioreg", "-c", "IOHIDSystem"],
            stderr=subprocess.DEVNULL, timeout=3,
        ).decode("utf-8", errors="replace")
    except Exception:
        return 0.0
    # HIDIdleTime is in nanoseconds. Take the minimum across entries.
    matches = re.findall(r'"HIDIdleTime"\s*=\s*(\d+)', out)
    if not matches:
        return 0.0
    ns = min(int(m) for m in matches)
    return ns / 1_000_000_000.0


def _copy_to_clipboard(text: str) -> None:
    p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
    p.communicate(input=text.encode("utf-8"))


def _run_osascript(script: str) -> int:
    try:
        cp = subprocess.run(
            ["osascript", "-e", script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
        )
        if cp.returncode != 0:
            sys.stderr.write(cp.stderr.decode("utf-8", errors="replace"))
        return cp.returncode
    except Exception as e:
        sys.stderr.write(f"osascript failed: {e}\n")
        return 1


# Apple key codes for reference: 36 = Return, 53 = Escape
_CHAT_SHORTCUT_APPLESCRIPT = {
    # key code 34 = "i" on US layout
    "ctrl+cmd+i": 'keystroke "i" using {control down, command down}',
    "cmd+shift+i": 'keystroke "i" using {command down, shift down}',
    # Newer VS Code: "Chat: Focus Chat Input" often bound to
    # cmd+alt+b for side bar or custom; expose as override.
    "cmd+alt+i": 'keystroke "i" using {command down, option down}',
    # "palette" is special — handled below by opening Cmd+Shift+P and
    # typing the command name. This is toggle-proof: the palette always
    # opens, the named command always focuses chat (never closes it).
    "palette": "__PALETTE__",
}


def send_to_vs(
    message: str,
    submit: bool = True,
    chat_shortcut: str = "palette",
    settle_ms: int = 250,
) -> int:
    if platform.system() != "Darwin":
        sys.stderr.write("send_to_vs: only supported on macOS\n")
        return 3
    if not message.strip():
        sys.stderr.write("send_to_vs: empty message, nothing to send\n")
        return 0

    shortcut_cmd = _CHAT_SHORTCUT_APPLESCRIPT.get(
        chat_shortcut, _CHAT_SHORTCUT_APPLESCRIPT["palette"]
    )

    _copy_to_clipboard(message)

    delay_s = max(settle_ms, 50) / 1000.0
    submit_line = 'key code 36' if submit else '-- no-submit'

    if shortcut_cmd == "__PALETTE__":
        # Toggle-proof focus: open Command Palette, type the focus
        # command, press Enter. Always lands in the chat input whether
        # the panel was already open, closed, or hidden.
        focus_block = (
            '        -- Open Command Palette\n'
            '        keystroke "p" using {command down, shift down}\n'
            f'        delay {delay_s}\n'
            '        -- Type the focus command (not toggle)\n'
            '        keystroke "Chat: Focus Chat Input"\n'
            f'        delay {delay_s}\n'
            '        -- Run it\n'
            '        key code 36\n'
            f'        delay {delay_s}\n'
        )
    else:
        focus_block = (
            '        -- Focus the Copilot Chat input\n'
            f'        {shortcut_cmd}\n'
            f'        delay {delay_s}\n'
        )

    script = f'''
tell application "Visual Studio Code" to activate
delay {delay_s}
tell application "System Events"
    tell process "Code"
{focus_block}
        -- Paste clipboard
        keystroke "v" using command down
        delay {delay_s}
        -- Submit
        {submit_line}
    end tell
end tell
'''
    rc = _run_osascript(script)
    if rc != 0:
        sys.stderr.write(
            "\nHint: this needs macOS Accessibility permission.\n"
            "Open System Settings → Privacy & Security → Accessibility,\n"
            "and enable the app running this script (usually 'Terminal'\n"
            "or your VS Code terminal host).\n"
        )
    return 0 if rc == 0 else 4


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Type a message into VS Code Copilot Chat via AppleScript."
    )
    ap.add_argument("message", help="Text to send to the chat input.")
    ap.add_argument(
        "--no-submit", action="store_true",
        help="Paste the text but do not press Enter.",
    )
    ap.add_argument(
        "--idle-seconds", type=float, default=5.0,
        help="Abort if user HID activity within this window. 0 disables guard.",
    )
    ap.add_argument(
        "--force", action="store_true",
        help="Bypass the idle guard.",
    )
    ap.add_argument(
        "--chat-shortcut", choices=sorted(_CHAT_SHORTCUT_APPLESCRIPT.keys()),
        default="palette",
        help="How to focus the Copilot Chat input. 'palette' (default) "
             "opens the Command Palette and runs 'Chat: Focus Chat Input' — "
             "toggle-proof, works whether the panel is open or closed.",
    )
    ap.add_argument(
        "--settle-ms", type=int, default=250,
        help="Delay between AppleScript steps (ms).",
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Print what would happen, don't touch keystrokes or clipboard.",
    )
    args = ap.parse_args()

    if platform.system() != "Darwin":
        print("send_to_vs: only supported on macOS", file=sys.stderr)
        return 3

    if args.idle_seconds > 0 and not args.force:
        idle = _hid_idle_seconds()
        if idle < args.idle_seconds:
            print(
                f"send_to_vs: aborted — user active {idle:.1f}s ago "
                f"(threshold={args.idle_seconds}s). Use --force to override.",
                file=sys.stderr,
            )
            return 2

    if args.dry_run:
        print(f"[dry-run] would send to VS Code ({len(args.message)} chars, "
              f"submit={not args.no_submit}, shortcut={args.chat_shortcut})")
        return 0

    return send_to_vs(
        args.message,
        submit=not args.no_submit,
        chat_shortcut=args.chat_shortcut,
        settle_ms=args.settle_ms,
    )


if __name__ == "__main__":
    sys.exit(main())
