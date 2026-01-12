"""
Form Thread API - Tool Dashboard
================================

CRUD operations for tools in the Form thread.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import re

router = APIRouter()

# Path to tools.py - go up from backend/api to AI_OS/Nola/threads/form
TOOLS_FILE = Path(__file__).resolve().parent.parent.parent.parent / "threads" / "form" / "tools.py"


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


def _parse_tools_from_file() -> List[Dict[str, Any]]:
    """Parse tool definitions from tools.py"""
    tools = []
    
    try:
        from Nola.threads.form.tools import TOOLS, check_tool_availability
        
        for tool in TOOLS:
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "category": tool.category.value,
                "actions": tool.actions,
                "requires_env": tool.requires_env,
                "weight": tool.weight,
                "enabled": tool.enabled,
                "available": check_tool_availability(tool),
            })
    except Exception as e:
        print(f"Error parsing tools: {e}")
    
    return tools


def _get_handler_code(tool_name: str) -> Optional[str]:
    """Get the handler code for a tool from executor.py"""
    executor_file = TOOLS_FILE.parent / "executor.py"
    
    if not executor_file.exists():
        return None
    
    content = executor_file.read_text()
    
    # Find the handler function - match from decorator to the next decorator or end
    pattern = rf'(@register_handler\("{re.escape(tool_name)}"\)\s*def\s+\w+\([^)]*\)\s*->\s*ToolResult:.*?)(?=\n@register_handler|\n\ndef\s+[a-z]|\nclass\s|\n__all__|$)'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        return match.group(1).strip()
    
    return None


def _add_tool_definition(tool: ToolCreate) -> bool:
    """Add a new tool definition to tools.py"""
    if not TOOLS_FILE.exists():
        return False
    
    content = TOOLS_FILE.read_text()
    
    # Find the TOOLS list and add the new tool
    # Look for the closing bracket of TOOLS = [...]
    
    new_tool = f'''    ToolDefinition(
        name="{tool.name}",
        description="{tool.description}",
        category=ToolCategory.{tool.category.upper()},
        actions={tool.actions},
        requires_env={tool.requires_env},
        weight={tool.weight},
        enabled={tool.enabled},
    ),
'''
    
    # Find the last tool in the list (before the closing ])
    pattern = r'(TOOLS:\s*List\[ToolDefinition\]\s*=\s*\[.*?)(]\s*\n)'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        # Insert before the closing ]
        new_content = content[:match.end(1)] + new_tool + content[match.start(2):]
        TOOLS_FILE.write_text(new_content)
        return True
    
    return False


def _add_handler_code(tool_name: str, code: str) -> bool:
    """Add handler code to executor.py"""
    executor_file = TOOLS_FILE.parent / "executor.py"
    
    if not executor_file.exists():
        return False
    
    content = executor_file.read_text()
    
    # Add before __all__
    if "__all__" in content:
        insert_pos = content.find("__all__")
        new_content = content[:insert_pos] + "\n" + code + "\n\n" + content[insert_pos:]
        executor_file.write_text(new_content)
        return True
    else:
        # Append to end
        content += "\n\n" + code
        executor_file.write_text(content)
        return True


def _remove_tool_definition(tool_name: str) -> bool:
    """Remove a tool definition from tools.py"""
    if not TOOLS_FILE.exists():
        return False
    
    content = TOOLS_FILE.read_text()
    
    # Find and remove the ToolDefinition block for this tool
    pattern = rf'    ToolDefinition\(\s*name="{tool_name}".*?\),\n'
    new_content = re.sub(pattern, '', content, flags=re.DOTALL)
    
    if new_content != content:
        TOOLS_FILE.write_text(new_content)
        return True
    
    return False


def _update_tool_definition(tool_name: str, updates: ToolUpdate) -> bool:
    """Update a tool definition in tools.py"""
    if not TOOLS_FILE.exists():
        return False
    
    content = TOOLS_FILE.read_text()
    
    # Find the tool definition block
    pattern = rf'(    ToolDefinition\(\s*name="{tool_name}",)(.*?)(    \),)'
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        return False
    
    # Parse existing values and update
    tool_block = match.group(2)
    
    if updates.description is not None:
        tool_block = re.sub(
            r'description="[^"]*"',
            f'description="{updates.description}"',
            tool_block
        )
    
    if updates.category is not None:
        tool_block = re.sub(
            r'category=ToolCategory\.\w+',
            f'category=ToolCategory.{updates.category.upper()}',
            tool_block
        )
    
    if updates.actions is not None:
        tool_block = re.sub(
            r'actions=\[[^\]]*\]',
            f'actions={updates.actions}',
            tool_block
        )
    
    if updates.weight is not None:
        tool_block = re.sub(
            r'weight=[\d.]+',
            f'weight={updates.weight}',
            tool_block
        )
    
    if updates.enabled is not None:
        tool_block = re.sub(
            r'enabled=\w+',
            f'enabled={updates.enabled}',
            tool_block
        )
    
    new_content = content[:match.start(2)] + tool_block + content[match.end(2):]
    TOOLS_FILE.write_text(new_content)
    
    return True


# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/tools")
async def list_tools():
    """Get all tool definitions."""
    tools = _parse_tools_from_file()
    return tools


@router.get("/tools/{name}")
async def get_tool(name: str):
    """Get a specific tool with its handler code."""
    tools = _parse_tools_from_file()
    
    for tool in tools:
        if tool["name"] == name:
            tool["code"] = _get_handler_code(name)
            return tool
    
    raise HTTPException(status_code=404, detail=f"Tool not found: {name}")


@router.post("/tools")
async def create_tool(tool: ToolCreate):
    """Create a new tool definition."""
    # Check if tool already exists
    existing = _parse_tools_from_file()
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
    if not _add_tool_definition(tool):
        raise HTTPException(status_code=500, detail="Failed to add tool definition")
    
    # Add handler code if provided
    if tool.code:
        if not _add_handler_code(tool.name, tool.code):
            raise HTTPException(status_code=500, detail="Failed to add handler code")
    
    # Reload the module to pick up changes
    import importlib
    import Nola.threads.form.tools as tools_module
    importlib.reload(tools_module)
    
    return {"status": "created", "name": tool.name}


@router.put("/tools/{name}")
async def update_tool(name: str, updates: ToolUpdate):
    """Update a tool definition."""
    tools = _parse_tools_from_file()
    
    if not any(t["name"] == name for t in tools):
        raise HTTPException(status_code=404, detail=f"Tool not found: {name}")
    
    if not _update_tool_definition(name, updates):
        raise HTTPException(status_code=500, detail="Failed to update tool")
    
    # Update handler code if provided
    if updates.code:
        # Remove old handler and add new one
        executor_file = TOOLS_FILE.parent / "executor.py"
        if executor_file.exists():
            content = executor_file.read_text()
            # Remove old handler
            pattern = rf'@register_handler\("{name}"\)\s*\ndef\s+\w+\([^)]*\)\s*->\s*ToolResult:.*?(?=\n@register_handler|\n\ndef\s|\nclass\s|__all__)'
            content = re.sub(pattern, '', content, flags=re.DOTALL)
            executor_file.write_text(content)
            # Add new handler
            _add_handler_code(name, updates.code)
    
    return {"status": "updated", "name": name}


@router.delete("/tools/{name}")
async def delete_tool(name: str):
    """Delete a tool definition."""
    tools = _parse_tools_from_file()
    
    if not any(t["name"] == name for t in tools):
        raise HTTPException(status_code=404, detail=f"Tool not found: {name}")
    
    if not _remove_tool_definition(name):
        raise HTTPException(status_code=500, detail="Failed to delete tool")
    
    # Also remove handler if exists
    executor_file = TOOLS_FILE.parent / "executor.py"
    if executor_file.exists():
        content = executor_file.read_text()
        pattern = rf'@register_handler\("{name}"\)\s*\ndef\s+\w+\([^)]*\)\s*->\s*ToolResult:.*?(?=\n@register_handler|\n\ndef\s|\nclass\s|__all__)'
        new_content = re.sub(pattern, '', content, flags=re.DOTALL)
        if new_content != content:
            executor_file.write_text(new_content)
    
    return {"status": "deleted", "name": name}


@router.get("/categories")
async def list_categories():
    """Get available tool categories."""
    return [
        {"value": "communication", "label": "Communication", "icon": "📧"},
        {"value": "browser", "label": "Browser", "icon": "🌐"},
        {"value": "memory", "label": "Memory", "icon": "🧠"},
        {"value": "files", "label": "Files", "icon": "📁"},
        {"value": "automation", "label": "Automation", "icon": "⚙️"},
        {"value": "internal", "label": "Internal", "icon": "🔧"},
    ]


@router.post("/tools/{name}/test")
async def test_tool(name: str, action: str = "get_identity", params: Dict[str, Any] = None):
    """Test a tool execution."""
    try:
        from Nola.threads.form import execute_tool
        
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
