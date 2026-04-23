#!/usr/bin/env python3
"""Seed data/db/state_demo.db from a sanitized snapshot of state.db.

The demo DB needs to *show* the system's properties (real concept graph,
real loops registered, real philosophy, real identity profile shape) without
leaking the owner's actual name, email, conversations, or recent thoughts.

Strategy:
  1. Wipe existing state_demo.db (back it up first).
  2. Run schema migrations to create empty tables.
  3. Copy STRUCTURAL tables wholesale (concepts, tools, fact-type definitions,
     consent taxonomy seed). These have no PII.
  4. Copy IDENTITY tables with PII scrubbed (real name → "Demo User", emails
     blanked, phone blanked, anything matching the user's name in long values
     gets replaced).
  5. Copy a TINY hand-picked sample of conversational/log tables — enough to
     show shape, not enough to leak history. Hardcoded fixtures here.
  6. Copy PHILOSOPHY wholesale (already public-safe — these are stated values).
  7. Reset volatile tables (sessions, heartbeats, notifications, sensory).

Idempotent: re-run anytime to rebuild state_demo.db from current state.db.

Usage:
    .venv/bin/python scripts/seed_demo_db.py
    .venv/bin/python scripts/seed_demo_db.py --dry-run
"""
from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REAL_DB = ROOT / "data" / "db" / "state.db"
DEMO_DB = ROOT / "data" / "db" / "state_demo.db"

# ── Sanitization rules ──────────────────────────────────────────────
# All real-name variants → "Demo User"; emails → demo@example.com;
# phone numbers wiped. These run on string values pulled from the real DB.
_NAME_PATTERNS = [
    (re.compile(r"\bAllee[\s_-]?Cade[\s_-]?Roden\b", re.I), "Demo User"),
    (re.compile(r"\bCade[\s_-]?Roden\b", re.I), "Demo User"),
    (re.compile(r"\bAllee\b", re.I), "Demo"),
    (re.compile(r"\bCade\b", re.I), "Demo"),
    (re.compile(r"\bRoden\b", re.I), "User"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "demo@example.com"),
    (re.compile(r"\+?\d[\d\s().-]{7,}\d"), ""),
]


def _scrub(value):
    """Apply sanitization patterns to any string-ish value."""
    if not isinstance(value, str) or not value:
        return value
    out = value
    for pat, repl in _NAME_PATTERNS:
        out = pat.sub(repl, out)
    return out


def _scrub_row(row: sqlite3.Row) -> tuple:
    """Return a tuple of column values with strings sanitized."""
    return tuple(_scrub(v) for v in row)


# ── Tables to copy whole (no PII) ──────────────────────────────────
STRUCTURAL_TABLES = [
    "fact_types",
    "philosophy_fact_types",
    "philosophy_profile_types",
    "profile_types",
    "form_tools",
    "concept_links",          # 650k edges — all word-pairs, no PII
    "philosophy_profiles",
    "philosophy_profile_facts",  # values — public by design
    "reflex_triggers",
    "eval_benchmarks",
    "workspace_files",        # already 12 generic sample files
    "memory_loop_state",
    "fact_types",
]

# ── Tables to copy with sanitization on string columns ─────────────
SCRUB_TABLES = [
    "profiles",
    "profile_facts",
]

# ── Tables to copy LIMITED tail with sanitization ──────────────────
# (table, ORDER BY clause, LIMIT)
# Use ROWID for ordering since not every table has an `id` column.
LIMITED_TABLES = [
    ("proposed_goals",       "ROWID DESC", 15),
    ("reflex_meta_thoughts", "ROWID DESC", 30),
    ("research_items",       "ROWID DESC", 20),
    ("focus_topics",         "ROWID DESC", 15),
    ("tasks",                "ROWID DESC", 20),
    ("eval_runs",            "ROWID DESC", 10),
    ("tool_traces",          "ROWID DESC", 50),
    ("thought_log",          "ROWID DESC", 50),
    ("log_server",           "ROWID DESC", 100),
    ("unified_events",       "ROWID DESC", 200),
    ("heartbeat_ticks",      "ROWID DESC", 30),
]

