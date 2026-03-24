#!/bin/bash
# Shell script preview test — workspace FileViewer syntax highlighting

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP_NAME="ai-os"
PORT="${AIOS_PORT:-8000}"

echo "🧠 Deploying ${APP_NAME}..."

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "Python 3 required"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js required"; exit 1; }

# Build frontend
if [ -d "${REPO_ROOT}/frontend" ]; then
    echo "📦 Building frontend..."
    cd "${REPO_ROOT}/frontend"
    npm ci --silent
    npm run build
    echo "✅ Frontend built"
fi

# Install Python deps
cd "${REPO_ROOT}"
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
fi

# Run migrations
python3 -c "from agent.core.migrations import ensure_all_schemas; ensure_all_schemas()"

# Start server
echo "🚀 Starting on port ${PORT}..."
exec uvicorn scripts.server:app --host 0.0.0.0 --port "${PORT}"
