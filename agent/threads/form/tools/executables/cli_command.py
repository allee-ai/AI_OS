"""
cli_command — Execute AI OS CLI commands internally
====================================================

Actions:
    run(command)           → execute a CLI command and return its output
    list_commands()        → list available CLI commands
    help(command)          → get help for a specific command

Wraps the AI OS CLI internally so the task planner can use 
/identity, /memory, /links, /tasks, /feeds etc. without shelling out.

Output truncated at 10KB.
"""

import io
import sys
from contextlib import redirect_stdout, redirect_stderr

MAX_OUTPUT = 10_000


def run(action: str, params: dict) -> str:
    """Execute a cli_command action."""
    actions = {
        "run": _run_command,
        "list_commands": _list_commands,
        "help": _help_command,
    }

    fn = actions.get(action)
    if not fn:
        return f"Unknown action: {action}. Available: {', '.join(actions)}"

    try:
        return fn(params)
    except Exception as e:
        return f"Error: {e}"


# Available internal CLI commands and their handler paths
_CLI_COMMANDS = {
    "/identity":  "View or search identity facts",
    "/memory":    "Browse approved long-term memory",
    "/links":     "Query the concept graph",
    "/threads":   "Show active threads",
    "/tasks":     "Task queue management (new, queue, cancel)",
    "/feeds":     "Feed source status",
    "/loops":     "Background loop status",
    "/stats":     "System stats (memory, tokens, uptime)",
    "/context":   "Build consciousness context at specified level",
    "/help":      "List all commands",
}


def _run_command(params: dict) -> str:
    """Execute a CLI command string and capture its output."""
    command = params.get("command", "").strip()
    if not command:
        return "No command provided. Use /help to see available commands."

    # Ensure it starts with /
    if not command.startswith("/"):
        command = "/" + command

    parts = command.split(None, 1)
    cmd_name = parts[0]
    cmd_args = parts[1] if len(parts) > 1 else ""

    if cmd_name not in _CLI_COMMANDS and cmd_name != "/help":
        return f"Unknown command: {cmd_name}\nAvailable: {', '.join(_CLI_COMMANDS)}"

    # Route to the appropriate handler
    try:
        output = _dispatch(cmd_name, cmd_args)
    except Exception as e:
        output = f"Command error: {e}"

    if len(output) > MAX_OUTPUT:
        output = output[:MAX_OUTPUT] + "\n... [truncated]"

    return output


def _dispatch(cmd: str, args: str) -> str:
    """Dispatch a command to its handler and capture output."""

    if cmd == "/help":
        return _list_commands({})

    if cmd == "/identity":
        return _cmd_identity(args)

    if cmd == "/memory":
        return _cmd_memory(args)

    if cmd == "/links":
        return _cmd_links(args)

    if cmd == "/threads":
        return _cmd_threads(args)

    if cmd == "/tasks":
        return _cmd_tasks(args)

    if cmd == "/feeds":
        return _cmd_feeds(args)

    if cmd == "/loops":
        return _cmd_loops(args)

    if cmd == "/stats":
        return _cmd_stats(args)

    if cmd == "/context":
        return _cmd_context(args)

    return f"Command not implemented: {cmd}"


# ── Command handlers ──────────────────────────────────────

def _cmd_identity(args: str) -> str:
    try:
        from agent.threads.identity.schema import pull_profile_facts
        search = args.strip() if args.strip() else None
        facts = pull_profile_facts(profile_id="primary_user", limit=20)
        if search:
            facts = [f for f in facts if search.lower() in str(f).lower()]
        if not facts:
            return "No identity facts found." + (f" (filter: {search})" if search else "")
        lines = []
        for f in facts:
            key = f.get("key", "?")
            val = f.get("l1_value", f.get("value", ""))
            lines.append(f"  {key}: {val}")
        return "Identity facts:\n" + "\n".join(lines)
    except Exception as e:
        return f"Identity error: {e}"


def _cmd_memory(args: str) -> str:
    try:
        from agent.subconscious.temp_memory.store import get_facts
        facts = get_facts(status="approved", limit=20)
        if not facts:
            facts = get_facts(limit=20)
        if not facts:
            return "No memory facts found."
        search = args.strip().lower() if args.strip() else None
        lines = []
        for f in facts:
            text = f.text if hasattr(f, "text") else str(f)
            if search and search not in text.lower():
                continue
            lines.append(f"  [{f.id if hasattr(f, 'id') else '?'}] {text}")
        return f"Memory ({len(lines)} facts):\n" + "\n".join(lines) if lines else "No matching facts."
    except Exception as e:
        return f"Memory error: {e}"


