# Nola — Personal AI with Hierarchical State

**A model-agnostic personal AI with thread-safe state management and metadata-driven sync.**

Traditional chatbots either forget everything or dump your entire history into every conversation. Nola uses **hierarchical state architecture** — raw data modules sync through an identity aggregator into global runtime state, with metadata controlling the flow.

## The Problem

- ChatGPT Memory: Black box, token-heavy, vendor lock-in
- RAG systems: 10,000 fragments, expensive retrieval
- Fine-tuning: Overkill for personal context

## The Solution

**Hierarchical State + Metadata Contract:**

```
Raw Data (machineID.json, user.json)
    ↓ push with metadata
Identity Aggregator (identity.json)
    ↓ push with metadata  
Global Runtime (Nola.json)
    ↓
Agent Singleton (thread-safe, auto-bootstrapped)
```

**3-Level Context System:**
- **Level 1** (Minimal): Quick identity summary → ~10 tokens, realtime responses
- **Level 2** (Moderate): Projects, schedule, relationships → ~50 tokens, default
- **Level 3** (Full): Complete history, preferences, deep context → ~200 tokens, analytical

## Architecture

```
Nola/
├── agent.py              # Thread-safe singleton with auto-bootstrap
├── contract.py           # Metadata protocol for inter-thread communication
├── Nola.json             # Global runtime state
├── identity_thread/
│   ├── identity.py       # Context aggregator (syncs submodules → Nola.json)
│   ├── identity.json     # Aggregated identity data
│   ├── machineID/
│   │   ├── machineID.py  # Machine info module
│   │   └── machineID.json
│   └── userID/
│       ├── user.py       # User info module
│       └── user.json
├── Stimuli/              # External stimuli control
│   ├── comms/            # Phone, email modules
│   └── conversations/    # Chat history storage
├── chat_demo.py          # Interactive demo
└── utils.py              # Shared helpers
```

**Key Innovation:** Metadata is the control plane, config sections are the data plane. Modules signal sync needs via `needs_sync` flag, and the Agent auto-bootstraps the full chain on first access.

## Quick Start

```bash
# Install dependencies
pip install ollama


# Run the demo
python chat_demo.py
```

Or use the Agent directly:

```python
from agent import get_agent

agent = get_agent()  # Auto-bootstraps on first call
print(agent.name)
response = agent.generate("Hello!", stimuli_type="realtime")
```

## Example Conversation

```
You: Hi Nola!
Nola: Hey there! Hope your day's off to a great start.

You: Work has me stressed
🧠 ⬆️ Escalating context: level 1 → 2
Nola: I hear you—you're juggling the Cognitive Agent Framework 
      rollout and sprint deadlines. Let's talk through it...

You: Tell me a joke
[2 turns later, context de-escalates back to level 1]
```

## Features

✅ **Thread-safe singleton** - Atomic reads/writes with Lock  
✅ **Auto-bootstrap** - `get_agent()` syncs full state chain on first call  
✅ **Metadata contract** - Modules communicate via standardized protocol  
✅ **Hierarchical sync** - Raw data → aggregator → global state  
✅ **Model-agnostic** - Works with any Ollama model  
✅ **Context levels** - 1=minimal, 2=moderate, 3=full  
✅ **User-owned data** - Your data, your machine, no vendor lock-in

## How It Works

1. **Bootstrap**: `get_agent()` triggers full sync chain (machineID → identity → Nola.json)
2. **Metadata Check**: Each module has `{metadata: {...}, data: {...}}` structure
3. **Sync Protocol**: Modules set `needs_sync: true`, parent pulls and aggregates
4. **Generation**: Agent builds system prompt from current IdentityConfig
5. **Context Control**: `stimuli_type` parameter selects depth (realtime=1, analytical=3)

## Metadata Contract

All state sections follow this structure:

```json
{
  "metadata": {
    "last_updated": "2025-12-13T10:00:00+00:00",
    "context_level": 2,
    "status": "ready",
    "needs_sync": false,
    "stale_threshold_seconds": 600,
    "source_file": "identity_thread/identity.json"
  },
  "data": {
    "machineID": { ... },
    "userID": { ... }
  }
}
```

**contract.py** provides helpers:
- `create_metadata()` - Generate standard metadata dict
- `should_sync()` - Check if module needs refresh
- `is_stale()` - Check if data exceeded age threshold
- `mark_synced()` - Clear needs_sync flag
- `request_sync()` - Signal parent to pull

## Agent API

```python
from agent import get_agent

agent = get_agent()

# Properties
agent.name                    # "Nola"
agent.system_state            # Raw JSON string

# State management
agent.get_state(reload=True)  # Get parsed dict
agent.set_state("section", {})# Update top-level section atomically
agent.reload_state()          # Force reload from disk

# Bootstrap
agent.bootstrap(context_level=2, force=True)  # Re-sync full chain

# Generation
agent.generate(user_input, stimuli_type="realtime", convo=None)
agent.introspect(prompt)      # Self-reflection without history
```

## Customization

1. **Machine identity**: Edit `identity_thread/machineID/machineID.json`
2. **User identity**: Edit `identity_thread/userID/user.json`
3. **Run sync**: `get_agent().bootstrap(force=True)` or restart Python

Each raw file uses 3-level structure:
```json
{
  "identity": {
    "level_1": "Brief summary",
    "level_2": {"key": "More detail"},
    "level_3": {"key": {"nested": "Full depth"}}
  }
}
```

## Roadmap

- [ ] Agent customization UI
- [ ] Automatic profile generation from description
- [ ] Session persistence (save/resume conversations)
- [ ] Background pulse system (autonomous reflection)
- [ ] Module training (fine-tuned specialists)
- [ ] Multi-agent orchestration
- [ ] Web UI

## Why This Matters

This is an **operating system for personal AI**, not just a chatbot. The LLM is the processor, but the agent architecture is what makes it yours.

| Feature | ChatGPT Memory | RAG Systems | Nola |
|---------|---------------|-------------|------|
| Token efficiency | ❌ Dumps everything | ⚠️ Retrieves many chunks | ✅ Dynamic depth |
| User control | ❌ Black box | ⚠️ Partial | ✅ Full transparency |
| Thread safety | ❌ N/A | ⚠️ Varies | ✅ Atomic operations |
| State hierarchy | ❌ Flat | ⚠️ Flat | ✅ Layered sync |
| Model flexibility | ❌ OpenAI only | ⚠️ Depends | ✅ Any model |

## License

MIT

---

**Built with:** Python 3.11+, Ollama, JSON-first design  
**Philosophy:** Memory > vibes. Structure > scale. User > vendor.

