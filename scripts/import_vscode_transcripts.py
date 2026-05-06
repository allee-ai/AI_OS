#!/usr/bin/env python3
"""
Import VS Code Copilot Chat .jsonl transcripts into AI_OS state.db.

For each transcript:
  - Upserts a row in `convos` (source='vscode-copilot', session_id from filename)
  - Pairs user.message / assistant.message into `convo_turns`
  - Writes EVERY tool.execution_complete into `tool_traces` (subagent calls included)
  - Logs one `unified_events` row per imported session

Idempotent on session_id: re-running replaces turns/traces for that session.

Usage:
  .venv/bin/python scripts/import_vscode_transcripts.py            # auto-discover
  .venv/bin/python scripts/import_vscode_transcripts.py PATH...    # specific files
"""
from __future__ import annotations

import json
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.db import get_connection  # noqa: E402
from agent.threads.log.schema import log_event  # noqa: E402

VSCODE_STORAGE = (
    Path.home()
    / "Library/Application Support/Code/User/workspaceStorage"
)


def discover_transcripts() -> List[Path]:
    if not VSCODE_STORAGE.exists():
        return []
    return sorted(VSCODE_STORAGE.glob("*/GitHub.copilot-chat/transcripts/*.jsonl"))


def _ts_to_iso(ts) -> Optional[str]:
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts  # already ISO
    try:
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
    except Exception:
        return None


