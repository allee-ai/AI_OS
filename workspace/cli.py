"""Workspace CLI — /files"""

DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def _cmd_files(args: str):
    """Virtual filesystem."""
    tokens = args.strip().split(maxsplit=1)
    verb = tokens[0] if tokens else ""
    rest = tokens[1] if len(tokens) > 1 else ""

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


COMMANDS = {
    "/files": _cmd_files,
}
