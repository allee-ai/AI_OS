# Form Thread — Implementation Notes

Primary sources: `docs/logs/CHANGELOG.md`, `docs/implementation/THREAD_BROWSER_UI.md`, `docs/DEV_NOTES.md`.

What lives here (canonical):
- Tool registry (`tools.py`), executor (`executor.py`), and form tool metadata vs runtime state separation.

Recommended consolidation steps:
1. Copy tool registry schema and examples from `docs/logs/CHANGELOG.md` and `THREAD_BROWSER_UI.md` into this file.
2. Document `format_tools_for_prompt()` and how tools are represented in system prompts.
3. Add examples for registering and testing tools via the Form API endpoints.

Notes:
- Form contains both capabilities (metadata) and current state (data); keep both documented here.
