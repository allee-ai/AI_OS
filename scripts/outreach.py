#!/usr/bin/env python3
"""
scripts/outreach.py — CLI for the outreach queue (Nola's outbound).

Usage:
    outreach.py draft --to <email> --subject "..." --body-file <path> [--purpose tag]
    outreach.py draft --to <email> --subject "..." --body "inline text"
    outreach.py list [--status drafted|approved|sent|failed|rejected]
    outreach.py show <id>
    outreach.py approve <id> [--send-after ISO]
    outreach.py reject <id> [--reason "..."]
    outreach.py send <id> [--dry-run]
    outreach.py send-approved [--dry-run] [--max 50]

Send-gate: nothing is delivered until status='approved' AND `send` runs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from outreach import (  # noqa: E402
    init_outreach_tables,
    queue_draft,
    approve_draft,
    reject_draft,
    list_queue,
    get_item,
)
from outreach.sender import send_one, send_all_approved  # noqa: E402


def _load_body(args) -> str:
    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8")
    if args.body:
        return args.body
    print("error: --body or --body-file required", file=sys.stderr)
    sys.exit(2)


def cmd_draft(args) -> int:
    body = _load_body(args)
    new_id = queue_draft(
        to_email=args.to,
        to_name=args.to_name,
        subject=args.subject,
        body=body,
        contact_key=args.contact_key,
        purpose=args.purpose,
        thread_ref=args.thread_ref,
    )
    print(f"drafted #{new_id} → {args.to} :: {args.subject}")
    return 0


def cmd_list(args) -> int:
    rows = list_queue(status=args.status, limit=args.limit)
    if not rows:
        print(f"(no items{' with status=' + args.status if args.status else ''})")
        return 0
    for r in rows:
        sa = r.get("send_after") or ""
        sa_str = f"  send_after={sa}" if sa else ""
        print(f"#{r['id']:<4} [{r['status']:<9}] {r['to_email']:<35} :: "
              f"{r['subject'][:60]}{sa_str}")
    return 0


def cmd_show(args) -> int:
    r = get_item(args.id)
    if not r:
        print(f"no item #{args.id}", file=sys.stderr)
        return 1
    print(f"#{r['id']} [{r['status']}]  purpose={r.get('purpose') or '-'}")
    print(f"to:      {r.get('to_name') or ''} <{r['to_email']}>")
    print(f"subject: {r['subject']}")
    if r.get("thread_ref"):
        print(f"in-reply-to: {r['thread_ref']}")
    if r.get("send_after"):
        print(f"send_after: {r['send_after']}")
    if r.get("error"):
        print(f"error:   {r['error']}")
    if r.get("sent_at"):
        print(f"sent_at: {r['sent_at']}  message_id={r.get('sent_message_id')}")
    print()
    print(r["body"])
    return 0


def cmd_approve(args) -> int:
    ok = approve_draft(args.id, send_after=args.send_after)
    print(f"#{args.id} approved" if ok else f"could not approve #{args.id} (already approved or not drafted)")
    return 0 if ok else 1


def cmd_reject(args) -> int:
    ok = reject_draft(args.id, reason=args.reason)
    print(f"#{args.id} rejected" if ok else f"could not reject #{args.id}")
    return 0 if ok else 1


def cmd_send(args) -> int:
    r = send_one(args.id, dry_run=args.dry_run)
    if args.dry_run:
        print(f"[dry-run] {r}")
        return 0 if r.get("ok") else 1
    if r.get("ok"):
        print(f"#{args.id} sent  message_id={r.get('message_id')}")
        return 0
    print(f"#{args.id} send failed: {r.get('error')}", file=sys.stderr)
    return 1


def cmd_send_approved(args) -> int:
    results = send_all_approved(dry_run=args.dry_run, max_items=args.max)
    if not results:
        print("(nothing approved + due)")
        return 0
    ok = sum(1 for r in results if r.get("ok"))
    print(f"sent: {ok}/{len(results)}")
    for r in results:
        if not r.get("ok"):
            print(f"  failed #{r['item_id']}: {r.get('error')}")
    return 0 if ok == len(results) else 1


def main(argv: list[str] | None = None) -> int:
    init_outreach_tables()

    ap = argparse.ArgumentParser(prog="outreach.py")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pd = sub.add_parser("draft", help="queue a new outreach draft")
    pd.add_argument("--to", required=True)
    pd.add_argument("--to-name", default=None)
    pd.add_argument("--subject", required=True)
    pd.add_argument("--body", default=None)
    pd.add_argument("--body-file", default=None)
    pd.add_argument("--purpose", default="outreach")
    pd.add_argument("--contact-key", default=None)
    pd.add_argument("--thread-ref", default=None)

    pl = sub.add_parser("list")
    pl.add_argument("--status", default=None)
    pl.add_argument("--limit", type=int, default=50)

    psh = sub.add_parser("show")
    psh.add_argument("id", type=int)

    pa = sub.add_parser("approve")
    pa.add_argument("id", type=int)
    pa.add_argument("--send-after", default=None,
                    help="ISO timestamp; if set, send is delayed until then.")

    pr = sub.add_parser("reject")
    pr.add_argument("id", type=int)
    pr.add_argument("--reason", default="")

    ps = sub.add_parser("send")
    ps.add_argument("id", type=int)
    ps.add_argument("--dry-run", action="store_true")

    psa = sub.add_parser("send-approved")
    psa.add_argument("--dry-run", action="store_true")
    psa.add_argument("--max", type=int, default=50)

    args = ap.parse_args(argv)

    return {
        "draft": cmd_draft,
        "list": cmd_list,
        "show": cmd_show,
        "approve": cmd_approve,
        "reject": cmd_reject,
        "send": cmd_send,
        "send-approved": cmd_send_approved,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
