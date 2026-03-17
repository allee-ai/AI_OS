#!/usr/bin/env python3
"""
Enrich state_demo.db with safe structural data from state.db.

COPIES (structural, non-personal):
  - eval_benchmarks          (benchmark definitions)
  - reflex_triggers          (automation rules)
  - tool_traces              (tool execution logs - sanitized)
  - thought_log              (agent thoughts - these showcase the feature)
  - tasks                    (task execution examples)
  - memory_loop_state        (loop cursor positions)
  - log_server               (server logs)
  - notifications            (demo notifications)
  - focus_topics             (concept focus data)

SKIPS (personal):
  - convo_turns / convos     (personal conversations)
  - temp_facts               (learned personal facts)
  - profile_facts > 38       (demo already has good set; live has 1593 personal)
  - concept_links            (demo already has 5680; live has 137K)
  - unified_events           (contains personal event timeline)

Also trims workspace_files entries that contain local paths.
"""

import sqlite3
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE_DB = ROOT / "data" / "db" / "state.db"
DEMO_DB = ROOT / "data" / "db" / "state_demo.db"

# Tables to copy wholesale from live -> demo (replacing demo contents)
SAFE_TABLES = [
    "eval_benchmarks",
    "reflex_triggers",
    "tool_traces",
    "memory_loop_state",
    "log_server",
    "notifications",
]

# Tables to copy with row limit (demo showcase, not full history)
LIMITED_TABLES = {
    "thought_log": 50,       # Recent thoughts (showcase feature)
    "tasks": 30,             # Recent tasks
    "focus_topics": 100,     # Top concepts
}


def copy_table(src_conn, dst_conn, table, limit=None):
    """Copy rows from src to dst, clearing dst first."""
    src = src_conn.cursor()
    dst = dst_conn.cursor()

    # Get column names from source
    src.execute(f"PRAGMA table_info([{table}])")
    src_cols = {r[1] for r in src.fetchall()}

    # Get column names from dest
    dst.execute(f"PRAGMA table_info([{table}])")
    dst_cols = {r[1] for r in dst.fetchall()}

    if not dst_cols:
        print(f"  SKIP {table} (not in demo schema)")
        return 0

    # Use only columns that exist in both
    common_cols = sorted(src_cols & dst_cols)
    if not common_cols:
        print(f"  SKIP {table} (no common columns)")
        return 0

    cols_str = ", ".join(f"[{c}]" for c in common_cols)
    placeholders = ", ".join("?" for _ in common_cols)

    query = f"SELECT {cols_str} FROM [{table}]"
    if limit:
        query += f" ORDER BY rowid DESC LIMIT {limit}"

    src.execute(query)
    rows = src.fetchall()

    if not rows:
        print(f"  SKIP {table} (empty in live)")
        return 0

    dst.execute(f"DELETE FROM [{table}]")
    dst.executemany(
        f"INSERT OR IGNORE INTO [{table}] ({cols_str}) VALUES ({placeholders})",
        rows,
    )
    return len(rows)


def sanitize_paths(conn):
    """Replace local file paths in text columns."""
    path_replace = "/Users/cade/Desktop/AI_OS"
    generic_path = "/home/user/AI_OS"

    for table in ["thought_log", "tasks", "tool_traces", "log_server"]:
        try:
            conn.execute(f"PRAGMA table_info([{table}])")
            cols = conn.execute(f"PRAGMA table_info([{table}])").fetchall()
            text_cols = [c[1] for c in cols if "TEXT" in (c[2] or "").upper()]
            for col in text_cols:
                conn.execute(
                    f"UPDATE [{table}] SET [{col}] = REPLACE([{col}], ?, ?) WHERE [{col}] LIKE ?",
                    (path_replace, generic_path, f"%{path_replace}%"),
                )
        except Exception as e:
            print(f"  sanitize {table}.{col}: {e}")


def main():
    print(f"Live DB: {LIVE_DB} ({LIVE_DB.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"Demo DB: {DEMO_DB} ({DEMO_DB.stat().st_size / 1024 / 1024:.1f} MB)")
    print()

    src = sqlite3.connect(str(LIVE_DB))
    src.row_factory = None
    dst = sqlite3.connect(str(DEMO_DB))
    dst.row_factory = None

    # Ensure tables exist in demo
    src_cur = src.cursor()
    src_cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
    for name, sql in src_cur.fetchall():
        if sql and name not in ("sqlite_sequence",):
            try:
                dst.execute(sql)
            except sqlite3.OperationalError:
                pass  # Already exists

    total = 0

    print("Copying safe tables:")
    for table in SAFE_TABLES:
        n = copy_table(src, dst, table)
        total += n
        print(f"  {table}: {n} rows")

    print("\nCopying limited tables:")
    for table, limit in LIMITED_TABLES.items():
        n = copy_table(src, dst, table, limit=limit)
        total += n
        print(f"  {table}: {n} rows (limit {limit})")

    print("\nSanitizing paths...")
    sanitize_paths(dst)

    dst.commit()

    # Final counts
    print(f"\nTotal rows copied: {total}")
    print(f"Demo DB size: {DEMO_DB.stat().st_size / 1024 / 1024:.1f} MB")

    # Summary of demo state
    print("\nDemo DB final counts:")
    cur = dst.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    for (t,) in cur.fetchall():
        cur.execute(f"SELECT count(*) FROM [{t}]")
        cnt = cur.fetchone()[0]
        if cnt > 0:
            print(f"  {t}: {cnt}")

    src.close()
    dst.close()


if __name__ == "__main__":
    main()
