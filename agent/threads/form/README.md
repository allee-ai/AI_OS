# Form Thread

**Cognitive Question**: WHAT can I do? WHAT am I doing?  
**Resolution Order**: 2nd (after WHO, resolve capabilities and current state)  
**Brain Mapping**: Motor Cortex + Sensory Cortex (action/perception)

---

## Purpose

Embodiment requires knowing: "What am I? What can I do? What am I currently doing?" This is the physical self — tools, actions, state. Without Form, an agent is a disembodied voice with no ability to act.

---

## Architecture

Form follows the L1/L2/L3 pattern:

```
L1: Registry   (what tools exist, metadata)
    ↓
L2: Executor   (how to run them, orchestration)
    ↓
L3: Executables (actual implementations)
```

### Directory Structure

```
form/
├── README.md           # This file
├── __init__.py
├── adapter.py          # Thread adapter (introspection, state)
├── api.py              # FastAPI routes (/api/form/*)
├── schema.py           # DB operations, tool management
├── train.py            # Learning from tool usage
└── tools/
    ├── __init__.py     # Package exports
    ├── registry.py     # L1: Tool definitions (TOOLS list)
    ├── executor.py     # L2: Execution engine
    └── executables/    # L3: Actual Python implementations
        ├── browser.py
        ├── terminal.py
        ├── file_read.py
        ├── file_write.py
        ├── memory_identity.py
        ├── memory_philosophy.py
        ├── memory_log.py
        ├── memory_linking.py
        ├── web_search.py
        ├── ask_llm.py
        ├── introspect.py
        ├── notify.py
        ├── scheduler.py
        └── feed_*.py  # External service integrations
```

---

## Key Files

| File | Layer | Purpose |
|------|-------|---------|
| `schema.py` | - | DB ops, API helpers, tool CRUD |
| `api.py` | - | FastAPI routes for frontend |
| `tools/registry.py` | L1 | Tool definitions, categories, metadata |
| `tools/executor.py` | L2 | Load and run executables |
| `tools/executables/*.py` | L3 | Actual tool implementations |

---

## Tool Definition (L1)

Each tool in `registry.py` has:

```python
ToolDefinition(
    name="browser",
    description="Kernel browser automation",
    category=ToolCategory.BROWSER,
    actions=["navigate", "click", "screenshot", "get_content"],
    run_file="browser.py",           # File in executables/
    run_type=RunType.PYTHON,         # How to execute
    requires_env=["KERNEL_API_KEY"], # Required env vars
    weight=0.8,                      # Priority (0-1)
    enabled=True,
)
```

---

## Executable Interface (L3)

Every executable must implement:

```python
def run(action: str, params: Dict[str, Any]) -> Any:
    """Execute a tool action."""
    if action == "my_action":
        return {"status": "success", ...}
    else:
        raise ValueError(f"Unknown action: {action}")
```

The executor loads the module and calls `run(action, params)`.

---

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/form/tools` | List all tools |
| GET | `/api/form/tools/{name}` | Get tool details + code |
| GET | `/api/form/tools/{name}/code` | Get executable source |
| POST | `/api/form/tools/{name}/execute` | Execute a tool action |
| POST | `/api/form/tools` | Create new tool |
| PUT | `/api/form/tools/{name}` | Update tool definition |
| DELETE | `/api/form/tools/{name}` | Delete tool |
| GET | `/api/form/categories` | List categories |

### Execute Request

```json
POST /api/form/tools/browser/execute
{
  "action": "navigate",
  "params": {"url": "https://github.com"}
}
```

### Execute Response

```json
{
  "tool_name": "browser",
  "action": "navigate",
  "status": "success",
  "output": {"url": "https://github.com", "title": "GitHub"},
  "error": null,
  "duration_ms": 1234.5,
  "timestamp": "2026-01-26T10:30:00",
  "success": true
}
```

---

## Tool Categories

| Category | Icon | Tools |
|----------|------|-------|
| **Communication** | 📧 | `feed_gmail`, `feed_slack`, `feed_sms`, `feed_discord`, `feed_telegram` |
| **Browser** | 🌐 | `browser`, `web_search` |
| **Memory** | 🧠 | `memory_identity`, `memory_philosophy`, `memory_log`, `memory_linking` |
| **Files** | 📁 | `file_read`, `file_write` |
| **Automation** | ⚙️ | `terminal`, `scheduler`, `stimuli_github`, `feed_linear`, `feed_notion` |
| **Internal** | 🔧 | `ask_llm`, `introspect`, `notify` |

---

## Context Levels

| Level | Content |
|-------|---------|
| **L1** | Tool names, current action |
| **L2** | L1 + available tools with descriptions |
| **L3** | L2 + executable source code (for editing) |

---

## Frontend

| Component | Location | Features |
|-----------|----------|----------|
| `ToolDashboard.tsx` | `frontend/src/components/` | View tools, execute actions, edit code |

**Dashboard Features**:
- 🌀 View all registered tools
- 🌀 See availability status (green/red for env vars)
- 🌀 Execute tool actions with params
- 🌀 View execution results
- 🌀 View/edit executable source code

---

## Integration Points

| Thread | Integration |
|--------|-------------|
| **Identity** | `memory_identity` tool accesses profile facts |
| **Philosophy** | `memory_philosophy` tool checks ethical constraints |
| **Log** | `memory_log` tool records/queries events |
| **Linking** | `memory_linking` tool manages concept associations |

---

## Adding a New Tool

1. **Add definition** to `tools/registry.py`:
```python
ToolDefinition(
    name="my_tool",
    description="Does something useful",
    category=ToolCategory.AUTOMATION,
    actions=["action_one", "action_two"],
    run_file="my_tool.py",
    run_type=RunType.PYTHON,
)
```

2. **Create executable** at `tools/executables/my_tool.py`:
```python
def run(action: str, params: dict) -> dict:
    if action == "action_one":
        return {"result": "did action one"}
    elif action == "action_two":
        return {"result": "did action two"}
    else:
        raise ValueError(f"Unknown action: {action}")
```

3. **Test** via API:
```bash
curl -X POST http://localhost:8000/api/form/tools/my_tool/execute \
  -H "Content-Type: application/json" \
  -d '{"action": "action_one", "params": {}}'
```

---

## Weight Semantics

Weight affects tool suggestion priority:

| Weight | Meaning |
|--------|---------|
| **0.8+** | Core tools (browser, terminal, files) |
| **0.5-0.7** | Standard tools (communication) |
| **0.3-0.5** | Specialized tools (less frequent) |

---

## Kernel Browser Integration

The `browser` tool integrates with Kernel for human-like automation:

- **Human behavior**: Mouse jerks, typing delays, typo correction
- **Persistent profiles**: Cookies/sessions saved across runs
- **Live View**: Real-time browser visibility via URL

See `kernel_service.py` in `/agent/services/` for implementation.


