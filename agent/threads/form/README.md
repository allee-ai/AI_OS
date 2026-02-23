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
    ├── registry.py     # L1: Tool definitions + safety allowlist
    ├── scanner.py      # :::execute::: block parser
    ├── executor.py     # L2: Execution engine
    └── executables/    # L3: Python implementations
        ├── file_read.py    # Read files (sandboxed)
        ├── file_write.py   # Write files (sandboxed)
        ├── terminal.py     # Shell commands (30s timeout)
        └── web_search.py   # DuckDuckGo search
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
- [ ] **Tool editor UI** — Visual tool builder for creating/editing tools
- [ ] **Tool marketplace** — Shareable tool definitions
- [ ] **Action chaining** — Multi-step tool workflows
- [ ] **Usage analytics** — Track tool success/failure rates

### Done
- [x] **Text-native tool calling** — `:::execute:::` block protocol parsed by scanner.py
- [x] **Safety allowlist** — `SAFE_ACTIONS` / `BLOCKED_ACTIONS` in registry.py with `is_action_safe()` gating
- [x] **Core executables** — file_read, file_write, terminal, web_search (sandboxed)
- [x] **Permission system** — Two-layer safety: allowlist check + DB `allowed` flag
- [x] **Tool loop in agent** — `_process_tool_calls()` with max 5 rounds, auto-re-call after execution
- [x] **Frontend rendering** — `:::execute:::` and `:::result:::` blocks render as styled cards in chat
- [x] **WebSocket tool events** — Real-time `tool_executing` / `tool_complete` messages

### Starter tasks
- [ ] Add tool search/filter in UI
- [ ] Show tool usage history
- [ ] Implement tool favorites
<!-- /ROADMAP:form -->

---

## Changelog

<!-- CHANGELOG:form -->
### 2026-02-22
- Text-native tool calling via `:::execute:::` / `:::result:::` block protocol
- Scanner (`scanner.py`): regex parser for execute blocks, ToolCall dataclass, block replacement
- Safety allowlist (`registry.py`): SAFE_ACTIONS, BLOCKED_ACTIONS, `is_action_safe()`
- Four core executables: file_read, file_write, terminal, web_search
- Agent tool loop: `_process_tool_calls()` in agent.py (max 5 rounds)
- Form adapter injects `:::execute:::` usage instructions at L2+
- Frontend ToolCallBlock / ToolResultBlock components in MessageList.tsx
- WebSocket tool event forwarding (tool_executing, tool_complete)
- 42 new tests in test_tool_calling.py (scanner, safety, executables, integration)

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
def run(action: str, params: dict) -> str:
    if action == "action_one":
        return "did action one"
    elif action == "action_two":
        return "did action two"
    else:
        return f"Unknown action: {action}"
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


