# Tool Executables

This directory contains executable files for tools registered in the `form_tools` database table.

## How it works

1. **Tool definitions** live in the SQLite database (`form_tools` table)
2. **Executable files** are created here when tools are added via the API
3. File extensions are determined by `run_type`:
   - `python` → `.py`
   - `shell` / `bash` → `.sh`
   - `node` / `javascript` → `.js`
   - `typescript` → `.ts`

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
