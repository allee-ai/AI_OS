"""
Form Thread API
===============
CRUD endpoints for tools in the Form thread.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from .schema import (
    get_tools, get_tool, get_handler_code,
    add_tool_definition, add_handler_code,
    remove_tool_definition, remove_handler_code,
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
    requires_env: List[str] = []
    weight: float = 0.5
    enabled: bool = True
    code: Optional[str] = None  # Python code for the handler


class ToolUpdate(BaseModel):
    description: Optional[str] = None
    category: Optional[str] = None
    actions: Optional[List[str]] = None
    requires_env: Optional[List[str]] = None
    weight: Optional[float] = None
    enabled: Optional[bool] = None
    code: Optional[str] = None


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
    
    # Add tool definition
    if not add_tool_definition(
        name=tool.name,
        description=tool.description,
        category=tool.category,
        actions=tool.actions,
        requires_env=tool.requires_env,
        weight=tool.weight,
        enabled=tool.enabled,
    ):
        raise HTTPException(status_code=500, detail="Failed to add tool definition")
    
    # Add handler code if provided
    if tool.code:
        if not add_handler_code(tool.name, tool.code):
            raise HTTPException(status_code=500, detail="Failed to add handler code")
    
    # Reload the module to pick up changes
    reload_tools_module()
    
    return {"status": "created", "name": tool.name}


@router.put("/tools/{name}")
async def update_tool(name: str, updates: ToolUpdate):
    """Update a tool definition."""
    tools = get_tools()
    
    if not any(t["name"] == name for t in tools):
        raise HTTPException(status_code=404, detail=f"Tool not found: {name}")
    
    if not update_tool_definition(
        tool_name=name,
        description=updates.description,
        category=updates.category,
        actions=updates.actions,
        requires_env=updates.requires_env,
        weight=updates.weight,
        enabled=updates.enabled,
    ):
        raise HTTPException(status_code=500, detail="Failed to update tool")
    
    # Update handler code if provided
    if updates.code:
        remove_handler_code(name)
        add_handler_code(name, updates.code)
    
    return {"status": "updated", "name": name}


@router.delete("/tools/{name}")
async def delete_tool(name: str):
    """Delete a tool definition."""
    tools = get_tools()
    
    if not any(t["name"] == name for t in tools):
        raise HTTPException(status_code=404, detail=f"Tool not found: {name}")
    
    if not remove_tool_definition(name):
        raise HTTPException(status_code=500, detail="Failed to delete tool")
    
    # Also remove handler if exists
    remove_handler_code(name)
    
    return {"status": "deleted", "name": name}


@router.get("/categories")
async def list_categories():
    """Get available tool categories."""
    return get_categories()


@router.post("/tools/{name}/test")
async def test_tool(name: str, action: str = "get_identity", params: Dict[str, Any] = None):
    """Test a tool execution."""
    try:
        from . import execute_tool
        
        result = execute_tool(name, action, params or {})
        return {
            "status": result.status.value,
            "output": result.output,
            "error": result.error,
        }
    except Exception as e:
        return {
            "status": "error",
            "output": None,
            "error": str(e),
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
