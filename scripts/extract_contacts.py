#!/usr/bin/env python3
"""
scripts/extract_contacts.py — read-only contact discovery.

Scans imported conversation history (convo_turns) for plausible contacts
mentioned by Cade and surfaces the top candidates as a triage list.

Writes NOTHING.  Output is pure text for Cade to read and decide.

Heuristics (kept dumb on purpose — avoids LLM burn while she's asleep):
  - Email regex on all turn content.
  - Name pattern: "<First Last>" before / after an email, or after
    common verbs ("met with", "emailed", "talked to", "from <Name> at").
  - Group by email; rank by frequency × recency.

Usage:
    .venv/bin/python scripts/extract_contacts.py            # top 20
    .venv/bin/python scripts/extract_contacts.py --limit 50
    .venv/bin/python scripts/extract_contacts.py --since 2026-01-01
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.db import get_connection  # noqa: E402

EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)
NAME_NEAR_EMAIL_RE = re.compile(
    r"(?:^|\s)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})"
    r"\s*[\(\[<]?\s*(\S+@\S+)"
)
NAME_AFTER_VERB_RE = re.compile(
    r"(?:met with|emailed|talked to|spoke with|reached out to|from)\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
    re.IGNORECASE,
)

# Things to filter out — not real prospects
NOISE_DOMAINS = {
    "example.com", "test.com", "localhost", "allee-ai.com",  # us
    "sentry.io", "github.com", "gmail.com",  # too generic alone
    "proton.me", "notify.proton.me", "no-reply",
}
NOISE_LOCAL_PARTS = {"no-reply", "noreply", "support", "info", "hello"}


def _is_noise(email: str) -> bool:
    email = email.lower()
    if "@" not in email:
        return True
    local, _, domain = email.partition("@")
    if domain in NOISE_DOMAINS:
        return True
    if local in NOISE_LOCAL_PARTS:
        return True
    if email.endswith("@allee-ai.com"):
        return True
    # Filename patterns picked up by the email regex: icon_512x512@2x.png
    if domain.endswith(".png") or domain.endswith(".jpg") or domain.endswith(".gif"):
        return True
    if domain.endswith(".local") or domain.endswith(".lan"):
        return True
    # Cade's own
    if email in {"caderoden2@icloud.com", "cade@bycade.com", "assistant@allee-ai.com"}:
        return True
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--since", default=None,
                    help="ISO date (YYYY-MM-DD) to start from. Default: all time.")
    ap.add_argument("--show-context", action="store_true",
                    help="Print one line of surrounding text per contact.")
    args = ap.parse_args(argv)

    where = ""
    params: list = []
    if args.since:
        where = "WHERE created_at >= ?"
        params.append(args.since)

    # convo_turns columns: user_message, assistant_message, timestamp
    where_clause = ""
    params2: list = []
    if args.since:
        where_clause = "WHERE timestamp >= ?"
        params2.append(args.since)

    rows: list = []
    with closing(get_connection(readonly=True)) as conn:
        try:
            cur = conn.execute(
                f"SELECT id, user_message, assistant_message, timestamp "
                f"FROM convo_turns {where_clause} "
                f"ORDER BY id DESC LIMIT 50000",
                params2,
            )
            rows = cur.fetchall()
        except Exception as e:
            print(f"(convo_turns query failed: {e})")
            rows = []

    if not rows:
        print("(no conversation rows found in convo_turns)")
        return 0

    # Aggregate per email
    counts: dict[str, int] = defaultdict(int)
    last_seen: dict[str, str] = {}
    name_for: dict[str, str] = {}
    sample_for: dict[str, str] = {}

    # Also collect bare-name mentions for prospects with no email
    name_counts: dict[str, int] = defaultdict(int)
    name_last_seen: dict[str, str] = {}

    for r in rows:
        um = (r["user_message"] if hasattr(r, "keys") else r[1]) or ""
        am = (r["assistant_message"] if hasattr(r, "keys") else r[2]) or ""
        content = um + "\n" + am
        ts = r["timestamp"] if hasattr(r, "keys") else r[3]
        ts_str = str(ts) if ts else ""

        for email in EMAIL_RE.findall(content):
            if _is_noise(email):
                continue
            counts[email] += 1
            if ts_str > last_seen.get(email, ""):
                last_seen[email] = ts_str
                idx = content.lower().find(email.lower())
                if idx >= 0:
                    start = max(0, idx - 60)
                    end = min(len(content), idx + len(email) + 60)
                    sample_for[email] = content[start:end].replace("\n", " ").strip()

        for m in NAME_NEAR_EMAIL_RE.finditer(content):
            nm, em = m.group(1), m.group(2)
            if not _is_noise(em):
                name_for.setdefault(em, nm)

        for m in NAME_AFTER_VERB_RE.finditer(content):
            nm = m.group(1)
            if any(c.islower() for c in nm.split()[0]):
                continue
            name_counts[nm] += 1
            if ts_str > name_last_seen.get(nm, ""):
                name_last_seen[nm] = ts_str

    if not counts and not name_counts:
        print("(no plausible contacts found)")
        return 0

    # Rank emails: frequency × recency-weight
    now = datetime.now(timezone.utc)

    def _recency_w(ts_str: str) -> float:
        try:
            dt = datetime.fromisoformat(ts_str.replace(" ", "T"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_d = max(0.1, (now - dt).total_seconds() / 86400.0)
            return 1.0 / (1.0 + age_d / 30.0)  # half-weight at 30d
        except Exception:
            return 0.5

    scored = sorted(
        counts.items(),
        key=lambda kv: kv[1] * _recency_w(last_seen.get(kv[0], "")),
        reverse=True,
    )

    print(f"=== Top {min(args.limit, len(scored))} email contacts (read-only triage) ===\n")
    for i, (email, cnt) in enumerate(scored[: args.limit], 1):
        nm = name_for.get(email, "?")
        seen = last_seen.get(email, "?")
        line = f"{i:2}. {email:<40}  mentions={cnt:<3}  last={seen[:10]}  name={nm}"
        print(line)
        if args.show_context and email in sample_for:
            print(f"     …{sample_for[email]}…")

    # Also show top bare names (no email yet)
    if name_counts:
        scored_names = sorted(
            name_counts.items(),
            key=lambda kv: kv[1] * _recency_w(name_last_seen.get(kv[0], "")),
            reverse=True,
        )[: max(5, args.limit // 4)]
        print(f"\n=== Bare-name mentions (no email yet, you'd need to look up) ===\n")
        for i, (nm, cnt) in enumerate(scored_names, 1):
            print(f"{i:2}. {nm:<30}  mentions={cnt:<3}  last={name_last_seen.get(nm, '?')[:10]}")

    print("\n(read-only — no facts written to identity. Pick targets and we draft together.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
