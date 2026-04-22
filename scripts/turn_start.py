"""
scripts/turn_start.py — Single entry point every coding turn must start with.

Usage:
    python3 scripts/turn_start.py "<one-line summary of user's ask>"

What it does (in order):
    1. Records a timestamp to ``data/.last_state_read`` so turn-end can
       confirm the ritual actually fired on this turn.
    2. Calls ``get_subconscious().get_state(query)`` — the same assembly
       the live agent uses at inference time.
    3. Prints the STATE block.
    4. Appends a *compact* health line:
         - time since last run (how stale was my prior snapshot?)
         - total events in log thread
         - idle time since the live daemon last emitted an event
         - any empty / crashed thread blocks

Design notes:
    - This is deliberately one file, one command.  The workspace
      instructions only have to say "start every turn with
      ``scripts/turn_start.py``" and there is no way to forget a flag.
    - Exit code is always 0 unless STATE itself failed to build;
      a broken STATE always takes priority over the user's request.
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MARKER = ROOT / "data" / ".last_state_read"

# Commit-limit thresholds.  These drive banner warnings and the
# `[consequences]` section of the log metadata.  Tune in one place.
SOFT_UNCOMMITTED_LIMIT = 10   # a nudge
HARD_UNCOMMITTED_LIMIT = 25   # stop coding, run tests + commit
STALE_COMMIT_AGE_H = 4.0      # if HEAD is older than this while changes pile up


def _stamp(query: str) -> dict:
    """Write the marker and return metadata including prior-run stats."""
    prior = None
    if MARKER.exists():
        try:
            prior = json.loads(MARKER.read_text())
        except Exception:
            prior = None

    now_ts = time.time()
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")

    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(json.dumps({
        "ts": now_ts,
        "iso": now_iso,
        "query": query,
    }, indent=2))

    out = {"now": now_iso, "prior_age_seconds": None}
    if prior and "ts" in prior:
        out["prior_age_seconds"] = round(now_ts - prior["ts"], 1)
        out["prior_query"] = prior.get("query", "")
        out["prior_ts"] = prior["ts"]
    return out


def _git_delta(since_ts: float | None) -> dict:
    """What changed in the working tree since the prior turn-start.

    Uses two cheap git calls:
      - ``git status --porcelain``: uncommitted changes right now.
      - ``git log --name-only --since=<ts>``: commits landed between turns.

    Everything is best-effort; if git isn't available or this isn't a
    repo, return an empty delta.  The caller must never fail on this.
    """
    import subprocess
    delta: dict = {"uncommitted": [], "committed": [], "commits": []}
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT, capture_output=True, text=True, timeout=3,
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                # Porcelain: "XY path"
                path = line[3:].strip()
                if path:
                    delta["uncommitted"].append(path)
    except Exception:
        pass

    if since_ts:
        try:
            since_iso = datetime.fromtimestamp(since_ts, tz=timezone.utc).isoformat()
            r = subprocess.run(
                ["git", "log", f"--since={since_iso}",
                 "--pretty=format:%h %s", "--name-only"],
                cwd=ROOT, capture_output=True, text=True, timeout=3,
            )
            if r.returncode == 0 and r.stdout.strip():
                current_commit = None
                files: set[str] = set()
                for line in r.stdout.splitlines():
                    if not line.strip():
                        continue
                    # A commit header line starts with a short hash + space + subject
                    if re.match(r"^[0-9a-f]{7,40}\s", line):
                        if current_commit:
                            delta["commits"].append(current_commit)
                        current_commit = {"hdr": line.strip(), "files": []}
                    else:
                        if current_commit is not None:
                            current_commit["files"].append(line.strip())
                        files.add(line.strip())
                if current_commit:
                    delta["commits"].append(current_commit)
                delta["committed"] = sorted(files)
        except Exception:
            pass

    # How long since the last commit, anywhere on the current branch?
    # Independent of prior-turn timestamp.
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, timeout=3,
        )
        if r.returncode == 0 and r.stdout.strip():
            last_commit_ts = int(r.stdout.strip())
            delta["last_commit_age_s"] = int(time.time() - last_commit_ts)
    except Exception:
        pass

    return delta


def _scan_state(state: str) -> dict:
    """Cheap sanity scan: count blocks, flag any that look empty."""
    blocks = re.findall(r"^\[(\w+)\][^\n]*$", state, flags=re.MULTILINE)
    block_set = sorted(set(blocks))
    empty = []
    for name in block_set:
        # Block is "empty" if the only line in its section is the header
        # followed immediately by another `[name]` or end of string, OR
        # if fact_count is 0.
        m = re.search(
            rf"^\[{re.escape(name)}\].*?(?=^\[|\Z)",
            state, flags=re.MULTILINE | re.DOTALL,
        )
        if not m:
            continue
        section = m.group(0)
        fc = re.search(r"fact_count:\s*(\d+)", section)
        if fc and int(fc.group(1)) == 0:
            empty.append(name)
    return {"blocks": block_set, "empty_or_zero_fact": empty}


def _grade_prior_turn(current_uncommitted: list, current_committed: list) -> dict:
    """Grade the most recent prior ``agent_turn`` event.

    Reads the last ``agent_turn`` row (which is the *prior* turn, because
    the current turn's residue has not been written yet), pulls the
    ``files_touched`` list from its metadata, and classifies each file:

      - ``surviving_uncommitted``: still dirty → change still present, not
        yet committed
      - ``committed``: made it into a commit between then and now
      - ``reverted_or_clean``: file no longer appears anywhere → either the
        change was reverted or the checkout was restored

    Returns a dict with counts + a ``status`` one-liner and writes a single
    ``turn_outcome`` event tagged to the prior turn.  All DB writes
    best-effort; grading failure never breaks the ritual.
    """
    out: dict = {
        "graded": False,
        "prior_turn_id": None,
        "surviving": 0,
        "committed": 0,
        "reverted": 0,
        "total": 0,
        "status": None,
        "outcome_event_id": None,
        "errors": [],
    }
    try:
        import json as _json
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            row = conn.execute(
                """
                SELECT id, data, metadata_json, timestamp
                FROM unified_events
                WHERE event_type = 'agent_turn'
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return out  # no prior turn to grade — this is the first ever
        out["prior_turn_id"] = row["id"]
        md = {}
        if row["metadata_json"]:
            try:
                md = _json.loads(row["metadata_json"]) or {}
            except Exception:
                md = {}
        # Was that prior turn already graded?  (If we ever double-fire
        # turn-start, don't double-grade.)
        if md.get("graded"):
            return out
        prior_files = md.get("files_touched") or []
        prior_count = md.get("files_touched_count", len(prior_files))
        if not prior_files:
            return out  # nothing to grade

        cur_uncommitted_set = set(current_uncommitted)
        cur_committed_set = set(current_committed)
        surviving, committed, reverted = [], [], []
        for p in prior_files:
            if p in cur_uncommitted_set:
                surviving.append(p)
            elif p in cur_committed_set:
                committed.append(p)
            else:
                reverted.append(p)
        total = len(prior_files)
        out.update({
            "graded": True,
            "surviving": len(surviving),
            "committed": len(committed),
            "reverted": len(reverted),
            "total": total,
            "sample_files_capped_at_25": total != prior_count,
        })

        # Status rules (order matters):
        #   all reverted → [broken]
        #   any committed, nothing reverted → [success]
        #   mostly surviving → [partial]
        #   mostly reverted → [reverted]
        if total and len(reverted) == total:
            status = "broken"
        elif len(committed) > 0 and len(reverted) == 0:
            status = "success"
        elif len(reverted) > total / 2:
            status = "reverted"
        else:
            status = "partial"
        out["status"] = status

        # Emit a turn_outcome event linked to the prior turn id
        try:
            from agent.threads.log.schema import log_event
            out["outcome_event_id"] = log_event(
                event_type="turn_outcome",
                data=(
                    f"prior turn [{status}]: "
                    f"{len(surviving)}/{total} still dirty, "
                    f"{len(committed)} committed, "
                    f"{len(reverted)} reverted"
                ),
                metadata={
                    "prior_turn_event_id": row["id"],
                    "status": status,
                    "surviving": len(surviving),
                    "committed": len(committed),
                    "reverted": len(reverted),
                    "total_graded": total,
                    "sample_files_capped_at_25": total != prior_count,
                    "sample_reverted": reverted[:10],
                    "sample_committed": committed[:10],
                },
                source="agent.turn_start",
            )
        except Exception as exc:  # pragma: no cover
            out["errors"].append(f"log_event(outcome): {exc!r}")

        # Also drop a reflex meta-thought so the pattern shows up in the
        # reflex block, not only in log.events.
        try:
            from agent.threads.reflex.schema import add_meta_thought
            kind = "expected" if status == "success" else "rejected"
            add_meta_thought(
                kind=kind,
                content=(
                    f"prior turn graded [{status}]: "
                    f"{len(surviving)} survived, "
                    f"{len(committed)} committed, "
                    f"{len(reverted)} reverted "
                    f"of {total}"
                ),
                source="system",
                confidence=0.8,
                weight=0.8,
            )
        except Exception as exc:  # pragma: no cover
            out["errors"].append(f"add_meta_thought(outcome): {exc!r}")

        # Mark the prior turn as graded so a second turn-start doesn't
        # double-count.  Uses a direct UPDATE since log_event doesn't
        # expose a mutation path for existing rows.
        try:
            from data.db import get_connection
            from contextlib import closing
            md["graded"] = True
            md["graded_status"] = status
            with closing(get_connection()) as conn:
                conn.execute(
                    "UPDATE unified_events SET metadata_json = ? WHERE id = ?",
                    (_json.dumps(md), row["id"]),
                )
                conn.commit()
        except Exception as exc:  # pragma: no cover
            out["errors"].append(f"mark_graded: {exc!r}")

    except Exception as exc:  # pragma: no cover
        out["errors"].append(f"grade_prior_turn: {exc!r}")
    return out


def _leave_residue(
    query: str,
    prior_age_seconds: float | None,
    delta: dict,
) -> dict:
    """Drop breadcrumbs so the *next* turn's STATE sees what happened here.

    Three writes, all best-effort:
      1. ``unified_events``: a ``agent_turn`` row carrying the query and
         which files changed since the prior turn (in metadata).
      2. If any files changed: one ``code_change`` row per file, so the
         log block surfaces real paths, not just "something happened".
      3. ``reflex_meta_thoughts``: a ``compression`` meta-thought that
         pins the current topic + file list to the rolling summary slot.

    Nothing here may raise; the ritual must never fail because of
    logging side-effects.
    """
    out: dict = {
        "event_id": None,
        "code_event_ids": [],
        "meta_thought_id": None,
        "errors": [],
    }
    touched = sorted(set(delta.get("uncommitted", []) + delta.get("committed", [])))

    # Primary agent_turn event
    try:
        from agent.threads.log.schema import log_event
        gap = round(prior_age_seconds, 1) if prior_age_seconds is not None else None
        out["event_id"] = log_event(
            event_type="agent_turn",
            data=f"VS Code coding turn: {query}",
            metadata={
                "source_runtime": "vscode_copilot",
                "prior_turn_age_seconds": gap,
                "files_touched_count": len(touched),
                "files_touched": touched[:25],
                "commits_landed": [c["hdr"] for c in delta.get("commits", [])][:10],
            },
            source="agent.turn_start",
        )
    except Exception as exc:  # pragma: no cover
        out["errors"].append(f"log_event(turn): {exc!r}")

    # One code_change event per touched file.  Cap conservatively — the
    # primary agent_turn event already carries the full list in metadata,
    # so these individual rows exist for high-signal display in the log
    # block, not as the source of truth.  8 is enough to be representative
    # without drowning the log stream in a single turn.
    try:
        from agent.threads.log.schema import log_event
        for path in touched[:8]:
            ev_id = log_event(
                event_type="code_change",
                data=f"M {path}",
                metadata={
                    "path": path,
                    "turn_query": query,
                    "total_files_in_turn": len(touched),
                },
                source="agent.turn_start",
            )
            if ev_id:
                out["code_event_ids"].append(ev_id)
    except Exception as exc:  # pragma: no cover
        out["errors"].append(f"log_event(code_change): {exc!r}")

    # Meta-thought: kind="compression" is the rolling-topic slot.
    try:
        from agent.threads.reflex.schema import add_meta_thought
        content = f"coder working on: {query}"
        if touched:
            content += f" | touched {len(touched)} files: " + ", ".join(touched[:5])
            if len(touched) > 5:
                content += f" (+{len(touched) - 5} more)"
        out["meta_thought_id"] = add_meta_thought(
            kind="compression",
            content=content,
            source="system",
            confidence=0.7,
            weight=0.7,
        )
    except Exception as exc:  # pragma: no cover
        out["errors"].append(f"add_meta_thought: {exc!r}")

    return out


def _sync_to_chat(query: str, state_snapshot: str, delta: dict, residue: dict) -> dict:
    """Mirror this turn into the AIOS chat tables so it shows up in the UI.

    Design:
      - One convo per UTC day, session_id ``vscode_copilot_<YYYY-MM-DD>``.
      - ``user_message`` = the coder's query.
      - ``assistant_message`` starts as a placeholder; the NEXT turn-start
        rewrites it with the graded outcome once residue has settled.
      - ``metadata_json`` carries the full STATE snapshot that was in
        scope when this query arrived — that is the training pair input.

    Result: every VS Code coding turn becomes a training example of the
    form ``(state_before, query) -> (files_changed, grade)``, and the
    AIOS chat UI shows the conversation live.
    """
    out: dict = {"convo_turn_id": None, "session_id": None, "errors": []}
    try:
        from chat.schema import add_turn, save_conversation
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        session_id = f"vscode_copilot_{day}"
        out["session_id"] = session_id

        # Ensure the convo exists with a readable name + copilot source.
        # save_conversation is idempotent (UPSERT on session_id).
        try:
            save_conversation(
                session_id=session_id,
                name=f"VS Code coding — {day}",
                channel="vscode",
                source="copilot",
            )
        except Exception as exc:
            out["errors"].append(f"save_conversation: {exc!r}")

        touched = sorted(set(
            delta.get("uncommitted", []) + delta.get("committed", [])
        ))
        metadata = {
            "source": "vscode_copilot",
            "state_snapshot": state_snapshot,
            "state_len": len(state_snapshot),
            "files_touched_at_start": touched[:50],
            "files_touched_count": len(touched),
            "agent_turn_event_id": residue.get("event_id"),
            "reflex_meta_thought_id": residue.get("meta_thought_id"),
            "outcome_filled": False,
        }
        # Placeholder assistant message — the NEXT turn-start will rewrite
        # this once the outcome is known.
        turn_index = add_turn(
            session_id=session_id,
            user_message=query,
            assistant_message="[turn in progress — outcome pending]",
            feed_type="coding",
            context_level=2,
            metadata=metadata,
        )
        out["convo_turn_id"] = turn_index
    except Exception as exc:  # pragma: no cover
        out["errors"].append(f"sync_to_chat: {exc!r}")
    return out


def _fill_prior_assistant_message(grade: dict, delta: dict) -> dict:
    """Rewrite the prior convo_turn row with its graded outcome.

    Only runs if ``grade['graded']`` is true.  Matches the prior turn by
    ``agent_turn_event_id`` stored in metadata (the most reliable link
    — session_id rolls over at UTC midnight).
    """
    out: dict = {"updated": False, "convo_turn_id": None, "errors": []}
    if not grade.get("graded"):
        return out
    prior_event_id = grade.get("prior_turn_id")
    if not prior_event_id:
        return out
    try:
        import json as _json
        from contextlib import closing
        from data.db import get_connection

        # Build the assistant message from observed outcome.
        status = grade.get("status", "unknown")
        lines = [f"[{status}] "
                 f"survived={grade['surviving']}  "
                 f"committed={grade['committed']}  "
                 f"reverted={grade['reverted']}  "
                 f"of {grade['total']} tracked files"]
        commits = delta.get("commits") or []
        if commits:
            lines.append("")
            lines.append("commits since prior turn:")
            for c in commits[:5]:
                lines.append(f"  - {c['hdr']}")
        assistant_message = "\n".join(lines)

        with closing(get_connection()) as conn:
            cur = conn.cursor()
            # Find the convo_turn whose metadata points at this event id.
            cur.execute("""
                SELECT id, metadata_json
                FROM convo_turns
                WHERE metadata_json LIKE ?
                ORDER BY id DESC
                LIMIT 1
            """, (f'%"agent_turn_event_id": {int(prior_event_id)}%',))
            row = cur.fetchone()
            if row is None:
                return out
            turn_id = row[0]
            md = {}
            if row[1]:
                try:
                    md = _json.loads(row[1]) or {}
                except Exception:
                    md = {}
            md["outcome_filled"] = True
            md["graded_status"] = status
            md["grade_counts"] = {
                "surviving": grade["surviving"],
                "committed": grade["committed"],
                "reverted": grade["reverted"],
                "total": grade["total"],
            }
            cur.execute("""
                UPDATE convo_turns
                SET assistant_message = ?, metadata_json = ?
                WHERE id = ?
            """, (assistant_message, _json.dumps(md), turn_id))
            conn.commit()
            out["updated"] = True
            out["convo_turn_id"] = turn_id
    except Exception as exc:  # pragma: no cover
        out["errors"].append(f"fill_prior_assistant_message: {exc!r}")
    return out


def main() -> int:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        print(
            "usage: turn_start.py \"<one-line summary of the user's ask>\"",
            file=sys.stderr,
        )
        return 2

    stamp = _stamp(query)

    try:
        from agent.subconscious.orchestrator import get_subconscious
        state = get_subconscious().get_state(query=query)
    except Exception as exc:
        print(f"!! STATE BUILD FAILED: {exc!r}", file=sys.stderr)
        print("Broken STATE takes priority over the user's request.", file=sys.stderr)
        return 1

    scan = _scan_state(state)
    delta = _git_delta(stamp.get("prior_ts"))
    # Grade the prior turn BEFORE leaving residue — otherwise we'd grade
    # ourselves.  Uses the current tree vs. the prior turn's recorded
    # file list.
    grade = _grade_prior_turn(
        current_uncommitted=delta.get("uncommitted", []),
        current_committed=delta.get("committed", []),
    )
    residue = _leave_residue(query, stamp["prior_age_seconds"], delta)
    # Now that we know the prior grade, rewrite the prior convo_turn's
    # assistant_message (if any).  This makes the AIOS chat UI show the
    # real outcome instead of the placeholder we wrote last turn.
    fill_out = _fill_prior_assistant_message(grade, delta)
    # Mirror this turn into the chat tables so it shows up in the AIOS UI
    # and, crucially, so the STATE snapshot is paired with the query for
    # training.
    chat_out = _sync_to_chat(query, state, delta, residue)

    banner = "═" * 72
    print(banner)
    print(f"AIOS TURN-START  •  query={query!r}")
    if stamp["prior_age_seconds"] is not None:
        age = stamp["prior_age_seconds"]
        if age < 120:
            age_str = f"{age:.0f}s"
        elif age < 7200:
            age_str = f"{age / 60:.1f}m"
        else:
            age_str = f"{age / 3600:.1f}h"
        print(f"prior turn-start: {age_str} ago  ({stamp.get('prior_query','')!r})")
    else:
        print("prior turn-start: none (first run)")
    print(f"state: {len(state)} chars  •  blocks: {', '.join(scan['blocks'])}")
    if scan["empty_or_zero_fact"]:
        print(f"!! zero-fact blocks: {', '.join(scan['empty_or_zero_fact'])}")
    touched = sorted(set(delta.get("uncommitted", []) + delta.get("committed", [])))
    if touched:
        preview = ", ".join(touched[:5])
        if len(touched) > 5:
            preview += f" (+{len(touched) - 5} more)"
        print(f"git delta since prior turn: {len(touched)} file(s) — {preview}")

    # Prior-turn grade (do I have a track record?)
    if grade.get("graded"):
        icon = {
            "success": "✓",
            "partial": "~",
            "reverted": "↩",
            "broken": "✗",
        }.get(grade["status"], "?")
        print(
            f"prior turn grade: [{icon} {grade['status']}]  "
            f"survived={grade['surviving']}  "
            f"committed={grade['committed']}  "
            f"reverted={grade['reverted']}  "
            f"of {grade['total']} tracked files"
        )

    # Consequences — what does the working tree look like right now?
    uncommitted = delta.get("uncommitted", [])
    last_commit_age_s = delta.get("last_commit_age_s")
    if uncommitted or last_commit_age_s is not None:
        print("")
        print("[consequences] what just happened / where we stand:")
        print(f"  uncommitted: {len(uncommitted)} file(s)")
        if last_commit_age_s is not None:
            if last_commit_age_s < 3600:
                age_s = f"{last_commit_age_s // 60}m"
            elif last_commit_age_s < 86400:
                age_s = f"{last_commit_age_s / 3600:.1f}h"
            else:
                age_s = f"{last_commit_age_s / 86400:.1f}d"
            print(f"  last_commit: {age_s} ago")
        # Threshold enforcement
        n = len(uncommitted)
        if n >= HARD_UNCOMMITTED_LIMIT:
            print(f"  !! HARD LIMIT: {n} uncommitted files (>= {HARD_UNCOMMITTED_LIMIT}).")
            print("     STOP adding features. Run tests. Commit in logical chunks.")
        elif n >= SOFT_UNCOMMITTED_LIMIT:
            print(f"  !  soft limit: {n} uncommitted files (>= {SOFT_UNCOMMITTED_LIMIT}).")
            print("     Consider a checkpoint commit before the next significant change.")
        # Stale HEAD with active changes is a stronger signal than either alone
        if (last_commit_age_s is not None
                and last_commit_age_s >= STALE_COMMIT_AGE_H * 3600
                and n >= SOFT_UNCOMMITTED_LIMIT):
            print(f"  !  HEAD is {age_s} old with {n} uncommitted files — long-lived divergence.")
    residue_parts = []
    if residue["event_id"]:
        residue_parts.append(f"event#{residue['event_id']}")
    if residue["code_event_ids"]:
        residue_parts.append(f"code_events×{len(residue['code_event_ids'])}")
    if residue["meta_thought_id"]:
        residue_parts.append(f"meta#{residue['meta_thought_id']}")
    if residue_parts:
        print(f"residue: {', '.join(residue_parts)}")
    if residue["errors"]:
        print(f"!! residue errors: {residue['errors']}")

    # Chat sync — this turn is now visible in the AIOS UI.
    chat_parts = []
    if chat_out.get("convo_turn_id") is not None:
        chat_parts.append(
            f"convo={chat_out['session_id']} turn#{chat_out['convo_turn_id']}"
        )
    if fill_out.get("updated"):
        chat_parts.append(
            f"filled prior_turn#{fill_out['convo_turn_id']}"
        )
    if chat_parts:
        print(f"chat-sync: {', '.join(chat_parts)}")
    if chat_out.get("errors") or fill_out.get("errors"):
        errs = (chat_out.get("errors") or []) + (fill_out.get("errors") or [])
        print(f"!! chat-sync errors: {errs}")

    # Unread pings from the user — surface at top-of-turn.
    try:
        from contextlib import closing as _closing
        from data.db import get_connection as _get_conn
        with _closing(_get_conn(readonly=True)) as _c:
            row = _c.execute(
                "SELECT COUNT(*), COALESCE(MAX(id), 0) FROM notifications "
                "WHERE read = 0 AND dismissed = 0"
            ).fetchone()
            unread = (row[0] if row else 0) or 0
            if unread:
                latest = _c.execute(
                    "SELECT id, priority, substr(message, 1, 100) FROM notifications "
                    "WHERE read = 0 AND dismissed = 0 ORDER BY id DESC LIMIT 1"
                ).fetchone()
                print(f"pings: {unread} unread (latest #{latest[0]} [{latest[1]}]: {latest[2]})")
    except Exception:
        pass

    print(banner)
    print(state)
    print(banner)
    print("ritual-ok  •  marker:", MARKER.relative_to(ROOT))
    # Autopilot self-reminder.  Copilot-instructions.md is NOT re-injected
    # on autopilot turns, so the ritual has to be visible in the tool
    # output itself.  This is the last thing I see in scrollback.
    print("")
    print("┌" + "─" * 70 + "┐")
    print("│ AUTOPILOT REMINDER: run  .venv/bin/python scripts/turn_start.py  │")
    print("│ \"<one-line summary>\" at the START of EVERY next turn.            │")
    print("│ STATE is not automatic on autopilot. You must re-fetch it.       │")
    print("└" + "─" * 70 + "┘")
    return 0


if __name__ == "__main__":
    sys.exit(main())
