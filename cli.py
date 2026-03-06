#!/usr/bin/env python3
"""
AI OS — Terminal Interface
==========================

Full REPL with chat, state visibility, and system management.
Zero new dependencies — just readline + the existing codebase.

Usage:
    python cli.py                # start REPL (demo mode)
    python cli.py --show-state   # print STATE block with each response
    python cli.py --mode live    # use live DB instead of demo
    aios                         # if installed via pip install -e .

Slash commands:
    /status          — subconscious stats, loop status, queue depth
    /memory          — list recent temp_memory facts
    /memory approve <id>  — approve a pending fact
    /memory reject  <id>  — reject a pending fact
    /triggers        — list reflex triggers
    /triggers toggle <id> — toggle a trigger on/off
    /protocols       — list protocol templates
    /protocols install <name> — install a protocol bundle
    /graph <query>   — spread-activate and show related concepts
    /config          — current configuration
    /config set <key> <value> — set env var for this session
    /test            — run full test suite
    /test flows      — run flow tests only
    /test pure       — run pure-function tests only
    /clear           — clear message history
    /help            — show this help
    /quit            — exit
"""

import asyncio
import os
import sys
import subprocess
from pathlib import Path

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


# ── Slash commands ───────────────────────────────────────────────────────

def _cmd_status():
    parts = []

    try:
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        parts.append(f"  threads:  {sub.registry.count()}")
    except Exception:
        pass

    try:
        from agent.subconscious.temp_memory.store import get_stats
        s = get_stats()
        parts.append(f"  memory:   {s}")
    except Exception:
        pass

    try:
        from Feeds.polling import get_polling_status
        parts.append(f"  polling:  {get_polling_status()}")
    except Exception:
        pass

    try:
        from agent.threads.reflex.schedule import get_schedule_status
        parts.append(f"  schedule: {get_schedule_status()}")
    except Exception:
        pass

    print("\n".join(parts) if parts else "  no status available")


def _cmd_memory(args: str):
    tokens = args.strip().split()

    if tokens and tokens[0] == "approve" and len(tokens) > 1:
        from agent.subconscious.temp_memory.store import approve_fact
        ok = approve_fact(int(tokens[1]))
        print(f"  {'approved' if ok else 'not found'}")
        return

    if tokens and tokens[0] == "reject" and len(tokens) > 1:
        from agent.subconscious.temp_memory.store import reject_fact
        ok = reject_fact(int(tokens[1]))
        print(f"  {'rejected' if ok else 'not found'}")
        return

    from agent.subconscious.temp_memory.store import get_facts
    facts = get_facts(limit=20)
    if not facts:
        print("  no facts in temp_memory")
        return
    for f in facts:
        status = getattr(f, "status", "pending")
        print(f"  {DIM}[{f.id}]{RESET} {status:10s} {f.text[:80]}")


def _cmd_triggers(args: str):
    tokens = args.strip().split()

    if tokens and tokens[0] == "toggle" and len(tokens) > 1:
        from agent.threads.reflex.schema import toggle_trigger
        new = toggle_trigger(int(tokens[1]))
        print(f"  {'enabled' if new else 'disabled' if new is not None else 'not found'}")
        return

    from agent.threads.reflex.schema import get_triggers
    triggers = get_triggers()
    if not triggers:
        print("  no triggers")
        return
    for t in triggers:
        enabled = "on " if t.get("enabled") else "off"
        mode = t.get("response_mode", "tool")
        cron = t.get("cron_expression", "")
        print(f"  {DIM}[{t['id']}]{RESET} {enabled} {mode:6s} {t['name'][:40]}"
              f"  {t.get('feed_name','')}/{t.get('event_type','')}"
              f"  {cron}")


def _cmd_protocols(args: str):
    tokens = args.strip().split()

    if tokens and tokens[0] == "install" and len(tokens) > 1:
        name = tokens[1]
        from agent.threads.reflex.api import PROTOCOL_TEMPLATES
        from agent.threads.reflex.schema import create_trigger
        template = PROTOCOL_TEMPLATES.get(name)
        if not template:
            print(f"  unknown protocol: {name}")
            return
        for td in template:
            tid = create_trigger(
                name=td["name"], feed_name=td["feed_name"],
                event_type=td["event_type"],
                tool_name=td.get("tool_name", ""),
                tool_action=td.get("tool_action", ""),
                description=td.get("description", ""),
                trigger_type=td.get("trigger_type", "webhook"),
                cron_expression=td.get("cron_expression"),
                response_mode=td.get("response_mode", "tool"),
                priority=td.get("priority", 5),
            )
            print(f"  created trigger {tid}: {td['name']}")
        return

    from agent.threads.reflex.api import PROTOCOL_TEMPLATES
    for name, trigs in PROTOCOL_TEMPLATES.items():
        desc = trigs[0].get("description", "") if trigs else ""
        print(f"  {BOLD}{name}{RESET}  ({len(trigs)} triggers)  {desc}")


