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
    /loops context <name> [on|off] — toggle context-aware mode (STATE injection) for a loop
    /loops prompts <name>          — show all prompt stages for a loop
    /loops prompts <name> <stage>  — show full prompt for a stage
    /loops prompts <name> <stage> <text> — replace prompt text
    /loops prompts <name> <stage> default — reset to default
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

    # /loops context <name> [on|off]  — toggle context-aware (STATE injection)
    if verb == "context":
        ctx_tokens = rest.strip().split()
        if not ctx_tokens:
            print("  usage: /loops context <loop_name> [on|off]")
            return
        loop_name = ctx_tokens[0]
        toggle = ctx_tokens[1].lower() if len(ctx_tokens) > 1 else None
        try:
            from agent.subconscious import _loop_manager
            if not _loop_manager:
                print(f"  {RED}loops not started{RESET}")
                return
            loop = _loop_manager.get_loop(loop_name)
            if not loop:
                print(f"  {RED}unknown loop: {loop_name}{RESET}")
                return
            if toggle is None:
                status = GREEN + "on" + RESET if loop.config.context_aware else DIM + "off" + RESET
                print(f"  {loop_name} context_aware: {status}")
                print(f"  {DIM}when on, the orchestrator STATE (identity/philosophy/linking/log) is injected into LLM prompts{RESET}")
            elif toggle in ("on", "true", "1"):
                loop.config.context_aware = True
                print(f"  {GREEN}{loop_name} context_aware → on{RESET}")
            elif toggle in ("off", "false", "0"):
                loop.config.context_aware = False
                print(f"  {YELLOW}{loop_name} context_aware → off{RESET}")
            else:
                print(f"  usage: /loops context {loop_name} on|off")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /loops prompts <name> [stage [new_text]]  — view/edit prompts
    if verb == "prompts":
        p_tokens = rest.strip().split(maxsplit=1)
        if not p_tokens:
            print("  usage: /loops prompts <loop_name> [stage [new prompt text]]")
            return
        loop_name = p_tokens[0]
        stage_rest = p_tokens[1] if len(p_tokens) > 1 else ""
        try:
            from agent.subconscious import _loop_manager
            if not _loop_manager:
                print(f"  {RED}loops not started{RESET}")
                return
            loop = _loop_manager.get_loop(loop_name)
            if not loop:
                print(f"  {RED}unknown loop: {loop_name}{RESET}")
                return
            prompts = getattr(loop, '_prompts', None)
            if prompts is None:
                print(f"  {DIM}{loop_name} has no editable prompts{RESET}")
                return

            if not stage_rest:
                # Show all stages
                print(f"  {BOLD}Prompts for {loop_name}:{RESET}")
                for stage, text in prompts.items():
                    preview = text.replace('\n', ' ')[:100]
                    print(f"    {GREEN}{stage}{RESET}: {DIM}{preview}...{RESET}")
                print(f"  {DIM}edit: /loops prompts {loop_name} <stage> <new prompt>{RESET}")
                print(f"  {DIM}reset: /loops prompts {loop_name} <stage> default{RESET}")
                return

            s_tokens = stage_rest.split(maxsplit=1)
            stage = s_tokens[0]
            new_text = s_tokens[1] if len(s_tokens) > 1 else ""

            if stage not in prompts:
                print(f"  {RED}unknown stage: {stage}{RESET}")
                print(f"  {DIM}available: {', '.join(prompts.keys())}{RESET}")
                return

            if not new_text:
                # Show the full prompt for this stage
                print(f"  {BOLD}{loop_name} → {stage}:{RESET}")
                print(f"  {'─' * 60}")
                for line in prompts[stage].splitlines():
                    print(f"  {line}")
                print(f"  {'─' * 60}")
                return

            if new_text.strip().lower() == "default":
                # Reset to default
                from agent.subconscious.loops.memory import DEFAULT_PROMPTS as MEM_D
                from agent.subconscious.loops.thought import DEFAULT_PROMPTS as TH_D
                from agent.subconscious.loops.task_planner import DEFAULT_PROMPTS as TP_D
                all_d = {**MEM_D, **TH_D, **TP_D}
                if stage in all_d:
                    prompts[stage] = all_d[stage]
                    print(f"  {GREEN}{loop_name} → {stage} reset to default{RESET}")
                else:
                    print(f"  {RED}no default for stage '{stage}'{RESET}")
                return

            prompts[stage] = new_text
            print(f"  {GREEN}{loop_name} → {stage} updated ({len(new_text)} chars){RESET}")
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
                ctx_str = f"  {GREEN}◉ ctx{RESET}" if s.get('context_aware') else ""
                print(f"  {color}{s['name']:20s} {status:10s}{RESET}"
                      f"  runs={s.get('run_count', 0)}"
                      f"  errors={s.get('error_count', 0)}"
                      f"{model_str}{provider_str}{ctx_str}")
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


