# Reflex Thread — Implementation Notes

Primary sources: `docs/logs/CHANGELOG.md`, `docs/DEV_NOTES.md`, `agent/threads/reflex/README.md`.

What lives here (canonical):
- Reflex storage for trigger→response mappings, shortcuts, and system reflex promotion rules (10x rule).

Recommended consolidation steps:
1. Move promotion rules and 10x criteria from `docs/DEV_NOTES.md` into this file with concrete thresholds and example queries.
2. Document how Log tracks reflex usage and how promotion is triggered by the consolidation daemon.
3. Add examples for registering shortcuts and system reflex CRUD API usage.

Notes:
- Reflexes are lightweight and should be the simplest files to maintain; keep examples minimal and runnable.
