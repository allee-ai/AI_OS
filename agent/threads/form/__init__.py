"""Form Thread - tool use, actions, and capabilities."""
from .adapter import FormThreadAdapter
from .api import router
from .tools import (
    ToolCategory,
    ToolDefinition,
    TOOLS,
    get_all_tools,
    get_tool,
    get_available_tools,
    get_tools_by_category,
    format_tools_for_prompt,
)
from .executor import (
    ExecutionStatus,
    ToolResult,
    execute_tool,
    register_handler,
    get_registered_handlers,
)
from .schema import (
    get_tools as get_tools_from_db,
    get_categories,
    add_tool_definition,
    remove_tool_definition,
    update_tool_definition,
)

__all__ = [
    "FormThreadAdapter",
    "router",
    # Tools
    "ToolCategory",
    "ToolDefinition",
    "TOOLS",
    "get_all_tools",
    "get_tool",
    "get_available_tools",
    "get_tools_by_category",
    "format_tools_for_prompt",
    # Executor
    "ExecutionStatus",
    "ToolResult",
    "execute_tool",
    "register_handler",
    "get_registered_handlers",
    # Schema
    "get_tools_from_db",
    "get_categories",
    "add_tool_definition",
    "remove_tool_definition",
    "update_tool_definition",
]
