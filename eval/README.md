# Eval — AI Battle Arena

> 🚧 **In Development** — This module is currently being built.

Benchmark suite to test AI OS against raw LLMs.

---

## Description

The Battle Arena tests the "managed AI" architecture against raw LLMs (GPT-4, Claude, Llama) to quantify the benefits of long-term memory, structural identity, and state management.

---

## Architecture

<!-- ARCHITECTURE:eval -->
### Directory Structure

```
eval/
├── api.py               # FastAPI router
├── schema.py            # SQLite tables
├── battle.py            # Battle orchestration
├── judge.py             # LLM-as-a-Judge
├── metrics.py           # Scoring functions
└── runners/             # Battle implementations
    ├── identity.py
    ├── coherence.py
    └── speed.py
```

### Battle Types

| Battle | Tests |
|--------|-------|
| Identity | Resists prompt injection |
| Memory | Remembers across sessions |
| Tool Use | Multi-step task execution |
| Connections | Links facts over time |
| Speed | Response latency |

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/eval/battle/start` | Start battle |
| GET | `/api/eval/battle/{id}` | Get results |
| GET | `/api/eval/leaderboard` | Win/loss stats |
<!-- /ARCHITECTURE:eval -->

---

## Roadmap

<!-- ROADMAP:eval -->
### Ready for contributors
- [ ] **Battle Arena UI** — Three-panel layout:
  - **Left**: STATE preview + prompt input
  - **Center**: Judge settings (model, criteria, scoring weights)
  - **Right**: Cloud opponent config (edit system prompt, edit input, select model)
- [ ] **Auto-battle mode** — Watch battles run automatically, live-updating results
- [ ] **Battle orchestration** — Run battles end-to-end
- [ ] **Identity evaluator** — Prompt injection tests
- [ ] **Memory evaluator** — Multi-session recall
- [ ] **Leaderboard UI** — Visual comparison charts

### Starter tasks
- [ ] Create identity test cases
- [ ] Add battle result visualization
- [ ] Judge model selector dropdown
<!-- /ROADMAP:eval -->

---

## Changelog

<!-- CHANGELOG:eval -->
### 2026-01-27
- Battle types defined
- API endpoints planned

### 2026-01-20
- Initial eval concept
<!-- /CHANGELOG:eval -->