def _cmd_tasks(args: str):
    """Handle /tasks command — manage context-aware task planner."""
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

    # /tasks new <goal>  — create and execute a task
    if verb == "new" and rest:
        print(f"  {DIM}planning task: {rest}{RESET}")
        try:
            from agent.subconscious.loops import create_task, TaskPlanner
            task = create_task(rest, source="cli")
            print(f"  {DIM}task #{task['id']} created — executing...{RESET}")

            planner = TaskPlanner(enabled=False)
            result = planner.execute_task(task["id"])

            status = result.get("status", "unknown")
            scolor = GREEN if status == "completed" else RED if status == "failed" else YELLOW
            print(f"  {scolor}[{status}]{RESET} task #{result.get('id', '?')}")

            steps = result.get("steps", [])
            results = result.get("results", [])
            for i, step in enumerate(steps):
                r = results[i] if i < len(results) else {}
                icon = "✓" if r.get("success") else "✗"
                rcolor = GREEN if r.get("success") else RED
                print(f"    {rcolor}{icon}{RESET} {step.get('description', f'Step {i+1}')}")
                if r.get("error"):
                    print(f"      {RED}{r['error'][:120]}{RESET}")

            # Print summary if present
            summary_results = [r for r in results if r.get("step") == "summary"]
            if summary_results:
                print(f"\n  {BOLD}Summary:{RESET} {summary_results[0].get('output', '')[:300]}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /tasks queue <goal>  — create task but don't execute (wait for planner loop)
    if verb == "queue" and rest:
        try:
            from agent.subconscious.loops import create_task
            task = create_task(rest, source="cli")
            print(f"  {GREEN}queued{RESET} task #{task['id']}: {rest}")
            print(f"  {DIM}will be picked up by the task planner loop{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /tasks <id>  — show details for a specific task
    if verb.isdigit():
        try:
            from agent.subconscious.loops import get_task
            task = get_task(int(verb))
            if not task:
                print(f"  {RED}task #{verb} not found{RESET}")
                return
            scolor = GREEN if task["status"] == "completed" else RED if task["status"] == "failed" else YELLOW
            print(f"  {BOLD}Task #{task['id']}{RESET} {scolor}[{task['status']}]{RESET}")
            print(f"  {BOLD}Goal:{RESET} {task['goal']}")
            print(f"  {DIM}source: {task['source']} | step: {task['current_step']}/{len(task['steps'])}{RESET}")
            if task.get("context_summary"):
                print(f"  {DIM}context: {task['context_summary'][:100]}{RESET}")
            for i, step in enumerate(task.get("steps", [])):
                results = task.get("results", [])
                r = results[i] if i < len(results) else {}
                icon = "✓" if r.get("success") else "✗" if r else "○"
                rcolor = GREEN if r.get("success") else RED if r.get("error") else DIM
                tool_info = f"[{step.get('tool', '?')}]" if step.get('tool') else ""
                print(f"    {rcolor}{icon}{RESET} {step.get('description', f'Step {i+1}')} {DIM}{tool_info}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /tasks cancel <id>
    if verb == "cancel" and rest.isdigit():
        try:
            from agent.subconscious.loops import cancel_task
            success = cancel_task(int(rest))
            if success:
                print(f"  {GREEN}cancelled{RESET} task #{rest}")
            else:
                print(f"  {RED}cannot cancel — task not found or already done{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /tasks  or  /tasks <status>  — list tasks
    try:
        from agent.subconscious.loops import get_tasks, TASK_STATUSES
        status_filter = verb if verb in TASK_STATUSES else None
        tasks = get_tasks(status=status_filter, limit=15)

        if not tasks:
            title = f"no {status_filter} tasks" if status_filter else "no tasks yet — run /tasks new <goal>"
            print(f"  {DIM}{title}{RESET}")
        else:
            title = f"Recent {status_filter} tasks:" if status_filter else "Recent tasks:"
            print(f"  {BOLD}{title}{RESET}")
            for t in tasks:
                scolor = GREEN if t["status"] == "completed" else RED if t["status"] == "failed" else YELLOW
                step_info = f"{t['current_step']}/{len(t['steps'])}" if t['steps'] else "0/?"
                print(f"  {DIM}#{t['id']}{RESET} {scolor}[{t['status']}]{RESET} ({step_info}) {t['goal'][:60]}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")
# ── Tools ────────────────────────────────────────────────────────────────

def _cmd_tools(args: str):
    """Manage tools.

    /tools                     — list all tools
    /tools <name>              — show tool details
    /tools run <name> <action> [json_params] — execute a tool action
    /tools new                 — interactive tool creator
    /tools code <name>         — show executable code
    /tools toggle <name>       — enable/disable tool
    /tools delete <name>       — delete tool
    /tools categories          — list categories
    """
    tokens = args.strip().split(maxsplit=2)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""
    extra = tokens[2] if len(tokens) > 2 else ""

    # /tools run <name> <action> [params]
    if verb == "run":
        run_tokens = rest.strip().split(maxsplit=1) if rest else []
        tool_name = run_tokens[0] if run_tokens else ""
        action_rest = run_tokens[1] if len(run_tokens) > 1 else ""
        action_tokens = action_rest.split(maxsplit=1) if action_rest else []
        action = action_tokens[0] if action_tokens else "default"
        params_str = action_tokens[1] if len(action_tokens) > 1 else ""

        if not tool_name:
            print("  usage: /tools run <name> <action> [json_params]")
            return

        import json as _json
        params = {}
        if params_str:
            try:
                params = _json.loads(params_str)
            except _json.JSONDecodeError:
                print(f"  {RED}invalid JSON params{RESET}")
                return

        try:
            from agent.threads.form.schema import execute_tool_action
            result = execute_tool_action(tool_name, action, params or None)
            status = result.get("status", "?")
            scolor = GREEN if result.get("success") else RED
            print(f"  {scolor}[{status}]{RESET} {tool_name}.{action}  ({result.get('duration_ms', '?')}ms)")
            if result.get("output"):
                output = str(result["output"])
                for line in output.splitlines()[:30]:
                    print(f"    {line}")
            if result.get("error"):
                print(f"  {RED}{result['error']}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /tools new  — interactive creator
    if verb == "new":
        try:
            from agent.threads.form.schema import add_tool, get_categories
            cats = get_categories()
            cat_names = [c["name"] for c in cats]

            name = input(f"  {BOLD}name:{RESET} ").strip()
            if not name:
                print("  cancelled")
                return
            desc = input(f"  {BOLD}description:{RESET} ").strip()
            print(f"  {DIM}categories: {', '.join(cat_names)}{RESET}")
            cat = input(f"  {BOLD}category:{RESET} ").strip() or "automation"
            actions_str = input(f"  {BOLD}actions{RESET} (comma-sep, or Enter for 'default'): ").strip()
            actions = [a.strip() for a in actions_str.split(",")] if actions_str else ["default"]
            run_type = input(f"  {BOLD}run_type{RESET} (python/shell/node) [{GREEN}python{RESET}]: ").strip() or "python"

            ok = add_tool(name=name, description=desc, category=cat,
                          actions=actions, run_type=run_type)
            if ok:
                print(f"  {GREEN}created tool: {name}{RESET}")
                print(f"  {DIM}edit code with: /tools code {name}{RESET}")
            else:
                print(f"  {RED}failed to create tool{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /tools code <name>
    if verb == "code":
        name = rest.strip()
        if not name:
            print("  usage: /tools code <name>")
            return
        try:
            from agent.threads.form.schema import get_executable_code
            code = get_executable_code(name)
            if code:
                print(f"  {BOLD}{name} code:{RESET}")
                print(f"  {'─' * 60}")
                for line in code.splitlines():
                    print(f"  {line}")
                print(f"  {'─' * 60}")
            else:
                print(f"  {DIM}no code for {name}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /tools toggle <name>
    if verb == "toggle":
        name = rest.strip()
        if not name:
            print("  usage: /tools toggle <name>")
            return
        try:
            from agent.threads.form.schema import get_tool, update_tool
            tool = get_tool(name)
            if not tool:
                print(f"  {RED}tool not found: {name}{RESET}")
                return
            new_state = not tool.get("enabled", True)
            update_tool(name, enabled=new_state)
            print(f"  {name} → {'enabled' if new_state else 'disabled'}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /tools delete <name>
    if verb == "delete":
        name = rest.strip()
        if not name:
            print("  usage: /tools delete <name>")
            return
        try:
            from agent.threads.form.schema import remove_tool_definition
            ok = remove_tool_definition(name)
            print(f"  {'deleted' if ok else 'not found'}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /tools categories
    if verb == "categories":
        try:
            from agent.threads.form.schema import get_categories
            for c in get_categories():
                print(f"  {BOLD}{c['name']}{RESET}  {DIM}{c.get('description', '')}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /tools <name>  — show details
    if verb and verb not in ("list",):
        try:
            from agent.threads.form.schema import get_tool
            tool = get_tool(verb)
            if not tool:
                print(f"  {RED}tool not found: {verb}{RESET}")
                return
            enabled = GREEN + "on" + RESET if tool.get("enabled") else RED + "off" + RESET
            allowed = GREEN + "yes" + RESET if tool.get("allowed") else RED + "no" + RESET
            print(f"  {BOLD}{tool['name']}{RESET}  [{tool.get('category', '?')}]  {enabled}")
            print(f"  {DIM}{tool.get('description', '')}{RESET}")
            print(f"  run_type: {tool.get('run_type', '?')}  allowed: {allowed}  weight: {tool.get('weight', '?')}")
            actions = tool.get("actions", [])
            if actions:
                print(f"  actions: {', '.join(actions)}")
            env = tool.get("requires_env", [])
            if env:
                print(f"  requires_env: {', '.join(env)}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Default: list all tools
    try:
        from agent.threads.form.schema import get_tools
        tools = get_tools()
        if not tools:
            print("  no tools — run /tools new to create one")
            return
        for t in tools:
            enabled = GREEN + "●" + RESET if t.get("enabled") else DIM + "○" + RESET
            actions = t.get("actions", [])
            act_str = f"  [{', '.join(actions)}]" if actions else ""
            print(f"  {enabled} {BOLD}{t['name']:20s}{RESET} {t.get('category', ''):14s} {t.get('run_type', ''):8s}{act_str}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


# ── Identity ─────────────────────────────────────────────────────────────

def _cmd_identity(args: str):
    """Manage identity profiles and facts.

    /identity                      — list profiles
    /identity <profile_id>         — show facts for a profile
    /identity new                  — create profile interactively
    /identity fact <profile> <key> <value> — add/update a fact
    /identity delete <profile_id>  — delete profile
    """
    tokens = args.strip().split(maxsplit=2)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""
    extra = tokens[2] if len(tokens) > 2 else ""

    # /identity new
    if verb == "new":
        try:
            from agent.threads.identity.schema import create_profile, get_profile_types
            types = get_profile_types()
            type_names = [t["type_name"] for t in types]
            print(f"  {DIM}types: {', '.join(type_names)}{RESET}")
            pid = input(f"  {BOLD}profile_id:{RESET} ").strip()
            if not pid:
                print("  cancelled")
                return
            tname = input(f"  {BOLD}type_name:{RESET} ").strip() or "self"
            dname = input(f"  {BOLD}display_name:{RESET} ").strip() or pid
            create_profile(pid, tname, dname)
            print(f"  {GREEN}created profile: {pid}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /identity fact <profile> <key> <value>
    if verb == "fact":
        fact_tokens = (rest + " " + extra).strip().split(maxsplit=2)
        if len(fact_tokens) < 3:
            print("  usage: /identity fact <profile_id> <key> <value>")
            return
        profile_id, key, value = fact_tokens[0], fact_tokens[1], fact_tokens[2]
        try:
            from agent.threads.identity.schema import push_profile_fact
            push_profile_fact(profile_id, key, fact_type="trait",
                              l1_value=value[:60], l2_value=value)
            print(f"  {GREEN}saved{RESET} {profile_id}/{key}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /identity delete <profile_id>
    if verb == "delete":
        pid = rest.strip()
        if not pid:
            print("  usage: /identity delete <profile_id>")
            return
        try:
            from agent.threads.identity.schema import delete_profile
            ok = delete_profile(pid)
            print(f"  {'deleted' if ok else 'not found'}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /identity <profile_id>  — show facts
    if verb:
        try:
            from agent.threads.identity.schema import pull_profile_facts
            facts = pull_profile_facts(profile_id=verb)
            if not facts:
                print(f"  {DIM}no facts for '{verb}'{RESET}")
                return
            for f in facts:
                val = f.get("l2_value") or f.get("l1_value") or ""
                w = f.get("weight", 0)
                print(f"  {DIM}[{f.get('fact_type', '?')}]{RESET} {BOLD}{f['key']}{RESET}: {val}  {DIM}w={w:.1f}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Default: list profiles
    try:
        from agent.threads.identity.schema import get_profiles
        profiles = get_profiles()
        if not profiles:
            print("  no profiles — run /identity new")
            return
        for p in profiles:
            print(f"  {BOLD}{p['profile_id']:20s}{RESET} [{p.get('type_name', '?')}]  {p.get('display_name', '')}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


# ── Philosophy ───────────────────────────────────────────────────────────

def _cmd_philosophy(args: str):
    """Manage philosophy profiles and stances.

    /philosophy                      — list profiles
    /philosophy <profile_id>         — show facts/stances
    /philosophy new                  — create profile interactively
    /philosophy fact <profile> <key> <value> — add/update a stance
    /philosophy delete <profile_id>  — delete profile
    """
    tokens = args.strip().split(maxsplit=2)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""
    extra = tokens[2] if len(tokens) > 2 else ""

    # /philosophy new
    if verb == "new":
        try:
            from agent.threads.philosophy.schema import (
                create_philosophy_profile, get_philosophy_profile_types
            )
            types = get_philosophy_profile_types()
            type_names = [t["type_name"] for t in types]
            print(f"  {DIM}types: {', '.join(type_names)}{RESET}")
            pid = input(f"  {BOLD}profile_id:{RESET} ").strip()
            if not pid:
                print("  cancelled")
                return
            tname = input(f"  {BOLD}type_name:{RESET} ").strip() or "stance"
            dname = input(f"  {BOLD}display_name:{RESET} ").strip() or pid
            create_philosophy_profile(pid, tname, dname)
            print(f"  {GREEN}created profile: {pid}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /philosophy fact <profile> <key> <value>
    if verb == "fact":
        fact_tokens = (rest + " " + extra).strip().split(maxsplit=2)
        if len(fact_tokens) < 3:
            print("  usage: /philosophy fact <profile_id> <key> <value>")
            return
        profile_id, key, value = fact_tokens[0], fact_tokens[1], fact_tokens[2]
        try:
            from agent.threads.philosophy.schema import push_philosophy_profile_fact
            push_philosophy_profile_fact(profile_id, key,
                                         l1_value=value[:60], l2_value=value)
            print(f"  {GREEN}saved{RESET} {profile_id}/{key}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /philosophy delete <profile_id>
    if verb == "delete":
        pid = rest.strip()
        if not pid:
            print("  usage: /philosophy delete <profile_id>")
            return
        try:
            from agent.threads.philosophy.schema import delete_philosophy_profile
            ok = delete_philosophy_profile(pid)
            print(f"  {'deleted' if ok else 'not found'}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /philosophy <profile_id>  — show facts
    if verb:
        try:
            from agent.threads.philosophy.schema import pull_philosophy_profile_facts
            facts = pull_philosophy_profile_facts(profile_id=verb)
            if not facts:
                print(f"  {DIM}no stances for '{verb}'{RESET}")
                return
            for f in facts:
                val = f.get("l2_value") or f.get("l1_value") or ""
                w = f.get("weight", 0)
                print(f"  {DIM}[{f.get('fact_type', '?')}]{RESET} {BOLD}{f['key']}{RESET}: {val}  {DIM}w={w:.1f}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Default: list profiles
    try:
        from agent.threads.philosophy.schema import get_philosophy_profiles
        profiles = get_philosophy_profiles()
        if not profiles:
            print("  no philosophy profiles — run /philosophy new")
            return
        for p in profiles:
            print(f"  {BOLD}{p['profile_id']:20s}{RESET} [{p.get('type_name', '?')}]  {p.get('display_name', '')}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


# ── Log / Timeline ───────────────────────────────────────────────────────

def _cmd_log(args: str):
    """View event log and timeline.

    /log                    — recent timeline
    /log events [type]      — raw events (optionally filtered by type)
    /log search <query>     — search log events
    /log types              — list event types
    /log stats              — log statistics
    """
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

    # /log events [type]
    if verb == "events":
        try:
            from agent.threads.log.schema import get_events
            event_type = rest.strip() or None
            events = get_events(event_type=event_type, limit=25)
            if not events:
                print(f"  {DIM}no events{RESET}")
                return
            for e in events:
                ts = str(e.get("timestamp", ""))[:19]
                print(f"  {DIM}{ts}{RESET} [{e.get('event_type', '?'):12s}] {e.get('data', '')[:80]}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /log search <query>
    if verb == "search":
        if not rest.strip():
            print("  usage: /log search <query>")
            return
        try:
            from agent.threads.log.schema import get_events
            events = get_events(limit=50)
            query_lower = rest.strip().lower()
            matches = [e for e in events if query_lower in str(e.get("data", "")).lower()]
            if not matches:
                print(f"  {DIM}no matches{RESET}")
                return
            for e in matches[:20]:
                ts = str(e.get("timestamp", ""))[:19]
                print(f"  {DIM}{ts}{RESET} [{e.get('event_type', '?'):12s}] {e.get('data', '')[:80]}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /log types
    if verb == "types":
        try:
            from agent.threads.log.schema import get_event_types
            for t in get_event_types():
                print(f"  {t}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /log stats
    if verb == "stats":
        try:
            from agent.threads.log.schema import get_log_stats
            stats = get_log_stats()
            for k, v in stats.items():
                print(f"  {k:20s}  {v}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Default: timeline
    try:
        from agent.threads.log.schema import get_user_timeline
        timeline = get_user_timeline(limit=20)
        if not timeline:
            print(f"  {DIM}no timeline events{RESET}")
            return
        for e in timeline:
            ts = str(e.get("timestamp", ""))[:19]
            print(f"  {DIM}{ts}{RESET}  {e.get('data', e.get('event_type', ''))[:80]}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


# ── Workspace / Files ────────────────────────────────────────────────────

def _cmd_files(args: str):
    """Virtual filesystem.

    /files [path]            — list directory (default /)
    /files read <path>       — show file content
    /files search <query>    — search files
    /files stats             — workspace statistics
    """
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

    # /files read <path>
    if verb == "read":
        path = rest.strip()
        if not path:
            print("  usage: /files read <path>")
            return
        try:
            from workspace.schema import get_file
            f = get_file(path)
            if not f:
                print(f"  {RED}not found: {path}{RESET}")
                return
            content = f.get("content", b"")
            if isinstance(content, bytes):
                try:
                    content = content.decode("utf-8")
                except UnicodeDecodeError:
                    print(f"  {DIM}binary file ({len(content)} bytes){RESET}")
                    return
            print(f"  {BOLD}{path}{RESET}  ({len(content)} chars)")
            print(f"  {'─' * 60}")
            for line in content.splitlines()[:50]:
                print(f"  {line}")
            if content.count('\n') > 50:
                print(f"  {DIM}... truncated ({content.count(chr(10))} total lines){RESET}")
            print(f"  {'─' * 60}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /files search <query>
    if verb == "search":
        if not rest.strip():
            print("  usage: /files search <query>")
            return
        try:
            from workspace.schema import search_files
            results = search_files(rest.strip())
            if not results:
                print(f"  {DIM}no matches{RESET}")
                return
            for r in results:
                print(f"  {BOLD}{r.get('path', '?')}{RESET}  {DIM}{r.get('mime_type', '')}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /files stats
    if verb == "stats":
        try:
            from workspace.schema import get_workspace_stats
            stats = get_workspace_stats()
            for k, v in stats.items():
                print(f"  {k:20s}  {v}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Default: list directory
    path = verb or "/"
    try:
        from workspace.schema import list_directory
        entries = list_directory(path)
        if not entries:
            print(f"  {DIM}empty or not found: {path}{RESET}")
            return
        for e in entries:
            is_dir = e.get("is_dir", False)
            icon = "📁" if is_dir else "📄"
            size = e.get("size", "")
            size_str = f"  {DIM}{size} bytes{RESET}" if size and not is_dir else ""
            print(f"  {icon} {e.get('name', e.get('path', '?'))}{size_str}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


# ── Conversations ────────────────────────────────────────────────────────

def _cmd_convos(args: str):
    """Manage conversations.

    /convos                  — list recent conversations
    /convos <id>             — show conversation turns
    /convos search <query>   — search conversations
    /convos new [name]       — create new conversation
    /convos delete <id>      — delete conversation
    """
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

    # /convos search <query>
    if verb == "search":
        if not rest.strip():
            print("  usage: /convos search <query>")
            return
        try:
            from chat.schema import search_conversations
            results = search_conversations(rest.strip())
            if not results:
                print(f"  {DIM}no matches{RESET}")
                return
            for c in results[:15]:
                name = c.get("name") or c.get("session_id", "?")[:20]
                turns = c.get("turn_count", "?")
                print(f"  {BOLD}{name}{RESET}  {DIM}{c.get('session_id', '?')[:12]}  {turns} turns{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /convos new [name]
    if verb == "new":
        try:
            import uuid as _uuid
            from chat.schema import save_conversation
            sid = str(_uuid.uuid4())[:12]
            name = rest.strip() or f"cli-{sid[:8]}"
            save_conversation(sid, name=name, channel="cli")
            print(f"  {GREEN}created:{RESET} {name}  (id: {sid})")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /convos delete <id>
    if verb == "delete":
        sid = rest.strip()
        if not sid:
            print("  usage: /convos delete <session_id>")
            return
        try:
            from chat.schema import delete_conversation
            ok = delete_conversation(sid)
            print(f"  {'deleted' if ok else 'not found'}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /convos <id>  — show conversation
    if verb and verb not in ("list",):
        try:
            from chat.schema import get_conversation
            convo = get_conversation(verb)
            if not convo:
                print(f"  {RED}not found: {verb}{RESET}")
                return
            name = convo.get("name") or convo.get("session_id", "?")
            print(f"  {BOLD}{name}{RESET}  {DIM}{convo.get('channel', '?')}{RESET}")
            turns = convo.get("turns", [])
            for t in turns[-20:]:
                role = t.get("role", "?")
                rcolor = CYAN if role == "user" else GREEN
                content = t.get("content", "")[:120]
                print(f"  {rcolor}{role:10s}{RESET} {content}")
            if len(turns) > 20:
                print(f"  {DIM}... {len(turns) - 20} earlier turns{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Default: list conversations
    try:
        from chat.schema import list_conversations
        convos = list_conversations(limit=20)
        if not convos:
            print("  no conversations")
            return
        for c in convos:
            name = c.get("name") or "unnamed"
            sid = c.get("session_id", "?")[:12]
            turns = c.get("turn_count", "?")
            ch = c.get("channel", "?")
            print(f"  {BOLD}{name:30s}{RESET} {DIM}{sid}  {ch:8s}  {turns} turns{RESET}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


# ── Feeds ────────────────────────────────────────────────────────────────

def _cmd_feeds(args: str):
    """Manage feed sources.

    /feeds                  — list feed sources
    /feeds templates        — available integration templates
    /feeds toggle <name>    — enable/disable a feed
    /feeds test <name>      — test feed connection
    """
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

    # /feeds templates
    if verb == "templates":
        try:
            from Feeds.sources import get_feed_templates
            templates = get_feed_templates()
            if not templates:
                print(f"  {DIM}no templates{RESET}")
                return
            for t in templates:
                name = t if isinstance(t, str) else t.get("name", "?")
                desc = "" if isinstance(t, str) else t.get("description", "")
                print(f"  {BOLD}{name}{RESET}  {DIM}{desc}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /feeds toggle <name>
    if verb == "toggle":
        name = rest.strip()
        if not name:
            print("  usage: /feeds toggle <name>")
            return
        try:
            from Feeds.sources import toggle_feed_source
            new_state = toggle_feed_source(name)
            print(f"  {name} → {'enabled' if new_state else 'disabled'}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /feeds test <name>
    if verb == "test":
        name = rest.strip()
        if not name:
            print("  usage: /feeds test <name>")
            return
        try:
            from Feeds.sources import test_feed_source
            result = test_feed_source(name)
            ok = result.get("success", False) if isinstance(result, dict) else result
            scolor = GREEN if ok else RED
            print(f"  {scolor}{'ok' if ok else 'failed'}{RESET}")
            if isinstance(result, dict) and result.get("error"):
                print(f"  {RED}{result['error']}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Default: list sources
    try:
        from Feeds.sources import get_feed_sources
        sources = get_feed_sources()
        if not sources:
            print(f"  {DIM}no feed sources configured{RESET}")
            return
        for s in sources:
            name = s if isinstance(s, str) else s.get("name", "?")
            enabled = True if isinstance(s, str) else s.get("enabled", False)
            ecolor = GREEN + "●" + RESET if enabled else DIM + "○" + RESET
            desc = "" if isinstance(s, str) else f"  {DIM}{s.get('description', '')}{RESET}"
            print(f"  {ecolor} {BOLD}{name}{RESET}{desc}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


# ── Triggers (extended) ─────────────────────────────────────────────────

def _cmd_triggers_ext(args: str):
    """Extended trigger management (wraps original + new features).

    /triggers                      — list triggers (original)
    /triggers toggle <id>          — toggle on/off (original)
    /triggers new                  — create trigger interactively
    /triggers <id>                 — show trigger details
    /triggers delete <id>          — delete trigger
    """
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

    # /triggers new  — interactive creator
    if verb == "new":
        try:
            from agent.threads.reflex.schema import create_trigger
            print(f"  {DIM}Create a new reflex trigger{RESET}")
            name = input(f"  {BOLD}name:{RESET} ").strip()
            if not name:
                print("  cancelled")
                return
            feed = input(f"  {BOLD}feed_name:{RESET} ").strip()
            etype = input(f"  {BOLD}event_type:{RESET} ").strip()
            tool = input(f"  {BOLD}tool_name{RESET} (or Enter to skip): ").strip()
            action = input(f"  {BOLD}tool_action{RESET} (or Enter for default): ").strip() or "default"
            print(f"  {DIM}response_mode: tool, agent, notify{RESET}")
            mode = input(f"  {BOLD}response_mode{RESET} [{GREEN}tool{RESET}]: ").strip() or "tool"
            print(f"  {DIM}trigger_type: webhook, poll, schedule{RESET}")
            ttype = input(f"  {BOLD}trigger_type{RESET} [{GREEN}webhook{RESET}]: ").strip() or "webhook"
            cron = ""
            if ttype == "schedule":
                cron = input(f"  {BOLD}cron_expression:{RESET} ").strip()
            desc = input(f"  {BOLD}description:{RESET} ").strip()

            tid = create_trigger(
                name=name, feed_name=feed, event_type=etype,
                tool_name=tool, tool_action=action, description=desc,
                trigger_type=ttype, cron_expression=cron or None,
                response_mode=mode,
            )
            print(f"  {GREEN}created trigger #{tid}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /triggers delete <id>
    if verb == "delete" and rest.strip().isdigit():
        try:
            from agent.threads.reflex.schema import delete_trigger
            ok = delete_trigger(int(rest.strip()))
            print(f"  {'deleted' if ok else 'not found'}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /triggers <id>  — show details
    if verb.isdigit():
        try:
            from agent.threads.reflex.schema import get_trigger
            t = get_trigger(int(verb))
            if not t:
                print(f"  {RED}trigger #{verb} not found{RESET}")
                return
            enabled = GREEN + "on" + RESET if t.get("enabled") else RED + "off" + RESET
            print(f"  {BOLD}Trigger #{t['id']}{RESET}  {enabled}")
            print(f"  {BOLD}name:{RESET}       {t.get('name', '?')}")
            print(f"  {BOLD}feed:{RESET}       {t.get('feed_name', '?')} / {t.get('event_type', '?')}")
            print(f"  {BOLD}tool:{RESET}       {t.get('tool_name', '—')} → {t.get('tool_action', '—')}")
            print(f"  {BOLD}type:{RESET}       {t.get('trigger_type', '?')}")
            print(f"  {BOLD}mode:{RESET}       {t.get('response_mode', '?')}")
            if t.get("cron_expression"):
                print(f"  {BOLD}cron:{RESET}       {t['cron_expression']}")
            if t.get("description"):
                print(f"  {BOLD}desc:{RESET}       {t['description']}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Fall through to original handler
    _cmd_triggers(args)


# ── Custom Loops ─────────────────────────────────────────────────────────

def _cmd_loops_ext(args: str):
    """Extended loop management — wraps original + adds pause/resume/interval/custom.

    /loops new                      — create custom loop interactively
    /loops custom                   — list custom loops
    /loops delete <name>            — delete custom loop
    /loops pause <name>             — pause a loop
    /loops resume <name>            — resume a loop
    /loops interval <name> <secs>   — change loop interval
    (all other /loops subcommands fall through to original handler)
    """
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

    # /loops new  — interactive custom loop creator
    if verb == "new":
        try:
            from agent.subconscious.loops.custom import (
                save_custom_loop_config, CUSTOM_LOOP_SOURCES, CUSTOM_LOOP_TARGETS
            )
            print(f"  {BOLD}Create a custom loop{RESET}")
            name = input(f"  {BOLD}name:{RESET} ").strip()
            if not name:
                print("  cancelled")
                return
            print(f"  {DIM}sources: {', '.join(CUSTOM_LOOP_SOURCES)}{RESET}")
            source = input(f"  {BOLD}source:{RESET} ").strip()
            if source not in CUSTOM_LOOP_SOURCES:
                print(f"  {RED}invalid source — must be one of: {', '.join(CUSTOM_LOOP_SOURCES)}{RESET}")
                return
            print(f"  {DIM}targets: {', '.join(CUSTOM_LOOP_TARGETS)}{RESET}")
            target = input(f"  {BOLD}target:{RESET} ").strip() or "temp_memory"
            if target not in CUSTOM_LOOP_TARGETS:
                print(f"  {RED}invalid target — must be one of: {', '.join(CUSTOM_LOOP_TARGETS)}{RESET}")
                return
            interval = input(f"  {BOLD}interval_seconds{RESET} [{GREEN}60{RESET}]: ").strip()
            interval = float(interval) if interval else 60.0
            model = input(f"  {BOLD}model{RESET} (Enter for default): ").strip() or None
            print(f"  {DIM}Enter the prompt for the loop (what should it do each iteration?){RESET}")
            prompt = input(f"  {BOLD}prompt:{RESET} ").strip()
            if not prompt:
                print("  cancelled (prompt required)")
                return
            max_iters = input(f"  {BOLD}max_iterations{RESET} [{GREEN}1{RESET}]: ").strip()
            max_iters = int(max_iters) if max_iters else 1
            ctx = input(f"  {BOLD}context_aware{RESET} (inject STATE)? [y/N]: ").strip().lower()
            context_aware = ctx in ("y", "yes", "1", "true")

            config = save_custom_loop_config(
                name=name, source=source, target=target,
                interval=interval, model=model, prompt=prompt,
                max_iterations=max_iters, context_aware=context_aware,
            )
            print(f"  {GREEN}created custom loop: {name}{RESET}")
            print(f"  {DIM}source={source} → target={target}  interval={interval}s  iters={max_iters}{RESET}")
            if context_aware:
                print(f"  {GREEN}◉ context-aware{RESET} (STATE injected into prompts)")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /loops custom  — list custom loops
    if verb == "custom":
        try:
            from agent.subconscious.loops.custom import get_custom_loop_configs
            configs = get_custom_loop_configs()
            if not configs:
                print("  no custom loops — run /loops new to create one")
                return
            for c in configs:
                enabled = GREEN + "●" + RESET if c.get("enabled") else DIM + "○" + RESET
                ctx = f" {GREEN}◉ ctx{RESET}" if c.get("context_aware") else ""
                print(f"  {enabled} {BOLD}{c['name']:20s}{RESET} {c.get('source', '?')}→{c.get('target', '?')}"
                      f"  {c.get('interval', '?')}s  iters={c.get('max_iterations', '?')}{ctx}")
                prompt_preview = c.get("prompt", "")[:80]
                print(f"    {DIM}prompt: {prompt_preview}{'...' if len(c.get('prompt', '')) > 80 else ''}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /loops delete <name>
    if verb == "delete":
        name = rest.strip()
        if not name:
            print("  usage: /loops delete <name>")
            return
        try:
            from agent.subconscious.loops.custom import delete_custom_loop_config
            ok = delete_custom_loop_config(name)
            print(f"  {'deleted' if ok else 'not found'}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /loops pause <name>
    if verb == "pause":
        name = rest.strip()
        if not name:
            print("  usage: /loops pause <name>")
            return
        try:
            from agent.subconscious import _loop_manager
            if not _loop_manager:
                print(f"  {RED}loops not started{RESET}")
                return
            loop = _loop_manager.get_loop(name)
            if not loop:
                print(f"  {RED}unknown loop: {name}{RESET}")
                return
            loop.pause()
            print(f"  {YELLOW}{name} paused{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /loops resume <name>
    if verb == "resume":
        name = rest.strip()
        if not name:
            print("  usage: /loops resume <name>")
            return
        try:
            from agent.subconscious import _loop_manager
            if not _loop_manager:
                print(f"  {RED}loops not started{RESET}")
                return
            loop = _loop_manager.get_loop(name)
            if not loop:
                print(f"  {RED}unknown loop: {name}{RESET}")
                return
            loop.resume()
            print(f"  {GREEN}{name} resumed{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # /loops interval <name> <seconds>
    if verb == "interval":
        itokens = rest.strip().split()
        if len(itokens) < 2:
            print("  usage: /loops interval <name> <seconds>")
            return
        name, secs = itokens[0], itokens[1]
        try:
            new_interval = float(secs)
            from agent.subconscious import _loop_manager
            if not _loop_manager:
                print(f"  {RED}loops not started{RESET}")
                return
            loop = _loop_manager.get_loop(name)
            if not loop:
                print(f"  {RED}unknown loop: {name}{RESET}")
                return
            loop.config.interval_seconds = new_interval
            print(f"  {GREEN}{name} interval → {new_interval}s{RESET}")
        except ValueError:
            print(f"  {RED}invalid number: {secs}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Everything else → original handler
    _cmd_loops(args)


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
  {BOLD}AI OS — CLI Commands{RESET}

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

  {CYAN}Session{RESET}
    {BOLD}/clear{RESET}                     Clear message history
    {BOLD}/help{RESET}                      Show this help
    {BOLD}/quit{RESET}                      Exit
""")


_COMMANDS = {
    "/status": lambda a: _cmd_status(),
    "/memory": _cmd_memory,
    "/loops": _cmd_loops_ext,
    "/thoughts": _cmd_thoughts,
    "/tasks": _cmd_tasks,
    "/triggers": _cmd_triggers_ext,
    "/protocols": _cmd_protocols,
    "/graph": _cmd_graph,
    "/mindmap": _cmd_mindmap,
    "/tools": _cmd_tools,
    "/identity": _cmd_identity,
    "/philosophy": _cmd_philosophy,
    "/log": _cmd_log,
    "/files": _cmd_files,
    "/convos": _cmd_convos,
    "/feeds": _cmd_feeds,
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
