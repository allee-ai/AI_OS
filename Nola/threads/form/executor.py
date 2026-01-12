"""
Tool Executor
=============

Routes tool calls to their implementations.
Each tool has a handler that validates inputs and executes the action.
"""

from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import json


class ExecutionStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"
    DRAFT = "draft"  # For outputs that need human review


@dataclass
class ToolResult:
    """Result of a tool execution."""
    status: ExecutionStatus
    tool: str
    action: str
    output: Any
    error: Optional[str] = None
    draft: bool = False  # True if output needs human approval before send
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "tool": self.tool,
            "action": self.action,
            "output": self.output,
            "error": self.error,
            "draft": self.draft,
        }


# Tool handler registry
_handlers: Dict[str, Callable] = {}


def register_handler(tool_name: str):
    """Decorator to register a tool handler."""
    def decorator(func: Callable):
        _handlers[tool_name] = func
        return func
    return decorator


def execute_tool(tool: str, action: str, params: Dict[str, Any]) -> ToolResult:
    """
    Execute a tool action.
    
    Args:
        tool: Tool name (e.g., "browser", "memory_identity")
        action: Action to perform (e.g., "navigate", "get_identity")
        params: Parameters for the action
    
    Returns:
        ToolResult with status and output
    """
    handler = _handlers.get(tool)
    
    if not handler:
        return ToolResult(
            status=ExecutionStatus.ERROR,
            tool=tool,
            action=action,
            output=None,
            error=f"No handler registered for tool: {tool}",
        )
    
    try:
        result = handler(action, params)
        return result
    except Exception as e:
        return ToolResult(
            status=ExecutionStatus.ERROR,
            tool=tool,
            action=action,
            output=None,
            error=str(e),
        )


# ============================================================================
# BUILT-IN HANDLERS
# ============================================================================

@register_handler("memory_identity")
def handle_memory_identity(action: str, params: Dict[str, Any]) -> ToolResult:
    """Handle identity memory operations."""
    try:
        from Nola.threads.identity import IdentityThreadAdapter
        adapter = IdentityThreadAdapter()
        
        if action == "get_identity":
            key = params.get("key")
            level = params.get("level", 2)
            if key:
                result = adapter.get_by_key(key, level)
            else:
                result = adapter.introspect(level)
                result = result.facts
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                tool="memory_identity",
                action=action,
                output=result,
            )
        
        elif action == "list_keys":
            rows = adapter.get_module_data("identity", level=1)
            keys = [r.get("key") for r in rows]
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                tool="memory_identity",
                action=action,
                output=keys,
            )
        
        else:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                tool="memory_identity",
                action=action,
                output=None,
                error=f"Unknown action: {action}",
            )
    
    except Exception as e:
        return ToolResult(
            status=ExecutionStatus.ERROR,
            tool="memory_identity",
            action=action,
            output=None,
            error=str(e),
        )


@register_handler("memory_log")
def handle_memory_log(action: str, params: Dict[str, Any]) -> ToolResult:
    """Handle log memory operations."""
    try:
        from Nola.threads.log import LogThreadAdapter
        adapter = LogThreadAdapter()
        
        if action == "get_recent":
            limit = params.get("limit", 10)
            events = adapter.get_recent_events(limit)
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                tool="memory_log",
                action=action,
                output=events,
            )
        
        elif action == "search_logs":
            query = params.get("query", "")
            # Simple search in recent events
            events = adapter.get_recent_events(50)
            matches = [e for e in events if query.lower() in str(e).lower()]
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                tool="memory_log",
                action=action,
                output=matches[:10],
            )
        
        else:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                tool="memory_log",
                action=action,
                output=None,
                error=f"Unknown action: {action}",
            )
    
    except Exception as e:
        return ToolResult(
            status=ExecutionStatus.ERROR,
            tool="memory_log",
            action=action,
            output=None,
            error=str(e),
        )


@register_handler("introspect")
def handle_introspect(action: str, params: Dict[str, Any]) -> ToolResult:
    """Handle introspection operations."""
    try:
        from Nola.threads import get_all_threads, get_thread_names
        
        if action == "get_context":
            level = params.get("level", 2)
            threads = get_all_threads()
            context = {}
            for adapter in threads:
                try:
                    name = getattr(adapter, '_name', str(type(adapter).__name__))
                    result = adapter.introspect(level)
                    context[name] = result.facts
                except:
                    pass
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                tool="introspect",
                action=action,
                output=context,
            )
        
        elif action == "get_active_threads":
            thread_names = get_thread_names()
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                tool="introspect",
                action=action,
                output=thread_names,
            )
        
        else:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                tool="introspect",
                action=action,
                output=None,
                error=f"Unknown action: {action}",
            )
    
    except Exception as e:
        return ToolResult(
            status=ExecutionStatus.ERROR,
            tool="introspect",
            action=action,
            output=None,
            error=str(e),
        )


@register_handler("ask_llm")
def handle_ask_llm(action: str, params: Dict[str, Any]) -> ToolResult:
    """Handle LLM query operations."""
    try:
        import requests
        
        prompt = params.get("prompt", "")
        model = params.get("model", "llama3.2:3b")
        
        if not prompt:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                tool="ask_llm",
                action=action,
                output=None,
                error="No prompt provided",
            )
        
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        
        if response.ok:
            result = response.json().get("response", "")
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                tool="ask_llm",
                action=action,
                output=result,
            )
        else:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                tool="ask_llm",
                action=action,
                output=None,
                error=f"LLM request failed: {response.status_code}",
            )
    
    except Exception as e:
        return ToolResult(
            status=ExecutionStatus.ERROR,
            tool="ask_llm",
            action=action,
            output=None,
            error=str(e),
        )


@register_handler("notify")
def handle_notify(action: str, params: Dict[str, Any]) -> ToolResult:
    """Handle notification operations (currently just logs them)."""
    message = params.get("message", "")
    
    if action == "alert":
        # In the future, this could trigger actual notifications
        print(f"🔔 ALERT: {message}")
        return ToolResult(
            status=ExecutionStatus.SUCCESS,
            tool="notify",
            action=action,
            output=f"Alert sent: {message}",
        )
    
    elif action == "remind":
        when = params.get("when", "soon")
        print(f"⏰ REMINDER ({when}): {message}")
        return ToolResult(
            status=ExecutionStatus.DRAFT,  # Needs scheduling system
            tool="notify",
            action=action,
            output=f"Reminder queued: {message} ({when})",
            draft=True,
        )
    
    else:
        return ToolResult(
            status=ExecutionStatus.ERROR,
            tool="notify",
            action=action,
            output=None,
            error=f"Unknown action: {action}",
        )


def get_registered_handlers() -> Dict[str, str]:
    """Get list of registered handler names and their docstrings."""
    return {name: (func.__doc__ or "").strip() for name, func in _handlers.items()}


__all__ = [
    "ExecutionStatus",
    "ToolResult",
    "execute_tool",
    "register_handler",
    "get_registered_handlers",
]
