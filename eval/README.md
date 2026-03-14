# Eval — Benchmark Harness

Benchmark suite that tests Nola (with STATE) against raw LLMs and against herself without STATE.

---

## Description

The eval module runs prompts through multiple models, collects responses, and uses an LLM-as-judge to score them. The core question: **does the OS layer actually help?**

Five benchmark categories ship seeded:
- **State vs No State** — Same model, with and without `== STATE ==`
- **AI vs AI** — Nola against raw Ollama models
- **Base vs Finetuned** — Measure LoRA adapter impact
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
├── runner.py      # run_prompt(), judge_responses(), list_available_models()
├── schema.py      # SQLite tables + CRUD + seed benchmarks
└── README.md
```

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
- [ ] **STATE adherence drift** — Does a finetuned model's STATE format degrade over 50+ turns? Over multiple sessions? No longitudinal eval exists
- [ ] **Identity persistence** — Prompt injection resistance: does the model hold its identity under adversarial prompts? Multi-session recall: does it remember facts from session N in session N+5?
- [ ] **Memory precision/recall** — After 100 conversations, does the right fact surface at the right time? False positive rate? This measures the entire pipeline (extraction → storage → retrieval → STATE assembly)
- [ ] **Context window pressure** — Performance degradation as all 6 threads compete for budget in a long conversation with active workspace and tool history

### Starter tasks
- [ ] Create 10 identity persistence test cases (facts that should survive across sessions)
- [ ] Before/after benchmark script for finetuning runs
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