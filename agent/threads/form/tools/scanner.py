"""
Tool Call Scanner
=================

Scans model output for :::execute::: blocks and replaces them
with :::result::: blocks after execution.

Fits into existing chat renderer tag scanning — the frontend
picks up :::result::: blocks the same way it handles code blocks.

The model writes its intention in natural language, we parse it.
This is intentionally NOT JSON — LLMs are text completers, not
function callers. The execute block is a text-native protocol.
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """A parsed tool call from model output."""
    tool: str
    action: str
    params: Dict[str, str] = field(default_factory=dict)
    raw_block: str = ""
    start_pos: int = 0
    end_pos: int = 0


# Match :::execute ... ::: blocks (lazy, dotall)
EXECUTE_PATTERN = re.compile(
    r':::execute\s*\n(.*?):::',
    re.DOTALL
)


def scan_for_tool_calls(text: str) -> List[ToolCall]:
    """Scan model output for :::execute::: blocks.
    
    Returns list of ToolCall objects in order of appearance.
    Partial or malformed blocks are skipped gracefully.
    """
    calls = []
    
    for match in EXECUTE_PATTERN.finditer(text):
        raw_block = match.group(0)
        body = match.group(1).strip()
        
        parsed = _parse_block_body(body)
        if parsed is None:
            continue
        
        tool_name, action_name, params = parsed
        
        calls.append(ToolCall(
            tool=tool_name,
            action=action_name,
            params=params,
            raw_block=raw_block,
            start_pos=match.start(),
            end_pos=match.end()
        ))
    
    return calls


def _parse_block_body(body: str) -> Optional[Tuple[str, str, Dict[str, str]]]:
    """Parse key: value lines from an execute block body.
    
    Required: tool, action
    Everything else becomes a param.
    
    Example:
        tool: file_read
        action: read_file
        path: /README.md
    
    Returns (tool, action, params) or None if malformed.
    """
    lines = body.strip().split('\n')
    fields: Dict[str, str] = {}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        colon_pos = line.find(':')
        if colon_pos == -1:
            continue
        
        key = line[:colon_pos].strip().lower()
        value = line[colon_pos + 1:].strip()
        fields[key] = value
    
    tool = fields.pop('tool', None)
    action = fields.pop('action', None)
    
    if not tool or not action:
        return None
    
    return (tool, action, fields)


def replace_tool_calls_with_results(
    text: str,
    calls: List[ToolCall],
    results: List[str]
) -> str:
    """Replace :::execute::: blocks with :::result::: blocks.
    
    Preserves the model's text before/after/between tool calls.
    Results are formatted as :::result::: blocks so the frontend
    renderer and the model both see what happened.
    """
    if not calls:
        return text
    
    parts = []
    last_end = 0
    
    for call, result in zip(calls, results):
        # Text before this tool call
        parts.append(text[last_end:call.start_pos])
        # Replace with result block
        parts.append(f":::result tool={call.tool} action={call.action}\n{result}\n:::")
        last_end = call.end_pos
    
    # Text after last tool call
    parts.append(text[last_end:])
    
    return ''.join(parts)


__all__ = [
    "ToolCall",
    "scan_for_tool_calls",
    "replace_tool_calls_with_results",
]
