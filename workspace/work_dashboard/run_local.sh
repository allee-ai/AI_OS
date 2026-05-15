#!/bin/bash
# Run jake-app entirely locally — same code, same schema, local Postgres.
# Mirrors the droplet (root@159.223.195.100:/opt/jake-app) running stack.
#
# Usage:
#   bash run_local.sh           # set up + start
#   bash run_local.sh --build   # also rebuild frontend
set -e
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
DB_NAME="jake_app"
# Local default mirrors backend/database.py fallback (no password on Mac).
export DATABASE_URL="${DATABASE_URL:-dbname=$DB_NAME}"

echo "=== Python venv ==="
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo "=== Postgres database ==="
if ! psql -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
  echo "  creating database $DB_NAME"
  createdb "$DB_NAME"
fi

echo "=== Schema + users ==="
.venv/bin/python -c "from backend.database import init_db; init_db(); print('  schema ok')"
.venv/bin/python seed_users.py

if [ "$1" = "--build" ]; then
  echo "=== Frontend build ==="
  (cd frontend && npm install --silent && npm run build)
fi

if [ ! -d frontend/dist ]; then
  echo "=== Frontend build (first run) ==="
  (cd frontend && npm install --silent && npm run build)
fi

echo ""
echo "=== Starting backend on http://localhost:$PORT ==="
echo "    login: cade / peak2026!"
echo "    Ctrl-C to stop"
echo ""
exec .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port "$PORT" --reload
