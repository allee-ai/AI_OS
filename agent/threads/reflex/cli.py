"""Reflex CLI — /triggers, /protocols"""

DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def _cmd_triggers(args: str):
    """Basic trigger management — list and toggle."""
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


def _cmd_triggers_ext(args: str):
    """Extended trigger management — wraps original + new, details, delete."""
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

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

    if verb == "delete" and rest.strip().isdigit():
        try:
            from agent.threads.reflex.schema import delete_trigger
            ok = delete_trigger(int(rest.strip()))
            print(f"  {'deleted' if ok else 'not found'}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

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


COMMANDS = {
    "/triggers": _cmd_triggers_ext,
    "/protocols": _cmd_protocols,
}
