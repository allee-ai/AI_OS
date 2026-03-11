"""
Form Thread API
===============
CRUD endpoints for tools in the Form thread.
Supports L1/L2/L3 pattern: registry → executor → executables
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from .schema import (
    get_tools, get_tool, get_executable_code, save_executable_code,
    add_tool, add_tool_definition, execute_tool_action,
    remove_tool_definition, rename_tool, update_tool as schema_update_tool,
    update_tool_definition, get_categories, reload_tools_module,
)

router = APIRouter(prefix="/api/form", tags=["form"])


# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────

class ToolCreate(BaseModel):
    name: str
    description: str
    category: str  # communication, browser, memory, files, automation, internal
    actions: List[str]
    run_file: Optional[str] = None  # e.g., "my_tool.py"
    run_type: str = "python"  # python, shell, bash, node, javascript, typescript
    requires_env: List[str] = []
    weight: float = 0.5
    enabled: bool = True
    allowed: bool = True
    code: Optional[str] = None  # Code for the executable


class ToolUpdate(BaseModel):
    description: Optional[str] = None
    category: Optional[str] = None
    actions: Optional[List[str]] = None
    requires_env: Optional[List[str]] = None
    weight: Optional[float] = None
    enabled: Optional[bool] = None
    allowed: Optional[bool] = None
    code: Optional[str] = None


class ToolRename(BaseModel):
    new_name: str


class ExecuteRequest(BaseModel):
    action: str
    params: Optional[Dict[str, Any]] = None


# ─────────────────────────────────────────────────────────────
# Tool Endpoints
# ─────────────────────────────────────────────────────────────

@router.get("/tools")
async def list_tools():
    """Get all tool definitions."""
    return get_tools()


@router.get("/tools/{name}")
async def get_tool_by_name(name: str):
    """Get a specific tool with its handler code."""
    tool = get_tool(name)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool not found: {name}")
    return tool


@router.post("/tools")
async def create_tool(tool: ToolCreate):
    """Create a new tool definition."""
    # Check if tool already exists
    existing = get_tools()
    if any(t["name"] == tool.name for t in existing):
        raise HTTPException(status_code=400, detail=f"Tool already exists: {tool.name}")
    
    # Validate category
    valid_categories = ["communication", "browser", "memory", "files", "automation", "internal"]
    if tool.category.lower() not in valid_categories:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid category. Must be one of: {valid_categories}"
        )
    
    # Add tool using the new add_tool function
    if not add_tool(
        name=tool.name,
        description=tool.description,
        category=tool.category,
        actions=tool.actions,
        run_file=tool.run_file,
        run_type=tool.run_type,
        requires_env=tool.requires_env,
        weight=tool.weight,
        enabled=tool.enabled,
        allowed=tool.allowed,
        code=tool.code,
    ):
        raise HTTPException(status_code=500, detail="Failed to add tool definition")
    
    return {"status": "created", "name": tool.name}


@router.put("/tools/{name}")
async def update_tool(name: str, updates: ToolUpdate):
    """Update a tool definition."""
    tools = get_tools()
    
    if not any(t["name"] == name for t in tools):
        raise HTTPException(status_code=404, detail=f"Tool not found: {name}")
    
    if not schema_update_tool(
        name=name,
        description=updates.description,
        category=updates.category,
        actions=updates.actions,
        requires_env=updates.requires_env,
        weight=updates.weight,
        enabled=updates.enabled,
        allowed=updates.allowed,
        code=updates.code,
    ):
        raise HTTPException(status_code=500, detail="Failed to update tool")
    
    return {"status": "updated", "name": name}


@router.delete("/tools/{name}")
async def delete_tool(name: str):
    """Delete a tool definition."""
    tools = get_tools()
    
    if not any(t["name"] == name for t in tools):
        raise HTTPException(status_code=404, detail=f"Tool not found: {name}")
    
    if not remove_tool_definition(name):
        raise HTTPException(status_code=500, detail="Failed to delete tool")
    
    return {"status": "deleted", "name": name}


@router.post("/tools/{name}/rename")
async def rename_tool_endpoint(name: str, data: ToolRename):
    """Rename a tool and its executable file."""
    tools = get_tools()
    
    if not any(t["name"] == name for t in tools):
        raise HTTPException(status_code=404, detail=f"Tool not found: {name}")
    
    if any(t["name"] == data.new_name for t in tools):
        raise HTTPException(status_code=400, detail=f"Tool already exists: {data.new_name}")
    
    if not rename_tool(name, data.new_name):
        raise HTTPException(status_code=500, detail="Failed to rename tool")
    
    return {"status": "renamed", "old_name": name, "new_name": data.new_name}


@router.get("/tools/{name}/code")
async def get_tool_code(name: str):
    """Get the executable code for a tool (L3 - full implementation)."""
    code = get_executable_code(name)
    if code is None:
        raise HTTPException(status_code=404, detail=f"No executable found for: {name}")
    return {"name": name, "code": code}


@router.put("/tools/{name}/code")
async def update_tool_code(name: str, code: str):
    """Update the executable code for a tool."""
    if not save_executable_code(name, code):
        raise HTTPException(status_code=500, detail="Failed to save executable code")
    return {"status": "updated", "name": name}


@router.post("/tools/{name}/execute")
async def execute_tool(name: str, request: ExecuteRequest):
    """
    Execute a tool action in a sandboxed environment.
    
    This is the "env" - run a tool and see its output.
    """
    result = execute_tool_action(name, request.action, request.params)
    return result


@router.get("/categories")
async def list_categories():
    """Get available tool categories."""
    return get_categories()


# ─────────────────────────────────────────────────────────────
# Tool Traces — Weighted execution history visible in STATE
# ─────────────────────────────────────────────────────────────

@router.get("/traces")
async def list_tool_traces(limit: int = 50, min_weight: float = 0.0):
    """Get recent tool execution traces, ordered by weight."""
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute(
            """SELECT id, tool, action, success, output, weight,
                      duration_ms, session_id, metadata_json, created_at
               FROM tool_traces
               WHERE weight >= ?
               ORDER BY created_at DESC LIMIT ?""",
            (min_weight, limit)
        ).fetchall()
        return [{"id": r["id"], "tool": r["tool"], "action": r["action"],
                 "success": bool(r["success"]), "output": r["output"],
                 "weight": r["weight"], "duration_ms": r["duration_ms"],
                 "session_id": r["session_id"], "created_at": r["created_at"]}
                for r in rows]


@router.get("/traces/{trace_id}")
async def get_tool_trace(trace_id: int):
    """Get a single tool trace by ID."""
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection(readonly=True)) as conn:
        row = conn.execute(
            "SELECT * FROM tool_traces WHERE id = ?", (trace_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Trace not found: {trace_id}")
        return dict(row)


@router.get("/traces/stats")
async def get_trace_stats():
    """Get aggregate stats for tool traces."""
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection(readonly=True)) as conn:
        total = conn.execute("SELECT COUNT(*) FROM tool_traces").fetchone()[0]
        avg_weight = conn.execute("SELECT AVG(weight) FROM tool_traces").fetchone()[0] or 0
        by_tool = conn.execute(
            """SELECT tool, COUNT(*) as count, AVG(weight) as avg_weight,
                      SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes
               FROM tool_traces GROUP BY tool ORDER BY count DESC"""
        ).fetchall()
        return {
            "total": total,
            "avg_weight": round(avg_weight, 3),
            "by_tool": [{"tool": r["tool"], "count": r["count"],
                         "avg_weight": round(r["avg_weight"], 3),
                         "success_rate": round(r["successes"] / r["count"], 2) if r["count"] else 0}
                        for r in by_tool]
        }


@router.post("/tools/{name}/test")
async def test_tool(name: str, action: str = "get_identity", params: Dict[str, Any] = None):
    """Test a tool execution (legacy endpoint, use /execute instead)."""
    result = execute_tool_action(name, action, params)
    return {
        "status": result["status"],
        "output": result["output"],
        "error": result["error"],
    }


# ─────────────────────────────────────────────────────────────
# Introspection (Thread owns its state block)
# ─────────────────────────────────────────────────────────────

@router.get("/introspect")
async def introspect_form(level: int = 2, query: Optional[str] = None):
    """
    Get form thread's contribution to STATE block.
    
    Each thread is responsible for building its own state.
    If query provided, filters to relevant tools via LinkingCore.
    """
    from .adapter import FormThreadAdapter
    adapter = FormThreadAdapter()
    result = adapter.introspect(context_level=level, query=query)
    return result.to_dict()


@router.get("/health")
async def get_form_health():
    """Get form thread health status."""
    from .adapter import FormThreadAdapter
    adapter = FormThreadAdapter()
    return adapter.health().to_dict()


@router.get("/table")
async def get_form_table():
    """
    Get form/tools data in table format for UI display.
    
    Returns list of tools with their configuration matching frontend expectations.
    """
    tools = get_tools()
    return {
        "columns": ["name", "category", "description", "actions", "available", "weight"],
        "rows": tools,
        "row_count": len(tools)
    }
