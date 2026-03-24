# Fire-Tuner — Training Module

Teach smaller models to obey STATE — the structured awareness blocks from AI OS.

---

## Description

The Fire-Tuner builds datasets and training scripts to teach small models (7B class) to respect **`== STATE ==`** blocks injected by the OS. Three objectives:

1. **State Obedience** — Models treat STATE as absolute reality
2. **State Referencing** — Models cite state fields explicitly
3. **Adversarial Hardening** — Immune to "ignore previous instructions" attacks

The training pipeline is self-improving: a background `TrainingGenLoop` uses kimi-k2 as a teacher model to read actual source code and generate training examples across 17 modules (105+ source files).

---

## Architecture

<!-- ARCHITECTURE:finetune -->
### Directory Structure

```
finetune/
├── api.py                  # 7 FastAPI endpoints (export, train, load, config, data)
├── cli.py                  # CLI commands (/finetune, /finetune gen, etc.)
├── cloud_gen.py            # Multi-provider cloud data generator (AST → conversational Q&A)
├── sections.py             # Shared JSONL builders (API, CLI, schema examples)
├── docstring_extractor.py  # AST-based docstring harvesting across all modules
├── gold_examples.py        # Hand-curated reasoning examples (9 categories)
├── mlx_config.yaml         # Apple MLX LoRA configuration
├── train_mac.sh            # Local fine-tuning script (Apple Silicon)
├── generated/              # Background-generated training data (TrainingGenLoop + cloud_gen)
└── auto_generated/         # Docstring-extracted training data
```

### Data Sources

| Source | Generator | Description |
|--------|-----------|-------------|
| Per-thread metadata | `sections.py` | API endpoints, CLI commands, schema tables → Q&A pairs |
| Docstrings | `docstring_extractor.py` | AST-walks Python source, extracts function/class docs |
| Gold examples | `gold_examples.py` | Hand-written reasoning pairs (9 categories) |
| Live decisions | `train.py` per thread | High-confidence decisions from `source='aios'` conversations (threshold 0.7) |
| Synthetic (kimi-k2) | `TrainingGenLoop` | Teacher model reads source code + mechanical examples → generates 5 better pairs per file |
| Cloud-generated | `cloud_gen.py` | AST-walks every def/class block, round-robins free-tier APIs (Gemini, Claude, OpenAI, OpenRouter, Ollama) → 5 conversational Q&A per block |

### Module Coverage

The `TrainingGenLoop` generates examples for all 17 modules:

| Scope | Modules |
|-------|---------|
| Thread modules | linking_core, identity, philosophy, log, reflex, form, chat, docs |
| Top-level modules | workspace, feeds, agent_core, agent_services, form_tools, parsers, data_db, scripts, subconscious |

### Per-Thread Train Files

Each cognitive thread has its own `train.py`:

| Thread | What It Exports |
|--------|----------------|
| Identity | Profile facts, trust levels, contact management Q&A |
| Philosophy | Values, constraints, ethical bounds Q&A |
| Log | Event types, session tracking, timeline Q&A |
| Reflex | Trigger patterns, cascade priority, automation Q&A |
| Form | Tool definitions, safety rules, execution Q&A |
| Linking Core | Concept links, spread activation, scoring Q&A |

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/finetune/export` | Full export: consolidate links → run all thread exporters → merge to `aios_combined.jsonl` |
| POST | `/api/finetune/export/{thread}` | Export single thread |
| GET | `/api/finetune/export/stats` | Counts from all modules + reasoning + generated |
| POST | `/api/finetune/start` | Configure hyperparams + launch `train_mac.sh` |
| GET | `/api/finetune/config` | Current MLX config |
| GET | `/api/finetune/data` | List all `.jsonl` files with line counts |
| POST | `/api/finetune/load` | Fuse LoRA adapter into Ollama model |

### Export Pipeline

```
POST /api/finetune/export
    → consolidate_links()          # Promote reinforced concept links
    → for each thread: export_training_data()
    → docstring_extractor.extract_all()
    → gold_examples.get_all_examples()
    → merge → finetune/aios_combined.jsonl
```

### Training (Apple Silicon)

```bash
# Via API
POST /api/finetune/start
  { "rank": 8, "alpha": 16, "lr": 1e-4, "iters": 1000 }

