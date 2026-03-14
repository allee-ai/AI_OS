"""Subconscious CLI — /status, /memory, /loops, /thoughts, /tasks"""

import os
import sys

DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def _cmd_status(args: str = ""):
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


def _cmd_loops(args: str):
    """Original loop handler — stats, run, model, provider, extract, context, prompts."""
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

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

    if verb == "model":
        name = rest.strip()
        if not name:
            print(f"  current extract model: {os.environ.get('AIOS_EXTRACT_MODEL', os.environ.get('AIOS_MODEL_NAME', 'qwen2.5:7b'))}")
            return
        os.environ["AIOS_EXTRACT_MODEL"] = name
        print(f"  extract model → {name}")
        return

    if verb == "provider":
        name = rest.strip()
        if not name:
            print(f"  current extract provider: {os.environ.get('AIOS_EXTRACT_PROVIDER', os.environ.get('AIOS_MODEL_PROVIDER', 'ollama'))}")
            return
        os.environ["AIOS_EXTRACT_PROVIDER"] = name
        print(f"  extract provider → {name}")
        return

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
                print(f"  {BOLD}{loop_name} → {stage}:{RESET}")
                print(f"  {'─' * 60}")
                for line in prompts[stage].splitlines():
                    print(f"  {line}")
                print(f"  {'─' * 60}")
                return

            if new_text.strip().lower() == "default":
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
        print(f"  extract model:    {os.environ.get('AIOS_EXTRACT_MODEL', os.environ.get('AIOS_MODEL_NAME', 'qwen2.5:7b'))}")
        print(f"  extract provider: {os.environ.get('AIOS_EXTRACT_PROVIDER', os.environ.get('AIOS_MODEL_PROVIDER', 'ollama'))}")


def _cmd_loops_ext(args: str):
    """Extended loop management — wraps original + adds pause/resume/interval/custom."""
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

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


def _cmd_thoughts(args: str):
    """Manage the proactive thought loop."""
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""

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

    try:
        from agent.subconscious.loops import get_thought_log, THOUGHT_CATEGORIES
        category = verb if verb in THOUGHT_CATEGORIES else None
        thoughts = get_thought_log(limit=15, category=category)
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


