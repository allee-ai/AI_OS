# Tool Executables

L3 implementations for the Form thread's tool system. Each file exports a `run(action, params)` function.

## Current Executables (11)

| File | Tool | Actions |
|------|------|---------|
| `cli_command.py` | CLI passthrough | Shell command execution |
| `code_edit.py` | Code editing | Read/write/patch code files |
| `file_read.py` | File read | Read files (sandboxed to workspace) |
| `file_write.py` | File write | Write files (sandboxed to workspace) |
| `notify.py` | Notifications | Send user notifications |
| `regex_search.py` | Regex search | Search files by pattern |
| `terminal.py` | Terminal | Shell commands (30s timeout) |
| `web_search.py` | Web search | DuckDuckGo search |
| `workspace_read.py` | Workspace read | `read_file`, `list_directory`, `search_files` |
| `workspace_write.py` | Workspace write | `write_file`, `create_directory`, `move_file`, `delete_file` |

## How it works

1. **Tool definitions** live in the `form_tools` database table (synced from `registry.py` via `ensure_tools_in_db()`)
2. **Executable files** here implement the actual logic
3. The executor (`executor.py`) dispatches to these based on tool name

## File lifecycle

- **Created**: When a tool is added via `POST /api/form/tools`
- **Renamed**: When a tool is renamed via `POST /api/form/tools/{name}/rename`
- **Deleted**: When a tool is deleted via `DELETE /api/form/tools/{name}`

## Adding tools

```bash
curl -X POST http://localhost:8000/api/form/tools \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-tool",
    "description": "Does something useful",
    "category": "automation",
    "actions": ["run", "stop"],
    "run_type": "python"
  }'
```

This creates `my_tool.py` with a stub implementation.

## Stub format (Python)

```python
"""
My-Tool Tool
"""
from typing import Any, Dict

ACTIONS = ['run', 'stop']

def run(action: str, params: Dict[str, Any]) -> Any:
    """Execute tool action."""
    if ACTIONS and action not in ACTIONS:
        raise ValueError(f"Invalid action '{action}'. Available: {', '.join(ACTIONS)}")
    
    # TODO: Implement actions
    return {"status": "not_implemented", "action": action}
```
