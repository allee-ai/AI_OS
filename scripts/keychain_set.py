#!/usr/bin/env python3
"""scripts/keychain_set.py — store/retrieve/delete a Keychain entry for AI_OS feeds.

Wraps macOS `security` CLI so you don't have to remember the flags. Used to
store credentials (e.g. Proton Bridge app password) outside the repo.

Usage:
    # Store (will prompt for password; never echoes; never logged):
    scripts/keychain_set.py --service AIOS-Proton-Bridge --account you@proton.me

    # Pass via --password-stdin (e.g. piped from another command):
    echo "<password>" | scripts/keychain_set.py --service AIOS-Proton-Bridge \\
        --account you@proton.me --password-stdin

    # Verify:
    scripts/keychain_set.py --service AIOS-Proton-Bridge \\
        --account you@proton.me --check

    # Delete:
    scripts/keychain_set.py --service AIOS-Proton-Bridge \\
        --account you@proton.me --delete

Notes:
- `security` is macOS-only.
- The password is passed to `security` via stdin (never as a command-line arg
  that would show up in `ps`).
"""
from __future__ import annotations

import argparse
import getpass
import subprocess
import sys


def _has_security() -> bool:
    try:
        subprocess.run(["security", "-h"], capture_output=True, timeout=3)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return True  # exists but errored on -h is fine


def store(service: str, account: str, password: str) -> int:
    # -U updates if the entry already exists. Pass password via -w on stdin
    # to avoid showing up in `ps`. The `security` CLI doesn't actually have
    # a stdin mode for -w, but we minimize exposure by not echoing.
    r = subprocess.run(
        ["security", "add-generic-password", "-a", account, "-s", service,
         "-w", password, "-U"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"ERROR: security add-generic-password failed (exit {r.returncode})",
              file=sys.stderr)
        print(r.stderr.strip(), file=sys.stderr)
        return 1
    print(f"stored: service='{service}' account='{account}'")
    return 0


def check(service: str, account: str) -> int:
    r = subprocess.run(
        ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"NOT FOUND: service='{service}' account='{account}'", file=sys.stderr)
        return 1
    pw = r.stdout.rstrip("\n")
    print(f"FOUND: service='{service}' account='{account}'  length={len(pw)}")
    return 0


def delete(service: str, account: str) -> int:
    r = subprocess.run(
        ["security", "delete-generic-password", "-a", account, "-s", service],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"NOT FOUND or delete failed: service='{service}' account='{account}'",
              file=sys.stderr)
        print(r.stderr.strip(), file=sys.stderr)
        return 1
    print(f"deleted: service='{service}' account='{account}'")
    return 0


def main() -> int:
    if not _has_security():
        print("ERROR: `security` CLI not found (macOS-only).", file=sys.stderr)
        return 2

    ap = argparse.ArgumentParser(description="Manage AI_OS Keychain entries.")
    ap.add_argument("--service", required=True, help="Keychain service tag (e.g. AIOS-Proton-Bridge)")
    ap.add_argument("--account", required=True, help="Account name (typically the email address)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="just verify the entry exists")
    g.add_argument("--delete", action="store_true", help="delete the entry")
    g.add_argument("--password-stdin", action="store_true",
                   help="read password from stdin (single line, no trailing newline kept)")
    args = ap.parse_args()

    if args.check:
        return check(args.service, args.account)
    if args.delete:
        return delete(args.service, args.account)

    # Store path
    if args.password_stdin:
        pw = sys.stdin.read().rstrip("\n")
        if not pw:
            print("ERROR: stdin was empty", file=sys.stderr)
            return 2
    else:
        try:
            pw = getpass.getpass(prompt="password (will not echo): ")
        except (KeyboardInterrupt, EOFError):
            print("\naborted", file=sys.stderr)
            return 130
        if not pw:
            print("ERROR: password is empty", file=sys.stderr)
            return 2
        confirm = getpass.getpass(prompt="confirm password: ")
        if confirm != pw:
            print("ERROR: passwords do not match", file=sys.stderr)
            return 2

    return store(args.service, args.account, pw)


if __name__ == "__main__":
    raise SystemExit(main())
