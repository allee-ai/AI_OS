# Evaluation Harness

Benchmark suite for measuring Nola's coherence and performance.

---

## For Users

This folder contains tools to test how well Nola performs compared to baseline AI systems. You don't need this for normal use — it's for research and development.

---

## For Developers

### Structure

```
eval/
├── duel.py          # CLI runner for adversarial benchmarks
├── judges.py        # Judge model integrations (GPT-4, Claude, etc.)
├── metrics.py       # Scoring functions
├── baselines/       # Baseline configurations
└── transcripts/     # Benchmark results
```

### Quick Start

```bash
# Run adversarial coherence benchmark
python eval/duel.py --turns 50 --opponent raw --judge mock

# With specific judge
python eval/duel.py --turns 20 --judge gpt4
```

### Metrics

See [docs/evaluation_framework.md](../docs/evaluation_framework.md) for:
- Coherence scoring rubrics
- Context utilization metrics
- Adversarial prompt categories
