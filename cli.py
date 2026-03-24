#!/usr/bin/env python3
"""
AI OS — Terminal Interface
==========================

Thin dispatcher that assembles commands from per-module cli.py files.

Usage:
    python cli.py                # start REPL (demo mode)
    python cli.py --show-state   # print STATE block with each response
    python cli.py --mode live    # use live DB instead of demo
    aios                         # if installed via pip install -e .
"""

import asyncio
import os
import sys
import subprocess
from pathlib import Path

try:
    import readline  # noqa: F401 — enables arrow-key editing + history in input()
except ImportError:
    pass  # Windows fallback: pyreadline3 or bare input()

# Ensure project root on path
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Globals ──────────────────────────────────────────────────────────────

_agent_service = None
_show_state = False

# ANSI colors
DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


# ── Collect commands from modules ────────────────────────────────────────

def _load_commands() -> dict:
    """Import COMMANDS dict from each module cli.py and merge."""
    cmds = {}
    modules = [
        "agent.subconscious.cli",
        "agent.threads.reflex.cli",
        "agent.threads.linking_core.cli",
        "agent.threads.form.cli",
        "agent.threads.identity.cli",
        "agent.threads.philosophy.cli",
        "agent.threads.log.cli",
        "workspace.cli",
        "chat.cli",
        "Feeds.cli",
        "eval.cli",
    ]
    for mod_name in modules:
        try:
            mod = __import__(mod_name, fromlist=["COMMANDS"])
            cmds.update(mod.COMMANDS)
        except Exception as e:
            print(f"{DIM}[init] skipped {mod_name}: {e}{RESET}")
    return cmds


# ── Bootstrap ────────────────────────────────────────────────────────────

def _bootstrap():
    """Initialize schemas + subconscious + agent service."""
    global _agent_service

    # Migrations
    try:
        from agent.core.migrations import ensure_all_schemas
        ensure_all_schemas()
    except Exception as e:
        print(f"{DIM}[init] schema sync: {e}{RESET}")

    # Wake subconscious
    try:
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        sub.wake()
        print(f"{DIM}[init] subconscious awake — {sub.registry.count()} threads{RESET}")
    except Exception as e:
        print(f"{DIM}[init] subconscious: {e}{RESET}")

    # Agent service
    from agent.services.agent_service import get_agent_service
    _agent_service = get_agent_service()
    name = _agent_service.agent.name if _agent_service.agent else "Agent"
    print(f"{BOLD}{CYAN}{name}{RESET} ready.  Type /help for commands.\n")


# ── State summary line ──────────────────────────────────────────────────

def _state_line() -> str:
    """One-line summary of system state shown after each response."""
    parts = []
    try:
        from agent.subconscious.temp_memory.store import get_stats
        stats = get_stats()
        total = stats.get("total", stats.get("count", "?"))
        parts.append(f"mem:{total} facts")
    except Exception:
        pass

    try:
        from agent.threads.reflex.schema import get_triggers
        triggers = get_triggers(enabled_only=True)
        parts.append(f"{len(triggers)} triggers")
    except Exception:
        pass

    try:
        from agent.threads.linking_core.schema import get_graph_data
        data = get_graph_data()
        parts.append(f"graph:{data.get('node_count', '?')} nodes")
    except Exception:
        pass

    return f"{DIM}[{' | '.join(parts)}]{RESET}" if parts else ""


# ── Chat ─────────────────────────────────────────────────────────────────

def _chat(user_input: str):
    """Send a message and print the response."""
    global _show_state

    async def _send():
        return await _agent_service.send_message(user_input)

    msg = asyncio.run(_send())
    print(f"\n{BOLD}{msg.content}{RESET}")

    if _show_state:
        try:
            from agent.subconscious.orchestrator import get_subconscious
            state = get_subconscious().build_context(level=2)
            print(f"\n{DIM}── STATE ──\n{state}\n── /STATE ──{RESET}")
        except Exception:
            pass

    print(_state_line())


# ── Local commands (config, test, help) ──────────────────────────────────

