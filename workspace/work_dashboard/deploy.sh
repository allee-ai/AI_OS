#!/bin/bash
set -e

SERVER="root@159.223.195.100"
APP_DIR="/opt/jake-app"

echo "=== Building frontend ==="
cd "$(dirname "$0")/frontend"
npm run build
cd ..

DRY_RUN_FLAG=""
if [ "$1" = "--dry-run" ] || [ "$1" = "-n" ]; then
  DRY_RUN_FLAG="--dry-run"
  echo "*** DRY RUN — no changes will be made ***"
fi

echo ""
echo "=== Pushing to VM ==="
rsync -avz --delete $DRY_RUN_FLAG \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.git' \
  --exclude 'data' \
  --exclude '*.db' \
  --exclude '*.sqlite*' \
  --exclude 'frontend/node_modules' \
  --exclude 'frontend/src' \
  --exclude 'frontend/index.html' \
  --exclude 'frontend/vite.config.ts' \
  --exclude 'frontend/tsconfig.json' \
  --exclude 'frontend/package.json' \
  --exclude 'frontend/package-lock.json' \
  -e ssh \
  "$(dirname "$0")/" "$SERVER:$APP_DIR/"

if [ -n "$DRY_RUN_FLAG" ]; then
  echo ""
  echo "Dry run complete. Re-run without --dry-run to deploy."
  exit 0
fi

echo ""
echo "=== Restarting service ==="
ssh "$SERVER" bash -s << 'REMOTE'
cd /opt/jake-app
.venv/bin/pip install -q -r requirements.txt
DATABASE_URL=postgresql://jake_app:jk_pg_2026@localhost:5432/jake_app .venv/bin/python seed_users.py
systemctl restart jake-app
echo "Done — app restarted"
REMOTE
