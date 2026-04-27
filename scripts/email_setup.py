#!/usr/bin/env python3
"""scripts/email_setup.py — one-shot helpers for setting up email feeds.

Two subcommands:

  schedule        Install the cron trigger that polls all enabled email feeds
                  every N minutes (default 5). Idempotent.

  register-proton Register a Proton Bridge feed with Keychain credentials
                  (preferred) or env-var credentials. Idempotent (upsert).

Examples:
    scripts/email_setup.py schedule
    scripts/email_setup.py schedule --every 10

    scripts/email_setup.py register-proton --address alleeroden@pm.me \\
        --name allee-ai --keychain-service AIOS-Proton-Bridge

    scripts/email_setup.py register-proton --address you@proton.me \\
        --name personal --env PROTON_BRIDGE_PASS
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Subcommand: schedule
# ---------------------------------------------------------------------------

CRON_NAME = "email-poll"


def cmd_schedule(every_minutes: int) -> int:
    """Install (or replace) the email_poll cron trigger.

    response_mode='tool' → fires the `terminal/run_command` tool every tick,
    which runs `.venv/bin/python scripts/email_poll.py` from workspace root.
    """
    from contextlib import closing
    from data.db import get_connection
    from agent.threads.reflex.schema import (
        init_triggers_table, create_trigger,
    )

    if every_minutes < 1 or every_minutes > 60:
        print("--every must be between 1 and 60", file=sys.stderr)
        return 2

    cron_expr = f"*/{every_minutes} * * * *" if every_minutes != 1 else "* * * * *"

    # Check existing
    with closing(get_connection()) as conn:
        init_triggers_table(conn)
        existing = conn.execute(
            "SELECT id, cron_expression, enabled FROM reflex_triggers WHERE name = ?",
            (CRON_NAME,),
        ).fetchone()

    if existing:
        # Update via direct UPDATE since the public API doesn't expose a "replace"
        with closing(get_connection()) as conn:
            conn.execute(
                """UPDATE reflex_triggers
                   SET cron_expression = ?, enabled = 1,
                       trigger_type = 'schedule', response_mode = 'tool',
                       tool_name = 'terminal', tool_action = 'run_command',
                       tool_params_json = ?
                   WHERE id = ?""",
                (
                    cron_expr,
                    json.dumps({"command": ".venv/bin/python scripts/email_poll.py"}),
                    existing["id"],
                ),
            )
            conn.commit()
        print(f"updated trigger #{existing['id']} ({CRON_NAME}): cron='{cron_expr}'")
        return 0

    trigger_id = create_trigger(
        name=CRON_NAME,
        feed_name="schedule",
        event_type="cron_fired",
        tool_name="terminal",
        tool_action="run_command",
        description=f"Poll all enabled email feeds every {every_minutes} minute(s).",
        trigger_type="schedule",
        cron_expression=cron_expr,
        tool_params={"command": ".venv/bin/python scripts/email_poll.py"},
        priority=5,
        response_mode="tool",
    )
    print(f"created trigger #{trigger_id} ({CRON_NAME}): cron='{cron_expr}'")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: register-proton
# ---------------------------------------------------------------------------

def cmd_register_proton(
    *,
    address: str,
    name: str,
    keychain_service: str | None,
    keychain_account: str | None,
    env_var: str | None,
    host: str,
    port: int,
    mailbox: str,
    max_per_poll: int,
    initial_fetch: int,
) -> int:
    from sensory.schema import (
        init_sensory_feeds_table, register_feed,
    )

    if not (keychain_service or env_var):
        print("ERROR: provide either --keychain-service or --env", file=sys.stderr)
        return 2

    config: dict = {
        "host": host,
        "port": port,
        "username": address,
        "mailbox": mailbox,
        "max_per_poll": max_per_poll,
        "initial_fetch": initial_fetch,
        # Bridge defaults
        "use_ssl": False,
        "starttls": True,
        "verify_cert": False,
    }

    if keychain_service:
        config["password_keychain"] = {
            "service": keychain_service,
            "account": keychain_account or address,
        }
    if env_var:
        config["password_env"] = env_var

    init_sensory_feeds_table()
    fid = register_feed(
        source="email",
        feed_kind="imap",
        display_name=name,
        enabled=False,  # always register disabled; --enable separately
        config=config,
    )
    if fid is None:
        print("ERROR: register_feed returned None", file=sys.stderr)
        return 1

    print(f"feed #{fid} registered (DISABLED): email/imap \"{name}\"")
    print(f"  username: {address}")
    print(f"  host:     {host}:{port} (STARTTLS)")
    print(f"  cred:     "
          f"{'keychain ' + (keychain_service or '') if keychain_service else 'env ' + (env_var or '')}")
    print()
    print("Next steps (when Proton Bridge is running on 127.0.0.1:1143):")
    print(f"  scripts/sensory_feeds.py --enable {fid} --with-consent")
    print(f"  scripts/email_poll.py --feed {fid} --dry-run")
    print(f"  scripts/email_poll.py --feed {fid}")
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Email feed setup helpers.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp_sched = sub.add_parser("schedule", help="install email-poll cron trigger")
    sp_sched.add_argument("--every", type=int, default=5,
                          help="poll interval in minutes (1-60, default 5)")

    sp_reg = sub.add_parser("register-proton", help="register a Proton Bridge feed")
    sp_reg.add_argument("--address", required=True, help="full Proton address (IMAP username)")
    sp_reg.add_argument("--name", required=True, help="display name for the feed (e.g. allee-ai)")
    sp_reg.add_argument("--keychain-service",
                        help="Keychain service tag (e.g. AIOS-Proton-Bridge)")
    sp_reg.add_argument("--keychain-account",
                        help="Keychain account (defaults to --address)")
    sp_reg.add_argument("--env", dest="env_var",
                        help="env var name for password (fallback if no keychain)")
    sp_reg.add_argument("--host", default="127.0.0.1")
    sp_reg.add_argument("--port", type=int, default=1143)
    sp_reg.add_argument("--mailbox", default="INBOX")
    sp_reg.add_argument("--max-per-poll", type=int, default=20)
    sp_reg.add_argument("--initial-fetch", type=int, default=5)

    args = ap.parse_args()

    if args.cmd == "schedule":
        return cmd_schedule(args.every)
    if args.cmd == "register-proton":
        return cmd_register_proton(
            address=args.address,
            name=args.name,
            keychain_service=args.keychain_service,
            keychain_account=args.keychain_account,
            env_var=args.env_var,
            host=args.host,
            port=args.port,
            mailbox=args.mailbox,
            max_per_poll=args.max_per_poll,
            initial_fetch=args.initial_fetch,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