# ── Tables to wipe / leave at zero ─────────────────────────────────
WIPE_TABLES = [
    "notifications",         # private pings — never demo
    "sensory_events",        # demo gets seeded with a few canned events
    "sensory_consent_log",
    "sensory_blocked",
    "sensory_dropped",
    "convos",                # too much to scrub — visitors can read aios.html
    "convo_turns",
    "log_system",
    "user_notes",            # might have private content
    "temp_facts",            # short-term cache, regenerates
]


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def _columns(conn, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _ensure_table(src, dst, table: str) -> bool:
    """If dst is missing the table, copy CREATE TABLE from src."""
    if _table_exists(dst, table):
        return True
    if not _table_exists(src, table):
        return False
    row = src.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not row or not row[0]:
        return False
    try:
        dst.execute(row[0])
        return True
    except Exception as e:
        print(f"  could not create {table} in demo: {e}")
        return False


def _copy_table(src, dst, table: str, scrub: bool = False, limit_clause: str = "") -> int:
    """Copy a table from src→dst. Returns row count copied."""
    if not _table_exists(src, table):
        return 0
    if not _ensure_table(src, dst, table):
        return 0
    # Match destination columns (which is the schema of record). Drop columns
    # that don't exist in the destination (older snapshots, drifted columns).
    src_cols = set(_columns(src, table))
    dst_cols = _columns(dst, table)
    common = [c for c in dst_cols if c in src_cols]
    if not common:
        return 0
    col_list = ", ".join(common)
    sel = f"SELECT {col_list} FROM {table} {limit_clause}"
    rows = src.execute(sel).fetchall()
    placeholders = ", ".join("?" * len(common))
    ins = f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})"
    n = 0
    for r in rows:
        values = tuple(r)
        if scrub:
            values = tuple(_scrub(v) for v in values)
        try:
            dst.execute(ins, values)
            n += 1
        except sqlite3.IntegrityError as e:
            # Skip rows that violate FK after sampling (e.g. tail-only copies)
            print(f"  skip {table} row: {e}")
    return n


def _seed_sensory_demo(dst):
    """Insert a few canned sensory events so visitors see the bus is alive."""
    events = [
        ("system",     "lid_open",     "demo session started",                          1.0),
        ("system",     "lid_close",    "previous session ended",                        1.0),
        ("user_voice", "transcript",   "tell me what the system has been thinking",    0.92),
        ("camera",     "snapshot",     "a desk with a laptop and notebook",            0.8),
        ("screen",     "window_title", "AI OS — demo mode",                            1.0),
        ("mic",        "ambient",      "quiet room, occasional keyboard",              0.7),
    ]
    now = int(time.time())
    for i, (src, kind, text, conf) in enumerate(events):
        ts = now - (len(events) - i) * 60  # spread over recent minutes
        dst.execute(
            "INSERT INTO sensory_events (source, kind, text, confidence, created_at) "
            "VALUES (?, ?, ?, ?, datetime(?, 'unixepoch'))",
            (src, kind, text, conf, ts),
        )


def _seed_demo_convo(dst):
    """One curated sample conversation so visitors can see the chat shape."""
    if not _table_exists(dst, "convos") or not _table_exists(dst, "convo_turns"):
        return
    dst.execute(
        "INSERT OR REPLACE INTO convos "
        "(session_id, channel, name, summary, source, turn_count) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            "demo_walkthrough",
            "demo",
            "Demo walkthrough",
            "A short tour of what AI_OS knows about itself.",
            "demo",
            2,
        ),
    )
    convo_id = dst.execute(
        "SELECT id FROM convos WHERE session_id=?", ("demo_walkthrough",)
    ).fetchone()[0]

    turns = [
        ("What are you?",
         "An AI OS — a long-running agent with a self-model. I track who you are, "
         "what we're working on, and why. This is the demo, so I'm running on a "
         "sanitized DB and my LLM is turned off — you can read but I can't reply "
         "for real."),
        ("How do you remember things?",
         "Six threads: identity, philosophy, log, form (tools), reflex (patterns), "
         "linking_core (concept graph). Plus chat, workspace, goals, sensory. "
         "Each one introspects into a STATE block I read at the start of every turn."),
    ]
    for i, (user_msg, asst_msg) in enumerate(turns):
        try:
            dst.execute(
                "INSERT INTO convo_turns "
                "(convo_id, turn_index, user_message, assistant_message) "
                "VALUES (?, ?, ?, ?)",
                (convo_id, i, user_msg, asst_msg),
            )
        except sqlite3.IntegrityError as e:
            print(f"  convo_turn skip: {e}")


