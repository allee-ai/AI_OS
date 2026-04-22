"""
scripts/aios.py — Execute AI_OS tools from the command line.

This is the bridge that lets any client (VS Code, mobile, CLI, scripts)
speak the same tool protocol the running agent uses internally.
It parses the same ``:::execute`` block format the agent emits from
its LLM output, dispatches through ``ToolExecutor``, and prints the
same ``:::result`` block back.

Usage
=====

Block-style (from stdin, closest to what the agent itself writes):

    python3 scripts/aios.py <<'EOF'
    :::execute
    tool: workspace_read
    action: read_file
    path: README.md
    :::
    EOF

Inline-positional (shortcut for humans):

    python3 scripts/aios.py workspace_read read_file path=README.md
    python3 scripts/aios.py regex_search run pattern='def build_state' include='agent/**/*.py'
    python3 scripts/aios.py cli_command run command=/tools

List tools:

    python3 scripts/aios.py --list

Every call writes to the same execution log (``tool_traces`` /
``log_llm_inference``) the running agent writes to — so tool use
from VS Code turns up in STATE next turn.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _parse_kv_args(tokens: List[str]) -> Dict[str, str]:
    """Turn ['path=foo', 'n=3'] into {'path': 'foo', 'n': '3'}."""
    out: Dict[str, str] = {}
    for tok in tokens:
        if "=" not in tok:
            raise SystemExit(f"bad param (expected key=value): {tok!r}")
        k, v = tok.split("=", 1)
        out[k.strip()] = v
    return out


def _parse_stdin_block(raw: str) -> Tuple[str, str, Dict[str, str]]:
    """Parse a stdin blob.  Accepts either a bare ``tool:/action:/params``
    body or a full ``:::execute...:::`` block.
    """
    from agent.threads.form.tools.scanner import scan_for_tool_calls

    raw = raw.strip()
    if not raw:
        raise SystemExit("stdin was empty")

    # If the user handed us a fenced block, use the real scanner so the
    # behaviour matches the live agent exactly.
    if ":::execute" in raw:
        calls = scan_for_tool_calls(raw)
        if not calls:
            raise SystemExit("no valid :::execute::: block found on stdin")
        c = calls[0]
        return c.tool, c.action, dict(c.params)

    # Otherwise treat it as a bare key:value body and feed the scanner
    # a synthetic wrapper so we get consistent parsing.
    wrapped = ":::execute\n" + raw.strip() + "\n:::"
    calls = scan_for_tool_calls(wrapped)
    if not calls:
        raise SystemExit("stdin was not parseable as an execute block")
    c = calls[0]
    return c.tool, c.action, dict(c.params)


def _list_tools() -> int:
    from agent.threads.form.tools.registry import (
        get_all_tools,
        get_runnable_tools,
    )

    runnable = {getattr(t, "name", None) for t in get_runnable_tools()}
    rows = []
    for t in get_all_tools():
        name = getattr(t, "name", "?")
        desc = (getattr(t, "description", "") or "").splitlines()[0]
        actions = getattr(t, "actions", None) or []
        if isinstance(actions, dict):
            actions = list(actions.keys())
        marker = "●" if name in runnable else "○"
        rows.append((name, marker, ", ".join(actions), desc))
    width = max((len(r[0]) for r in rows), default=4)
    print("● runnable   ○ registered but not available")
    for name, marker, actions, desc in sorted(rows):
        print(f"{marker} {name:<{width}}  [{actions}]  {desc}")
    return 0


def _mirror_to_chat(tool: str, action: str, params: Dict[str, str], result_dict: Dict) -> None:
    """Append this tool call to today's vscode_copilot convo as a sub-turn.

    Goal: the AIOS chat UI shows every command I run (same grain the user sees
    in VS Code chat), so the two surfaces stay in sync.
    """
    try:
        from chat.schema import save_conversation, add_turn
        from datetime import datetime as _dt

        today = _dt.now().strftime("%Y-%m-%d")
        session_id = f"vscode_copilot_{today}"
        save_conversation(
            session_id=session_id,
            name=f"VS Code coding — {today}",
            channel="react",
            source="vscode_copilot",
        )

        # Summarise the call so it reads like a chat turn.
        param_preview = ", ".join(f"{k}={v!r}" for k, v in params.items())
        if len(param_preview) > 400:
            param_preview = param_preview[:400] + "…"
        user_msg = f"{tool}.{action}({param_preview})"

        out = result_dict.get("output")
        body = out if isinstance(out, str) else json.dumps(out, indent=2, default=str) if out is not None else ""
        if len(body) > 2000:
            body = body[:2000] + f"\n... [truncated, {len(body)} total chars]"
        status = result_dict.get("status", "?")
        err = result_dict.get("error")
        assistant_msg = body or (f"[{status}] (no output)")
        if err:
            assistant_msg = f"[{status}] error: {err}\n\n{assistant_msg}"

        add_turn(
            session_id=session_id,
            user_message=user_msg,
            assistant_message=assistant_msg,
            feed_type="tool_call",
            context_level=0,
            metadata={
                "source": "vscode_copilot",
                "tool": tool,
                "action": action,
                "status": status,
                "duration_ms": result_dict.get("duration_ms"),
                "params_keys": list(params.keys()),
            },
        )
    except Exception:
        # Mirroring must never break a tool call.
        pass


def _run(
    tool: str,
    action: str,
    params: Dict[str, str],
    as_json: bool,
    raw: bool,
) -> int:
    from agent.threads.form.tools.executor import execute_tool

    result = execute_tool(tool, action, dict(params))
    d = result.to_dict()
    _mirror_to_chat(tool, action, params, d)

    if as_json:
        print(json.dumps(d, indent=2, default=str))
        return 0 if result.success else 1

    if raw:
        # Match the shape the live agent feeds back to itself.
        out = d.get("output")
        body = out if isinstance(out, str) else json.dumps(out, indent=2, default=str)
        print(f":::result tool={tool} action={action}")
        print(body)
        print(":::")
        if not result.success and d.get("error"):
            print(f"# error: {d['error']}", file=sys.stderr)
        return 0 if result.success else 1

    # Default: human readable.
    status = d["status"]
    dur = d.get("duration_ms", 0)
    print(f"── {tool}.{action}  [{status}]  {dur:.0f}ms")
    if d.get("error"):
        print(f"   error: {d['error']}")
    out = d.get("output")
    if isinstance(out, str):
        print(out)
    elif out is not None:
        print(json.dumps(out, indent=2, default=str))
    return 0 if result.success else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an AI_OS tool from the command line "
        "(same registry the agent uses).",
    )
    parser.add_argument(
        "tool",
        nargs="?",
        help="Tool name (e.g. workspace_read). Omit to read an "
        "execute block from stdin, or pass --list.",
    )
    parser.add_argument(
        "action",
        nargs="?",
        help="Action on the tool (e.g. read_file).",
    )
    parser.add_argument(
        "params",
        nargs="*",
        help="key=value params.",
    )
    parser.add_argument("--list", action="store_true", help="List all registered tools and exit.")
    parser.add_argument("--json", action="store_true", help="Emit the raw ToolResult as JSON.")
    parser.add_argument("--raw", action="store_true", help="Emit a :::result::: block like the agent.")
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Force reading an execute block from stdin (ignore positional args).",
    )
    args = parser.parse_args()

    if args.list:
        return _list_tools()

    # Stdin mode: either explicit, or when no tool given and stdin is piped.
    use_stdin = args.stdin or (not args.tool and not sys.stdin.isatty())
    if use_stdin:
        tool, action, params = _parse_stdin_block(sys.stdin.read())
    else:
        if not args.tool or not args.action:
            parser.print_help(sys.stderr)
            return 2
        tool = args.tool
        action = args.action
        params = _parse_kv_args(args.params)

    return _run(tool, action, params, as_json=args.json, raw=args.raw)


if __name__ == "__main__":
    sys.exit(main())