def _cmd_links(args: str) -> str:
    try:
        from agent.threads.linking_core.schema import spread_activate, find_concepts_by_substring
        query = args.strip()
        if not query:
            return "Usage: /links <concept>  — spread-activate from a concept"
        # Try substring search first to find actual concepts
        matches = find_concepts_by_substring([query], limit=10)
        if matches:
            concepts = [m["concept"] for m in matches]
            activated = spread_activate(concepts[:3], max_hops=2, limit=15)
        else:
            activated = spread_activate([query], max_hops=2, limit=15)

        if not activated:
            return f"No concept links found for: {query}"
        lines = [f"Concept graph for '{query}':"]
        for a in activated:
            lines.append(f"  {a['concept']} (score: {a.get('score', 0):.2f})")
        return "\n".join(lines)
    except Exception as e:
        return f"Links error: {e}"


def _cmd_threads(args: str) -> str:
    try:
        from agent.core.thread_manager import list_threads
        threads = list_threads()
        if not threads:
            return "No active threads."
        lines = ["Active threads:"]
        for t in threads:
            name = t.get("name", t.get("thread_type", "?"))
            status = t.get("status", "?")
            lines.append(f"  {name}: {status}")
        return "\n".join(lines)
    except Exception as e:
        return f"Threads error: {e}"


def _cmd_tasks(args: str) -> str:
    try:
        from agent.subconscious.loops.task_planner import get_tasks
        parts = args.strip().split(None, 1) if args.strip() else []
        status_filter = parts[0] if parts else None

        valid = ["pending", "executing", "completed", "failed", "cancelled"]
        if status_filter and status_filter not in valid:
            status_filter = None

        tasks = get_tasks(status=status_filter, limit=15)
        if not tasks:
            return "No tasks found." + (f" (status: {status_filter})" if status_filter else "")
        lines = ["Task queue:"]
        for t in tasks:
            n_steps = len(t.get("steps", []))
            lines.append(f"  #{t['id']} [{t['status']}] {t['goal'][:60]} ({n_steps} steps)")
        return "\n".join(lines)
    except Exception as e:
        return f"Tasks error: {e}"


def _cmd_feeds(args: str) -> str:
    try:
        from Feeds.polling import get_active_sources
        sources = get_active_sources()
        if not sources:
            return "No active feed sources."
        lines = ["Feed sources:"]
        for s in sources:
            name = s.get("name", "?")
            status = s.get("status", "?")
            lines.append(f"  {name}: {status}")
        return "\n".join(lines)
    except Exception as e:
        return f"Feeds error: {e}"


def _cmd_loops(args: str) -> str:
    try:
        from agent.subconscious import get_subconscious
        sub = get_subconscious()
        if not sub or not hasattr(sub, '_loop_manager'):
            return "Loop manager not available."
        manager = sub._loop_manager
        if not manager:
            return "No loop manager."
        stats = manager.get_all_stats()
        lines = ["Background loops:"]
        for name, s in stats.items():
            status = s.get("status", "?")
            runs = s.get("total_runs", 0)
            lines.append(f"  {name}: {status} ({runs} runs)")
        return "\n".join(lines)
    except Exception as e:
        return f"Loops error: {e}"


def _cmd_stats(args: str) -> str:
    try:
        lines = ["System stats:"]
        # DB size
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM convo_turns")
            turns = cur.fetchone()[0]
            lines.append(f"  Conversation turns: {turns}")
            try:
                cur.execute("SELECT COUNT(*) FROM tasks")
                tasks = cur.fetchone()[0]
                lines.append(f"  Tasks: {tasks}")
            except Exception:
                pass
        return "\n".join(lines)
    except Exception as e:
        return f"Stats error: {e}"


def _cmd_context(args: str) -> str:
    try:
        from agent.subconscious import get_subconscious
        level = int(args.strip()) if args.strip().isdigit() else 2
        sub = get_subconscious()
        if not sub:
            return "Subconscious not available."
        ctx = sub.build_context(level=level)
        return f"Consciousness context (level {level}):\n{str(ctx)[:5000]}"
    except Exception as e:
        return f"Context error: {e}"


def _list_commands(params: dict) -> str:
    lines = ["Available CLI commands:"]
    for cmd, desc in _CLI_COMMANDS.items():
        lines.append(f"  {cmd}  — {desc}")
    return "\n".join(lines)


def _help_command(params: dict) -> str:
    cmd = params.get("command", "").strip()
    if not cmd:
        return _list_commands({})
    if not cmd.startswith("/"):
        cmd = "/" + cmd
    desc = _CLI_COMMANDS.get(cmd)
    if desc:
        return f"{cmd}: {desc}"
    return f"Unknown command: {cmd}"
