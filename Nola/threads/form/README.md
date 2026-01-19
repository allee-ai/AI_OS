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

## Implementation (canonical)

## Implementation (full)

The Kernel "living body" integration and demo summary are included here (transferred from `docs/implementation/KERNEL_INTEGRATION_SUMMARY.md` and `docs/implementation/KERNEL_DEMO_SETUP.md`). This documents how the Form thread integrates with the Kernel browser service, demo setup, and expected outputs.

# Kernel Integration Summary

## What Was Built

You now have a complete "Living Body" integration for Nola that enables browser automation with human-like behavior.

---

## 📁 Files Created/Modified

### New Files
1. **[kernel_service.py](../Nola/services/kernel_service.py)** (387 lines)
  - Core browser automation service
  - Human behavior mimicry (mouse jerks, typing delays)
  - Persistent profile management
  - Login and posting workflows

2. **[KERNEL_DEMO_SETUP.md](./KERNEL_DEMO_SETUP.md)**
  - Complete setup guide
  - Demo commands and customization
  - Troubleshooting section

3. **[WEDNESDAY_DEMO_CARD.md](./WEDNESDAY_DEMO_CARD.md)**
  - Quick reference for demo
  - Pitch script and technical talking points
  - Backup plans

4. **[test_kernel_demo.py](../tests/test_kernel_demo.py)**
  - Pre-flight test script
  - Verifies all components work

### Modified Files
1. **[agent_service.py](../Nola/services/agent_service.py)**
  - Added `_is_demo_command()` method
  - Added `_handle_demo_command()` method
  - Added `do_facebook_demo()` workflow
  - Added `_generate_post_from_identity()` content generator
  - Added helper functions for browser control

2. **[requirements.txt](../Nola/react-chat-app/backend/requirements.txt)**
  - Added `kernel>=0.1.0`
  - Added `playwright>=1.40.0`

3. **[.env.example](../.env.example)**
  - Added `KERNEL_API_KEY=` configuration

4. **[services/README.md](../Nola/services/README.md)**
  - Documented kernel_service.py
  - Added demo commands

---

## 🎯 Demo Flow

```
User types: "hey nola do the facebook thing"
        ↓
agent_service detects demo command
        ↓
Launches Kernel browser (with Live View URL)
        ↓
Navigates to login page with human-like mouse movements
        ↓
Generates post content from Nola's identity DB
        ↓
Types content with delays, typos, corrections
        ↓
Posts and returns Live View URL to user
```

---

## 🧠 Architecture Integration

```
┌─────────────────────────────────────────────────┐
│              agent_service.py (HEA Router)       │
│  • Detects demo command                           │
│  • Calls do_facebook_demo()                       │
└───────────┬─────────────────────────────────────┘
        │
        ↓
┌─────────────────────────────────────────────────┐
│       kernel_service.py (Living Body)           │
│  • launch_browser() → Kernel API                │
│  • human_mouse_movement() → Mouse jerk          │
│  • human_type() → Typing delays                 │
│  • navigate_and_login() → CDP + Playwright      │
│  • post_content() → Content posting             │
└─────────────────────────────────────────────────┘
        │
        ↓
┌─────────────────────────────────────────────────┐
│          Nola's Identity System                 │
│  • Pulls credentials from identity DB           │
│  • Generates content from personality           │
│  • Maintains persistent profile link            │
└─────────────────────────────────────────────────┘
```

---

## 💡 Key Technical Concepts

### 1. Human Behavior Mimicry

**Problem**: Bots get detected because they're too perfect.

**Solution**: Add entropy:
- **Mouse Jerks**: Random deviation mid-movement (simulates stuck ball)
- **Variable Typing**: 50-150ms delays, longer for punctuation
- **Typo Injection**: 5% chance of wrong key → backspace → correction
- **Hover Events**: Mouse lingers before clicking

### 2. Persistent Identity

**Problem**: Traditional bots lose state between runs.

**Solution**: Kernel Profiles
- Saves cookies, localStorage, session tokens
- Linked to Nola's identity via `profile_name`
- Survives 12+ hour gaps
- No "cold login" required

### 3. Unikernel Architecture

**Problem**: Docker/VMs are slow and expensive.

**Solution**: Kernel's Unikernels
- Single address space (no kernel/userspace split)
- <20ms cold starts vs 5-10 seconds for normal browsers
- Snapshot entire RAM state to disk (Intelligent Standby)
- Only billed for active compute time

### 4. Content Generation from Identity

**Problem**: Bots post generic content.

**Solution**: DB-Driven Content
```python
state = agent.get_state()
identity = state.get("IdentityConfig")
name = identity.get("name")
personality = identity.get("personality")
interests = identity.get("interests")

# Generate contextual content
content = agent.generate(prompt_with_identity)
```

---

## 🚀 Setup Checklist

Before Wednesday:

- [ ] Get Kernel API key from https://app.onkernel.com
- [ ] Add key to `.env` file: `KERNEL_API_KEY=your_key`
- [ ] Install dependencies: `pip install kernel playwright`
- [ ] Install browsers: `playwright install chromium`
- [ ] Run test script: `python tests/test_kernel_demo.py`
- [ ] Test demo command in React chat
- [ ] Verify Live View URL opens

---

## 🎊 Success Metrics

Your demo is successful if:

1. ✅ Browser launches and returns Live View URL
2. ✅ Audience sees the automation in real-time
3. ✅ At least one person asks "how does it work?"
4. ✅ Someone asks for the GitHub link
5. ✅ You make at least one technical connection

---

## 🎭 Demo Setup (Quick)

See `KERNEL_DEMO_SETUP.md` for detailed steps. In short:

```bash
# From repo root
cp .env.example .env
cd Nola/react-chat-app/backend
pip install kernel playwright
playwright install chromium
python main.py  # backend
cd ../frontend
npm install && npm run dev  # frontend
```

---

## Troubleshooting & Recovery

- If Live View doesn't load, show the terminal output and explain network issues.
- If Kernel API is down, walk through architecture diagrams and demo the identity system instead.


