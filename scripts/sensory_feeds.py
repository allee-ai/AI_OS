#!/usr/bin/env python3
"""scripts/sensory_feeds.py — list / register / enable / disable sensory feeds.

The sensory bus accepts events from anywhere (POST /api/sensory/record). This
CLI manages the SIDE-TABLE that worker loops use to remember their cursor and
last-run state.

Usage:
    scripts/sensory_feeds.py --list
    scripts/sensory_feeds.py --register --source email --kind imap \\
        --name "personal-gmail" --config '{"host":"imap.gmail.com"}'
    scripts/sensory_feeds.py --enable <id>
    scripts/sensory_feeds.py --disable <id>

Registering does NOT enable. Enable explicitly so a worker doesn't start
poking external services the second a row appears in the table.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sensory.schema import (  # noqa: E402
    init_sensory_feeds_table,
    register_feed,
    get_feeds,
    set_feed_enabled,
)


def cmd_list() -> int:
    init_sensory_feeds_table()
    feeds = get_feeds()
    if not feeds:
        print("(no feeds registered)")
        return 0
    for f in feeds:
        en = "ON " if f.get("enabled") else "off"
        last = (f.get("last_run_at") or "never")[-19:]
        errs = f.get("error_count") or 0
        err_tag = f" err×{errs}" if errs else ""
        print(
            f"  #{f['id']:<3} [{en}] {f['source']:<10} / {f['feed_kind']:<8} "
            f"\"{f['display_name']}\"  last={last}{err_tag}"
        )
        if f.get("last_error"):
            print(f"        last_error: {f['last_error']}")
    return 0


def cmd_register(source: str, kind: str, name: str, config_json: str, enabled: bool) -> int:
    init_sensory_feeds_table()
    try:
        config = json.loads(config_json) if config_json else {}
    except json.JSONDecodeError as e:
        print(f"ERROR: --config must be valid JSON ({e})", file=sys.stderr)
        return 2
    fid = register_feed(
        source=source,
        feed_kind=kind,
        display_name=name,
        enabled=enabled,
        config=config,
    )
    if fid is None:
        print("ERROR: register failed (missing source/kind/name?)", file=sys.stderr)
        return 1
    state = "enabled" if enabled else "disabled (use --enable to turn on)"
    print(f"feed #{fid} {state}: {source}/{kind} \"{name}\"")
    return 0


def cmd_set_enabled(feed_id: int, enabled: bool) -> int:
    init_sensory_feeds_table()
    if set_feed_enabled(feed_id, enabled):
        print(f"feed #{feed_id} {'enabled' if enabled else 'disabled'}")
        return 0
    print(f"feed #{feed_id} not found", file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Manage sensory bus feeds.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--register", action="store_true")
    g.add_argument("--enable", type=int, metavar="ID")
    g.add_argument("--disable", type=int, metavar="ID")

    ap.add_argument("--source", help="canonical source tag (e.g. email, calendar)")
    ap.add_argument("--kind", help="feed mechanism (e.g. imap, oauth, polling)")
    ap.add_argument("--name", help="display name (unique per source/kind)")
    ap.add_argument("--config", default="{}", help="JSON config blob")
    ap.add_argument(
        "--start-enabled",
        action="store_true",
        help="enable on register (default: register disabled)",
    )
    args = ap.parse_args()

    if args.list:
        return cmd_list()
    if args.register:
        if not (args.source and args.kind and args.name):
            print("--register requires --source, --kind, --name", file=sys.stderr)
            return 2
        return cmd_register(
            args.source, args.kind, args.name, args.config, args.start_enabled
        )
    if args.enable is not None:
        return cmd_set_enabled(args.enable, True)
    if args.disable is not None:
        return cmd_set_enabled(args.disable, False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