def _ensure_schema():
    """Run the same schema migrations the live server runs at startup."""
    # Force demo mode so migrations target state_demo.db.
    from data.db import set_demo_mode
    set_demo_mode(True)
    from agent.core.migrations import ensure_all_schemas
    ensure_all_schemas()
    # Sensory tables aren't in the migration registry — initialize directly.
    try:
        from sensory import init_sensory_tables, init_salience_tables, init_consent_tables
        init_sensory_tables()
        init_salience_tables()
        init_consent_tables()
    except Exception as e:
        print(f"  sensory init skipped: {e}")
    set_demo_mode(False)  # flip back so this script doesn't poison the user's session


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not REAL_DB.exists():
        print(f"error: real DB not found at {REAL_DB}", file=sys.stderr)
        return 1

    # Backup any existing demo DB
    if DEMO_DB.exists() and not args.dry_run:
        backup = DEMO_DB.with_suffix(f".db.bak-{int(time.time())}")
        shutil.copy(DEMO_DB, backup)
        print(f"backed up existing demo DB → {backup.name}")
        DEMO_DB.unlink()

    if args.dry_run:
        print("[dry-run] would wipe state_demo.db and re-seed from state.db")
        return 0

    # Create empty demo DB with full schema
    print("creating demo schema...")
    _ensure_schema()

    # Open both
    src = sqlite3.connect(str(REAL_DB))
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(str(DEMO_DB))
    dst.row_factory = sqlite3.Row

    try:
        with dst:
            print("\n== structural tables (no PII) ==")
            for t in STRUCTURAL_TABLES:
                n = _copy_table(src, dst, t, scrub=False)
                print(f"  {t:35s} {n}")

            print("\n== identity tables (scrubbed) ==")
            for t in SCRUB_TABLES:
                n = _copy_table(src, dst, t, scrub=True)
                print(f"  {t:35s} {n}")

            print("\n== limited / scrubbed tail copies ==")
            for t, order, limit in LIMITED_TABLES:
                clause = f"ORDER BY {order} LIMIT {limit}"
                n = _copy_table(src, dst, t, scrub=True, limit_clause=clause)
                print(f"  {t:35s} {n}  (last {limit})")

            print("\n== seeding sensory bus ==")
            _seed_sensory_demo(dst)
            print(f"  sensory_events                      6")
            # Consent: copy taxonomy from real DB but force all enabled=0
            n_consent = _copy_table(src, dst, "sensory_consent", scrub=False)
            dst.execute("UPDATE sensory_consent SET enabled=0")
            print(f"  sensory_consent                     {n_consent} (all OFF)")

            print("\n== seeding demo convo ==")
            _seed_demo_convo(dst)
            print(f"  convos + convo_turns                1 + 4")

        # Verify
        print("\n== verify ==")
        for t in [
            "profiles", "profile_facts",
            "philosophy_profiles", "philosophy_profile_facts",
            "form_tools", "concept_links",
            "proposed_goals", "reflex_meta_thoughts",
            "thought_log", "unified_events",
            "sensory_events", "sensory_consent",
            "convos", "convo_turns",
        ]:
            try:
                n = dst.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                print(f"  {t:35s} {n}")
            except Exception as e:
                print(f"  {t:35s} ERR {e}")

        # Spot-check sanitization
        print("\n== sanitization spot-check ==")
        rows = dst.execute(
            "SELECT key, l1_value FROM profile_facts "
            "WHERE profile_id='primary_user' AND key='name'"
        ).fetchall()
        for r in rows:
            print(f"  primary_user.name = {r['l1_value']!r}")

        print(f"\nDONE. demo DB at {DEMO_DB.relative_to(ROOT)}")
        print("test it: PORT=8081 .venv/bin/python scripts/server_demo.py")
    finally:
        src.close()
        dst.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
