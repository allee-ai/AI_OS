# Repository Health

Current snapshot (local run on 2026-01-12):

- Unit tests: 26 collected — 17 passed, 9 failed (run via `./runtests.sh --unit`).
- Notable failures:
  - `tests/test_idv2.py` tests failing with `ModuleNotFoundError: No module named 'idv2'` (identity module was refactored/removed).
  - Kernel/browser tests failing due to async plugin/environment expectations (pytest-asyncio is listed in `requirements.txt` — CI should pin and use the same venv).
  - Minor path oddities observed in runtime output (a trailing-space in repository path) that may cause platform-specific issues.

Top 3 blockers (recommended priorities)
1. Restore or shim `idv2` API or update tests to use the new thread/schema API — this is a CI blocker.
2. Confirm pytest environment in CI (ensure `pytest-asyncio` installed and pinned) and run tests in clean runner.
3. Fix workspace path handling (remove any accidental trailing-space directory names in scripts and path resolution).

How to reproduce locally
```bash
./install.sh
./runtests.sh --unit
```

Recommended immediate actions
- Create a small compatibility shim at `Nola/idv2/__init__.py` that forwards the minimal API used by tests to the current implementation (fastest path to green tests).
- Add a `.github/workflows/ci.yml` check (if not already present) that uses a clean runner, installs from `requirements.txt`, and runs `./runtests.sh --unit`.
- Add `docs/DEV_QUICKSTART.md` (created) and link it in `README.md` for reviewers.

Useful links
- Main docs index: `docs/README.md`
- Changelog: `docs/logs/CHANGELOG.md`
- Developer notes: `docs/DEV_NOTES.md`