def _cmd_config(args: str):
    tokens = args.strip().split(maxsplit=2)

    if tokens and tokens[0] == "set" and len(tokens) >= 3:
        os.environ[tokens[1]] = tokens[2]
        print(f"  {tokens[1]}={tokens[2]}")
        return

    from data.db import get_db_path
    print(f"  AIOS_MODE            = {os.environ.get('AIOS_MODE', 'not set')}")
    print(f"  DB_PATH              = {get_db_path()}")
    print(f"  AIOS_MODEL_NAME      = {os.environ.get('AIOS_MODEL_NAME', 'qwen2.5:7b')}")
    print(f"  AIOS_EXTRACT_MODEL   = {os.environ.get('AIOS_EXTRACT_MODEL', '(uses AIOS_MODEL_NAME)')}")
    print(f"  AIOS_EXTRACT_PROVIDER= {os.environ.get('AIOS_EXTRACT_PROVIDER', os.environ.get('AIOS_MODEL_PROVIDER', 'ollama'))}")
    print(f"  AIOS_FEED_BRIDGE     = {os.environ.get('AIOS_FEED_BRIDGE', '0')}")
    print(f"  AIOS_TEST_LIVE       = {os.environ.get('AIOS_TEST_LIVE', '0')}")


def _cmd_test(args: str):
    target = args.strip()
    if target == "flows":
        cmd = [sys.executable, "-m", "pytest", "tests/test_flows.py", "-x", "-q"]
    elif target == "pure":
        cmd = [sys.executable, "-m", "pytest", "tests/test_pure.py", "-x", "-q"]
    else:
        cmd = [sys.executable, "-m", "pytest", "tests/", "-x", "-q"]
    print(f"  running: {' '.join(cmd)}\n")
    subprocess.run(cmd, cwd=str(_ROOT))


