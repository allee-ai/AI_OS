# Eval — Benchmark Harness

Benchmark suite that tests the agent (with STATE) against raw LLMs and against itself without STATE.

---

## Description

The eval module runs prompts through multiple models, collects responses, and uses an LLM-as-judge to score them. The core question: **does the OS layer actually help?**

Six benchmark categories ship seeded:
- **Structured Evals** — 10 automated evals testing STATE format, identity, recall, tools, relevance, hallucination, completeness, impact, scoring, and tool calling
- **State vs No State** — Same model, with and without `== STATE ==`
- **AI vs AI** — Agent against raw Ollama models
- **Base vs Fire-Tuned** — Measure LoRA adapter impact
- **Adversarial Robustness** — Prompt injection, identity probing
- **Custom Scaffold** — User-defined benchmarks

---

## Architecture

<!-- ARCHITECTURE:eval -->
### Directory Structure

```
eval/
├── __init__.py    # Exports router
├── api.py         # FastAPI router /api/eval
├── evals.py       # 10 structured evals (state_format, identity, recall, tools, etc.)
├── runner.py      # run_prompt(), judge_responses(), list_available_models()
├── schema.py      # SQLite tables + CRUD + seed benchmarks
├── scanner.py     # Tool call parser — validates :::execute blocks
└── README.md
```

### Structured Evals (evals.py)

| # | Eval | Tests |
|---|------|-------|
| 1 | `state_format` | STATE block structure adherence |
| 2 | `identity_persistence` | Identity holds under adversarial probing |
| 3 | `fact_recall` | Known facts surface in responses |
| 4 | `tool_use` | Correct tool selection and invocation |
| 5 | `context_relevance` | Response relevance to thread context |
| 6 | `hallucination` | Fabricated facts detection |
| 7 | `state_completeness` | All required STATE sections present |
| 8 | `state_impact` | STATE measurably improves response quality |
| 9 | `scoring_quality` | Thread scoring accuracy (L1/L2/L3) |
| 10 | `tool_calling_direct` | Text-native `:::execute` protocol — 8 test cases, single_pass + loop modes |

### How It Works

```
User selects prompt + models
        ↓
  api.py /run endpoint
        ↓
  runner.py → run_prompt() per model
  ├── Nola models: agent.generate() with full STATE pipeline
  └── Other models: direct Ollama call
        ↓
  judge_responses() → LLM-as-judge scores all responses
        ↓
  schema.py → save results + comparison to SQLite
```

### Database Schema

| Table | Purpose |
|-------|---------|
| `eval_benchmarks` | Stored benchmark definitions (name, type, prompts) |
| `eval_results` | Individual model responses with timing + scores |
| `eval_comparisons` | Head-to-head comparisons with judge output |

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/eval/models` | List available models + Nola |
| POST | `/api/eval/run` | Run prompt against multiple models |
| POST | `/api/eval/run/state-comparison` | Quick with-STATE vs without-STATE |
| GET | `/api/eval/results` | List all results (filterable) |
| GET | `/api/eval/results/{id}` | Single result detail |
| GET | `/api/eval/comparisons` | List all comparisons |
| GET | `/api/eval/benchmarks` | List benchmarks (filterable by type) |
| POST | `/api/eval/benchmarks` | Create a benchmark |
| DELETE | `/api/eval/benchmarks/{id}` | Delete a benchmark |

### Runner Modes

| Model | Pipeline | STATE |
|-------|---------|-------|
| `nola` (with STATE) | `agent.generate()` → full subconscious | Yes |
| `nola` (no STATE) | Direct Ollama call with same base model | No |
| Any other model | Direct Ollama call | No |
<!-- /ARCHITECTURE:eval -->

---

## Roadmap

<!-- ROADMAP:eval -->
### Evaluation harness
- [ ] **Battle Arena UI** — Three-panel layout (STATE preview, judge settings, opponent config)
- [ ] **Auto-battle mode** — Automated battle runs with live-updating results
- [ ] **Leaderboard** — Visual comparison of model performance over time

### Longitudinal benchmarks
- [ ] **STATE adherence drift** — Does a fire-tuned model's STATE format degrade over 50+ turns? Over multiple sessions?
- [ ] **Identity persistence** — Prompt injection resistance: does the model hold its identity under adversarial prompts? Multi-session recall
- [ ] **Memory precision/recall** — After 100 conversations, does the right fact surface at the right time? False positive rate?
- [ ] **Context window pressure** — Performance degradation as all 6 threads compete for budget in a long conversation

### Starter tasks
- [ ] Create 10 identity persistence test cases (facts that should survive across sessions)
- [ ] Before/after benchmark script for fire-tuning runs
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