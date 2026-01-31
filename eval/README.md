# Eval — AI Battle Arena

> 🚧 **In Development** — This module is currently being built.

The **Battle Arena** is a benchmarking suite for AI OS. It allows you to test the "managed AI" architecture against raw LLMs (like GPT-4, Claude, or local Llama models) to visualize the benefits of long-term memory, structural identity, and state management.

## Goals

1.  **Quantify "Memory"**: Prove that OS-managed memory outperforms raw context windows over long sessions.
2.  **Test "Identity"**: Show how structural identity resists prompt injection compared to system prompts.
3.  **Benchmark "Speed"**: Measure latency improvements from retrieval-augmented generation vs full-context loading.

## Battle Types

| Battle | What It Tests |
|--------|--------------|
| **Identity** | Does the AI know who it is? Resists adversarial prompt injection. |
| **Memory** | Does it remember facts from previous sessions (simulated)? |
| **Tool Use** | Can it reliably execute multi-step tasks? |
| **Connections** | Can it link facts together across time? |
| **Speed** | Response latency at equivalent answer quality. |

## Architecture

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
│   └── speed.py
├── judge.py             # LLM-as-a-Judge integration
└── metrics.py           # Scoring functions
```

## API Endpoints

- `POST /api/eval/battle/start` - Start a new battle
- `GET /api/eval/battle/{id}` - Get battle status and results
- `GET /api/eval/leaderboard` - Win/loss stats

## Usage (Planned)

```python
# CLI usage for developers
python -m eval.battle --type coherence --adversary gpt-4o --turns 30
```

## Status

- [ ] Battle orchestration logic
- [ ] Database schema for results
- [ ] Judge model integration
- [ ] Evaluators for Identity/Memory
- [ ] Frontend visualization components

---

## Frontend Module

Located at `frontend/src/modules/eval/`:

```
eval/
└── index.ts                # Module exports (placeholder)
```

*Frontend components planned for battle visualization and leaderboard display.*