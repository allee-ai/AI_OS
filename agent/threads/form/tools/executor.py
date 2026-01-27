"""
Tool Executor
=============

Executes tools by loading and running their executable files.
Handles Python scripts, shell scripts, and module imports.
"""

import os
import json
import subprocess
import importlib.util
from pathlib import Path
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from .registry import (
    ToolDefinition,
    RunType,
    EXECUTABLES_DIR,
    get_tool,
    check_tool_availability,
)


class ExecutionStatus(Enum):
    """Status of tool execution."""
    SUCCESS = "success"
    ERROR = "error"
    NOT_FOUND = "not_found"
    NOT_AVAILABLE = "not_available"
    INVALID_ACTION = "invalid_action"
    TIMEOUT = "timeout"


@dataclass
class ToolResult:
    """Result of executing a tool."""
    tool_name: str
    action: str
    status: ExecutionStatus
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "action": self.action,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }
    
    @property
    def success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS


class ToolExecutor:
    """
    Executes tools based on their definitions.
    
    Supports:
        - Python scripts with run(action, params) function
        - Shell scripts with action as first argument
        - Python modules with action methods
    """
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._loaded_modules: Dict[str, Any] = {}
    
    def execute(
        self,
        tool_name: str,
        action: str,
        params: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """
        Execute a tool action with given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            action: Action to perform
            params: Parameters to pass to the action
            
        Returns:
            ToolResult with status and output
        """
        import time
        start_time = time.time()
        params = params or {}
        
        # Get tool definition
        tool = get_tool(tool_name)
        if not tool:
            return ToolResult(
                tool_name=tool_name,
                action=action,
                status=ExecutionStatus.NOT_FOUND,
                error=f"Tool '{tool_name}' not found in registry",
            )
        
        # Check availability
        if not check_tool_availability(tool):
            missing = [e for e in tool.requires_env if not os.environ.get(e)]
            return ToolResult(
                tool_name=tool_name,
                action=action,
                status=ExecutionStatus.NOT_AVAILABLE,
                error=f"Missing required env vars: {', '.join(missing)}",
            )
        
        # Validate action
        if action not in tool.actions:
            return ToolResult(
                tool_name=tool_name,
                action=action,
                status=ExecutionStatus.INVALID_ACTION,
                error=f"Invalid action '{action}'. Available: {', '.join(tool.actions)}",
            )
        
        # Check executable exists
        if not tool.exists:
            return ToolResult(
                tool_name=tool_name,
                action=action,
                status=ExecutionStatus.NOT_FOUND,
                error=f"Executable not found: {tool.run_file}",
            )
        
        # Execute based on run type
        try:
            if tool.run_type == RunType.PYTHON:
                output = self._execute_python(tool, action, params)
            elif tool.run_type == RunType.SHELL:
                output = self._execute_shell(tool, action, params)
            elif tool.run_type == RunType.MODULE:
                output = self._execute_module(tool, action, params)
            else:
                raise ValueError(f"Unknown run type: {tool.run_type}")
            
            duration = (time.time() - start_time) * 1000
            return ToolResult(
                tool_name=tool_name,
                action=action,
                status=ExecutionStatus.SUCCESS,
                output=output,
                duration_ms=duration,
            )
            
        except TimeoutError:
            duration = (time.time() - start_time) * 1000
            return ToolResult(
                tool_name=tool_name,
                action=action,
                status=ExecutionStatus.TIMEOUT,
                error=f"Execution timed out after {self.timeout}s",
                duration_ms=duration,
            )
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return ToolResult(
                tool_name=tool_name,
                action=action,
                status=ExecutionStatus.ERROR,
                error=str(e),
                duration_ms=duration,
            )
    
    def _execute_python(
        self,
        tool: ToolDefinition,
        action: str,
        params: Dict[str, Any]
    ) -> Any:
        """
        Execute a Python tool script.
        
        Expects the script to have a `run(action: str, params: dict) -> Any` function.
        """
        module = self._load_python_module(tool)
        
        if not hasattr(module, 'run'):
            raise AttributeError(f"Tool {tool.name} missing required 'run' function")
        
        return module.run(action, params)
    
    def _execute_shell(
        self,
        tool: ToolDefinition,
        action: str,
        params: Dict[str, Any]
    ) -> str:
        """
        Execute a shell script tool.
        
        Passes action as first arg, params as JSON in second arg.
        """
        script_path = tool.path
        params_json = json.dumps(params)
        
        result = subprocess.run(
            [str(script_path), action, params_json],
            capture_output=True,
            text=True,
            timeout=self.timeout,
            cwd=EXECUTABLES_DIR,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Shell script failed: {result.stderr}")
        
        return result.stdout.strip()
    
    def _execute_module(
        self,
        tool: ToolDefinition,
        action: str,
        params: Dict[str, Any]
    ) -> Any:
        """
        Execute a Python module tool.
        
        Calls the method matching the action name.
        """
        module = self._load_python_module(tool)
        
        if not hasattr(module, action):
            raise AttributeError(f"Tool {tool.name} has no action method '{action}'")
        
        action_func = getattr(module, action)
        return action_func(**params)
    
    def _load_python_module(self, tool: ToolDefinition) -> Any:
        """Load a Python module from file path, with caching."""
        if tool.name in self._loaded_modules:
            return self._loaded_modules[tool.name]
        
        spec = importlib.util.spec_from_file_location(
            f"tool_{tool.name}",
            tool.path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        self._loaded_modules[tool.name] = module
        return module
    
    def reload_tool(self, tool_name: str) -> bool:
        """Force reload a tool module."""
        if tool_name in self._loaded_modules:
            del self._loaded_modules[tool_name]
        tool = get_tool(tool_name)
        if tool and tool.exists:
            self._load_python_module(tool)
            return True
        return False


# Global executor instance
_executor: Optional[ToolExecutor] = None


def get_executor() -> ToolExecutor:
    """Get the global tool executor instance."""
    global _executor
    if _executor is None:
        _executor = ToolExecutor()
    return _executor


def execute_tool(
    tool_name: str,
    action: str,
    params: Optional[Dict[str, Any]] = None
) -> ToolResult:
    """
    Convenience function to execute a tool.
    
    Usage:
        result = execute_tool("browser", "navigate", {"url": "https://example.com"})
        if result.success:
            print(result.output)
        else:
            print(f"Error: {result.error}")
    """
    return get_executor().execute(tool_name, action, params)


# Custom handler registry for backwards compat
_CUSTOM_HANDLERS: Dict[str, Any] = {}

def register_handler(tool_name: str, handler: Any) -> None:
    """Register a custom handler for a tool."""
    _CUSTOM_HANDLERS[tool_name] = handler

def get_registered_handlers() -> Dict[str, Any]:
    """Get all registered custom handlers."""
    return dict(_CUSTOM_HANDLERS)


__all__ = [
    "ExecutionStatus",
    "ToolResult",
    "ToolExecutor",
    "get_executor",
    "execute_tool",
    "register_handler",
    "get_registered_handlers",
]
