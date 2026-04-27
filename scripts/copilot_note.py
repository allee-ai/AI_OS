#!/usr/bin/env python3
"""
scripts/copilot_note.py — leave a breadcrumb for next-turn-me.

Every Copilot turn reads STATE and then vanishes. This writes a one-line
entry into reflex_meta_thoughts (source=copilot) so insights, gotchas, and
"I tried X and it didn't work" notes survive across turns. The next
turn's STATE will surface these under reflex.meta.copilot.*

Goal #27 wired.

Usage:
    scripts/copilot_note.py "one-line insight"
    scripts/copilot_note.py --kind expected "hypothesis about what will happen"
    scripts/copilot_note.py --kind rejected "approach that didn't work: <why>"
    scripts/copilot_note.py --list
    scripts/copilot_note.py --list --limit 20

kinds:
    unknown      (default) — a plain note / observation
    expected     — a hypothesis about what will happen next
    rejected     — an approach that failed, with reason
    compression  — a summary of several recent turns

flags:
    --from-user  — capture as source='user_correction' instead of 'copilot'.
                   Use when Cade pushes back, corrects, or says "no, that's
                   wrong" — her words/reasoning go off-policy and the asymmetric
                   weighting in confidence.py + reflex adapter will treat them
                   accordingly. Self-notes about her corrections stay 'copilot'.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.threads.reflex.schema import (  # noqa: E402
    add_meta_thought,
    get_recent_meta_thoughts,
    init_meta_thoughts_table,
    META_THOUGHT_KINDS,
)


def cmd_add(content: str, kind: str, confidence: float, weight: float, source: str) -> int:
    init_meta_thoughts_table()
    rid = add_meta_thought(
        kind=kind,
        content=content,
        source=source,
        confidence=confidence,
        weight=weight,
    )
    if rid is None:
        print(
            f"note dropped (kind={kind!r} not in {META_THOUGHT_KINDS} "
            f"or content empty / db error)",
            file=sys.stderr,
        )
        return 1
    tag = source if source != "copilot" else kind
    print(f"note#{rid} [{tag}] {content[:80]}")
    return 0


def cmd_list(limit: int, kind: str | None) -> int:
    init_meta_thoughts_table()
    kinds = [kind] if kind else None
    rows = get_recent_meta_thoughts(kinds=kinds, limit=limit)
    # Filter to copilot source only
    rows = [r for r in rows if r.get("source") == "copilot"]
    if not rows:
        print("(no copilot notes yet)")
        return 0
    for r in rows:
        rid = r.get("id")
        k = r.get("kind", "?")
        ts = r.get("created_at", "")
        c = r.get("content", "")
        print(f"#{rid:<4} {ts}  [{k:<11}] {c}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Leave a note for next-turn-me")
    ap.add_argument("content", nargs="?", help="note text (one line)")
    ap.add_argument(
        "--kind",
        default="unknown",
        choices=list(META_THOUGHT_KINDS),
        help="kind of note (default: unknown)",
    )
    ap.add_argument("--confidence", type=float, default=0.6)
    ap.add_argument("--weight", type=float, default=0.5)
    ap.add_argument("--list", action="store_true", help="list recent copilot notes")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument(
        "--from-user",
        action="store_true",
        help="capture as source='user_correction' (off-policy ground truth) "
             "instead of 'copilot' self-note.",
    )
    args = ap.parse_args()

    if args.list:
        return cmd_list(args.limit, args.kind if args.kind != "unknown" else None)
    if not args.content:
        ap.print_help()
        return 2
    source = "user_correction" if args.from_user else "copilot"
    # User corrections get a higher default weight — they're off-policy ground
    # truth and should not be easily decayed out of STATE surfacing.
    weight = args.weight if args.weight != 0.5 else (0.95 if args.from_user else 0.5)
    return cmd_add(args.content, args.kind, args.confidence, weight, source)


if __name__ == "__main__":
    raise SystemExit(main())
