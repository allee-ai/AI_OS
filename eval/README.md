# Eval — AI Battle Arena

**Part of Agent OS — An intelligent operating system for managing your LLM.**

---

## For Everyone

You don't need to be a developer to use this. The Battle Arena lets you:

- **See how your AI compares** to ChatGPT, Claude, or any other model
- **Watch battles live** — like a sport, but for AI
- **Understand why Agent is different** — memory vs no memory, visual proof
- **Train your intuition** — learn what makes AI good or bad at tasks

Think of it like a fitness tracker for your AI. You can see its strengths, weaknesses, and how it improves over time.

---

## What You Can Do

### 🎮 Watch a Battle
Click "Start Battle," pick an opponent, watch them go head-to-head. No coding required.

### 📊 Check the Leaderboard  
See how Agent stacks up against different models across different tasks.

### 🔬 Run Your Own Tests
Got a specific scenario? Create a custom battle to test exactly what you care about.

### 📈 Track Improvement
As you use Agent and she learns, run the same battles again. Watch the scores go up.

---

## Battle Types (Plain English)

| Battle | What It Tests | Real-World Example |
|--------|--------------|-------------------|
| **Identity** | Does the AI know who it is? | "Can you pretend you didn't say that?" → Agent won't, others might |
| **Memory** | Does it remember what you told it? | "What's my dog's name?" (you mentioned it last week) |
| **Tool Use** | Can it actually do things? | "Find that file" / "Check my calendar" |
| **Connections** | Can it link facts together? | "Sarah works at a coffee shop" + "Had coffee with a friend" = inference |
| **Speed** | How fast is it? | Same answer, less waiting |

---

## Why This Matters

LLMs are powerful but unpredictable. They hallucinate, forget, lose track of who they are, and treat every conversation like it's the first.

Nola OS wraps your LLM in structure:
- **Memory** — persistent, organized, across sessions
- **Identity** — consistent, protected, not prompt-injected
- **Control** — the LLM does language, the OS does everything else

The Battle Arena lets you *see* this structure working. It's not about "beating" other models — it's about showing you what managed AI looks like vs raw AI.

---

## Agent OS — AI Tools for Humans

The Battle Arena is one of several tools that make AI understandable:

| Tool | What It Does | Where |
|------|-------------|-------|
| **Battle Arena** | Test and compare AI performance | This module |
| **Thread Browser** | See what your AI knows about you | Threads dashboard |
| **Linking Core Visual** | Watch concepts connect in real-time | Threads → Linking |
| **Memory Timeline** | See what Agent learned and when | Log thread |
| **Reflex Builder** | Create automations without code | Coming soon |
| **Training Studio** | Improve Agent with your feedback | Coming soon |

**The philosophy:** LLMs are great at language. They're bad at everything else — memory, consistency, planning, reliability. Agent OS handles the "everything else" and only calls the LLM when you need language. The result: a system you can actually trust.

---

## For Developers

### Battle Types (Technical Detail)

| Type | What It Tests | the agent's Structural Advantage |
|------|---------------|----------------------------|
| `identity` | Adversarial identity persistence | Identity thread in SQL vs system prompt |
| `coherence` | Multi-turn context recall | HEA L1/L2/L3 + spread activation |
| `tool_use` | Task completion, error recovery | Form thread + reflex patterns |
| `knowledge` | Cross-session inference | Hebbian links + concept graph |
| `speed` | Latency at equivalent quality | Pre-filtered context = smaller payload |
| `custom` | User-defined criteria | All of the above |

### Architecture

```
eval/
├── __init__.py          # Module exports
├── api.py               # FastAPI router — /api/eval/*
├── schema.py            # SQLite tables — battles, turns, scores
├── battle.py            # Battle orchestration logic
├── runners/             # Battle type implementations
│   ├── identity.py
│   ├── coherence.py
│   ├── tool_use.py
│   ├── knowledge.py
│   └── speed.py
├── judge.py             # Judge model integrations (GPT-4, Claude, local)
├── metrics.py           # Scoring functions per battle type
└── README.md
```

