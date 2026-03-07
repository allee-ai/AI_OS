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
    /loops           — show background loop stats
    /loops run memory     — run one extraction cycle now
    /loops extract <text> — dry-run fact extraction on text
    /loops model <name>   — change extraction model
    /loops provider <name>— change provider (ollama|openai)
    /thoughts        — show recent proactive thoughts
    /thoughts think  — trigger one thought cycle now
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


def _cmd_mindmap(args: str):
    """Show the structural shape of the agent's mind.

    /mindmap            — show thread hierarchy with node counts
    /mindmap links      — also show cross-thread associative links
    /mindmap <thread>   — show details for one thread (identity, philosophy, form, reflex, log)
    """
    tokens = args.strip().split()
    verb = tokens[0] if tokens else ""

    try:
        from agent.threads.linking_core.schema import get_structural_graph
        show_cross = (verb == "links")
        data = get_structural_graph(include_cross_links=show_cross)

        nodes = data["nodes"]
        structural = data["structural"]
        associative = data.get("associative", [])

        # Filter to specific thread if requested
        filter_thread = None
        if verb and verb not in ("links",):
            filter_thread = verb

        # Build children map from structural edges
        children: dict = {}
        for edge in structural:
            children.setdefault(edge["source"], []).append(edge["target"])

        thread_colors = {
            "identity": CYAN, "philosophy": YELLOW, "form": GREEN,
            "reflex": RED, "log": DIM, "linking_core": BOLD,
        }

        def _print_tree(node_id: str, indent: int = 0):
            node = next((n for n in nodes if n["id"] == node_id), None)
            if not node:
                return
            color = thread_colors.get(node["thread"], "")
            label = node["label"]
            value = node.get("data", {}).get("value", "")
            suffix = f"  = {value}" if value else ""
            kind_badge = f"[{node['kind']}]" if node["kind"] not in ("thread",) else ""
            weight = node.get("weight", 0)
            weight_str = f" w={weight:.1f}" if weight and node["kind"] == "fact" else ""
            prefix = "  " * indent
            print(f"{prefix}{color}{label}{RESET} {DIM}{kind_badge}{weight_str}{suffix}{RESET}")

            for child_id in children.get(node_id, []):
                _print_tree(child_id, indent + 1)

        # Print thread trees
        thread_nodes = [n for n in nodes if n["kind"] == "thread"]
        for tn in sorted(thread_nodes, key=lambda n: n["id"]):
            if filter_thread and tn["id"] != filter_thread:
                continue
            _print_tree(tn["id"], indent=1)
            print()

        # Stats
        stats = data["stats"]
        print(f"{DIM}  {stats['node_count']} nodes, "
              f"{stats['structural_count']} structural edges, "
              f"{stats['associative_count']} associative edges{RESET}")

        # Show cross-thread links
        if associative:
            cross_thread = [l for l in associative if l.get("cross_thread")]
            if cross_thread:
                print(f"\n  {BOLD}Cross-thread links:{RESET}")
                for link in cross_thread[:20]:
                    s = link["strength"]
                    bar = "█" * int(s * 15)
                    print(f"    {s:.2f} {bar}  {link['source']} ↔ {link['target']}")

    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


