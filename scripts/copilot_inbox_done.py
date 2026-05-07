"""
scripts/copilot_inbox_done.py — close a copilot_request after acting.

Usage:
    # Local copilot_request (rare; mostly the requests come from droplet)
    python scripts/copilot_inbox_done.py <local_card_id>
    python scripts/copilot_inbox_done.py <local_card_id> --note "shipped X"

    # Request that originated on the droplet (the common path)
    python scripts/copilot_inbox_done.py --droplet <droplet_card_id>
    python scripts/copilot_inbox_done.py --droplet 42 --note "done in commit deadbeef"

What it does:
    1. Removes the workspace mirror file (so VS Code's tree clears).
    2. If --droplet: POSTs to the remote /api/outbox/{id}/approve so the
       phone-side sees the request closed.
    3. If local id: marks the local outbox row approved.

The split exists because phone requests live on the droplet (always-on),
not the laptop.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _git_head_sha() -> str | None:
    """Best-effort: return short SHA of current HEAD."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=3,
        )
        if out.returncode == 0:
            return out.stdout.strip() or None
    except Exception:
        return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="close a copilot_request after acting")
    ap.add_argument("card_id", nargs="?", type=int, help="local outbox card id")
    ap.add_argument("--droplet", type=int, default=None,
                    help="close a remote droplet outbox card by id")
    ap.add_argument("--note", default=None,
                    help="resolution note (commit SHA auto-appended if available)")
    ap.add_argument("--no-sha", action="store_true",
                    help="skip auto-appending current HEAD short SHA to note")
    args = ap.parse_args()

    if args.card_id is None and args.droplet is None:
        ap.error("provide a local card id OR --droplet <id>")

    note = args.note or "done"
    if not args.no_sha:
        sha = _git_head_sha()
        if sha:
            note = f"{note} [HEAD {sha}]"

    from outbox import copilot_inbox as cinbox

    # Local close (when the request was created locally)
    if args.card_id is not None:
        card = cinbox.mark_done(args.card_id, note=note)
        if card is None:
            print(f"!! local card {args.card_id} not found", file=sys.stderr)
            return 2
        print(f"✓ local card {args.card_id} closed  ({note})")
        if args.droplet is None:
            return 0

    # Droplet close (the common phone-originated path)
    if args.droplet is not None:
        droplet_id = int(args.droplet)
        # Remove the local mirror first (uses the 9xxxxxx synthetic id)
        mirror_id = 900000 + droplet_id
        cinbox._remove_mirror(mirror_id)
        ok = cinbox.mark_droplet_done(droplet_id, note=note)
        if not ok:
            print(
                f"!! could not POST close to droplet "
                f"(check AIOS_DROPLET_URL / AIOS_API_TOKEN env vars)",
                file=sys.stderr,
            )
            print(
                f"   local mirror removed; remote card #{droplet_id} "
                "still pending on droplet.",
                file=sys.stderr,
            )
            return 3
        print(f"✓ droplet card {droplet_id} closed  ({note})")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
