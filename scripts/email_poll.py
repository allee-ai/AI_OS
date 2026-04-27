#!/usr/bin/env python3
"""scripts/email_poll.py — poll all enabled email feeds, write to sensory bus.

Usage:
    scripts/email_poll.py                  # poll all enabled email feeds once
    scripts/email_poll.py --feed <id>      # poll one specific feed (must be enabled)
    scripts/email_poll.py --dry-run        # connect+fetch but do not record_event
    scripts/email_poll.py --verbose        # extra logging

Designed to be safe to run from cron / reflex schedule loop. Each feed is
isolated: a failure in one feed does not block others.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── Load .env so PROTON_BRIDGE_PASS et al are available ────────────
def _load_env_file() -> None:
    import os
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass


_load_env_file()


from sensory.schema import (  # noqa: E402
    init_sensory_feeds_table,
    get_feeds,
    mark_feed_run,
    mark_feed_error,
)
from sensory.feeds.proton_imap import poll_once  # noqa: E402


def _poll_one(feed: dict, *, dry_run: bool, verbose: bool) -> dict:
    name = f"#{feed['id']} {feed['source']}/{feed['feed_kind']} \"{feed['display_name']}\""
    if verbose:
        print(f"[poll] {name} starting...")

    if dry_run:
        # poll_once now respects dry_run — fetches but does NOT call record_event
        result = poll_once(feed, dry_run=True)
        print(
            f"[dry-run] {name}: polled={result['polled']} would_record={result['recorded']} "
            f"skipped={result['skipped']} errors={result['errors']}"
        )
        if result.get("error_msg"):
            print(f"[dry-run] {name}: error = {result['error_msg']}")
        return result

    result = poll_once(feed)
    if result.get("error_msg") and result["polled"] == 0:
        # Hard failure (no messages even attempted)
        mark_feed_error(feed["id"], result["error_msg"])
        print(f"[error] {name}: {result['error_msg']}")
        return result

    # Soft success (any messages attempted) — advance cursor + clear errors
    mark_feed_run(feed["id"], cursor=result.get("cursor"))
    print(
        f"[ok] {name}: polled={result['polled']} recorded={result['recorded']} "
        f"skipped={result['skipped']} errors={result['errors']} cursor={result.get('cursor')}"
    )
    if result.get("error_msg"):
        # Non-fatal but worth surfacing
        print(f"[warn] {name}: {result['error_msg']}")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Poll enabled email feeds.")
    ap.add_argument("--feed", type=int, help="poll only this feed id")
    ap.add_argument("--dry-run", action="store_true", help="connect + fetch but do not record")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    init_sensory_feeds_table()
    all_feeds = [f for f in get_feeds(enabled_only=True) if f["source"] == "email"]
    if args.feed is not None:
        all_feeds = [f for f in all_feeds if f["id"] == args.feed]

    if not all_feeds:
        print("(no enabled email feeds)" if args.feed is None
              else f"(feed #{args.feed} not found or not enabled email feed)")
        return 0

    total_recorded = 0
    total_errors = 0
    for f in all_feeds:
        try:
            r = _poll_one(f, dry_run=args.dry_run, verbose=args.verbose)
            total_recorded += r.get("recorded", 0)
            total_errors += r.get("errors", 0)
            if r.get("error_msg") and r.get("polled", 0) == 0:
                total_errors += 1
        except Exception as e:
            total_errors += 1
            mark_feed_error(f["id"], f"unhandled poll exception: {e}")
            print(f"[fatal] feed #{f['id']}: {e}", file=sys.stderr)

    print(f"--- summary: recorded={total_recorded} errors={total_errors} feeds={len(all_feeds)}")
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
