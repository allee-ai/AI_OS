"""
code_edit — Edit project source files from the chat (sandboxed)
===============================================================

Actions:
    edit_file(path, old, new)   → replace exact text in a file
    read_file(path)             → read a source file
    search_code(pattern, dir)   → regex search across the codebase
    list_files(path)            → list directory contents

All paths are sandboxed to the workspace root.
Write operations are restricted to source files (no binaries, no .env, no DB).
"""

import re
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[5]  # → AI_OS/

# Files that must never be edited
BLOCKED_PATHS = {
    ".env", ".env.local", ".env.production",
    "data/db/aios.db", "data/db/aios.db-wal", "data/db/aios.db-shm",
}

# Extensions that are allowed for editing
ALLOWED_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml",
    ".md", ".txt", ".html", ".css", ".toml", ".cfg", ".ini", ".sh",
}

MAX_FILE_SIZE = 100 * 1024  # 100KB read limit


def run(action: str, params: dict) -> str:
    """Execute a code_edit action."""
    actions = {
        "edit_file": _edit_file,
        "read_file": _read_file,
        "search_code": _search_code,
        "list_files": _list_files,
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
        raise ValueError("No path provided")
    path = (WORKSPACE_ROOT / path_str).resolve()
    if not str(path).startswith(str(WORKSPACE_ROOT)):
        raise ValueError(f"Path outside workspace: {path_str}")
    return path


def _check_editable(path: Path) -> None:
    """Verify a file is safe to edit."""
    rel = str(path.relative_to(WORKSPACE_ROOT))
    if rel in BLOCKED_PATHS:
        raise ValueError(f"Editing blocked for: {rel}")
    if path.suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type not editable: {path.suffix}")
    if "__pycache__" in rel or "node_modules" in rel or ".git/" in rel:
        raise ValueError(f"Cannot edit generated/vendor files: {rel}")


def _edit_file(params: dict) -> str:
    """Replace exact text in a file (old → new)."""
    path = _resolve_safe_path(params.get("path", ""))
    old_text = params.get("old", "")
    new_text = params.get("new", "")

    if not old_text:
        return "Error: 'old' text is required (exact text to replace)"
    if not path.exists():
        return f"File not found: {params.get('path')}"

    _check_editable(path)

    content = path.read_text(errors="replace")
    count = content.count(old_text)
    if count == 0:
        return "Error: 'old' text not found in file"
    if count > 1:
        return f"Error: 'old' text matches {count} locations — be more specific"

    new_content = content.replace(old_text, new_text, 1)
    path.write_text(new_content)

    rel = path.relative_to(WORKSPACE_ROOT)
    return f"Edited {rel}: replaced {len(old_text)} chars with {len(new_text)} chars"


def _read_file(params: dict) -> str:
    """Read a source file."""
    path = _resolve_safe_path(params.get("path", ""))
    if not path.exists():
        return f"File not found: {params.get('path')}"
    if not path.is_file():
        return f"Not a file: {params.get('path')}"

    size = path.stat().st_size
    content = path.read_text(errors="replace")

    if size > MAX_FILE_SIZE:
        content = content[:MAX_FILE_SIZE]
        return f"{content}\n\n... [truncated — {size:,} bytes, showing first {MAX_FILE_SIZE:,}]"

    return content


def _search_code(params: dict) -> str:
    """Regex search across source files."""
    pattern = params.get("pattern", "")
    directory = params.get("directory", ".")
    file_pattern = params.get("file_pattern", "*.py")

    if not pattern:
        return "Error: 'pattern' is required"

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Invalid regex: {e}"

    search_path = _resolve_safe_path(directory)
    if not search_path.is_dir():
        return f"Not a directory: {directory}"

    results = []
    for fpath in search_path.rglob(file_pattern):
        if not fpath.is_file():
            continue
        rel = str(fpath.relative_to(WORKSPACE_ROOT))
        if "__pycache__" in rel or "node_modules" in rel or ".git/" in rel:
            continue
        try:
            text = fpath.read_text(errors="replace")
        except Exception:
            continue

        for i, line in enumerate(text.splitlines(), 1):
            if regex.search(line):
                results.append(f"{rel}:{i}: {line.strip()}")
                if len(results) >= 50:
                    results.append("... (showing first 50 matches)")
                    return "\n".join(results)

    return "\n".join(results) if results else f"No matches for '{pattern}'"


def _list_files(params: dict) -> str:
    """List directory contents."""
    path = _resolve_safe_path(params.get("path", "."))
    if not path.exists():
        return f"Directory not found: {params.get('path')}"
    if not path.is_dir():
        return f"Not a directory: {params.get('path')}"

    entries = sorted(path.iterdir())
    lines = []
    for entry in entries[:100]:
        if entry.name.startswith("."):
            continue
        try:
            rel = entry.relative_to(WORKSPACE_ROOT)
        except ValueError:
            continue
        suffix = "/" if entry.is_dir() else ""
        lines.append(f"{rel}{suffix}")

    if len(entries) > 100:
        lines.append(f"... and {len(entries) - 100} more")

    return "\n".join(lines) if lines else "(empty directory)"