def _cmd_loops(args: str):
    """Manage and inspect background loops.

    /loops                  — show all loop stats
    /loops run memory       — run one memory-extraction cycle now
    /loops run consolidation — run one consolidation cycle now
    /loops model <name>     — change extraction model
    /loops provider <name>  — change extraction provider (ollama|openai)
    /loops extract <text>   — extract facts from text (dry-run)
    """
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

    # /loops run <name>  — run one cycle of a loop
    if verb == "run":
        loop_name = rest.strip() or "memory"
        try:
            from agent.subconscious.loops import MemoryLoop, ConsolidationLoop
            if loop_name == "memory":
                ml = MemoryLoop.__new__(MemoryLoop)
                ml._model = None
                ml._last_processed_turn_id = None
                ml.config = type('C', (), {'name': 'memory', 'enabled': True})()
                ml._extract()
                print(f"  {GREEN}memory extraction cycle complete{RESET}")
            elif loop_name == "consolidation":
                cl = ConsolidationLoop.__new__(ConsolidationLoop)
                cl.DUPLICATE_THRESHOLD = 0.85
                cl.AUTO_APPROVE_THRESHOLD = 0.8
                cl.AUTO_REJECT_THRESHOLD = 0.2
                cl._linking_core = None
                cl.config = type('C', (), {'name': 'consolidation', 'enabled': True})()
                cl._consolidate()
                print(f"  {GREEN}consolidation cycle complete{RESET}")
            else:
                print(f"  unknown loop: {loop_name}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /loops model <name>  — set extraction model
    if verb == "model":
        name = rest.strip()
        if not name:
            print(f"  current extract model: {os.environ.get('AIOS_EXTRACT_MODEL', os.environ.get('AIOS_MODEL_NAME', 'qwen2.5:7b'))}")
            return
        os.environ["AIOS_EXTRACT_MODEL"] = name
        print(f"  extract model → {name}")
        return

    # /loops provider <name>  — set extraction provider
    if verb == "provider":
        name = rest.strip()
        if not name:
            print(f"  current extract provider: {os.environ.get('AIOS_EXTRACT_PROVIDER', os.environ.get('AIOS_MODEL_PROVIDER', 'ollama'))}")
            return
        os.environ["AIOS_EXTRACT_PROVIDER"] = name
        print(f"  extract provider → {name}")
        return

    # /loops extract <text>  — dry-run extraction
    if verb == "extract":
        text = rest.strip()
        if not text:
            print("  usage: /loops extract <conversation text>")
            return
        try:
            from agent.subconscious.loops import MemoryLoop
            ml = MemoryLoop.__new__(MemoryLoop)
            ml._model = None
            facts = ml._extract_facts_from_text(f"User: {text}", session_id="cli_test")
            if not facts:
                print("  no facts extracted")
            else:
                for f in facts:
                    print(f"  {GREEN}{f.get('key', '?')}{RESET}: {f.get('text', '')}")
            print(f"  {DIM}(model: {ml.model} | provider: {ml.provider}){RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Default: show all loop stats
    try:
        from agent.subconscious import _loop_manager
        if _loop_manager:
            for s in _loop_manager.get_stats():
                status = s.get('status', '?')
                color = GREEN if status == 'running' else YELLOW if status == 'paused' else DIM
                model_str = f"  model={s['model']}" if 'model' in s else ""
                provider_str = f"  provider={s['provider']}" if 'provider' in s else ""
                print(f"  {color}{s['name']:20s} {status:10s}{RESET}"
                      f"  runs={s.get('run_count', 0)}"
                      f"  errors={s.get('error_count', 0)}"
                      f"{model_str}{provider_str}")
        else:
            print("  loops not started (run /status to check)")
    except Exception:
        # Fallback: just show config
        print(f"  extract model:    {os.environ.get('AIOS_EXTRACT_MODEL', os.environ.get('AIOS_MODEL_NAME', 'qwen2.5:7b'))}")
        print(f"  extract provider: {os.environ.get('AIOS_EXTRACT_PROVIDER', os.environ.get('AIOS_MODEL_PROVIDER', 'ollama'))}")


def _cmd_thoughts(args: str):
    """Manage and inspect the proactive thought loop.

    /thoughts               — show recent thoughts
    /thoughts think         — trigger one thought cycle now
    /thoughts <category>    — filter by category (insight, alert, reminder, suggestion, question)
    """
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""

    # /thoughts think  — run one thought cycle
    if verb == "think":
        print(f"  {DIM}running thought cycle...{RESET}")
        try:
            from agent.subconscious.loops import ThoughtLoop, get_thought_log
            tl = ThoughtLoop.__new__(ThoughtLoop)
            tl._model = None
            tl._thought_count = 0
            tl.config = type('C', (), {'name': 'thought', 'enabled': True})()
            
            before = get_thought_log(limit=1)
            before_id = before[0]["id"] if before else 0
            
            tl._think()
            
            after = get_thought_log(limit=5)
            new_thoughts = [t for t in after if t["id"] > before_id]
            
            if not new_thoughts:
                print(f"  {DIM}no new thoughts — nothing notable right now{RESET}")
            else:
                for t in new_thoughts:
                    pcolor = RED if t["priority"] in ("high", "urgent") else YELLOW if t["priority"] == "medium" else GREEN
                    cat_icon = {"insight": "💡", "alert": "🚨", "reminder": "📌", "suggestion": "💬", "question": "❓"}.get(t["category"], "•")
                    print(f"  {cat_icon} {pcolor}[{t['priority']}]{RESET} {t['thought']}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /thoughts <category>  or  /thoughts  (show all)
    try:
        from agent.subconscious.loops import get_thought_log, THOUGHT_CATEGORIES
        category = verb if verb in THOUGHT_CATEGORIES else None
        limit = 15
        
        thoughts = get_thought_log(limit=limit, category=category)
        if not thoughts:
            title = f"no {category} thoughts" if category else "no thoughts yet — run /thoughts think"
            print(f"  {DIM}{title}{RESET}")
        else:
            title = f"Recent {category} thoughts:" if category else "Recent thoughts:"
            print(f"  {BOLD}{title}{RESET}")
            for t in thoughts:
                pcolor = RED if t["priority"] in ("high", "urgent") else YELLOW if t["priority"] == "medium" else GREEN
                cat_icon = {"insight": "💡", "alert": "🚨", "reminder": "📌", "suggestion": "💬", "question": "❓"}.get(t["category"], "•")
                acted = " ✓" if t["acted_on"] else ""
                print(f"  {DIM}#{t['id']}{RESET} {cat_icon} {pcolor}[{t['priority']}]{RESET} {t['thought']}{acted}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


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
  {BOLD}/mindmap{RESET}     Structural shape of the agent's mind
  {BOLD}/mindmap links{RESET} Include cross-thread associative edges
  {BOLD}/mindmap <thread>{RESET} Show one thread (identity, philosophy, form, ...)
  {BOLD}/loops{RESET}      Show background loop stats
  {BOLD}/loops run memory{RESET}  Run one extraction cycle
  {BOLD}/loops run consolidation{RESET}  Run one consolidation cycle
  {BOLD}/loops extract <text>{RESET}  Dry-run fact extraction
  {BOLD}/loops model <name>{RESET}   Change extraction model
  {BOLD}/loops provider <name>{RESET} Change extraction provider (ollama|openai)
  {BOLD}/thoughts{RESET}   Show recent proactive thoughts
  {BOLD}/thoughts think{RESET}  Trigger one thought cycle now
  {BOLD}/thoughts <cat>{RESET} Filter: insight, alert, reminder, suggestion, question
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
    "/loops": _cmd_loops,
    "/thoughts": _cmd_thoughts,
    "/triggers": _cmd_triggers,
    "/protocols": _cmd_protocols,
    "/graph": _cmd_graph,
    "/mindmap": _cmd_mindmap,
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
