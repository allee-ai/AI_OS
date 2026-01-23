# Agent — The Brain

This is the agent's core AI system. Everything that makes her remember, think, and respond lives here.

---

## For Users

### How Agent Remembers You

When you chat with Agent, she:

1. **Listens** — Picks up facts you mention (your name, job, projects)
2. **Saves** — Stores these facts locally on your computer
3. **Recalls** — Uses relevant facts in future conversations

### Where Your Data Lives

```
agent/
├── Agent.json                    # Her current "thoughts" about you
├── identity_thread/
│   └── userID/user.json         # What she knows about you
└── Stimuli/conversations/       # Your chat history
```

### Customizing the Agent

**Change her personality** — Edit `Agent.json`:
```json
{
  "name": "Aria",
  "role": "creative writing assistant",
  "personality": "encouraging and imaginative"
}
```

**Update your info** — Edit `identity_thread/userID/user.json`:
```json
{
  "name": "Jordan",
  "interests": ["photography", "travel"],
  "work": "freelance designer"
}
```

---

## For Developers

See [ARCHITECTURE.md](ARCHITECTURE.md) for technical details.

### Quick Reference

| Module | Purpose |
|--------|---------|
| `agent.py` | LLM interface, response generation |
| `subconscious/` | Context assembly from all threads |
| `threads/` | Identity and state management system |
| `temp_memory/` | Session facts before consolidation |
| `log_thread/` | Event timeline |
| `services/` | FastAPI integration, HEA routing |

### Key Pattern

```
User Message → agent_service.py
                    ↓
              classify_stimuli() → L1/L2/L3
                    ↓
              get_consciousness_context(level)
                    ↓
              agent.generate(context)
                    ↓
              Response
```
