
# Changelog

All notable changes to this repository are documented below. Entries are grouped by date and describe features added, architecture changes, and notable fixes.

## 2025-12-15 — React Chat Stimuli Channel Integration

- **Integrated React UI as a stimuli channel:** React chat app now acts as an external stimuli source for the agent pipeline.
- **Backend integration:** `react-chat-app/backend/services/agent_service.py` now routes messages through the Nola agent via `Nola.generate(user_input, convo, stimuli_type)`.
- **Conversation persistence:** Conversations from the React channel persist to `Stimuli/conversations/react_*.json` and include metadata fields: `session_id`, `channel`, timestamps, `stimuli_type`, and `context_level` per turn.
- **Context management:** Implemented HEA (Hierarchical Experiential Attention) to classify stimuli and automatically escalate/de-escalate context levels (L1/L2/L3).
- **Onboarding script:** Added a root-level `start.sh` for one-click local onboarding (checks prerequisites, sets up virtual environment, starts FastAPI backend and Vite frontend, and opens the browser).

## 2025-12-13 — Architecture Overhaul

- **Agent refactor:** Converted the agent to a thread-safe singleton with `Lock` and atomic file writes (tempfile + `fsync` + replace).
- **Auto-bootstrap:** `get_agent()` triggers a full sync chain on first call to ensure consistent initial state.
- **Contracts & metadata protocol:** Added `contract.py` to standardize inter-thread metadata with helpers: `create_metadata()`, `should_sync()`, `is_stale()`, `mark_synced()`, and `request_sync()`.
- **Hierarchical state sync:** Implemented a sync chain: `machineID.json` → `identity.json` → `Nola.json` with metadata-driven sync decisions.
- **JSON layout change:** Each identity file now follows the shape `{ "metadata": {...}, "data": {...} }` separating control plane (metadata) from data plane (config/state).
- **Context levels:** Defined context levels: 1 = minimal (realtime), 2 = moderate (default), 3 = full (analytical).
- **Agent API improvements:** Added and clarified methods: `get_state()`, `set_state()`, `reload_state()`, `bootstrap()`, `generate()`, and `introspect()`.
- **Removed bootstrap.py:** Bootstrapping moved into `Agent.bootstrap()` for clearer lifecycle management.

## 2025-12-07 — Miscellaneous updates and housekeeping

- **Renamed agent profile:** Renamed agent previously called `alex` to `nola` in `agent.py`.
- **Stimuli and utilities:** Created `Stimuli/` folder for external stimuli control and added phone/email modules plus `utils.py` developer helpers (conversation append, set chat id, etc.).
- **Identity/threading improvements:** Implemented a thread system and moved `personal`/`work` into identity threads; later changed `personal` to `machineID` and `work` to `userID`.
- **Conversation file handling:** Added new-chat/old-chat functionality; each chat now has an ID, name, and separate file.

## Notes / Telemetry

- Several automated conversation session entries were recorded for diagnostics.

## Files added / modified (high level)

- `start.sh` (root-level onboarding script)
- `notes.txt` (cross-agent assessment workflow)
- `react-chat-app/backend/services/agent_service.py` (Nola integration)
- `contract.py` (metadata protocol)
- Updated identity modules: `identity.py`, `machineID.py`, `user.py` to use the metadata contract
- `Nola/` (agent and supporting modules)

## 2025-12-17 — Repo reorganization & cleanup

 - **Portability fixes (startup & interpreter):** Fixed hard-coded interpreter and startup invocation to improve cross-machine launches — changed `.venv/bin/uvicorn` shebang to `/usr/bin/env python3` and updated `start.sh` to invoke the project's virtualenv explicitly with `"$VENV_DIR/bin/python" -m uvicorn`, ensuring the program uses its own environment rather than a user-specific Python.