def _read_lines(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _extract_text(content: Any) -> str:
    """assistant.message.content can be string or list-of-parts."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict):
                for k in ("text", "value", "content"):
                    v = p.get(k)
                    if isinstance(v, str) and v.strip():
                        parts.append(v)
                        break
        return "\n".join(parts)
    if isinstance(content, dict):
        for k in ("text", "value", "content"):
            v = content.get(k)
            if isinstance(v, str):
                return v
    return ""


def import_transcript(path: Path) -> Dict[str, Any]:
    session_id = f"vscode_copilot_{path.stem}"
    title = f"VS Code Copilot session {path.stem[:8]}"

    # --- pass 1: load events ---
    events = list(_read_lines(path))
    if not events:
        return {"path": str(path), "skipped": "empty"}

    started_iso = None
    last_iso = None
    user_msgs: List[Dict[str, Any]] = []
    assistant_msgs: List[Dict[str, Any]] = []
    tool_starts: Dict[str, Dict[str, Any]] = {}
    tool_traces: List[Dict[str, Any]] = []

    for ev in events:
        et = ev.get("type")
        ts_iso = _ts_to_iso(ev.get("timestamp"))
        if started_iso is None and ts_iso:
            started_iso = ts_iso
        if ts_iso:
            last_iso = ts_iso
        data = ev.get("data") or {}

        if et == "user.message":
            user_msgs.append({
                "ts": ts_iso,
                "id": ev.get("id"),
                "parent": ev.get("parentId"),
                "text": _extract_text(data.get("content")),
                "attachments": data.get("attachments") or [],
            })
        elif et == "assistant.message":
            assistant_msgs.append({
                "ts": ts_iso,
                "id": ev.get("id"),
                "parent": ev.get("parentId"),
                "text": _extract_text(data.get("content")),
                "tool_requests": data.get("toolRequests") or [],
                "reasoning": data.get("reasoningText") or "",
            })
        elif et == "tool.execution_start":
            tid = data.get("toolCallId") or data.get("callId") or ev.get("id")
            tool_starts[str(tid)] = {
                "ts": ts_iso,
                "tool": data.get("toolName") or data.get("name") or "unknown",
                "params": data.get("arguments") or data.get("parameters") or data.get("input") or {},
            }
        elif et == "tool.execution_complete":
            tid = data.get("toolCallId") or data.get("callId") or ev.get("parentId")
            start = tool_starts.pop(str(tid), {}) if tid else {}
            tool_name = start.get("tool") or data.get("toolName") or data.get("name") or "unknown"
            success = bool(data.get("success", True))
            err = data.get("error")
            if err:
                success = False
            output = data.get("output") or data.get("result") or ""
            if not isinstance(output, str):
                try:
                    output = json.dumps(output, default=str)[:1000]
                except Exception:
                    output = str(output)[:1000]
            duration_ms = data.get("durationMs") or data.get("duration") or 0
            tool_traces.append({
                "ts": ts_iso,
                "tool": tool_name,
                "action": data.get("action") or "invoke",
                "success": success,
                "output": (output or (err or ""))[:1000],
                "duration_ms": int(duration_ms) if isinstance(duration_ms, (int, float)) else 0,
                "params_preview": json.dumps(start.get("params", {}), default=str)[:500],
            })

    # Pair user→assistant by timestamp ordering (assistant follows user).
    turns: List[Dict[str, Any]] = []
    ai_idx = 0
    for u in user_msgs:
        # find next assistant message after this user msg
        a_text = ""
        a_meta: Dict[str, Any] = {}
        while ai_idx < len(assistant_msgs):
            a = assistant_msgs[ai_idx]
            if not u["ts"] or not a["ts"] or a["ts"] >= u["ts"]:
                # accumulate consecutive assistant messages until next user
                a_text_parts = [a["text"]]
                a_meta = {"reasoning": a.get("reasoning", "")[:2000],
                          "tool_request_count": len(a.get("tool_requests") or [])}
                ai_idx += 1
                while ai_idx < len(assistant_msgs):
                    nxt = assistant_msgs[ai_idx]
                    # stop if we'd cross another user message
                    next_user_ts = None
                    # peek: any later user.message ts?
                    a_text_parts.append(nxt["text"])
                    ai_idx += 1
                    break
                a_text = "\n".join(p for p in a_text_parts if p)
                break
            ai_idx += 1
        turns.append({
            "ts": u["ts"],
            "user": u["text"],
            "assistant": a_text,
            "meta": a_meta,
        })

    # --- pass 2: write to DB ---
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        # Upsert convo
        cur.execute("SELECT id FROM convos WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        if row:
            convo_id = row[0]
            cur.execute("DELETE FROM convo_turns WHERE convo_id = ?", (convo_id,))
            cur.execute(
                "UPDATE convos SET name=?, last_updated=?, turn_count=?, source=? WHERE id=?",
                (title, last_iso or started_iso, len(turns), "vscode-copilot", convo_id),
            )
        else:
            cur.execute(
                """INSERT INTO convos (session_id, channel, name, started, last_updated,
                                       turn_count, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, "import", title, started_iso, last_iso or started_iso,
                 len(turns), "vscode-copilot"),
            )
            convo_id = cur.lastrowid

        for i, t in enumerate(turns):
            cur.execute(
                """INSERT INTO convo_turns
                   (convo_id, turn_index, timestamp, user_message, assistant_message,
                    feed_type, context_level, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (convo_id, i, t["ts"], t["user"], t["assistant"],
                 "vscode-copilot", 0, json.dumps(t["meta"], default=str)),
            )

        # Wipe & re-insert tool_traces for this session
        cur.execute("DELETE FROM tool_traces WHERE session_id = ?", (session_id,))
        for tr in tool_traces:
            cur.execute(
                """INSERT INTO tool_traces
                   (tool, action, success, output, weight, duration_ms,
                    session_id, metadata_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (tr["tool"], tr["action"], 1 if tr["success"] else 0,
                 tr["output"], 0.5 if tr["success"] else 0.8,
                 tr["duration_ms"], session_id,
                 json.dumps({"params_preview": tr["params_preview"]}),
                 tr["ts"] or last_iso or datetime.now(timezone.utc).isoformat()),
            )

        conn.commit()

    # Log event so import surfaces in STATE
    log_event(
        event_type="chat_import",
        data=f"Imported VS Code Copilot transcript: {len(turns)} turns, {len(tool_traces)} tool calls",
        metadata={
            "session_id": session_id,
            "transcript_path": str(path),
            "turn_count": len(turns),
            "tool_trace_count": len(tool_traces),
            "tool_breakdown": _tool_breakdown(tool_traces),
        },
        source="local",
        session_id=session_id,
        thread_subject="vscode_chat_import",
        tags=["import", "vscode", "copilot"],
    )

    return {
        "path": str(path),
        "session_id": session_id,
        "turns": len(turns),
        "tool_traces": len(tool_traces),
        "tool_breakdown": _tool_breakdown(tool_traces),
    }


def _tool_breakdown(traces: List[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for t in traces:
        out[t["tool"]] = out.get(t["tool"], 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def main() -> int:
    args = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else discover_transcripts()
    if not args:
        print("No transcripts found.")
        return 1
    print(f"Found {len(args)} transcript(s).")
    total_turns = 0
    total_traces = 0
    for p in args:
        try:
            result = import_transcript(p)
        except Exception as e:
            print(f"  FAIL  {p.name}: {e}")
            continue
        if "skipped" in result:
            print(f"  skip  {p.name} ({result['skipped']})")
            continue
        print(f"  ok    {p.name}: {result['turns']} turns, "
              f"{result['tool_traces']} tool calls -> {result['session_id']}")
        if result.get("tool_breakdown"):
            top = list(result["tool_breakdown"].items())[:5]
            print(f"        top tools: {top}")
        total_turns += result["turns"]
        total_traces += result["tool_traces"]
    print(f"\nTotal: {total_turns} turns, {total_traces} tool calls imported.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
