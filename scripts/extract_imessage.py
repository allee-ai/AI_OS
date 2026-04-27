#!/usr/bin/env python3
"""
scripts/extract_imessage.py — Dump Apple Messages history to JSONL.

Step 1 of the "model of me" pipeline. Read-only: reads
~/Library/Messages/chat.db and writes normalized message rows to
data/personal_corpus/imessage.jsonl.

Requires Full Disk Access for whatever terminal/process runs this.
Grant via: System Settings → Privacy & Security → Full Disk Access
→ enable Terminal (or iTerm, or whichever).

Output row schema:
  {
    "ts": "2024-01-15T09:30:00-08:00",   # ISO, local tz
    "thread_id": "+15551234567" | "name@example.com" | "group:N",
    "thread_label": "+15551234567" or display name if we have it,
    "who": "me" | "them",
    "handle": "+15551234567",             # whoever this message came from
    "body": "…",
    "service": "iMessage" | "SMS",
    "is_group": false,
    "attachments": 0,
    "rowid": 12345                        # for dedup / incremental
  }

Privacy notes:
- Local file. Never uploaded. This is your data on your disk.
- `who == "them"` rows are other people's words; keep them only so the
  curator can build (prior context → your_reply) training pairs.
  Pair-builder should NOT train the model to generate "them" text.

Usage:
  .venv/bin/python scripts/extract_imessage.py
  .venv/bin/python scripts/extract_imessage.py --since 2024-01-01
  .venv/bin/python scripts/extract_imessage.py --min-chars 30
  .venv/bin/python scripts/extract_imessage.py --out /path/to/out.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# iMessage timestamps are nanoseconds since 2001-01-01 UTC (Cocoa epoch).
# Convert to POSIX: posix = cocoa_ns/1e9 + 978307200
COCOA_EPOCH_OFFSET = 978307200


def _cocoa_ns_to_iso(ns: int) -> str:
    if not ns:
        return ""
    try:
        posix = ns / 1_000_000_000 + COCOA_EPOCH_OFFSET
        dt = datetime.fromtimestamp(posix, tz=timezone.utc).astimezone()
        return dt.isoformat()
    except Exception:
        return ""


def _iso_to_cocoa_ns(iso: str) -> int:
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.astimezone()
    posix = dt.timestamp()
    return int((posix - COCOA_EPOCH_OFFSET) * 1_000_000_000)


# attributedBody is an NSKeyedArchiver plist blob used on newer macOS
# instead of the plain `text` column. We strip it out crudely — good
# enough for training data.
def _decode_attributed_body(blob: Optional[bytes]) -> str:
    if not blob:
        return ""
    try:
        s = blob.decode("utf-8", errors="replace")
    except Exception:
        return ""
    # Find the NSString marker; the actual text usually follows.
    # Works for the common single-string case. Multi-part messages
    # (reactions, edits) are rare enough to skip on first pass.
    marker = "NSString"
    idx = s.find(marker)
    if idx < 0:
        return ""
    tail = s[idx + len(marker):]
    # First printable run after the marker, minus control noise.
    out = []
    started = False
    for ch in tail:
        code = ord(ch)
        if 0x20 <= code < 0x7f or code in (0x09, 0x0a) or code > 0x9f:
            out.append(ch)
            started = True
        elif started:
            # Stop at the next control sequence after we have content.
            if len(out) >= 4:
                break
            out.clear()
    return "".join(out).strip().strip("+").strip()


def extract(
    db_path: Path,
    out_path: Path,
    since_iso: Optional[str] = None,
    min_chars: int = 0,
    limit: Optional[int] = None,
) -> dict:
    """Stream rows from chat.db into JSONL. Returns summary stats."""
    if not db_path.exists():
        raise FileNotFoundError(f"iMessage DB not found: {db_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Use URI mode to open read-only. Chat.db is sometimes locked by the
    # Messages app; read-only + immutable=1 lets us read anyway.
    uri = f"file:{db_path}?mode=ro&immutable=1"

    where = ["m.text IS NOT NULL OR m.attributedBody IS NOT NULL"]
    params: list = []
    if since_iso:
        where.append("m.date >= ?")
        params.append(_iso_to_cocoa_ns(since_iso))
    where_sql = " AND ".join(where) if where else "1=1"

    limit_sql = f"LIMIT {int(limit)}" if limit else ""

    # Core query: join message → chat (thread) and handle (sender).
    # chat_message_join is the many-to-many bridge.
    sql = f"""
        SELECT
            m.ROWID                AS rowid,
            m.date                 AS cocoa_ns,
            m.is_from_me           AS is_from_me,
            m.text                 AS text,
            m.attributedBody       AS attr_body,
            m.service              AS service,
            m.cache_has_attachments AS has_attachments,
            h.id                   AS handle_id,
            c.chat_identifier      AS chat_identifier,
            c.display_name         AS chat_display_name,
            c.style                AS chat_style
        FROM message m
        LEFT JOIN handle h               ON m.handle_id = h.ROWID
        LEFT JOIN chat_message_join cmj  ON cmj.message_id = m.ROWID
        LEFT JOIN chat c                 ON c.ROWID = cmj.chat_id
        WHERE {where_sql}
        ORDER BY m.date ASC
        {limit_sql}
    """

    total = 0
    kept = 0
    skipped_empty = 0
    skipped_short = 0
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        with open(out_path, "w", encoding="utf-8") as fout:
            for row in conn.execute(sql, params):
                total += 1
                body = (row["text"] or "").strip()
                if not body:
                    body = _decode_attributed_body(row["attr_body"])
                if not body:
                    skipped_empty += 1
                    continue
                if min_chars and len(body) < min_chars:
                    skipped_short += 1
                    continue

                ident = row["chat_identifier"] or row["handle_id"] or ""
                # chat.style == 43 means group chat in Apple's schema.
                is_group = (row["chat_style"] or 0) == 43
                thread_label = row["chat_display_name"] or ident

                rec = {
                    "ts": _cocoa_ns_to_iso(row["cocoa_ns"] or 0),
                    "thread_id": ident,
                    "thread_label": thread_label,
                    "who": "me" if row["is_from_me"] else "them",
                    "handle": row["handle_id"] or ("me" if row["is_from_me"] else ""),
                    "body": body,
                    "service": row["service"] or "",
                    "is_group": bool(is_group),
                    "attachments": int(row["has_attachments"] or 0),
                    "rowid": int(row["rowid"]),
                }
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                kept += 1

    return {
        "total_rows_scanned": total,
        "rows_kept": kept,
        "skipped_empty": skipped_empty,
        "skipped_short": skipped_short,
        "out_path": str(out_path),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--db",
        default=str(Path.home() / "Library" / "Messages" / "chat.db"),
        help="Path to Messages chat.db (default: ~/Library/Messages/chat.db)",
    )
    ap.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parents[1] / "data" / "personal_corpus" / "imessage.jsonl"),
        help="Output JSONL path.",
    )
    ap.add_argument(
        "--since",
        default=None,
        help="ISO date/datetime lower bound (e.g. 2024-01-01 or 2024-01-01T00:00:00).",
    )
    ap.add_argument(
        "--min-chars", type=int, default=0,
        help="Skip messages shorter than N chars. 0 = keep all.",
    )
    ap.add_argument(
        "--limit", type=int, default=None,
        help="Debug: cap number of rows scanned.",
    )
    args = ap.parse_args()

    db_path = Path(args.db).expanduser()
    out_path = Path(args.out).expanduser()

    try:
        stats = extract(
            db_path=db_path,
            out_path=out_path,
            since_iso=args.since,
            min_chars=args.min_chars,
            limit=args.limit,
        )
    except sqlite3.OperationalError as e:
        msg = str(e).lower()
        if "authorization denied" in msg or "unable to open database" in msg:
            sys.stderr.write(
                "\nCannot read chat.db — macOS Full Disk Access required.\n"
                "  System Settings → Privacy & Security → Full Disk Access\n"
                "  Enable the terminal app (Terminal / iTerm / VS Code) running this script.\n"
                "  You may need to quit+reopen the terminal after granting.\n\n"
            )
            return 2
        raise
    except FileNotFoundError as e:
        sys.stderr.write(f"{e}\n")
        return 3

    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
