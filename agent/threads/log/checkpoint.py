"""
Log Thread — Checkpoint Module
==============================

Internal capability: clone the live state.db to the AIOS VM as a verified
warm replica, with WAL flushed and row counts confirmed.

The checkpoint *itself* is an event on the log thread's timeline
(event_type='checkpoint'), so the same adapter that surfaces "recent
agent_turns" naturally surfaces "last checkpoint: Nh ago [vm-replica ok]".

Public API:
    create_checkpoint(reason="manual") -> dict
    get_last_checkpoint() -> dict | None
    list_checkpoints(limit=10) -> list[dict]
"""

from __future__ import annotations

import json
import os
import shlex
import sqlite3
import subprocess
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from data.db import get_connection
from agent.threads.log.schema import log_event

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOCAL_DB = PROJECT_ROOT / "data" / "db" / "state.db"

VM_HOST = "AIOS"  # ssh alias from ~/.ssh/config
VM_PROJECT_ROOT = "/opt/aios"
VM_DB_PATH = f"{VM_PROJECT_ROOT}/data/db/state.db"

# Tables we ignore when comparing row counts (sqlite-internal, transient)
IGNORE_TABLES = {"sqlite_sequence", "sqlite_stat1", "sqlite_stat4"}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _row_counts_local() -> Dict[str, int]:
    """Per-table row counts for the live local DB."""
    out: Dict[str, int] = {}
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        for (name,) in cur.fetchall():
            if name in IGNORE_TABLES:
                continue
            try:
                cur.execute(f'SELECT COUNT(*) FROM "{name}"')
                out[name] = cur.fetchone()[0]
            except sqlite3.Error:
                out[name] = -1
    return out