def _cmd_graph(query: str):
    if not query.strip():
        print("  usage: /graph <query>")
        return
    from agent.threads.linking_core.schema import spread_activate
    seeds = [w.strip() for w in query.strip().split() if w.strip()]
    scores = spread_activate(seeds, hops=2)
    if not scores:
        print("  no activations found")
        return
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:15]
    for concept, score in ranked:
        bar = "█" * int(score * 20)
        print(f"  {score:.2f} {bar} {concept}")


def _cmd_config(args: str):
    tokens = args.strip().split(maxsplit=2)

    if tokens and tokens[0] == "set" and len(tokens) >= 3:
        os.environ[tokens[1]] = tokens[2]
        print(f"  {tokens[1]}={tokens[2]}")
        return

    from data.db import get_db_path
    print(f"  AIOS_MODE       = {os.environ.get('AIOS_MODE', 'not set')}")
    print(f"  DB_PATH         = {get_db_path()}")
    print(f"  AIOS_MODEL_NAME = {os.environ.get('AIOS_MODEL_NAME', 'qwen2.5:7b')}")
    print(f"  AIOS_FEED_BRIDGE= {os.environ.get('AIOS_FEED_BRIDGE', '0')}")
    print(f"  AIOS_TEST_LIVE  = {os.environ.get('AIOS_TEST_LIVE', '0')}")


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
  {BOLD}Chat:{RESET}       Just type a message.
  {BOLD}/status{RESET}     Subconscious stats, loops, queue depth
  {BOLD}/memory{RESET}     List temp_memory facts
  {BOLD}/memory approve <id>{RESET}   Approve a fact
  {BOLD}/memory reject  <id>{RESET}   Reject a fact
  {BOLD}/triggers{RESET}   List reflex triggers
  {BOLD}/triggers toggle <id>{RESET}  Toggle trigger on/off
  {BOLD}/protocols{RESET}  List protocol templates
  {BOLD}/protocols install <name>{RESET}  Install a protocol
  {BOLD}/graph <query>{RESET}  Spread-activate concept graph
  {BOLD}/config{RESET}     Show config
  {BOLD}/config set <key> <value>{RESET}  Set env var
  {BOLD}/test{RESET}       Run all tests
  {BOLD}/test flows{RESET} Run flow tests
  {BOLD}/test pure{RESET}  Run pure tests
  {BOLD}/clear{RESET}      Clear message history
  {BOLD}/quit{RESET}       Exit
""")


_COMMANDS = {
    "/status": lambda a: _cmd_status(),
    "/memory": _cmd_memory,
    "/triggers": _cmd_triggers,
    "/protocols": _cmd_protocols,
    "/graph": _cmd_graph,
    "/config": _cmd_config,
    "/test": _cmd_test,
    "/help": lambda a: _cmd_help(),
    "/clear": lambda a: (_agent_service.message_history.clear(), print("  history cleared")),
}


def _dispatch(line: str) -> bool:
    """Handle a line of input.  Returns False to quit."""
    stripped = line.strip()
    if not stripped:
        return True
    if stripped in ("/quit", "/exit", "/q"):
        return False

    # Slash command?
    for prefix, handler in _COMMANDS.items():
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
    parser = argparse.ArgumentParser(description="AI OS — Terminal Interface")
    parser.add_argument("--show-state", action="store_true", help="Print STATE block with each response")
    parser.add_argument("--mode", default=None, help="DB mode: demo (default) or live")
    args = parser.parse_args()

    if args.mode:
        os.environ["AIOS_MODE"] = args.mode
    else:
        os.environ.setdefault("AIOS_MODE", "demo")

    _show_state = args.show_state

    print(f"\n{BOLD}AI OS{RESET} — Terminal Interface")
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