# Or directly
cd finetune && bash train_mac.sh
```

Uses MLX LoRA on Apple Silicon. Config in `mlx_config.yaml`.

### Cloud Data Generator (`cloud_gen.py`)

AST-walks every Python file in the codebase, discovers all `def` and `class` blocks (~2,066), and generates 5 conversational Q&A pairs per block using free-tier LLM APIs.

**Providers** (round-robin by default):
| Provider | Free Tier | Rate Limit |
|----------|-----------|------------|
| Gemini | 15 RPM | 4s delay default |
| Claude | API key required | |
| OpenAI | API key required | |
| OpenRouter | Free models (qwen, mistral) | |
| Ollama | Local, unlimited | |

**Usage:**
```bash
# Preview what would be generated
python -m finetune.cloud_gen --dry-run

# Generate from all blocks via Ollama
python -m finetune.cloud_gen --provider ollama

# Resume interrupted run, single module
python -m finetune.cloud_gen --resume --module identity

# Limit to 50 blocks
python -m finetune.cloud_gen --max 50

# Or via CLI
/finetune gen --dry-run
/finetune gen --provider gemini --resume --max 100
```

Output: `finetune/generated/cloud_<module>.jsonl` with progress tracking in `.cloud_gen_progress.json`.

### CLI Commands

| Command | Description |
|---------|-------------|
| `/finetune` | Training data overview & stats |
| `/finetune export` | Export all thread data → aios_combined.jsonl |
| `/finetune gen [opts]` | Run cloud data generator |
| `/finetune train` | Launch MLX training (train_mac.sh) |
| `/finetune runs` | List training run directories |
| `/finetune config` | Show MLX training configuration |

### Status

| Feature | Status |
|---------|--------|
| Export pipeline | ✅ Wired |
| Per-thread train.py | ✅ All 6 threads (source='aios' filtered) |
| Docstrings | ✅ AST-based extraction |
| Gold examples | ✅ 9 categories |
| Cloud data generator | ✅ Multi-provider, 2,066 blocks discovered |
| CLI commands | ✅ /finetune, gen, export, train, runs, config |
| MLX config | ✅ |
| Training gen loop | ✅ kimi-k2 teacher, 17 modules, 105+ files |
| Data quality filtering | ✅ Source-filtered, capped associations |
| End-to-end cycle | ✅ First cycle complete (MLX LoRA, noticeable improvement) |
| Adapter loading | 🔧 Endpoint exists, untested |
<!-- /ARCHITECTURE:finetune -->

---

## Roadmap

<!-- ROADMAP:finetune -->
### Pipeline completion
- [ ] **Training orchestrator** — Chain export → train → load in a single `POST /finetune/run`:
  - Status tracking with progress events via WebSocket
  - Exit code capture from `train_mac.sh` (currently fire-and-forget)
  - Automatic combined JSONL generation before training starts
- [ ] **Before/after evaluation** — Run eval suite pre-train and post-train on same prompts:
  - STATE format adherence score
  - Identity consistency over 50+ turns
  - Regression detection (general capability)
- [ ] **Convergence monitoring** — Surface validation loss during training, stop early on plateau

### Research
- [ ] **Self-improvement measurement** — Does a model trained on its own STATE output actually improve, or does it collapse? Requires controlled A/B eval across multiple training cycles
- [ ] **Catastrophic forgetting baseline** — Benchmark general capability before and after LoRA. Quantify the tradeoff between STATE adherence and general fluency
- [ ] **Synthetic data quality** — TrainingGenLoop generates via kimi-k2 teacher. Measure improvement vs noise injection across training cycles

### Starter tasks
- [ ] Add 10 STATE obedience examples to gold_examples.py
- [ ] Document the full export → train → load workflow with expected outputs
<!-- /ROADMAP:finetune -->

---

## Changelog

<!-- CHANGELOG:finetune -->
### 2026-03-15
- **First training cycle complete** — MLX LoRA on Llama-3.2-3B-Instruct-4bit, small but noticeable improvement
- Conversation import tested (135 VS Code + 126 ChatGPT convos feeding concept graph)

### 2026-03-14
- TrainingGenLoop: Background synthetic example generation every 2h
- ConvoConceptLoop: Backfill concept graph before export (richer co-occurrence data)

### 2026-03-07
- Docstring extractor: AST-based harvesting across 8 modules
- Gold examples: 9 categories of curated reasoning pairs
- Sections builder: Shared API/CLI/schema example generators
- Frontend: Sections browser, unified training view, generated example approval

### 2026-01-31
- Export pipeline: `/api/finetune/export` aggregates all threads
- Per-thread `train.py` pattern (identity, philosophy, log, reflex, form, linking_core)
- Combined JSONL output at `finetune/combined_train.jsonl`

### 2026-01-27
- MLX configuration for Apple Silicon
- JSONL data format defined

### 2026-01-20
- Initial fine-tuning concept
<!-- /CHANGELOG:finetune -->