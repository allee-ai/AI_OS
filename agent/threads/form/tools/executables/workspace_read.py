"""
workspace_read — Read files from workspace database
====================================================

Actions:
    read_file(path)        → file content from workspace DB
    list_directory(path)   → directory listing from workspace DB
    search_files(query)    → full-text search across workspace files

Unlike file_read (which reads from disk), this reads from the
workspace virtual filesystem stored in SQLite. These are files
the user has uploaded or created through the workspace UI.
"""

import json
import sys
from pathlib import Path

# Add project root to path for workspace imports
PROJECT_ROOT = Path(__file__).resolve().parents[5]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workspace.schema import get_file, list_directory, search_files as ws_search


def run(action: str, params: dict) -> str:
    """Execute a workspace_read action."""
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
    except Exception as e:
        return f"Error: {e}"


def _read_file(params: dict) -> str:
    path = params.get("path", "")
    if not path:
        return "Error: path is required"

    record = get_file(path)
    if not record:
        return f"File not found in workspace: {path}"
    if record.get("is_folder"):
        return f"'{path}' is a folder, not a file. Use list_directory instead."

    content = record.get("content")
    if content is None:
        return "(empty file)"

    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return f"(binary file — {len(content):,} bytes, mime: {record.get('mime_type', 'unknown')})"
    else:
        text = str(content)

    # Truncate very large files
    if len(text) > 50_000:
        return text[:50_000] + f"\n\n... [truncated — {len(text):,} chars total]"

    return text


def _list_directory(params: dict) -> str:
    path = params.get("path", "/")
    entries = list_directory(path)

    if not entries:
        return f"(empty directory: {path})"

    lines = []
    for entry in entries[:100]:
        suffix = "/" if entry.get("is_folder") else ""
        size = entry.get("size", 0)
        name = entry.get("name", "?")
        if suffix:
            lines.append(f"  {name}/")
        else:
            lines.append(f"  {name}  ({size:,} bytes)")

    header = f"Directory: {path}  ({len(entries)} items)"
    if len(entries) > 100:
        lines.append(f"  ... and {len(entries) - 100} more")
    return header + "\n" + "\n".join(lines)


def _search_files(params: dict) -> str:
    query = params.get("query", "")
    if not query:
        return "Error: query is required"

    limit = int(params.get("limit", 20))
    results = ws_search(query, limit=limit)

    if not results:
        return f"No workspace files matching '{query}'"

    lines = []
    for r in results:
        snippet = r.get("snippet", "")
        lines.append(f"  {r['path']}  ({r.get('size', 0):,} bytes)")
        if snippet:
            lines.append(f"    > {snippet[:200]}")

    return f"Search results for '{query}' ({len(results)} matches):\n" + "\n".join(lines)