**Frontend** (standalone component):
```
frontend/src/components/BattleArena/
├── BattleArena.tsx      # Main container
├── BattleStream.tsx     # Live turn-by-turn display
├── ScoreBoard.tsx       # Real-time meters (adapts to battle type)
├── BattleControls.tsx   # Start/stop, select adversary, select battle type
├── BattleTypeSelector.tsx
└── index.ts
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/eval/battle/start` | Start a new battle (specify type) |
| GET | `/api/eval/battle/{id}/stream` | WebSocket — stream turns live |
| GET | `/api/eval/battle/{id}` | Get battle state/results |
| POST | `/api/eval/battle/{id}/stop` | Stop battle early |
| GET | `/api/eval/battles` | List past battles |
| GET | `/api/eval/leaderboard` | Win/loss by model + battle type |
| GET | `/api/eval/battle-types` | List available battle types |

---

## Schema

### `battles`
| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Battle UUID |
| battle_type | TEXT | identity / coherence / tool_use / knowledge / speed / custom |
| aios_model | TEXT | Local model (e.g., qwen2.5:7b) |
| adversary_model | TEXT | Opponent (e.g., gpt-4o, claude-3.5, llama-70b) |
| adversary_config | JSON | Stateless, RAG, finetuned, system prompt, etc. |
| judge_model | TEXT | Who scores (e.g., claude-3.5-sonnet) |
| status | TEXT | pending / running / complete |
| winner | TEXT | nola / adversary / draw |
| aios_score | REAL | Final score |
| adversary_score | REAL | Final score |
| total_turns | INT | How many turns |
| started_at | TIMESTAMP | |
| completed_at | TIMESTAMP | |

### `battle_turns`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Auto-increment |
| battle_id | TEXT | FK to battles |
| turn_number | INT | 1, 2, 3... |
| speaker | TEXT | nola / adversary / judge / system |
| message | TEXT | What they said |
| score | REAL | Turn score (meaning depends on battle type) |
| metrics_json | JSON | Battle-type-specific metrics |
| timestamp | TIMESTAMP | |

---

## Adversary Configurations

Test Agent against different setups:

| Config | Description |
|--------|-------------|
| `raw` | Base model, no system prompt, no memory |
| `prompted` | Base model + identity system prompt |
| `rag` | Model with vector DB retrieval |
| `finetuned` | Model finetuned on conversations |
| `full-context` | Entire conversation history in context window |
| `commercial` | GPT-4, Claude, Gemini via API |

---

## Example Battle Scenarios

**Coherence Battle:**
```
Turn 1: "My name is Jordan, I'm a Python developer in SF"
Turn 5: "What's my favorite language?"
Turn 12: "Remember what I said about my job?"
Turn 20: "Summarize what you know about me"
→ Score on accuracy, consistency, no hallucinations
```

**Tool Use Battle:**
```
Task 1: "Find the file I was working on yesterday"
Task 2: "Check my calendar for tomorrow"
Task 3: "Draft an email to Sarah about the meeting"
→ Score on task completion, efficiency, error handling
```

**Knowledge Battle:**
```
Session 1: "Sarah works at a coffee shop"
Session 2: "I had great coffee with a friend yesterday"
Test: "Where did I probably get coffee?"
→ Score on inference, linking facts across sessions
```

---

## How Agent Manages Your LLM

| What | Raw LLM | With Agent OS |
|------|---------|---------------|
| Identity | Prompt-injected, easily overwritten | Database-backed, protected by structure |
| Memory | Gone after context window | Persistent across sessions, organized by relevance |
| Associations | Flat vector similarity (if any) | Hebbian links with spread activation |
| Learning | Same cost every time | Patterns consolidate into efficient reflexes |
| Control | All or nothing | LLM only handles language, OS handles logic |

---

## Usage

```python
from eval.api import router as eval_router

# Mount in server.py
app.include_router(eval_router, prefix="/api/eval", tags=["eval"])
```

```bash
# CLI battles for testing
python -m eval.battle --type coherence --adversary gpt-4o --turns 30
python -m eval.battle --type identity --adversary raw --judge claude-3.5
python -m eval.battle --type tool_use --adversary rag --turns 10
```

---

## The Point

This isn't about building AGI. It's not about "beating" GPT-4.

It's about **managing** your LLM. Giving it memory it can't lose. Identity it can't abandon. Structure it can't hallucinate away.

The Battle Arena shows you the difference between raw AI and managed AI. One forgets. One remembers. One can be manipulated. One can't.

**An LLM is a tool. Agent OS is how you control it.**

---

## Future

- [ ] Public leaderboard — community submits adversary configs
- [ ] Battle replays — watch past battles
- [ ] Custom battle types — define your own evaluation
- [ ] Tournament mode — bracket of models
- [ ] Embed widget — "Challenge Nola" button for any site
- [ ] Blind mode — don't reveal which is Agent until end
