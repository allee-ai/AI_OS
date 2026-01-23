# Log Thread — Implementation Notes

Primary sources: `docs/implementation/log_thread_implementation_plan.md`, `docs/DEV_NOTES.md`.

What lives here (canonical):
- Append-only event logging API (`log_event`, `log_error`) writing to `agent/log_thread/master.log`.
- Tables/modules: `log_events`, `log_sessions` (future DB migration described in docs).

Recommended consolidation steps:
1. Move the file→DB migration plan sections from `docs/implementation/log_thread_implementation_plan.md` into this file (migration steps, schema).
2. Add clear examples for `log_event()` usage and session lifecycle API.
3. Document the `LOG_CONVERSATION_TURNS` env toggle and where to find master.log.

Notes:
- Log is temporal; linking_core uses recency windows (L1/L2/L3) to surface timeline facts.