def _cmd_help():
    print(f"""
  {BOLD}AI OS \u2014 CLI Commands{RESET}

  {CYAN}Chat{RESET}           Just type a message to talk to the agent.

  {CYAN}System{RESET}
    {BOLD}/status{RESET}                    Subconscious stats, loops, queue depth
    {BOLD}/config{RESET}                    Show current configuration
    {BOLD}/config set <key> <val>{RESET}    Set env var for this session

  {CYAN}Memory{RESET}
    {BOLD}/memory{RESET}                    List recent temp_memory facts
    {BOLD}/memory approve <id>{RESET}       Approve a pending fact
    {BOLD}/memory reject  <id>{RESET}       Reject a pending fact

  {CYAN}Knowledge Graph{RESET}
    {BOLD}/graph <query>{RESET}             Spread-activate concept graph
    {BOLD}/mindmap{RESET}                   Structural shape of the agent's mind
    {BOLD}/mindmap links{RESET}             Include cross-thread associative edges
    {BOLD}/mindmap <thread>{RESET}          Show one thread (identity, philosophy, ...)

  {CYAN}Background Loops{RESET}
    {BOLD}/loops{RESET}                     Show all loop stats
    {BOLD}/loops new{RESET}                 Create a custom loop (interactive)
    {BOLD}/loops custom{RESET}              List custom loops
    {BOLD}/loops delete <name>{RESET}       Delete a custom loop
    {BOLD}/loops pause <name>{RESET}        Pause a running loop
    {BOLD}/loops resume <name>{RESET}       Resume a paused loop
    {BOLD}/loops interval <name> <s>{RESET} Change loop interval (seconds)
    {BOLD}/loops run memory{RESET}          Run one extraction cycle
    {BOLD}/loops run consolidation{RESET}   Run one consolidation cycle
    {BOLD}/loops extract <text>{RESET}      Dry-run fact extraction
    {BOLD}/loops model <name>{RESET}        Change extraction model
    {BOLD}/loops provider <name>{RESET}     Change extraction provider (ollama|openai)
    {BOLD}/loops context <n> on|off{RESET}  Toggle STATE injection
    {BOLD}/loops prompts <name>{RESET}      View/edit loop prompts

  {CYAN}Thoughts{RESET}
    {BOLD}/thoughts{RESET}                  Show recent proactive thoughts
    {BOLD}/thoughts think{RESET}            Trigger one thought cycle now
    {BOLD}/thoughts <category>{RESET}       Filter: insight, alert, reminder, suggestion, question

  {CYAN}Tasks{RESET}
    {BOLD}/tasks{RESET}                     List tasks
    {BOLD}/tasks new <goal>{RESET}          Create and execute a task now
    {BOLD}/tasks queue <goal>{RESET}        Queue for background execution
    {BOLD}/tasks <id>{RESET}                Show task details
    {BOLD}/tasks cancel <id>{RESET}         Cancel a pending task

  {CYAN}Tools{RESET}
    {BOLD}/tools{RESET}                     List all tools
    {BOLD}/tools <name>{RESET}              Show tool details
    {BOLD}/tools run <name> <action>{RESET} Execute a tool action (+ optional JSON params)
    {BOLD}/tools new{RESET}                 Create a tool (interactive)
    {BOLD}/tools code <name>{RESET}         Show tool's executable code
    {BOLD}/tools toggle <name>{RESET}       Enable/disable a tool
    {BOLD}/tools delete <name>{RESET}       Delete a tool
    {BOLD}/tools categories{RESET}          List tool categories

  {CYAN}Identity{RESET}
    {BOLD}/identity{RESET}                  List identity profiles
    {BOLD}/identity <profile>{RESET}        Show facts for a profile
    {BOLD}/identity new{RESET}              Create profile (interactive)
    {BOLD}/identity fact <p> <k> <v>{RESET} Add/update a fact
    {BOLD}/identity delete <profile>{RESET} Delete profile

  {CYAN}Philosophy{RESET}
    {BOLD}/philosophy{RESET}                List philosophy profiles
    {BOLD}/philosophy <profile>{RESET}      Show stances for a profile
    {BOLD}/philosophy new{RESET}            Create profile (interactive)
    {BOLD}/philosophy fact <p> <k> <v>{RESET} Add/update a stance
    {BOLD}/philosophy delete <profile>{RESET} Delete profile

  {CYAN}Log / Timeline{RESET}
    {BOLD}/log{RESET}                       Recent timeline
    {BOLD}/log events [type]{RESET}         Raw events (optionally filtered)
    {BOLD}/log search <query>{RESET}        Search events
    {BOLD}/log types{RESET}                 List event types
    {BOLD}/log stats{RESET}                 Log statistics

  {CYAN}Workspace / Files{RESET}
    {BOLD}/files [path]{RESET}              List directory (default /)
    {BOLD}/files read <path>{RESET}         Show file content
    {BOLD}/files search <query>{RESET}      Search files
    {BOLD}/files stats{RESET}               Workspace statistics

  {CYAN}Conversations{RESET}
    {BOLD}/convos{RESET}                    List recent conversations
    {BOLD}/convos <id>{RESET}               Show conversation turns
    {BOLD}/convos search <query>{RESET}     Search conversations
    {BOLD}/convos new [name]{RESET}         Create new conversation
    {BOLD}/convos delete <id>{RESET}        Delete conversation

  {CYAN}Feeds{RESET}
    {BOLD}/feeds{RESET}                     List feed sources
    {BOLD}/feeds templates{RESET}           Available integrations
    {BOLD}/feeds toggle <name>{RESET}       Enable/disable a feed
    {BOLD}/feeds test <name>{RESET}         Test feed connection

  {CYAN}Calendar{RESET}
    {BOLD}/calendar{RESET}                  List calendar sources
    {BOLD}/calendar add <name> <url>{RESET} Add iCal source
    {BOLD}/calendar remove <name>{RESET}    Remove a calendar
    {BOLD}/calendar poll{RESET}             Poll all calendars now

  {CYAN}Goals{RESET}
    {BOLD}/goals{RESET}                     List pending proposed goals
    {BOLD}/goals approve <id>{RESET}        Approve a goal
    {BOLD}/goals reject <id>{RESET}         Reject a goal
    {BOLD}/goals dismiss <id>{RESET}        Dismiss a goal

  {CYAN}Notifications{RESET}
    {BOLD}/notifications{RESET}             List recent notifications
    {BOLD}/notifications unread{RESET}      Show unread only
    {BOLD}/notifications read <id>{RESET}   Mark as read
    {BOLD}/notifications dismiss <id>{RESET} Dismiss a notification

  {CYAN}Improvements{RESET}
    {BOLD}/improvements{RESET}              List pending code improvements
    {BOLD}/improvements approve <id>{RESET} Approve an improvement
    {BOLD}/improvements reject <id>{RESET}  Reject an improvement
    {BOLD}/improvements apply <id>{RESET}   Apply an approved improvement

  {CYAN}Reflexes{RESET}
    {BOLD}/triggers{RESET}                  List reflex triggers
    {BOLD}/triggers <id>{RESET}             Show trigger details
    {BOLD}/triggers new{RESET}              Create trigger (interactive)
    {BOLD}/triggers toggle <id>{RESET}      Toggle a trigger on/off
    {BOLD}/triggers delete <id>{RESET}      Delete a trigger
    {BOLD}/protocols{RESET}                 List protocol templates
    {BOLD}/protocols install <name>{RESET}  Install a protocol bundle

  {CYAN}Testing{RESET}
    {BOLD}/test{RESET}                      Run full test suite
    {BOLD}/test flows{RESET}                Run flow tests only
    {BOLD}/test pure{RESET}                 Run pure-function tests only

  {CYAN}Evals{RESET}
    {BOLD}/eval list{RESET}                 List available evals + defaults
    {BOLD}/eval run <name> [opts]{RESET}    Run a single eval (--save --model X --key=val)
    {BOLD}/eval run all [opts]{RESET}       Run all evals
    {BOLD}/eval results [--last N]{RESET}   Show saved runs
    {BOLD}/eval judge <run_id>{RESET}       Human-judge a saved run

  {CYAN}Session{RESET}
    {BOLD}/clear{RESET}                     Clear message history
    {BOLD}/help{RESET}                      Show this help
    {BOLD}/quit{RESET}                      Exit
""")


