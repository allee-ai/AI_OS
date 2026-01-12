# Form Thread

The Form Thread answers: **"What can I do? What's happening right now?"**

## Purpose

Form manages capabilities and current state. It tracks what tools exist (static) and what's actively happening (dynamic).

## Files

| File | Purpose |
|------|---------|
| `adapter.py` | Thread adapter with introspection |
| `tools.py` | Tool definitions and registry |
| `executor.py` | Tool execution framework |

## Quick Start

```python
from Nola.threads.form import (
    FormThreadAdapter,
    get_available_tools,
    execute_tool,
    format_tools_for_prompt,
)

# Get available tools (those with requirements met)
tools = get_available_tools()
for t in tools:
    print(f"{t.name}: {t.description}")

# Format for system prompt
prompt_text = format_tools_for_prompt(level=2)

# Execute a tool
result = execute_tool("memory_identity", "get_identity", {"level": 2})
print(result.output)

# Introspection (auto-seeds tools)
adapter = FormThreadAdapter()
facts = adapter.introspect(context_level=2)
```

## Tool Categories

| Category | Tools |
|----------|-------|
| **Communication** | stimuli_gmail, stimuli_slack, stimuli_sms, stimuli_discord, stimuli_telegram |
| **Browser** | browser, web_search |
| **Memory** | memory_identity, memory_philosophy, memory_log, memory_linking |
| **Files** | file_read, file_write |
| **Automation** | terminal, scheduler, stimuli_github, stimuli_linear, stimuli_notion |
| **Internal** | ask_llm, introspect, notify |

## Architecture: Metadata vs Data Split

Form uses a unique split:

```
metadata_json = CAPABILITIES (what CAN happen)
data_json = CURRENT STATE (what IS happening)
```

### Example: Browser Tool

```json
{
  "key": "tool_browser",
  "metadata": {
    "name": "browser",
    "description": "Kernel browser for web automation",
    "actions": ["navigate", "screenshot", "interact", "extract"],
    "requires": ["KERNEL_API_KEY"]
  },
  "data": {
    "available": true,
    "session_id": "abc123",
    "current_url": "https://github.com",
    "last_used": "2026-01-08T14:30:00Z"
  }
}
```

**Metadata** (static): What the browser can do
**Data** (dynamic): What the browser is doing now

## Modules

### `form_tool_registry`
Available tools and their capabilities:

| Tool | Capabilities |
|------|--------------|
| `browser` | Navigate, screenshot, interact, extract |
| `terminal` | Execute commands, read output |
| `files` | Read, write, search workspace |
| `search` | Web search, documentation lookup |

### `form_action_history`
Record of actions taken:

| Field | Purpose |
|-------|---------|
| `tool` | Which tool was used |
| `action` | What action was taken |
| `success` | Did it work? |
| `timestamp` | When it happened |

### `form_browser`
Current browser/Kernel state:

| Field | Purpose |
|-------|---------|
| `session_id` | Active browser session |
| `url` | Current page URL |
| `title` | Page title |
| `status` | ready, loading, error |

## Weight = Tool Priority

When multiple tools could handle a request:

- **0.9+**: Explicitly requested tools
- **0.6-0.8**: Preferred tools for this task type
- **0.3-0.5**: Fallback options

## Example Data

```sql
-- Register browser tool
INSERT INTO form_tool_registry (key, metadata_json, data_json, level, weight)
VALUES (
  'tool_browser',
  '{"name": "browser", "description": "Kernel browser", "actions": ["navigate", "screenshot"]}',
  '{"available": true, "session_id": null, "last_used": null}',
  2,
  0.7
);

-- Record an action
INSERT INTO form_action_history (key, metadata_json, data_json, level, weight)
VALUES (
  'action_20260108_143022',
  '{"type": "action", "tool": "browser", "action": "navigate"}',
  '{"success": true, "url": "https://github.com", "duration_ms": 1200}',
  3,
  0.3
);
```

## Capability Discovery

Form enables Nola to know what she can do:

```python
# "What tools do I have?"
tools = form.get_tools()

# "Can I browse the web?"
browser = form.get_tool("browser")
if browser.data["available"]:
    # Yes, browser is ready
```

## Action History for Learning

Action history enables:

1. **Error recovery**: "Last time this failed because..."
2. **Efficiency**: "I've done this before, here's how..."
3. **User patterns**: "User often asks me to do X after Y"

## API Usage

```python
from Nola.threads.form.adapter import FormThreadAdapter

adapter = FormThreadAdapter()

# Get available tools
tools = adapter.get_tools(level=2)

# Register a new tool
adapter.register_tool(
    name="email",
    description="Send and read emails",
    actions=["send", "read", "search"],
    available=False  # Not configured yet
)

# Update browser state
adapter.update_browser_state(
    url="https://github.com",
    title="GitHub",
    session_id="abc123"
)

# Record action
adapter.record_action(
    tool="browser",
    action="navigate",
    success=True,
    details="Loaded GitHub homepage"
)
```

## Form vs Other Threads

| Thread | Stores |
|--------|--------|
| **Form** | What I CAN do, what I AM doing |
| **Log** | What I DID (temporal record) |
| **Identity** | Who I AM |
| **Reflex** | Quick patterns (no tool needed) |

## Integration with Other Threads

- **Identity**: User preferences affect tool defaults
- **Log**: Actions are timestamped in Log
- **Philosophy**: Ethics constrain what actions are acceptable
- **Reflex**: Shortcuts can trigger Form actions
- **Linking Core**: Tool relevance based on current context
