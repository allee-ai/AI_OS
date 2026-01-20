"""
Form Thread Schema
==================
Database operations for tool definitions and action history.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import re

# Path to tools.py in the same directory
TOOLS_FILE = Path(__file__).parent / "tools.py"


def _parse_tools_from_file() -> List[Dict[str, Any]]:
    """Parse tool definitions from tools.py"""
    tools = []
    
    try:
        from .tools import TOOLS, check_tool_availability
        
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


def get_tools() -> List[Dict[str, Any]]:
    """Get all tool definitions."""
    return _parse_tools_from_file()


def get_tool(name: str) -> Optional[Dict[str, Any]]:
    """Get a specific tool by name."""
    tools = _parse_tools_from_file()
    for tool in tools:
        if tool["name"] == name:
            tool["code"] = get_handler_code(name)
            return tool
    return None


def get_handler_code(tool_name: str) -> Optional[str]:
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


def add_tool_definition(
    name: str,
    description: str,
    category: str,
    actions: List[str],
    requires_env: List[str] = None,
    weight: float = 0.5,
    enabled: bool = True,
) -> bool:
    """Add a new tool definition to tools.py"""
    if not TOOLS_FILE.exists():
        return False
    
    content = TOOLS_FILE.read_text()
    
    requires_env = requires_env or []
    
    new_tool = f'''    ToolDefinition(
        name="{name}",
        description="{description}",
        category=ToolCategory.{category.upper()},
        actions={actions},
        requires_env={requires_env},
        weight={weight},
        enabled={enabled},
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


def add_handler_code(tool_name: str, code: str) -> bool:
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


def remove_tool_definition(tool_name: str) -> bool:
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


def remove_handler_code(tool_name: str) -> bool:
    """Remove handler code from executor.py"""
    executor_file = TOOLS_FILE.parent / "executor.py"
    
    if not executor_file.exists():
        return False
    
    content = executor_file.read_text()
    pattern = rf'@register_handler\("{tool_name}"\)\s*\ndef\s+\w+\([^)]*\)\s*->\s*ToolResult:.*?(?=\n@register_handler|\n\ndef\s|\nclass\s|__all__)'
    new_content = re.sub(pattern, '', content, flags=re.DOTALL)
    
    if new_content != content:
        executor_file.write_text(new_content)
        return True
    
    return False


def update_tool_definition(
    tool_name: str,
    description: Optional[str] = None,
    category: Optional[str] = None,
    actions: Optional[List[str]] = None,
    requires_env: Optional[List[str]] = None,
    weight: Optional[float] = None,
    enabled: Optional[bool] = None,
) -> bool:
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
    
    if description is not None:
        tool_block = re.sub(
            r'description="[^"]*"',
            f'description="{description}"',
            tool_block
        )
    
    if category is not None:
        tool_block = re.sub(
            r'category=ToolCategory\.\w+',
            f'category=ToolCategory.{category.upper()}',
            tool_block
        )
    
    if actions is not None:
        tool_block = re.sub(
            r'actions=\[[^\]]*\]',
            f'actions={actions}',
            tool_block
        )
    
    if weight is not None:
        tool_block = re.sub(
            r'weight=[\d.]+',
            f'weight={weight}',
            tool_block
        )
    
    if enabled is not None:
        tool_block = re.sub(
            r'enabled=\w+',
            f'enabled={enabled}',
            tool_block
        )
    
    new_content = content[:match.start(2)] + tool_block + content[match.end(2):]
    TOOLS_FILE.write_text(new_content)
    
    return True


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


def reload_tools_module() -> None:
    """Reload the tools module to pick up changes."""
    import importlib
    from . import tools as tools_module
    importlib.reload(tools_module)
