"""
file_write — Write files to workspace (sandboxed)
==================================================

Actions:
    write_file(path, content)      → writes content, returns bytes written
    append_file(path, content)     → appends content
    create_directory(path)         → creates directory (mkdir -p)

All paths are sandboxed to the workspace root.
"""

from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[5]  # → AI_OS/


def run(action: str, params: dict) -> str:
    """Execute a file_write action."""
    actions = {
        "write_file": _write_file,
        "append_file": _append_file,
        "create_directory": _create_directory,
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


def _write_file(params: dict) -> str:
    path = _resolve_safe_path(params.get("path", ""))
    content = params.get("content", "")
    
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    
    rel = path.relative_to(WORKSPACE_ROOT)
    return f"Wrote {len(content)} bytes to {rel}"


def _append_file(params: dict) -> str:
    path = _resolve_safe_path(params.get("path", ""))
    content = params.get("content", "")
    
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a') as f:
        f.write(content)
    
    rel = path.relative_to(WORKSPACE_ROOT)
    return f"Appended {len(content)} bytes to {rel}"


def _create_directory(params: dict) -> str:
    path = _resolve_safe_path(params.get("path", ""))
    path.mkdir(parents=True, exist_ok=True)
    
    rel = path.relative_to(WORKSPACE_ROOT)
    return f"Created directory: {rel}"
