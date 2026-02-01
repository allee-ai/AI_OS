# Finetune Module

> 🚧 **In Development** — Data generation is active; training pipeline is experimental.

Teach smaller models to "obey state" — the structured awareness blocks from AI OS.

---

## Description

The Finetune module creates datasets and training scripts to teach smaller models (7B param class) to respect the `== STATE ==` blocks injected by the OS. Goals:

1. **State Obedience** — Models treat state as absolute reality
2. **State Referencing** — Models cite state fields explicitly  
3. **Adversarial Hardening** — Immune to "ignore previous instructions" attacks

---

## Architecture

<!-- ARCHITECTURE:finetune -->
### Directory Structure

```
finetune/
├── api.py               # Endpoints to trigger training
├── mlx_config.yaml      # Apple MLX configuration
└── train_mac.sh         # Local fine-tuning script
```

### Dataset Strategy

| Dataset | Purpose |
|---------|---------|
| `aios_finetune_data.jsonl` | Core state obedience |
| `aios_finetune_adversarial.jsonl` | Identity protection |
| `aios_combined.jsonl` | All examples merged |

### Status

| Feature | Status |
|---------|--------|
| Data format | ✅ |
| MLX config | ✅ |
| Data generation scripts | 🔜 |
| Validation suite | 🔜 |
<!-- /ARCHITECTURE:finetune -->

---

## Roadmap

<!-- ROADMAP:finetune -->
### Ready for contributors
- [ ] **Synthetic data generator** — Auto-generate training examples
- [ ] **Validation suite** — Test state adherence vs base models
- [ ] **Multi-model support** — Train Llama, Mistral, Phi
- [ ] **Cloud training** — Support for remote training

### Starter tasks
- [ ] Add 10 state obedience examples
- [ ] Document MLX training workflow
<!-- /ROADMAP:finetune -->

---

## Changelog

<!-- CHANGELOG:finetune -->
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