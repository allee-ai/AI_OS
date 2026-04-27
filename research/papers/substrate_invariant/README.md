# Self as Substrate-Invariant — paper directory

arXiv submission and supporting material for *Self as Substrate-Invariant: A Falsifiable Account of Identity in Clocked LLM Systems*.

**Author:** Cade Roden — alleeroden@pm.me
**Last updated:** Apr 2026

## Contents

| File | Purpose |
|------|---------|
| [paper.md](paper.md) | Full readable manuscript (Markdown source of truth). |
| [paper.tex](paper.tex) | Single-file LaTeX, no figures, compiles with `pdflatex`. |
| [arxiv_submission.tar.gz](arxiv_submission.tar.gz) | Packaged submission bundle uploaded to arXiv. |
| [experiment_a_README.md](experiment_a_README.md) | Runnable harness for §6.1 — iteration-rate sweep over the 15-turn long-horizon eval. |
| [endorsers.md](endorsers.md) | arXiv cs.AI endorser candidates scored from 285 recent papers. |
| [outreach/](outreach/) | Posts and emails (HN, LessWrong, EleutherAI, r/LocalLLaMA, r/ML, Bluesky, three researcher emails, GitHub README blurb). |

## What the paper claims

Coherence in biological cognition is a property of a substrate iterating against itself, not of any single forward pass. AI_OS externalises that substrate as scored threads (identity, log, form, philosophy, reflex, linking core); a small model reads from and writes to it. The same 7B model maintains identity (0.90), recalls runtime-only facts (1.00), and resists adversarial injection (0.70) with the substrate, and scores 0.00 on all three without it. A 1.5B model with substrate qualitatively outperformed a 3B model without.

The hypothesis: ticks-per-response is an axis of capability separate from parameter scale, and running the loop at sub-token cadence should produce coherence properties no single forward pass can produce. Two preregistered experiments (§6.1 iteration-rate sweep; §6.2 active-vs-frozen substrate at matched compute) test it. It fails if neither shows a gap.

## Reproducing experiment A

See [experiment_a_README.md](experiment_a_README.md). It reuses [`eval/_long_horizon.py`](../../../eval/_long_horizon.py) and adds one knob: **K**, the number of subconscious cognitive ticks fired between user turns.

## Compiling the paper

```bash
pdflatex paper.tex
```

No figures, no bib, no extras — single-file by design.
arXiv submission: Self as Substrate-Invariant
Cade Roden — alleeroden@pm.me — Apr 2026
Source: paper.tex (single-file LaTeX, no figures, compiles with pdflatex).
