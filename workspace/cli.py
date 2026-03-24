"""Workspace CLI — /files"""

DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def _cmd_files(args: str):
    """Virtual filesystem.
    
    Subcommands:
        /files [path]                  — list directory (default /)
        /files read <path>             — read file contents
        /files write <path> <content>  — create / update a file
        /files mkdir <path>            — create a folder
        /files mv <old> <new>          — move / rename
        /files rm <path>               — delete file or folder
        /files search <query>          — full-text search
        /files stats                   — workspace statistics
    """
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

    if verb == "write":
        parts = rest.strip().split(maxsplit=1)
        path = parts[0] if parts else ""
        content = parts[1] if len(parts) > 1 else ""
        if not path:
            print("  usage: /files write <path> <content>")
            return
        try:
            from workspace.schema import create_file
            content_bytes = content.encode("utf-8")
            result = create_file(path=path, content=content_bytes)
            size = result.get("size", len(content_bytes)) if result else 0
            print(f"  {GREEN}wrote {size} bytes → {path}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "mkdir":
        path = rest.strip()
        if not path:
            print("  usage: /files mkdir <path>")
            return
        try:
            from workspace.schema import ensure_folder
            ensure_folder(path)
            print(f"  {GREEN}created {path}/{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "mv":
        parts = rest.strip().split(maxsplit=1)
        if len(parts) < 2:
            print("  usage: /files mv <old_path> <new_path>")
            return
        old_path, new_path = parts
        try:
            from workspace.schema import move_file
            move_file(old_path, new_path)
            print(f"  {GREEN}moved {old_path} → {new_path}{RESET}")
        except Exception as e:
            print(f"  {RED}error: {e}{RESET}")
        return

    if verb == "rm":
        path = rest.strip()
        if not path:
            print("  usage: /files rm <path>")
            return
        try:
            from workspace.schema import delete_file, get_file
            record = get_file(path)
            if not record:
                print(f"  {RED}not found: {path}{RESET}")
                return
            is_folder = record.get("is_folder", False)
            delete_file(path, recursive=is_folder)
            label = "directory" if is_folder else "file"
            print(f"  {GREEN}deleted {label}: {path}{RESET}")
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
