# Linking Core — Implementation Notes

Primary sources: `docs/implementation/FOCUS_IMPLEMENTATION.md`, `docs/theory/concept_attention_theory.md`, `docs/DEV_NOTES.md`.

What lives here (canonical):
- Spread activation, Hebbian learning (`link_concepts`, `decay_concept_links`), co-occurrence scoring, and `fact_relevance` scoring functions.

Recommended consolidation steps:
1. Move math and algorithm pseudocode from `docs/theory/*` and `docs/implementation/*` into this file (algorithms + table definitions).
2. Add runnable examples for `spread_activate()` and `record_concept_cooccurrence()`.
3. Annotate background daemon usage (decay schedule) and where the consolidation daemon calls these functions.

Notes:
- Linking Core is algorithmic — keep theory in `docs/theory/*` but implementation, params, and tuning knobs here.
