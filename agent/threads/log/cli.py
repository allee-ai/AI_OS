"""Log / Timeline CLI — /log"""

DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def _cmd_log(args: str):
    """View event log and timeline."""
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

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

    if verb == "types":
        try:
            from agent.threads.log.schema import get_event_types
            for t in get_event_types():
                print(f"  {t}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

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


COMMANDS = {
    "/log": _cmd_log,
}
