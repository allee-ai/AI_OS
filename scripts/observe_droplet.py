"""
observe_droplet — sync droplet state.db locally + show what the brain has been thinking.
=========================================================================================

Two modes:

  observe    : pull data/db/state.db from droplet to a local read-only
               copy at data/db/droplet_state.db, then print:
                 - alive summary (which loops ticking, last age)
                 - top hot concepts
                 - top salient facts
                 - last 10 meta-thoughts
                 - last 5 readiness samples
                 - any recent shift meta-thoughts
               Run this when you sit down at laptop. ~2s.

  watch      : observe in a loop every N seconds (default 30s). Use it
               in a terminal beside whatever else you're doing — the
               brain ticks beside you.

Usage:
  .venv/bin/python scripts/observe_droplet.py
  .venv/bin/python scripts/observe_droplet.py watch --interval 30

Requires SSH alias 'AIOS' (already configured).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL_COPY = ROOT / "data" / "db" / "droplet_state.db"
REMOTE_PATH = "/opt/aios/data/db/state.db"
SSH_HOST = "AIOS"


def _sync() -> bool:
    """Use sqlite .backup over SSH for a consistent snapshot.

    Avoids the partial-file hazard of plain rsync against a hot WAL DB.
    Pipes a small Python program into the droplet's interpreter via stdin
    so we don't fight ssh/bash quoting.
    """
    LOCAL_COPY.parent.mkdir(parents=True, exist_ok=True)
    backup_script = (
        "import sqlite3\n"
        f"src = sqlite3.connect({REMOTE_PATH!r})\n"
        "dst = sqlite3.connect('/tmp/_aios_brain_snapshot.db')\n"
        "src.backup(dst)\n"
        "dst.close(); src.close()\n"
    )
    r = subprocess.run(
        ["ssh", SSH_HOST, "/opt/aios/.venv/bin/python", "-"],
        input=backup_script,
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"[sync] backup failed: {r.stderr}", file=sys.stderr)
        return False
    r = subprocess.run(
        ["scp", "-q", f"{SSH_HOST}:/tmp/_aios_brain_snapshot.db", str(LOCAL_COPY)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(f"[sync] scp failed: {r.stderr}", file=sys.stderr)
        return False
    subprocess.run(
        ["ssh", SSH_HOST, "rm", "-f", "/tmp/_aios_brain_snapshot.db"],
        capture_output=True,
    )
    return True


def _conn():
    import sqlite3
    c = sqlite3.connect(f"file:{LOCAL_COPY}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def _alive_summary(conn) -> str:
    try:
        rows = conn.execute(
            """
            SELECT loop, ticks, errors,
                   (julianday('now') - julianday(last_ts)) * 86400.0 AS age_s
            FROM loop_heartbeat ORDER BY loop
            """
        ).fetchall()
    except Exception:
        return "no loop_heartbeat (supervisor never ran)"
    if not rows:
        return "loop_heartbeat empty"
    parts = []
    for r in rows:
        age = float(r["age_s"] or 0)
        if age < 60:
            a = f"{age:.0f}s"
        elif age < 3600:
            a = f"{age/60:.1f}m"
        else:
            a = f"{age/3600:.1f}h"
        flag = "" if age < 300 else "STALE!"
        parts.append(f"{r['loop']} {a}/{r['ticks']}t{flag}")
    return ", ".join(parts)


def _section(title: str) -> None:
    print()
    print(f"── {title} " + "─" * (66 - len(title)))


def _hot(conn, limit: int = 8) -> None:
    try:
        rows = conn.execute(
            "SELECT concept, activation FROM concept_activation "
            "ORDER BY activation DESC LIMIT ?", (limit,)
        ).fetchall()
    except Exception:
        return
    for r in rows:
        print(f"  {r['activation']:.2f}  {r['concept']}")


def _salient(conn, limit: int = 8) -> None:
    try:
        rows = conn.execute(
            "SELECT profile_id, key, value, salience FROM state_cache "
            "ORDER BY salience DESC LIMIT ?", (limit,)
        ).fetchall()
    except Exception:
        return
    for r in rows:
        v = (r["value"] or "")[:90].replace("\n", " ")
        print(f"  {r['salience']:.2f}  {r['profile_id']}.{r['key']}: {v}")


def _meta(conn, limit: int = 10) -> None:
    try:
        rows = conn.execute(
            """
            SELECT kind, weight, content, created_at
            FROM reflex_meta_thoughts
            ORDER BY id DESC LIMIT ?
            """, (limit,)
        ).fetchall()
    except Exception:
        return
    for r in rows:
        c = (r["content"] or "")[:100].replace("\n", " ")
        print(f"  [{r['kind']:12s} w={r['weight']:.2f}] {r['created_at']}  {c}")


def _goals(conn, limit: int = 5) -> None:
    try:
        rows = conn.execute(
            """
            SELECT id, goal, priority, urgency, status
            FROM proposed_goals
            WHERE status IN ('pending','approved','in_progress')
            ORDER BY id DESC LIMIT ?
            """, (limit,)
        ).fetchall()
    except Exception:
        return
    for r in rows:
        g = (r["goal"] or "")[:100].replace("\n", " ")
        print(f"  #{r['id']} ({r['status']}/{r['priority']}/{r['urgency'] or 0})  {g}")


def _events(conn) -> None:
    try:
        r = conn.execute(
            "SELECT COUNT(*) c, MAX(timestamp) mx FROM unified_events"
        ).fetchone()
        h = conn.execute(
            "SELECT COUNT(*) c FROM unified_events WHERE timestamp >= datetime('now','-1 hour')"
        ).fetchone()
        d = conn.execute(
            "SELECT COUNT(*) c FROM unified_events WHERE timestamp >= datetime('now','-1 day')"
        ).fetchone()
        print(f"  total: {r['c']:,}   last_event: {r['mx']}   1h: {h['c']}   24h: {d['c']}")
    except Exception:
        pass


def observe_once() -> None:
    t0 = time.time()
    print(f"[sync] pulling {REMOTE_PATH} → {LOCAL_COPY}")
    if not _sync():
        return
    dt = time.time() - t0
    size_mb = LOCAL_COPY.stat().st_size / 1e6
    print(f"[sync] {size_mb:.1f} MB in {dt:.1f}s")

    with closing(_conn()) as conn:
        _section("ALIVE")
        print(f"  {_alive_summary(conn)}")

        _section("EVENTS")
        _events(conn)

        _section("HOT concepts")
        _hot(conn)

        _section("TOP salient")
        _salient(conn)

        _section("LIVE goals")
        _goals(conn)

        _section("RECENT meta-thoughts")
        _meta(conn)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mode", nargs="?", default="observe",
                   choices=["observe", "watch"])
    p.add_argument("--interval", type=float, default=30.0)
    args = p.parse_args()

    if args.mode == "observe":
        observe_once()
        return 0

    print(f"watching every {args.interval}s — Ctrl-C to stop\n")
    while True:
        try:
            os.system("clear")
            observe_once()
            time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())
