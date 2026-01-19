# Identity Thread — Implementation Notes

Primary sources: `docs/implementation/database_integration_plan.md`, `docs/DEV_NOTES.md`, `docs/FOCUS_CHECKLIST.md`.

What lives here (current canonical):
- Per-key L1/L2/L3 storage (see `Nola/threads/identity/adapter.py`).
- Tables: `identity_flat` or module tables under `threads/identity/modules/`.
- Weight, metadata, and consolidation logic referenced in `docs/FOCUS_IMPLEMENTATION.md`.

Recommended consolidation steps:
1. Copy the identity-specific schema sections from `docs/implementation/database_integration_plan.md` into this file or `README.md` (short summary + migration notes).
2. Move identity migration/migration scripts into `Nola/threads/identity/migrations/` and reference here.
3. Add examples for `push_identity`, `pull_identity`, and `sync_for_stimuli` (small code snippets).

Notes:
- Tests in `tests/test_idv2.py` reference legacy `idv2` APIs; consider adding a small compatibility shim that forwards to `Nola/threads/identity` adapter while you update tests.
