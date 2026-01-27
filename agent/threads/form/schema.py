"""
Form Thread Schema
==================
Database operations for tool definitions.
Tools stored in DB, executables in files.
"""

import sqlite3
import json
import os
import time
import importlib.util
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

from data.db import get_connection

TOOLS_DIR = Path(__file__).parent / "tools"
EXECUTABLES_DIR = TOOLS_DIR / "executables"

RUN_TYPE_EXTENSIONS = {
    "python": ".py",
    "shell": ".sh",
    "bash": ".sh",
    "node": ".js",
    "javascript": ".js",
    "typescript": ".ts",
}


def init_form_tools_table() -> None:
    """Create form_tools table if it doesn't exist."""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS form_tools (
                name TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'internal',
                actions TEXT NOT NULL DEFAULT '[]',
                run_file TEXT,
                run_type TEXT NOT NULL DEFAULT 'python',
                requires_env TEXT NOT NULL DEFAULT '[]',
                weight REAL NOT NULL DEFAULT 0.5,
                enabled INTEGER NOT NULL DEFAULT 1,
                allowed INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_form_tools_category ON form_tools(category)")
        conn.commit()
    finally:
        conn.close()


def _ensure_table() -> None:
    """Ensure table exists before operations."""
    init_form_tools_table()


def get_tools() -> List[Dict[str, Any]]:
    """Get all tools from database."""
    _ensure_table()
    conn = get_connection(readonly=True)
    try:
        rows = conn.execute("""
            SELECT name, description, category, actions, run_file, run_type,
                   requires_env, weight, enabled, allowed, created_at, updated_at
            FROM form_tools ORDER BY weight DESC, name ASC
        """).fetchall()
        return [_row_to_tool(row) for row in rows]
    finally:
        conn.close()


def get_tool(name: str) -> Optional[Dict[str, Any]]:
    """Get a single tool by name."""
    _ensure_table()
    conn = get_connection(readonly=True)
    try:
        row = conn.execute("""
            SELECT name, description, category, actions, run_file, run_type,
                   requires_env, weight, enabled, allowed, created_at, updated_at
            FROM form_tools WHERE name = ?
        """, (name,)).fetchone()
        if not row:
            return None
        tool = _row_to_tool(row)
        tool["code"] = get_executable_code(name)
        return tool
    finally:
        conn.close()


def _row_to_tool(row) -> Dict[str, Any]:
    """Convert database row to tool dict."""
    run_file = row["run_file"]
    exec_path = EXECUTABLES_DIR / run_file if run_file else None
    exists = exec_path.exists() if exec_path else False
    requires_env = json.loads(row["requires_env"]) if row["requires_env"] else []
    env_ok = all(os.environ.get(var) for var in requires_env)
    available = bool(row["enabled"]) and bool(row["allowed"]) and exists and env_ok
    
    return {
        "name": row["name"],
        "description": row["description"],
        "category": row["category"],
        "actions": json.loads(row["actions"]) if row["actions"] else [],
        "run_file": run_file,
        "run_type": row["run_type"],
        "path": str(exec_path) if exec_path else None,
        "exists": exists,
        "requires_env": requires_env,
        "weight": row["weight"],
        "enabled": bool(row["enabled"]),
        "allowed": bool(row["allowed"]),
        "available": available,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def add_tool(
    name: str,
    description: str,
    category: str = "internal",
    actions: Optional[List[str]] = None,
    run_file: Optional[str] = None,
    run_type: str = "python",
    requires_env: Optional[List[str]] = None,
    weight: float = 0.5,
    enabled: bool = True,
    allowed: bool = True,
    code: Optional[str] = None
) -> bool:
    """Add a new tool to the database."""
    _ensure_table()
    actions = actions or []
    requires_env = requires_env or []
    
    # Generate run_file with correct extension if not provided
    if not run_file:
        ext = RUN_TYPE_EXTENSIONS.get(run_type.lower(), ".py")
        run_file = f"{name.replace('-', '_')}{ext}"
    
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO form_tools (name, description, category, actions, run_file, run_type, requires_env, weight, enabled, allowed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, description, category.lower(), json.dumps(actions),
            run_file, run_type, json.dumps(requires_env), weight,
            1 if enabled else 0, 1 if allowed else 0
        ))
        conn.commit()
        
        # Create executable file
        if code:
            save_executable_code(name, code)
        elif not (EXECUTABLES_DIR / run_file).exists():
            _create_stub_executable(name, run_file, run_type, actions)
        
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def update_tool(
    name: str,
    description: Optional[str] = None,
    category: Optional[str] = None,
    actions: Optional[List[str]] = None,
    run_file: Optional[str] = None,
    run_type: Optional[str] = None,
    requires_env: Optional[List[str]] = None,
    weight: Optional[float] = None,
    enabled: Optional[bool] = None,
    allowed: Optional[bool] = None,
    code: Optional[str] = None
) -> bool:
    """Update an existing tool."""
    _ensure_table()
    updates, params = [], []
    
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if category is not None:
        updates.append("category = ?")
        params.append(category.lower())
    if actions is not None:
        updates.append("actions = ?")
        params.append(json.dumps(actions))
    if run_file is not None:
        updates.append("run_file = ?")
        params.append(run_file)
    if run_type is not None:
        updates.append("run_type = ?")
        params.append(run_type)
    if requires_env is not None:
        updates.append("requires_env = ?")
        params.append(json.dumps(requires_env))
    if weight is not None:
        updates.append("weight = ?")
        params.append(weight)
    if enabled is not None:
        updates.append("enabled = ?")
        params.append(1 if enabled else 0)
    if allowed is not None:
        updates.append("allowed = ?")
        params.append(1 if allowed else 0)
    
    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(name)
        conn = get_connection()
        try:
            result = conn.execute(
                f"UPDATE form_tools SET {', '.join(updates)} WHERE name = ?",
                params
            )
            conn.commit()
            if result.rowcount == 0:
                return False
        finally:
            conn.close()
    
    if code is not None:
        save_executable_code(name, code)
    
    return True


def delete_tool(name: str) -> bool:
    """Delete a tool and its executable file."""
    _ensure_table()
    conn = get_connection()
    try:
        row = conn.execute("SELECT run_file FROM form_tools WHERE name = ?", (name,)).fetchone()
        if not row:
            return False
        
        conn.execute("DELETE FROM form_tools WHERE name = ?", (name,))
        conn.commit()
        
        # Always delete the executable file
        if row["run_file"]:
            exec_path = EXECUTABLES_DIR / row["run_file"]
            if exec_path.exists():
                exec_path.unlink()
        
        return True
    finally:
        conn.close()


def rename_tool(old_name: str, new_name: str) -> bool:
    """Rename a tool and its executable file."""
    _ensure_table()
    conn = get_connection()
    try:
        row = conn.execute("SELECT run_file, run_type FROM form_tools WHERE name = ?", (old_name,)).fetchone()
        if not row:
            return False
        
        # Check new name doesn't exist
        if conn.execute("SELECT 1 FROM form_tools WHERE name = ?", (new_name,)).fetchone():
            return False
        
        old_run_file = row["run_file"]
        ext = RUN_TYPE_EXTENSIONS.get(row["run_type"].lower(), ".py")
        new_run_file = f"{new_name.replace('-', '_')}{ext}"
        
        conn.execute(
            "UPDATE form_tools SET name = ?, run_file = ?, updated_at = CURRENT_TIMESTAMP WHERE name = ?",
            (new_name, new_run_file, old_name)
        )
        conn.commit()
        
        # Rename the executable file
        if old_run_file:
            old_path = EXECUTABLES_DIR / old_run_file
            new_path = EXECUTABLES_DIR / new_run_file
            if old_path.exists() and not new_path.exists():
                old_path.rename(new_path)
        
        return True
    finally:
        conn.close()


def get_executable_code(tool_name: str) -> Optional[str]:
    """Get the code content of a tool's executable."""
    conn = get_connection(readonly=True)
    try:
        row = conn.execute("SELECT run_file FROM form_tools WHERE name = ?", (tool_name,)).fetchone()
        if not row or not row["run_file"]:
            return None
        exec_path = EXECUTABLES_DIR / row["run_file"]
        return exec_path.read_text() if exec_path.exists() else None
    finally:
        conn.close()


def save_executable_code(tool_name: str, code: str) -> bool:
    """Save code to a tool's executable file."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT run_file FROM form_tools WHERE name = ?", (tool_name,)).fetchone()
        if not row or not row["run_file"]:
            return False
        EXECUTABLES_DIR.mkdir(parents=True, exist_ok=True)
        (EXECUTABLES_DIR / row["run_file"]).write_text(code)
        conn.execute("UPDATE form_tools SET updated_at = CURRENT_TIMESTAMP WHERE name = ?", (tool_name,))
        conn.commit()
        return True
    finally:
        conn.close()


def _create_stub_executable(name: str, run_file: str, run_type: str, actions: List[str]) -> None:
    """Create a stub executable file for a new tool."""
    EXECUTABLES_DIR.mkdir(parents=True, exist_ok=True)
    exec_path = EXECUTABLES_DIR / run_file
    if exec_path.exists():
        return
    
    if run_type in ("shell", "bash"):
        stub = _create_shell_stub(name, actions)
        exec_path.write_text(stub)
        exec_path.chmod(0o755)
    elif run_type in ("node", "javascript"):
        exec_path.write_text(_create_js_stub(name, actions))
    else:
        exec_path.write_text(_create_python_stub(name, actions))


def _create_python_stub(name: str, actions: List[str]) -> str:
    """Create Python stub code."""
    actions_str = repr(actions)
    return f'''"""
{name.replace("_", " ").title()} Tool
"""
from typing import Any, Dict

ACTIONS = {actions_str}

def run(action: str, params: Dict[str, Any]) -> Any:
    """Execute tool action."""
    if ACTIONS and action not in ACTIONS:
        raise ValueError(f"Invalid action '{{action}}'. Available: {{', '.join(ACTIONS)}}")
    
    # TODO: Implement actions
    return {{"status": "not_implemented", "action": action}}
'''


def _create_shell_stub(name: str, actions: List[str]) -> str:
    """Create shell stub code."""
    cases = "\n    ".join([f'{a})\n        echo "{a} not implemented"\n        ;;' for a in actions])
    return f'''#!/bin/bash
# {name.replace("_", " ").title()} Tool
ACTION="${{1:-help}}"
case "$ACTION" in
    {cases}
    *)
        echo "Unknown action: $ACTION"
        exit 1
        ;;
esac
'''


def _create_js_stub(name: str, actions: List[str]) -> str:
    """Create JavaScript stub code."""
    actions_json = json.dumps(actions)
    return f'''// {name.replace("_", " ").title()} Tool
const ACTIONS = {actions_json};

function run(action, params) {{
    if (!ACTIONS.includes(action)) {{
        throw new Error(`Invalid action '${{action}}'. Available: ${{ACTIONS.join(', ')}}`);
    }}
    return {{ status: "not_implemented", action }};
}}

module.exports = {{ run, ACTIONS }};
'''


def execute_tool_action(
    tool_name: str,
    action: str,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Execute a tool action with full validation."""
    start = time.time()
    params = params or {}
    now = datetime.utcnow().isoformat()
    
    tool = get_tool(tool_name)
    
    # Check tool exists
    if not tool:
        return {
            "tool_name": tool_name, "action": action, "status": "not_found",
            "output": None, "error": f"Tool '{tool_name}' not found",
            "duration_ms": 0, "timestamp": now, "success": False
        }
    
    # Check allowed
    if not tool.get("allowed"):
        return {
            "tool_name": tool_name, "action": action, "status": "denied",
            "output": None, "error": f"Tool '{tool_name}' not allowed",
            "duration_ms": 0, "timestamp": now, "success": False
        }
    
    # Check enabled
    if not tool.get("enabled"):
        return {
            "tool_name": tool_name, "action": action, "status": "disabled",
            "output": None, "error": f"Tool '{tool_name}' is disabled",
            "duration_ms": 0, "timestamp": now, "success": False
        }
    
    # Check executable exists
    if not tool.get("exists"):
        return {
            "tool_name": tool_name, "action": action, "status": "error",
            "output": None, "error": f"Executable not found: {tool.get('run_file')}",
            "duration_ms": 0, "timestamp": now, "success": False
        }
    
    # Validate action name
    valid_actions = tool.get("actions", [])
    if valid_actions and action not in valid_actions:
        return {
            "tool_name": tool_name, "action": action, "status": "invalid_action",
            "output": None, "error": f"Invalid action '{action}'. Available: {', '.join(valid_actions)}",
            "duration_ms": 0, "timestamp": now, "success": False
        }
    
    # Check environment variables
    missing = [v for v in tool.get("requires_env", []) if not os.environ.get(v)]
    if missing:
        return {
            "tool_name": tool_name, "action": action, "status": "error",
            "output": None, "error": f"Missing env vars: {', '.join(missing)}",
            "duration_ms": 0, "timestamp": now, "success": False
        }
    
    # Execute
    try:
        exec_path = Path(tool["path"])
        run_type = tool.get("run_type", "python")
        
        if run_type in ("shell", "bash"):
            import subprocess
            args = [str(exec_path), action] + [f"{k}={v}" for k, v in params.items()]
            result = subprocess.run(args, capture_output=True, text=True, timeout=30)
            output = {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
        else:
            # Python execution
            spec = importlib.util.spec_from_file_location(exec_path.stem, exec_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if not hasattr(module, "run"):
                raise AttributeError(f"Module {exec_path.name} has no 'run' function")
            output = module.run(action, params)
        
        return {
            "tool_name": tool_name, "action": action, "status": "success",
            "output": output, "error": None,
            "duration_ms": int((time.time() - start) * 1000),
            "timestamp": now, "success": True
        }
    except Exception as e:
        return {
            "tool_name": tool_name, "action": action, "status": "error",
            "output": None, "error": f"{type(e).__name__}: {e}",
            "duration_ms": int((time.time() - start) * 1000),
            "timestamp": now, "success": False
        }


def get_categories() -> List[Dict[str, str]]:
    """Get available tool categories."""
    return [
        {"value": "communication", "label": "Communication", "icon": "📧"},
        {"value": "browser", "label": "Browser", "icon": "🌐"},
        {"value": "memory", "label": "Memory", "icon": "🧠"},
        {"value": "files", "label": "Files", "icon": "📁"},
        {"value": "automation", "label": "Automation", "icon": "⚙️"},
        {"value": "internal", "label": "Internal", "icon": "🔧"},
    ]


# Legacy wrappers for api.py compatibility
def add_tool_definition(name, description, category, actions, run_file=None, requires_env=None, weight=0.5, enabled=True):
    return add_tool(name=name, description=description, category=category, actions=actions,
                    run_file=run_file, requires_env=requires_env, weight=weight, enabled=enabled)

def update_tool_definition(tool_name, description=None, category=None, actions=None, requires_env=None, weight=None, enabled=None):
    return update_tool(name=tool_name, description=description, category=category, actions=actions,
                       requires_env=requires_env, weight=weight, enabled=enabled)

def remove_tool_definition(tool_name):
    return delete_tool(tool_name)

def reload_tools_module():
    """No-op for compatibility."""
    pass
