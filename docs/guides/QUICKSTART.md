# Developer Quickstart

3 commands to get the project running locally and run unit tests.

Prerequisites
- macOS / Linux / Windows (WSL) with Git
- Python 3.11 (venv recommended)
- Node.js (for frontend) — optional for some features
- Ollama (optional for local LLM runtime)

Clone, install, test, run
```bash
git clone https://github.com/allee-ai/AI_OS.git
cd AI_OS
cp .env.example .env        # optional: add API keys for extended features
./install.sh                # creates app bundle, installs deps
./runtests.sh --unit        # run unit tests
./start.sh                  # start local backend + frontend
```

Notes
- If tests fail, run `./runtests.sh --unit` and inspect `eval/transcripts/` for test logs.
- Use the Docker flow (`./start-docker.sh`) if you prefer containerized runs (Ollama required on host).

Where to get help
- See `docs/README.md` for full docs index.
- Open an issue on GitHub if you hit environment-specific blockers.
