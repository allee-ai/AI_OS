# Form Thread

**Cognitive Question**: WHAT can I do? WHAT am I doing?  
**Resolution Order**: 2nd (after WHO, resolve capabilities and current state)  
**Brain Mapping**: Motor Cortex + Sensory Cortex (action/perception)

---

## Description

Embodiment requires knowing: "What am I? What can I do? What am I currently doing?" This is the physical self — tools, actions, state. Without Form, an agent is a disembodied voice with no ability to act.

---

## Architecture

<!-- ARCHITECTURE:form -->
Form follows the L1/L2/L3 pattern:

```
L1: Registry   (what tools exist, metadata)
L2: Executor   (how to run them, orchestration)
L3: Executables (actual implementations)
```

### Directory Structure

```
form/
├── adapter.py      # Thread adapter (introspection, state)
├── api.py          # FastAPI routes (/api/form/*)
├── schema.py       # DB operations, tool management
└── tools/
    ├── registry.py     # L1: Tool definitions
    ├── executor.py     # L2: Execution engine
    └── executables/    # L3: Python implementations
```

### Tool Definition

```python
ToolDefinition(
    name="browser",
    description="Kernel browser automation",
    category=ToolCategory.BROWSER,
    actions=["navigate", "click", "screenshot"],
    run_file="browser.py",
    requires_env=["KERNEL_API_KEY"],
)
```

### Context Levels

| Level | Content |
|-------|---------|
| **L1** | Tool names, current action |
| **L2** | L1 + available tools with descriptions |
| **L3** | L2 + executable source code |

### Tool Categories

| Category | Tools |
|----------|-------|
| Communication | gmail, slack, sms, discord |
| Browser | browser, web_search |
| Memory | identity, philosophy, log, linking |
| Files | file_read, file_write |
| Automation | terminal, scheduler |
<!-- /ARCHITECTURE:form -->

---

## Roadmap

<!-- ROADMAP:form -->
### Ready for contributors
- [ ] **Tool marketplace** — Shareable tool definitions
- [ ] **Action chaining** — Multi-step tool workflows
- [ ] **Permission system** — User approval for sensitive actions
- [ ] **Usage analytics** — Track tool success/failure rates

### Starter tasks
- [ ] Add tool search/filter in UI
- [ ] Show tool usage history
- [ ] Implement tool favorites
<!-- /ROADMAP:form -->

---

## Changelog

<!-- CHANGELOG:form -->
### 2026-02-01
- Fixed ToolDashboard.css to use theme CSS variables consistently
- Removed hardcoded hex color fallbacks
- Added ThemedSelect component for styled dropdowns
- Dashboard now properly supports light/dark theme switching

### 2026-01-27
- L1/L2/L3 tool architecture
- Executable hot-reload support

### 2026-01-20
- Tool registry with categories
- API execution with result tracking
<!-- /CHANGELOG:form -->
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


