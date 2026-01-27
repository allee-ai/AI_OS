"""
Tools Package
=============

Tool registry, executor, and executable tools for Agent.

Structure:
    tools/
        __init__.py      - Package exports
        registry.py      - Tool definitions and registration
        executor.py      - Tool execution engine
        executables/     - Actual tool implementations
"""

from .registry import (
    ToolCategory,
    ToolDefinition,
    TOOLS,
    get_all_tools,
    get_tools_by_category,
    get_tool,
    get_enabled_tools,
    get_available_tools,
    check_tool_availability,
    format_tools_for_prompt,
)

from .executor import (
    ToolExecutor,
    ToolResult,
    execute_tool,
)

__all__ = [
    # Registry
    "ToolCategory",
    "ToolDefinition",
    "TOOLS",
    "get_all_tools",
    "get_tools_by_category",
    "get_tool",
    "get_enabled_tools",
    "get_available_tools",
    "check_tool_availability",
    "format_tools_for_prompt",
    # Executor
    "ToolExecutor",
    "ToolResult",
    "execute_tool",
]
