# Personal AI with Layered Memory

**A model-agnostic personal AI that learns you efficiently.**

Traditional chatbots either forget everything or dump your entire history into every conversation. This agent uses **layered context loading** - starting minimal and dynamically escalating depth only when the conversation demands it.

## The Problem

- ChatGPT Memory: Black box, token-heavy, vendor lock-in
- RAG systems: 10,000 fragments, expensive retrieval
- Fine-tuning: Overkill for personal context

## The Solution

**3-Level Dynamic Context System:**
- **Level 1** (Basic): "Alex works at TechCorp" → ~10 tokens
- **Level 2** (Detailed): Active projects, schedules, relationships → ~50 tokens  
- **Level 3** (Comprehensive): Full career history, team names, therapy notes → ~200 tokens

The agent automatically escalates when you mention work/personal topics, then de-escalates after 2+ turns of irrelevant conversation.

## Architecture

```
agent.py           # Living cognitive entity (singleton)
├── Personal/
│   └── personal.json  # 3-level nested memory
├── Work/
│   └── work.json      # 3-level nested memory
└── chat_demo.py       # Interactive demo with Ollama
```

**Key Innovation:** Global state isn't static JSON - it's a living Python object that modules write to and sessions read from. Context depth adjusts in real-time based on conversation relevance.

## Quick Start

```bash
# Install dependencies
pip install ollama

# Pull model (or use any Ollama model)
ollama pull gpt-oss:20b-cloud

# Run the demo
python chat_demo.py
```

## Example Conversation

```
You: Hi Alex!
Alex: Hey there! Hope your day's off to a great start.

You: Work has me stressed
🧠 ⬆️ Escalating work context: level 1 → 2
Alex: I hear you—you're juggling the Cognitive Agent Framework 
      rollout and sprint deadlines. Let's talk through it...

You: Tell me a joke
[2 turns later, work context de-escalates back to level 1]
```

## Features

✅ **Model-agnostic** - Works with GPT, Claude, Llama, any LLM  
✅ **Token-efficient** - Only loads depth when needed  
✅ **Transparent** - You control what's remembered  
✅ **Dynamic escalation** - Detects relevant topics automatically  
✅ **Auto de-escalation** - Reduces context when topics shift  
✅ **User-owned data** - Your data, your machine, no vendor lock-in

## How It Works

1. **Bootstrap**: Agent loads level 1 context from all modules
2. **Conversation**: User message triggers keyword detection
3. **Escalation**: Relevant topics auto-load level 2 or 3 context
4. **Generation**: LLM receives only current context depth
5. **De-escalation**: After 2+ irrelevant turns, context reduces to level 1

## File Structure

**`agent.py`** - The living agent
- `_bootstrap()` - Loads initial level 1 context
- `set_context_depth()` - Escalates/de-escalates dynamically
- `generate()` - Calls LLM with current context

**`Personal/personal.json`** - Layered personal memory
- Identity, relationships, hobbies, health, routine, preferences, values
- Each section has level_1 (summary), level_2 (details), level_3 (comprehensive)

**`Work/work.json`** - Layered work memory  
- Role, projects, expertise, schedule, collaboration, relationships, goals
- Same 3-level nested structure

**`chat_demo.py`** - Interactive demo
- `manage_context_depth()` - Keyword detection + escalation/de-escalation logic
- `chat()` - Main conversation loop

## Customization

Edit the JSON files to match your own profile:

1. **Personal context**: Update `Personal/personal.json` with your identity, relationships, hobbies, etc.
2. **Work context**: Update `Work/work.json` with your role, projects, schedule, etc.
3. **Adjust keywords**: Modify `manage_context_depth()` in `chat_demo.py` to match your topics

Each section follows the pattern:
```json
{
  "section_name": {
    "level_1": "Brief summary string",
    "level_2": {"key": "More detail"},
    "level_3": {"key": {"nested": "Full depth"}}
  }
}
```

## Roadmap (v2)

- [ ] **Agent customization UI** - Set name, purpose, personality preferences
- [ ] **Automatic profile generation** - Describe yourself, agent creates layered JSON
- [ ] Session persistence (save/resume conversations)
- [ ] Background pulse system (autonomous reflection)
- [ ] Module training (30k pairs → fine-tuned specialists)
- [ ] Multi-agent orchestration
- [ ] Web UI

## Why This Matters

This is an **operating system for personal AI**, not just a chatbot. The LLM is the processor, but the agent architecture is what makes it yours.

**Comparison:**

| Feature | ChatGPT Memory | RAG Systems | This Agent |
|---------|---------------|-------------|------------|
| Token efficiency | ❌ Dumps everything | ⚠️ Retrieves many chunks | ✅ Dynamic depth |
| User control | ❌ Black box | ⚠️ Partial | ✅ Full transparency |
| Model flexibility | ❌ OpenAI only | ⚠️ Depends | ✅ Any model |
| Scalability | ❌ Context limits | ⚠️ Expensive | ✅ Efficient |

## Contributing

This is a research prototype demonstrating layered context architecture. Contributions welcome!

Ideas for v2:
- Agent setup wizard (name, purpose, auto-generate profile)
- More sophisticated escalation heuristics
- Multi-modal memory (images, documents)
- Cross-module reasoning

## License

MIT

---

**Built with:** Python 3.11+, Ollama, JSON-first design  
**Philosophy:** Memory > vibes. Structure > scale. User > vendor.