# ── Command registry ─────────────────────────────────────────────────────

_COMMANDS = None


def _get_commands() -> dict:
    """Lazy-load and cache the merged command registry."""
    global _COMMANDS
    if _COMMANDS is None:
        _COMMANDS = _load_commands()
        # Add local commands
        _COMMANDS["/config"] = _cmd_config
        _COMMANDS["/test"] = _cmd_test
        _COMMANDS["/help"] = lambda a: _cmd_help()
        _COMMANDS["/clear"] = lambda a: (_agent_service.message_history.clear(), print("  history cleared"))
    return _COMMANDS


def _dispatch(line: str) -> bool:
    """Handle a line of input.  Returns False to quit."""
    stripped = line.strip()
    if not stripped:
        return True
    if stripped in ("/quit", "/exit", "/q"):
        return False

    cmds = _get_commands()

    # Slash command?
    for prefix, handler in cmds.items():
        if stripped == prefix or stripped.startswith(prefix + " "):
            args = stripped[len(prefix):]
            try:
                handler(args)
            except Exception as e:
                print(f"  {RED}error: {e}{RESET}")
            return True

    # Otherwise it's a chat message
    try:
        _chat(stripped)
    except KeyboardInterrupt:
        print(f"\n{DIM}(interrupted){RESET}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")
    return True


# ── Entry point ──────────────────────────────────────────────────────────

def main():
    global _show_state

    import argparse
    parser = argparse.ArgumentParser(description="AI OS \u2014 Terminal Interface")
    parser.add_argument("--show-state", action="store_true", help="Print STATE block with each response")
    parser.add_argument("--mode", default=None, help="DB mode: demo (default) or live")
    args = parser.parse_args()

    if args.mode:
        os.environ["AIOS_MODE"] = args.mode
    else:
        os.environ.setdefault("AIOS_MODE", "demo")

    _show_state = args.show_state

    print(f"\n{BOLD}AI OS{RESET} \u2014 Terminal Interface")
    print(f"{DIM}mode={os.environ.get('AIOS_MODE')} | --show-state={'on' if _show_state else 'off'}{RESET}\n")

    _bootstrap()

    # REPL
    try:
        while True:
            try:
                prompt = f"{GREEN}>{RESET} "
                line = input(prompt)
            except EOFError:
                break
            if not _dispatch(line):
                break
    except KeyboardInterrupt:
        pass

    print(f"\n{DIM}goodbye{RESET}")


if __name__ == "__main__":
    main()