def _ssh(cmd: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a command on the VM over ssh."""
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", VM_HOST, cmd],
        capture_output=True, text=True, timeout=timeout,
    )


def _row_counts_remote() -> Dict[str, int]:
    """Per-table row counts read remotely from VM_DB_PATH."""
    # One sqlite invocation; emit rows as 'table\tcount'.
    sql = (
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    )
    list_proc = _ssh(f"sqlite3 -readonly {shlex.quote(VM_DB_PATH)} {shlex.quote(sql)}")
    if list_proc.returncode != 0:
        raise RuntimeError(f"remote table list failed: {list_proc.stderr.strip()}")
    tables = [t for t in list_proc.stdout.strip().splitlines() if t]
    if not tables:
        return {}
    # Build a single SELECT ... UNION ALL to fetch all counts at once.
    union = " UNION ALL ".join(
        f"SELECT '{t}' AS t, COUNT(*) AS c FROM \"{t}\"" for t in tables
    )
    proc = _ssh(
        f"sqlite3 -readonly -separator '\t' {shlex.quote(VM_DB_PATH)} "
        f"{shlex.quote(union)}"
    )
    if proc.returncode != 0:
        raise RuntimeError(f"remote count failed: {proc.stderr.strip()}")
    out: Dict[str, int] = {}
    for line in proc.stdout.strip().splitlines():
        if "\t" not in line:
            continue
        name, n = line.split("\t", 1)
        try:
            out[name] = int(n)
        except ValueError:
            out[name] = -1
    return out


def _git(args: List[str], timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=timeout,
    )


def _humanize_age(ts: str) -> str:
    """Convert ISO/sqlite timestamp to '5m ago' / '3.2h ago' / '2.1d ago'."""
    try:
        clean = ts.replace("T", " ").split(".")[0].replace("Z", "")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (datetime.now(timezone.utc) - dt).total_seconds()
        if delta < 60:
            return f"{int(delta)}s"
        if delta < 3600:
            return f"{int(delta // 60)}m"
        if delta < 86400:
            return f"{delta / 3600:.1f}h"
        return f"{delta / 86400:.1f}d"
    except Exception:
        return ts


# ----------------------------------------------------------------------
# Pipeline steps
# ----------------------------------------------------------------------

def _step_wal_checkpoint() -> Dict[str, Any]:
    """Flush WAL into the main DB so state.db is byte-complete on its own."""
    with closing(sqlite3.connect(str(LOCAL_DB))) as conn:
        cur = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        busy, log_pages, checkpointed = cur.fetchone()
    return {"busy": busy, "log_pages": log_pages, "checkpointed": checkpointed}


def _step_git_commit(reason: str) -> Dict[str, Any]:
    """Best-effort commit of dirty tree. Non-fatal: returns status either way."""
    info: Dict[str, Any] = {"committed": False}
    status = _git(["status", "--porcelain"])
    if status.returncode != 0:
        info["error"] = status.stderr.strip()
        return info
    dirty = [ln for ln in status.stdout.splitlines() if ln.strip()]
    info["dirty_files"] = len(dirty)
    if not dirty:
        info["note"] = "tree clean, nothing to commit"
        return info
    add = _git(["add", "-A"])
    if add.returncode != 0:
        info["error"] = f"git add failed: {add.stderr.strip()}"
        return info
    msg = f"checkpoint: {reason} ({len(dirty)} files)"
    commit = _git(["commit", "-m", msg, "--no-verify"])
    if commit.returncode != 0:
        info["error"] = f"git commit failed: {commit.stderr.strip() or commit.stdout.strip()}"
        return info
    sha = _git(["rev-parse", "--short", "HEAD"])
    info["committed"] = True
    info["sha"] = sha.stdout.strip() if sha.returncode == 0 else None
    info["message"] = msg
    return info


def _step_rsync() -> Dict[str, Any]:
    """Rsync the local state.db to the VM. WAL/SHM are NOT shipped (not needed
    after a TRUNCATE checkpoint, and shipping them would risk a torn DB)."""
    # Ensure remote dir exists.
    mk = _ssh(f"mkdir -p {shlex.quote(os.path.dirname(VM_DB_PATH))}")
    if mk.returncode != 0:
        return {"ok": False, "error": f"mkdir failed: {mk.stderr.strip()}"}
    # Delete any stale -wal/-shm on the VM so it can't try to apply them
    # to the newly-arrived complete file.
    _ssh(f"rm -f {shlex.quote(VM_DB_PATH)}-wal {shlex.quote(VM_DB_PATH)}-shm")
    started = time.time()
    proc = subprocess.run(
        [
            "rsync", "-az", "--inplace", "--partial",
            str(LOCAL_DB), f"{VM_HOST}:{VM_DB_PATH}",
        ],
        capture_output=True, text=True, timeout=600,
    )
    out = {
        "ok": proc.returncode == 0,
        "duration_s": round(time.time() - started, 2),
        "size_bytes": LOCAL_DB.stat().st_size,
    }
    if proc.returncode != 0:
        out["error"] = proc.stderr.strip() or proc.stdout.strip()
    return out


def _step_verify_replica() -> Dict[str, Any]:
    """Compare row counts table-by-table. Replica is good iff every table matches."""
    local = _row_counts_local()
    remote = _row_counts_remote()
    missing = sorted(t for t in local if t not in remote)
    extra = sorted(t for t in remote if t not in local)
    mismatched: Dict[str, List[int]] = {}
    for t, n in local.items():
        if t in remote and remote[t] != n:
            mismatched[t] = [n, remote[t]]
    ok = not (missing or extra or mismatched)
    return {
        "ok": ok,
        "local_tables": len(local),
        "remote_tables": len(remote),
        "missing_on_remote": missing,
        "extra_on_remote": extra,
        "mismatched": mismatched,
        "total_local_rows": sum(v for v in local.values() if v >= 0),
        "total_remote_rows": sum(v for v in remote.values() if v >= 0),
    }


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------

def create_checkpoint(reason: str = "manual", commit: bool = True) -> Dict[str, Any]:
    """
    Atomic checkpoint pipeline:
      1. WAL checkpoint(TRUNCATE)
      2. (optional) git commit dirty tree
      3. rsync state.db to AIOS:/opt/aios/data/db/state.db
      4. verify per-table row counts match

    Logs one event_type='checkpoint' row with the full summary as metadata.
    """
    started = time.time()
    summary: Dict[str, Any] = {
        "reason": reason,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "vm_host": VM_HOST,
        "vm_db_path": VM_DB_PATH,
        "steps": {},
        "ok": False,
    }

    try:
        summary["steps"]["wal_checkpoint"] = _step_wal_checkpoint()
        if commit:
            summary["steps"]["git_commit"] = _step_git_commit(reason)
        summary["steps"]["rsync"] = _step_rsync()
        if not summary["steps"]["rsync"].get("ok"):
            raise RuntimeError("rsync failed; aborting verify")
        summary["steps"]["verify"] = _step_verify_replica()
        summary["ok"] = bool(summary["steps"]["verify"].get("ok"))
    except Exception as e:
        summary["error"] = f"{type(e).__name__}: {e}"

    summary["duration_s"] = round(time.time() - started, 2)
    summary["finished_at"] = datetime.now(timezone.utc).isoformat()

    # Write the checkpoint as a timeline event.
    flag = "ok" if summary["ok"] else "FAIL"
    headline = f"[{flag}] checkpoint -> {VM_HOST}: {reason}"
    if summary["ok"]:
        v = summary["steps"].get("verify", {})
        headline += f" ({v.get('local_tables', '?')} tables, {v.get('total_local_rows', '?')} rows)"
    elif "error" in summary:
        headline += f" — {summary['error'][:80]}"

    try:
        log_event(
            event_type="checkpoint",
            data=headline,
            metadata=summary,
            source="log.checkpoint",
        )
    except Exception as e:
        # Don't let logging failure mask the checkpoint result.
        summary.setdefault("warnings", []).append(f"log_event failed: {e}")

    return summary


def get_last_checkpoint() -> Optional[Dict[str, Any]]:
    """Return the most recent checkpoint event, or None."""
    with closing(get_connection(readonly=True)) as conn:
        row = conn.execute(
            "SELECT timestamp, data, metadata_json "
            "FROM unified_events "
            "WHERE event_type = 'checkpoint' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    md: Dict[str, Any] = {}
    if row["metadata_json"]:
        try:
            md = json.loads(row["metadata_json"]) or {}
        except Exception:
            md = {}
    ok = bool(md.get("ok"))
    return {
        "timestamp": row["timestamp"],
        "age_human": _humanize_age(row["timestamp"]),
        "ok": ok,
        "status_label": "vm-replica ok" if ok else "vm-replica FAIL",
        "headline": row["data"],
        "reason": md.get("reason"),
        "duration_s": md.get("duration_s"),
        "summary": md,
    }


def list_checkpoints(limit: int = 10) -> List[Dict[str, Any]]:
    """Return recent checkpoints (newest first)."""
    out: List[Dict[str, Any]] = []
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute(
            "SELECT timestamp, data, metadata_json "
            "FROM unified_events "
            "WHERE event_type = 'checkpoint' "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    for row in rows:
        md: Dict[str, Any] = {}
        if row["metadata_json"]:
            try:
                md = json.loads(row["metadata_json"]) or {}
            except Exception:
                md = {}
        out.append({
            "timestamp": row["timestamp"],
            "age_human": _humanize_age(row["timestamp"]),
            "ok": bool(md.get("ok")),
            "reason": md.get("reason"),
            "headline": row["data"],
        })
    return out


__all__ = ["create_checkpoint", "get_last_checkpoint", "list_checkpoints"]
