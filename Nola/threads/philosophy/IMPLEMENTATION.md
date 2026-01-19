# Philosophy Thread — Implementation Notes

Primary sources: `docs/ROADMAP.md`, `docs/DEV_NOTES.md`, theory docs in `docs/theory/`.

What lives here (canonical):
- Values, constraints, ethics-related facts and modules that guide decision-making. Currently mostly a stub; system prompt contains many defaults.

Recommended consolidation steps:
1. Move the "Philosophy" design sections from `docs/ROADMAP.md` and `docs/DEV_NOTES.md` into this file to make the intended API explicit.
2. Add a short list of safety checks and `detect_harm()` placeholder signatures for implementers.
3. Document how Philosophy integrates with Form and Reflex threads (constraint checks before actions).

Notes:
- Philosophy is high-impact; keep public-facing TL;DR in `docs/theory/*` and implementation details here.
