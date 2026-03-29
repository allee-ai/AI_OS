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
    
    Or a protocol chain:
    {
        "protocol": "name_of_protocol",
        "steps": [
            {"tool": "file_read", "action": "read_file", "params": {...}},
            {"tool": "ask_llm", "action": "analyze", "params": {...}}
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
        elif operator == "concept_match":
            # value = list of seed concepts OR a float threshold
            # Check if the text in `actual` is conceptually related to seeds.
            try:
                from agent.threads.linking_core.schema import (
                    extract_concepts_from_text,
                    spread_activate,
                )
                if actual is None:
                    return False
                concepts = extract_concepts_from_text(str(actual))
                if not concepts:
                    return False
                seeds = value if isinstance(value, list) else [str(value)]
                scores = spread_activate(seeds, hops=1)
                # If any extracted concept appears in the activation map → match
                return any(c in scores for c in concepts)
            except Exception:
                return False
        
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
        
        # Parse tool params
        tool_params = trigger.get("tool_params") or trigger.get("tool_params_json")
        if isinstance(tool_params, str):
            try:
                tool_params = json.loads(tool_params)
            except json.JSONDecodeError:
                tool_params = {}

        response_mode = trigger.get("response_mode", "tool")

        if response_mode == "agent":
            # Escalate to the agent via the Feeds bridge
            exec_result = await _escalate_to_agent(
                trigger, event_payload, feed_name, event_type,
            )
        elif response_mode == "notify":
            # Surface a notification only – no tool execution
            exec_result = _notify_only(trigger, event_payload, feed_name, event_type)
        elif response_mode == "protocol":
            # Execute a stored task chain via the task planner
            exec_result = _execute_protocol(trigger, event_payload)
        else:
            # Default: execute tool action
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


# ---- response-mode helpers ----

async def _escalate_to_agent(
    trigger: Dict[str, Any],
    event_payload: Dict[str, Any],
    feed_name: str,
    event_type: str,
) -> Dict[str, Any]:
    """Route a matched trigger through the Feeds bridge for agent reasoning."""
    try:
        from Feeds.bridge import _handle_event  # type: ignore
        from Feeds.events import FeedEvent  # type: ignore

        event = FeedEvent(
            feed_name=feed_name,
            event_type=event_type,
            payload=event_payload,
        )
        await _handle_event(event)
        return {"success": True, "mode": "agent", "trigger": trigger.get("name")}
    except Exception as e:
        return {"success": False, "mode": "agent", "error": str(e)}


def _notify_only(
    trigger: Dict[str, Any],
    event_payload: Dict[str, Any],
    feed_name: str,
    event_type: str,
) -> Dict[str, Any]:
    """Log a notification event for the UI without executing anything."""
    try:
        from agent.threads.log.schema import log_event
        log_event(
            event_type="notification",
            data=f"[{trigger.get('name', 'trigger')}] {feed_name}/{event_type}",
            metadata={
                "trigger_id": trigger.get("id"),
                "feed_name": feed_name,
                "event_type": event_type,
                "payload_summary": str(event_payload)[:500],
            },
            source="reflex",
        )
    except Exception:
        pass
    return {"success": True, "mode": "notify"}


def _execute_protocol(
    trigger: Dict[str, Any],
    event_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Execute a protocol chain — multiple tool calls WITHOUT the LLM.

    Like a morning briefing: run 5-6 tools, collect their outputs,
    format the result. Only involves the LLM if something unexpected
    happens (API format change detected, regex mismatch, etc).

    Protocol format in tool_params_json:
    {
        "steps": [
            {"tool": "feed_gmail", "action": "read_inbox", "params": {"limit": 5}},
            {"tool": "browser",    "action": "extract",    "params": {"url": "..."}},
            {"tool": "memory",     "action": "recall",     "params": {"query": "schedule"}}
        ],
        "format": "briefing",        # "briefing" | "json" | "summary"
        "on_error": "continue",      # "continue" | "stop" | "escalate"
        "goal": "Morning briefing"   # Fallback to task planner if steps empty
    }

    If 'steps' is empty/missing, falls back to the task planner.
    """
    tool_params = trigger.get("tool_params") or {}
    if isinstance(tool_params, str):
        try:
            tool_params = json.loads(tool_params)
        except json.JSONDecodeError:
            tool_params = {}

    steps = tool_params.get("steps", [])
    on_error = tool_params.get("on_error", "continue")
    output_format = tool_params.get("format", "json")

    # Protocols MUST have explicit steps — reflexes cannot spawn thought loops
    if not steps:
        return {
            "success": False,
            "mode": "protocol",
            "error": "Protocol has no steps defined. Reflexes cannot delegate to the "
                     "task planner — define explicit tool steps instead.",
        }

    # Execute each step in sequence, collecting results
    step_results = []
    step_outputs = {}
    failed = False

    for i, step in enumerate(steps):
        step_tool = step.get("tool", "")
        step_action = step.get("action", "")
        step_params = dict(step.get("params", {}))
        step_name = step.get("name", f"step_{i}")

        # Template substitution: allow {{prev.field}} references
        step_params = _substitute_params(step_params, step_outputs, event_payload)

        try:
            result = asyncio.get_event_loop().run_until_complete(
                execute_tool_action(step_tool, step_action, step_params, event_payload)
            )
        except RuntimeError:
            # No event loop running — execute synchronously via the tool executor
            try:
                from agent.threads.form.tools.executor import execute_tool
                raw = execute_tool(step_tool, step_action, step_params)
                result = {
                    "success": raw.success,
                    "output": raw.output,
                    "error": raw.error,
                    "duration_ms": raw.duration_ms,
                }
            except Exception as e:
                result = {"success": False, "error": str(e)}

        step_results.append({
            "step": step_name,
            "tool": step_tool,
            "action": step_action,
            "success": result.get("success", False),
            "output": result.get("output"),
            "error": result.get("error"),
        })

        # Store output for referencing in later steps
        step_outputs[step_name] = result.get("output")
        step_outputs[f"step_{i}"] = result.get("output")

        if not result.get("success", False):
            failed = True
            if on_error == "stop":
                break
            elif on_error == "escalate":
                # Escalate to the agent for reasoning — NOT the task planner.
                # Reflexes cannot spawn subconscious loops.
                try:
                    loop = asyncio.get_event_loop()
                    escalation = loop.run_until_complete(_escalate_to_agent(
                        trigger, event_payload,
                        trigger.get("feed_name", "protocol"),
                        trigger.get("event_type", "protocol_error"),
                    ))
                except RuntimeError:
                    escalation = asyncio.run(_escalate_to_agent(
                        trigger, event_payload,
                        trigger.get("feed_name", "protocol"),
                        trigger.get("event_type", "protocol_error"),
                    ))
                escalation["partial_results"] = step_results
                escalation["escalated_at_step"] = i
                return escalation

    # Format the collected outputs
    formatted = _format_protocol_output(step_results, step_outputs, output_format)

    # Log the protocol run
    try:
        from agent.threads.log.schema import log_loop_run
        log_loop_run(
            loop_name=f"protocol:{trigger.get('name', 'unnamed')}",
            status="completed" if not failed else "partial",
            items_processed=len(steps),
            items_changed=len([r for r in step_results if r["success"]]),
            metadata={"trigger_id": trigger.get("id"), "on_error": on_error},
        )
    except Exception:
        pass

    return {
        "success": not failed or on_error == "continue",
        "mode": "protocol",
        "steps_completed": len([r for r in step_results if r["success"]]),
        "steps_total": len(steps),
        "results": step_results,
        "output": formatted,
    }


def _substitute_params(
    params: Dict[str, Any],
    step_outputs: Dict[str, Any],
    event_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Replace {{prev.key}} and {{event.key}} references in param values.
    Enables data flow between protocol steps without LLM involvement.
    """
    import re

    def _replace(val):
        if not isinstance(val, str):
            return val
        def _repl(m):
            ref = m.group(1)
            if ref.startswith("event."):
                path = ref[6:]
                parts = path.split(".")
                current = event_payload
                for p in parts:
                    if isinstance(current, dict) and p in current:
                        current = current[p]
                    else:
                        return m.group(0)
                return str(current)
            elif ref.startswith("prev.") or ref.startswith("step_"):
                parts = ref.split(".", 1)
                key = parts[0]
                output = step_outputs.get(key)
                if output is None:
                    return m.group(0)
                if len(parts) > 1 and isinstance(output, dict):
                    return str(output.get(parts[1], m.group(0)))
                return str(output)
            return m.group(0)
        return re.sub(r"\{\{(\w+(?:\.\w+)*)\}\}", _repl, val)

    return {k: _replace(v) for k, v in params.items()}


def _format_protocol_output(
    step_results: list,
    step_outputs: dict,
    fmt: str,
) -> Any:
    """Format protocol chain output."""
    if fmt == "json":
        return step_outputs
    elif fmt == "briefing":
        lines = []
        for r in step_results:
            status = "✓" if r["success"] else "✗"
            output_preview = str(r.get("output", ""))[:200]
            lines.append(f"[{status}] {r['tool']}/{r['action']}: {output_preview}")
        return "\n".join(lines)
    elif fmt == "summary":
        succeeded = len([r for r in step_results if r["success"]])
        return f"{succeeded}/{len(step_results)} steps completed"
    return step_outputs


# _execute_protocol_via_planner — REMOVED
# System Rule: Reflexes CANNOT spawn subconscious loops.
# Protocols must define explicit steps. If escalation is needed,
# use response_mode="agent" to route through the Feeds bridge.


__all__ = [
    'check_condition',
    'execute_tool_action',
    'execute_matching_triggers',
    'get_trigger_handler',
]
