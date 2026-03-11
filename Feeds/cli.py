"""Feeds CLI — /feeds"""

DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def _cmd_feeds(args: str):
    """Manage feed sources."""
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

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


COMMANDS = {
    "/feeds": _cmd_feeds,
}
