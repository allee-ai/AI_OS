"""
file_read — Read files from workspace (sandboxed)
=================================================

Actions:
    read_file(path)        → file contents (truncated at 50KB)
    list_directory(path)   → sorted entries with type indicators
    search_files(pattern, directory)  → glob match results

All paths are sandboxed to the workspace root.
"""

from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[5]  # → AI_OS/
MAX_FILE_SIZE = 50 * 1024  # 50KB


def run(action: str, params: dict) -> str:
    """Execute a file_read action."""
    actions = {
        "read_file": _read_file,
        "list_directory": _list_directory,
        "search_files": _search_files,
    }
    
    fn = actions.get(action)
    if not fn:
        return f"Unknown action: {action}. Available: {', '.join(actions)}"
    
    try:
        return fn(params)
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error: {e}"


def _resolve_safe_path(path_str: str) -> Path:
    """Resolve path, ensuring it stays within workspace."""
    if not path_str:
        return WORKSPACE_ROOT
    path = (WORKSPACE_ROOT / path_str).resolve()
    if not str(path).startswith(str(WORKSPACE_ROOT)):
        raise ValueError(f"Path outside workspace: {path_str}")
    return path


def _read_file(params: dict) -> str:
    path = _resolve_safe_path(params.get("path", ""))
    if not path.exists():
        return f"File not found: {params.get('path')}"
    if not path.is_file():
        return f"Not a file: {params.get('path')}"
    
    size = path.stat().st_size
    content = path.read_text(errors='replace')
    
    if size > MAX_FILE_SIZE:
        content = content[:MAX_FILE_SIZE]
        return f"{content}\n\n... [truncated — file is {size:,} bytes, showing first {MAX_FILE_SIZE:,}]"
    
    return content


def _list_directory(params: dict) -> str:
    path = _resolve_safe_path(params.get("path", "."))
    if not path.exists():
        return f"Directory not found: {params.get('path')}"
    if not path.is_dir():
        return f"Not a directory: {params.get('path')}"
    
    entries = sorted(path.iterdir())
    lines = []
    for entry in entries[:100]:
        try:
            rel = entry.relative_to(WORKSPACE_ROOT)
        except ValueError:
            continue
        suffix = "/" if entry.is_dir() else ""
        lines.append(f"{rel}{suffix}")
    
    if len(entries) > 100:
        lines.append(f"... and {len(entries) - 100} more")
    
    return "\n".join(lines) if lines else "(empty directory)"


def _search_files(params: dict) -> str:
    pattern = params.get("pattern", "*")
    directory = params.get("directory", ".")
    
    search_path = _resolve_safe_path(directory)
    if not search_path.is_dir():
        return f"Not a directory: {directory}"
    
    matches = list(search_path.rglob(pattern))[:50]
    
    if not matches:
        return f"No files matching '{pattern}' in {directory}"
    
    lines = []
    for m in matches:
        try:
            lines.append(str(m.relative_to(WORKSPACE_ROOT)))
        except ValueError:
            continue
    
    if len(matches) == 50:
        lines.append("... (showing first 50 results)")
    
    return "\n".join(lines)