def _cmd_tasks(args: str):
    """Handle /tasks command — manage context-aware task planner."""
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

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

            summary_results = [r for r in results if r.get("step") == "summary"]
            if summary_results:
                print(f"\n  {BOLD}Summary:{RESET} {summary_results[0].get('output', '')[:300]}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "queue" and rest:
        try:
            from agent.subconscious.loops import create_task
            task = create_task(rest, source="cli")
            print(f"  {GREEN}queued{RESET} task #{task['id']}: {rest}")
            print(f"  {DIM}will be picked up by the task planner loop{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

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
                icon = "✓" if r.get("success") else "✗" if r.get("error") else "○"
                rcolor = GREEN if r.get("success") else RED if r.get("error") else DIM
                tool_info = f"[{step.get('tool', '?')}]" if step.get('tool') else ""
                print(f"    {rcolor}{icon}{RESET} {step.get('description', f'Step {i+1}')} {DIM}{tool_info}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

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


# ─────────────────────────────────────────────────────────────
# /goals — list, approve, reject, dismiss
# ─────────────────────────────────────────────────────────────

def _cmd_goals(args: str):
    tokens = args.strip().split()
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

    if verb in ("approve", "reject", "dismiss") and rest.isdigit():
        try:
            from agent.subconscious.loops.goals import resolve_goal
            status_map = {"approve": "approved", "reject": "rejected", "dismiss": "dismissed"}
            ok = resolve_goal(int(rest), status=status_map[verb])
            color = GREEN if verb == "approve" else RED if verb == "reject" else YELLOW
            print(f"  {color}{status_map[verb]}{RESET} goal #{rest}" if ok else f"  {RED}not found{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Default: list goals
    status_filter = verb if verb in ("pending", "approved", "rejected", "dismissed") else "pending"
    try:
        from agent.subconscious.loops.goals import get_proposed_goals
        goals = get_proposed_goals(status=status_filter, limit=20)
        if not goals:
            print(f"  {DIM}no {status_filter} goals{RESET}")
            return
        print(f"  {BOLD}Proposed goals ({status_filter}):{RESET}")
        for g in goals:
            pcolor = {"high": RED, "medium": YELLOW, "low": DIM}.get(g["priority"], "")
            print(f"  {DIM}#{g['id']}{RESET} {pcolor}[{g['priority']}]{RESET} {g['goal'][:70]}")
            if g.get("rationale"):
                print(f"    {DIM}{g['rationale'][:80]}{RESET}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


# ─────────────────────────────────────────────────────────────
# /notifications — list, read, dismiss
# ─────────────────────────────────────────────────────────────

def _cmd_notifications(args: str):
    tokens = args.strip().split()
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

    if verb == "dismiss" and rest.isdigit():
        try:
            from agent.threads.form.tools.executables.notify import _ensure_notifications_table
            _ensure_notifications_table()
            from data.db import get_connection
            from contextlib import closing
            with closing(get_connection()) as conn:
                conn.execute("UPDATE notifications SET dismissed = 1 WHERE id = ?", (int(rest),))
                conn.commit()
            print(f"  {GREEN}dismissed{RESET} notification #{rest}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "read" and rest.isdigit():
        try:
            from agent.threads.form.tools.executables.notify import _ensure_notifications_table
            _ensure_notifications_table()
            from data.db import get_connection
            from contextlib import closing
            with closing(get_connection()) as conn:
                conn.execute("UPDATE notifications SET read = 1 WHERE id = ?", (int(rest),))
                conn.commit()
            print(f"  {GREEN}marked read{RESET} notification #{rest}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Default: list
    unread = verb == "unread"
    try:
        from agent.threads.form.tools.executables.notify import _ensure_notifications_table
        _ensure_notifications_table()
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            if unread:
                cur.execute(
                    "SELECT id, type, message, priority, read, created_at FROM notifications "
                    "WHERE read = 0 AND dismissed = 0 ORDER BY id DESC LIMIT 20"
                )
            else:
                cur.execute(
                    "SELECT id, type, message, priority, read, created_at FROM notifications "
                    "WHERE dismissed = 0 ORDER BY id DESC LIMIT 20"
                )
            rows = cur.fetchall()

        if not rows:
            label = "unread " if unread else ""
            print(f"  {DIM}no {label}notifications{RESET}")
            return
        print(f"  {BOLD}Notifications:{RESET}")
        for r in rows:
            nid, ntype, msg, priority, is_read, ts = r
            pcolor = RED if priority == "urgent" else YELLOW if priority == "high" else ""
            read_mark = DIM if is_read else BOLD
            icon = {"alert": "🔔", "reminder": "⏰", "confirm": "❓"}.get(ntype, "📌")
            print(f"  {read_mark}{DIM}#{nid}{RESET} {icon} {pcolor}{msg[:70]}{RESET} {DIM}{ts}{RESET}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


# ─────────────────────────────────────────────────────────────
# /improvements — list, approve, reject, apply
# ─────────────────────────────────────────────────────────────

def _cmd_improvements(args: str):
    tokens = args.strip().split()
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

    if verb in ("approve", "reject") and rest.isdigit():
        try:
            from agent.subconscious.loops.self_improve import resolve_improvement
            status = "approved" if verb == "approve" else "rejected"
            ok = resolve_improvement(int(rest), status=status)
            color = GREEN if verb == "approve" else RED
            print(f"  {color}{status}{RESET} improvement #{rest}" if ok else f"  {RED}not found{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "apply" and rest.isdigit():
        try:
            from agent.subconscious.loops.self_improve import apply_improvement, resolve_improvement
            resolve_improvement(int(rest), status="approved")
            result = apply_improvement(int(rest))
            print(f"  {GREEN}applied{RESET}: {result}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Default: list
    status_filter = verb if verb in ("pending", "approved", "rejected", "applied") else "pending"
    try:
        from agent.subconscious.loops.self_improve import get_proposed_improvements
        imps = get_proposed_improvements(status=status_filter, limit=20)
        if not imps:
            print(f"  {DIM}no {status_filter} improvements{RESET}")
            return
        print(f"  {BOLD}Proposed improvements ({status_filter}):{RESET}")
        for imp in imps:
            print(f"  {DIM}#{imp['id']}{RESET} {CYAN}{imp['file_path']}{RESET}")
            print(f"    {imp['description'][:80]}")
            if imp.get("rationale"):
                print(f"    {DIM}{imp['rationale'][:80]}{RESET}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


# ─────────────────────────────────────────────────────────────
# /calendar — list, add, remove, poll
# ─────────────────────────────────────────────────────────────

def _cmd_calendar(args: str):
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

    if verb == "add":
        parts = rest.strip().split(maxsplit=1)
        if len(parts) < 2:
            print("  usage: /calendar add <name> <ical_url>")
            return
        name, url = parts[0], parts[1]
        try:
            from Feeds.sources.calendar import add_calendar
            result = add_calendar(name, url)
            print(f"  {GREEN}added{RESET} calendar '{result['name']}' → {result['ical_url'][:60]}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "remove":
        name = rest.strip()
        if not name:
            print("  usage: /calendar remove <name>")
            return
        try:
            from Feeds.sources.calendar import remove_calendar
            ok = remove_calendar(name)
            print(f"  {GREEN}removed{RESET} '{name}'" if ok else f"  {RED}not found: {name}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "poll":
        try:
            from Feeds.sources.calendar import poll_calendars
            count = poll_calendars()
            print(f"  {GREEN}polled calendars{RESET}: {count} events emitted")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Default: list calendars
    try:
        from Feeds.sources.calendar import get_calendars
        cals = get_calendars()
        if not cals:
            print(f"  {DIM}no calendars configured — use /calendar add <name> <ical_url>{RESET}")
            return
        print(f"  {BOLD}Calendar sources:{RESET}")
        for cal in cals:
            status = GREEN + "enabled" + RESET if cal["enabled"] else DIM + "disabled" + RESET
            print(f"  📅 {cal['name']} {status} (poll: {cal['poll_interval']}s, lookahead: {cal['lookahead_minutes']}m)")
            print(f"    {DIM}{cal['ical_url'][:70]}{RESET}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


# ─────────────────────────────────────────────────────────────
# /backfill — conversation concept extraction
# ─────────────────────────────────────────────────────────────

def _cmd_backfill(args: str):
    """Manage conversation concept backfill."""
    tokens = args.strip().split()
    verb = tokens[0] if tokens else ""

    if verb == "run":
        print(f"  {DIM}running backfill batch...{RESET}")
        try:
            from agent.subconscious.loops.convo_concepts import ConvoConceptLoop
            loop = ConvoConceptLoop(enabled=False)
            loop._process_batch()
            stats = loop.stats
            print(f"  {GREEN}batch complete{RESET}")
            print(f"    processed:  {stats['total_processed']} conversations")
            print(f"    concepts:   {stats['total_concepts']}")
            print(f"    links:      {stats['total_links']}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "all":
        print(f"  {DIM}processing all unextracted conversations...{RESET}")
        try:
            from agent.subconscious.loops.convo_concepts import ConvoConceptLoop, get_backfill_status
            loop = ConvoConceptLoop(enabled=False, batch_size=50)
            status = get_backfill_status()
            remaining = status["remaining"]
            print(f"  {remaining} conversations to process")
            batch = 0
            while True:
                loop._process_batch()
                batch += 1
                new_status = get_backfill_status()
                if new_status["remaining"] == 0:
                    break
                print(f"  {DIM}  batch {batch}: {new_status['processed']}/{new_status['total_conversations']}{RESET}")
            stats = loop.stats
            print(f"  {GREEN}backfill complete{RESET}")
            print(f"    processed:  {stats['total_processed']} conversations")
            print(f"    concepts:   {stats['total_concepts']}")
            print(f"    links:      {stats['total_links']}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "reset":
        try:
            from agent.subconscious.loops.convo_concepts import reset_backfill
            reset_backfill()
            print(f"  {GREEN}backfill progress reset — all conversations will be reprocessed{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    # Default: show status
    try:
        from agent.subconscious.loops.convo_concepts import get_backfill_status
        status = get_backfill_status()
        print(f"  {BOLD}Concept Backfill Status:{RESET}")
        print(f"    total conversations:  {status['total_conversations']}")
        print(f"    processed:            {status['processed']}")
        print(f"    remaining:            {status['remaining']}")
        if status['remaining'] > 0:
            print(f"  {DIM}run /backfill run (one batch) or /backfill all (everything){RESET}")
        else:
            print(f"  {GREEN}all conversations processed{RESET}")
    except Exception as e:
        print(f"  {RED}error: {e}{RESET}")


COMMANDS = {
    "/status": lambda a: _cmd_status(),
    "/memory": _cmd_memory,
    "/loops": _cmd_loops_ext,
    "/thoughts": _cmd_thoughts,
    "/tasks": _cmd_tasks,
    "/goals": _cmd_goals,
    "/notifications": _cmd_notifications,
    "/improvements": _cmd_improvements,
    "/calendar": _cmd_calendar,
    "/backfill": _cmd_backfill,
}
