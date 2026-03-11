"""Chat / Conversations CLI — /convos"""

DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def _cmd_convos(args: str):
    """Manage conversations."""
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

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


COMMANDS = {
    "/convos": _cmd_convos,
}
