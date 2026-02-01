"""
Reflex Trigger Executor
=======================
Executes triggers when feed events are received.

This module bridges the Feeds event system with the Reflex triggers
and the Form tool executor.

Flow:
1. Feed emits event (e.g., gmail/email_received)
2. Event handler calls execute_matching_triggers()
3. For each matching trigger:
   - Check condition filter
   - Execute tool via Form executor
   - Record execution result
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from .schema import get_triggers, get_trigger, record_trigger_execution


def check_condition(condition: Optional[Dict[str, Any]], event_payload: Dict[str, Any]) -> bool:
    """
    Check if event payload matches trigger condition.
    
    Condition format:
    {
        "field": "payload.subject",
        "operator": "contains",
        "value": "urgent"
    }
    
    Or multiple conditions:
    {
        "all": [
            {"field": "payload.from", "operator": "eq", "value": "boss@work.com"},
            {"field": "payload.subject", "operator": "contains", "value": "urgent"}
        ]
    }
    """
    if not condition:
        return True  # No condition = always match
    
    def get_nested_value(obj: Dict[str, Any], path: str) -> Any:
        """Get value from nested dict using dot notation."""
        parts = path.split(".")
        current: Any = obj
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
    
    def evaluate_single(cond: Dict[str, Any]) -> bool:
        field = cond.get("field", "")
        operator = cond.get("operator", "eq")
        value = cond.get("value")
        
        actual = get_nested_value(event_payload, field)
        
        if operator == "eq":
            return actual == value
        elif operator == "neq":
            return actual != value
        elif operator == "contains":
            return str(value) in str(actual) if actual is not None and value is not None else False
        elif operator == "not_contains":
            return str(value) not in str(actual) if actual is not None and value is not None else True
        elif operator == "starts_with":
            return str(actual).startswith(str(value)) if actual is not None and value is not None else False
        elif operator == "ends_with":
            return str(actual).endswith(str(value)) if actual is not None and value is not None else False
        elif operator == "gt":
            try:
                return float(actual) > float(value) if actual is not None and value is not None else False
            except (ValueError, TypeError):
                return False
        elif operator == "lt":
            try:
                return float(actual) < float(value) if actual is not None and value is not None else False
            except (ValueError, TypeError):
                return False
        elif operator == "exists":
            return actual is not None
        elif operator == "not_exists":
            return actual is None
        elif operator == "in":
            return actual in value if isinstance(value, list) else False
        elif operator == "regex":
            import re
            if actual is None or value is None:
                return False
            return bool(re.search(str(value), str(actual)))
        
        return False
    
    # Handle composite conditions
    if "all" in condition:
        return all(evaluate_single(c) for c in condition["all"])
    elif "any" in condition:
        return any(evaluate_single(c) for c in condition["any"])
    elif "not" in condition:
        return not evaluate_single(condition["not"])
    else:
        return evaluate_single(condition)


async def execute_tool_action(
    tool_name: str,
    tool_action: str,
    tool_params: Optional[Dict[str, Any]] = None,
    event_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Execute a tool action via the Form executor.
    
    Falls back to a simulation if the executor isn't available.
    """
    merged_params = {
        **(tool_params or {}),
        "trigger_event": event_payload or {},
    }
    
    try:
        from agent.threads.form.tools.executor import ToolExecutor
        
        executor = ToolExecutor()
        result = executor.execute(
            tool_name=tool_name,
            action=tool_action,
            params=merged_params,
        )
        
        return {
            "success": result.success,
            "result": result.to_dict(),
            "output": result.output,
            "error": result.error,
        }
    except ImportError:
        # Form executor not available - return simulation
        return {
            "success": True,
            "simulated": True,
            "tool": tool_name,
            "action": tool_action,
            "params": merged_params,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def execute_matching_triggers(
    feed_name: str,
    event_type: str,
    event_payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Find and execute all triggers matching this feed event.
    
    Returns list of execution results.
    """
    # Get all enabled triggers for this feed/event
    triggers = get_triggers(
        feed_name=feed_name,
        event_type=event_type,
        enabled_only=True,
    )
    
    results = []
    
    for trigger in triggers:
        trigger_id = trigger["id"]
        trigger_name = trigger.get("name", f"trigger_{trigger_id}")
        
        # Check condition
        condition = trigger.get("condition") or trigger.get("condition_json")
        if isinstance(condition, str):
            try:
                condition = json.loads(condition)
            except json.JSONDecodeError:
                condition = None
        
        if not check_condition(condition, event_payload):
            results.append({
                "trigger_id": trigger_id,
                "trigger_name": trigger_name,
                "status": "skipped",
                "reason": "condition_not_met",
            })
            continue
        
        # Execute the tool
        tool_params = trigger.get("tool_params") or trigger.get("tool_params_json")
        if isinstance(tool_params, str):
            try:
                tool_params = json.loads(tool_params)
            except json.JSONDecodeError:
                tool_params = {}
        
        exec_result = await execute_tool_action(
            tool_name=trigger["tool_name"],
            tool_action=trigger["tool_action"],
            tool_params=tool_params,
            event_payload=event_payload,
        )
        
        # Record execution
        record_trigger_execution(
            trigger_id=trigger_id,
            success=exec_result.get("success", False),
            error=exec_result.get("error"),
        )
        
        results.append({
            "trigger_id": trigger_id,
            "trigger_name": trigger_name,
            "status": "executed" if exec_result.get("success") else "failed",
            "result": exec_result,
        })
        
        # Log the execution
        try:
            from agent.threads.log.schema import log_event
            log_event(
                event_type="trigger",
                data=f"Trigger '{trigger_name}' executed: {trigger['tool_name']}/{trigger['tool_action']}",
                metadata={
                    "trigger_id": trigger_id,
                    "feed_name": feed_name,
                    "event_type": event_type,
                    "tool_name": trigger["tool_name"],
                    "tool_action": trigger["tool_action"],
                    "success": exec_result.get("success", False),
                },
                source="reflex",
            )
        except ImportError:
            pass
    
    return results


def get_trigger_handler():
    """
    Return a sync handler function for feed events.
    
    This can be registered with the Feeds event system.
    Note: The actual execution is async but wrapped for the handler interface.
    """
    def handler(event):
        """Handle feed events and execute matching triggers."""
        import asyncio
        
        async def _run():
            return await execute_matching_triggers(
                feed_name=event.feed_name,
                event_type=event.event_type,
                event_payload=event.payload,
            )
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(_run())
            else:
                loop.run_until_complete(_run())
        except RuntimeError:
            asyncio.run(_run())
    
    return handler


__all__ = [
    'check_condition',
    'execute_tool_action',
    'execute_matching_triggers',
    'get_trigger_handler',
]
__all__ = [
    'check_condition',
    'execute_tool_action',
    'execute_matching_triggers',
    'get_trigger_handler',
]
