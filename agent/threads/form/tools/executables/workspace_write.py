"""
workspace_write — Write files to workspace database
====================================================

Actions:
    write_file(path, content)      → create or update a file in workspace DB
    create_directory(path)         → create a folder in workspace DB
    delete_file(path)              → delete a file/folder from workspace DB
    move_file(old_path, new_path)  → move/rename a file or folder in workspace DB

Unlike file_write (which writes to disk), this writes to the
workspace virtual filesystem stored in SQLite. Files written
here appear in the workspace UI and don't touch the git repo.
"""

import os
import sys
from pathlib import Path

# Add project root to path for workspace imports
PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workspace.schema import create_file, ensure_folder, delete_file as ws_delete, get_file, move_file as ws_move


def run(action: str, params: dict) -> str:
    """Execute a workspace_write action."""
    actions = {
        "write_file": _write_file,
        "create_directory": _create_directory,
        "delete_file": _delete_file,
        "move_file": _move_file,
    }

    fn = actions.get(action)
    if not fn:
        return f"Unknown action: {action}. Available: {', '.join(actions)}"

    try:
        return fn(params)
    except Exception as e:
        return f"Error: {e}"


def _write_file(params: dict) -> str:
    path = params.get("path", "")
    content = params.get("content", "")
    if not path:
        return "Error: path is required"

    # Enforce max file size from settings
    max_size = int(os.getenv("AIOS_WORKSPACE_MAX_FILE_SIZE", "1048576"))
    content_bytes = content.encode("utf-8") if isinstance(content, str) else content
    if len(content_bytes) > max_size:
        return f"Error: content is {len(content_bytes):,} bytes, max is {max_size:,}. Reduce content or increase AIOS_WORKSPACE_MAX_FILE_SIZE."

    # Determine mime type from extension
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    mime_map = {
        "py": "text/x-python", "js": "application/javascript",
        "ts": "application/typescript", "jsx": "text/jsx", "tsx": "text/tsx",
        "json": "application/json", "html": "text/html", "css": "text/css",
        "md": "text/markdown", "txt": "text/plain", "yaml": "text/yaml",
        "yml": "text/yaml", "toml": "text/toml", "sql": "text/sql",
        "sh": "text/x-shellscript", "xml": "text/xml", "svg": "image/svg+xml",
    }
    mime_type = mime_map.get(ext, "text/plain")

    content_bytes = content.encode("utf-8") if isinstance(content, str) else content
    result = create_file(path=path, content=content_bytes, mime_type=mime_type)

    if result:
        size = result.get("size", len(content_bytes))
        return f"Wrote {size:,} bytes to workspace:{path}"
    return f"Failed to write workspace:{path}"


def _create_directory(params: dict) -> str:
    path = params.get("path", "")
    if not path:
        return "Error: path is required"

    ensure_folder(path)
    return f"Created directory workspace:{path}"


def _delete_file(params: dict) -> str:
    path = params.get("path", "")
    if not path:
        return "Error: path is required"
    if path == "/":
        return "Error: cannot delete root directory"

    record = get_file(path)
    if not record:
        return f"Not found in workspace: {path}"

    is_folder = record.get("is_folder", False)
    ws_delete(path, recursive=is_folder)
    label = "directory" if is_folder else "file"
    return f"Deleted {label} workspace:{path}"


def _move_file(params: dict) -> str:
    old_path = params.get("old_path", "")
    new_path = params.get("new_path", "")
    if not old_path:
        return "Error: old_path is required"
    if not new_path:
        return "Error: new_path is required"
    if old_path == "/":
        return "Error: cannot move root directory"

    record = get_file(old_path)
    if not record:
        return f"Not found in workspace: {old_path}"

    ws_move(old_path, new_path)
    label = "directory" if record.get("is_folder") else "file"
    return f"Moved {label} workspace:{old_path} → workspace:{new_path}"
