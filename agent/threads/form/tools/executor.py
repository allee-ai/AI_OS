"""
Tool Executor
=============

Executes tools by loading and running their executable files.
Handles Python scripts, shell scripts, and module imports.

Hardened with:
- Input validation (param size/type limits)
- Output size limits (truncation)
- Retry logic with exponential backoff
- Rate limiting (per-tool cooldowns)
- Execution logging to log_llm_inference / tool_traces
"""

import os
import json
import subprocess
import importlib.util
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from collections import defaultdict

from .registry import (
    ToolDefinition,
    RunType,
    EXECUTABLES_DIR,
    get_tool,
    check_tool_availability,
)


# ── Safety limits ────────────────────────────────────────────
MAX_PARAM_SIZE = 50_000          # Max total JSON size of params (bytes)
MAX_PARAM_DEPTH = 10             # Max nesting depth in params
MAX_OUTPUT_SIZE = 500_000        # Truncate output beyond this (chars)
MAX_RETRIES = 2                  # Default retry count for transient errors
RETRY_BACKOFF_BASE = 0.5         # Seconds, doubles each retry
RATE_LIMIT_WINDOW = 1.0          # Seconds between calls to same tool


class ExecutionStatus(Enum):
    """Status of tool execution."""
    SUCCESS = "success"
    ERROR = "error"
    NOT_FOUND = "not_found"
    NOT_AVAILABLE = "not_available"
    INVALID_ACTION = "invalid_action"
    INVALID_PARAMS = "invalid_params"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    OUTPUT_TRUNCATED = "output_truncated"


@dataclass
class ToolResult:
    """Result of executing a tool."""
    tool_name: str
    action: str
    status: ExecutionStatus
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0
    retries: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "action": self.action,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "retries": self.retries,
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
    
    Hardened:
        - Input validation (size, depth)
        - Output truncation
        - Retry with exponential backoff for transient errors
        - Per-tool rate limiting
    """
    
    def __init__(self, timeout: int = 30, max_retries: int = MAX_RETRIES):
        self.timeout = timeout
        self.max_retries = max_retries
        self._loaded_modules: Dict[str, Any] = {}
        self._last_call: Dict[str, float] = defaultdict(float)
    
    def _validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate input parameters. Returns error string or None."""
        # Size check
        try:
            serialized = json.dumps(params, default=str)
        except (TypeError, ValueError) as e:
            return f"Params not serializable: {e}"
        if len(serialized) > MAX_PARAM_SIZE:
            return f"Params too large: {len(serialized)} bytes (max {MAX_PARAM_SIZE})"
        
        # Depth check
        def _check_depth(obj, depth=0):
            if depth > MAX_PARAM_DEPTH:
                return True
            if isinstance(obj, dict):
                return any(_check_depth(v, depth + 1) for v in obj.values())
            if isinstance(obj, (list, tuple)):
                return any(_check_depth(v, depth + 1) for v in obj)
            return False
        
        if _check_depth(params):
            return f"Params nested too deep (max {MAX_PARAM_DEPTH} levels)"
        return None
    
    def _truncate_output(self, output: Any) -> Any:
        """Truncate output if it exceeds size limit."""
        if output is None:
            return None
        if isinstance(output, str) and len(output) > MAX_OUTPUT_SIZE:
            return output[:MAX_OUTPUT_SIZE] + f"\n... [truncated, {len(output)} total chars]"
        if isinstance(output, (dict, list)):
            serialized = json.dumps(output, default=str)
            if len(serialized) > MAX_OUTPUT_SIZE:
                return {"_truncated": True, "preview": serialized[:MAX_OUTPUT_SIZE],
                        "original_size": len(serialized)}
        return output
    
    def _check_rate_limit(self, tool_name: str) -> bool:
        """Returns True if the tool is rate-limited (too soon to call again)."""
        now = time.time()
        elapsed = now - self._last_call[tool_name]
        return elapsed < RATE_LIMIT_WINDOW
    
    def _record_call(self, tool_name: str):
        """Record that a tool was just called."""
        self._last_call[tool_name] = time.time()
    
    def _log_execution(self, result: 'ToolResult'):
        """Log execution to tool_traces table (best-effort)."""
        try:
            from data.db import get_connection
            from contextlib import closing
            with closing(get_connection()) as conn:
                conn.execute("""
                    INSERT INTO tool_traces (tool, action, success, output, weight, duration_ms, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.tool_name, result.action,
                    1 if result.success else 0,
                    str(result.output)[:1000] if result.output else result.error,
                    0.5 if result.success else 0.8,  # errors are more interesting
                    result.duration_ms,
                    json.dumps({"status": result.status.value, "retries": result.retries}),
                ))
                conn.commit()
        except Exception:
            pass  # logging should never break execution
    
    def execute(
        self,
        tool_name: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        retries: int = None,
    ) -> 'ToolResult':
        """
        Execute a tool action with given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            action: Action to perform
            params: Parameters to pass to the action
            retries: Override max retries for this call
            
        Returns:
            ToolResult with status and output
        """
        start_time = time.time()
        params = params or {}
        max_retries = retries if retries is not None else self.max_retries
        
        # Rate limit check
        if self._check_rate_limit(tool_name):
            return ToolResult(
                tool_name=tool_name,
                action=action,
                status=ExecutionStatus.RATE_LIMITED,
                error=f"Rate limited: wait {RATE_LIMIT_WINDOW}s between calls to '{tool_name}'",
            )
        
        # Input validation
        validation_error = self._validate_params(params)
        if validation_error:
            return ToolResult(
                tool_name=tool_name,
                action=action,
                status=ExecutionStatus.INVALID_PARAMS,
                error=validation_error,
            )
        
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
        
        # Execute with retry logic
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                if tool.run_type == RunType.PYTHON:
                    output = self._execute_python(tool, action, params)
                elif tool.run_type == RunType.SHELL:
                    output = self._execute_shell(tool, action, params)
                elif tool.run_type == RunType.MODULE:
                    output = self._execute_module(tool, action, params)
                else:
                    raise ValueError(f"Unknown run type: {tool.run_type}")
                
                # Truncate large outputs
                output = self._truncate_output(output)
                truncated = isinstance(output, dict) and output.get("_truncated")
                
                duration = (time.time() - start_time) * 1000
                self._record_call(tool_name)
                
                result = ToolResult(
                    tool_name=tool_name,
                    action=action,
                    status=ExecutionStatus.OUTPUT_TRUNCATED if truncated else ExecutionStatus.SUCCESS,
                    output=output,
                    duration_ms=duration,
                    retries=attempt,
                )
                self._log_execution(result)
                return result
                
            except TimeoutError:
                duration = (time.time() - start_time) * 1000
                result = ToolResult(
                    tool_name=tool_name,
                    action=action,
                    status=ExecutionStatus.TIMEOUT,
                    error=f"Execution timed out after {self.timeout}s",
                    duration_ms=duration,
                    retries=attempt,
                )
                self._log_execution(result)
                return result  # Don't retry timeouts
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    time.sleep(RETRY_BACKOFF_BASE * (2 ** attempt))
                    continue
        
        # All retries exhausted
        duration = (time.time() - start_time) * 1000
        self._record_call(tool_name)
        result = ToolResult(
            tool_name=tool_name,
            action=action,
            status=ExecutionStatus.ERROR,
            error=last_error,
            duration_ms=duration,
            retries=max_retries,
        )
        self._log_execution(result)
        return result
    
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
