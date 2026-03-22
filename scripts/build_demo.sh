#!/usr/bin/env bash
# Build the demo app and deploy to GitHub Pages.
# Usage:
#   ./scripts/build_demo.sh              # fix data + build + deploy
#   ./scripts/build_demo.sh --capture    # capture from live server first
#   ./scripts/build_demo.sh --no-push    # build but don't git push
set -euo pipefail
cd "$(dirname "$0")/.."

CAPTURE=false
PUSH=true
for arg in "$@"; do
    case "$arg" in
        --capture) CAPTURE=true ;;
        --no-push) PUSH=false ;;
    esac
done

SITE_DIR="workspace/allee-ai.github.io"
DEMO_DIR="$SITE_DIR/aios-demo"

if [ ! -d "$SITE_DIR" ]; then
    echo "Error: $SITE_DIR not found. Clone the website repo first."
    exit 1
fi

# Step 1 (optional): Capture live API data
if $CAPTURE; then
    echo "==> Capturing live API data..."
    python3 scripts/capture_demo_data.py
fi

# Step 2: Fix/inject graph data (structural solar system, cooccurrence, etc.)
echo "==> Fixing demo graph data..."
python3 scripts/fix_demo_graph.py

# Step 3: Fix chat STATE sidebar + conversation dates
echo "==> Fixing chat/STATE data..."
python3 scripts/fix_demo_chat.py

# Step 4: Build frontend with demo mode
echo "==> Building frontend (demo mode)..."
cd frontend
VITE_DEMO_MODE=true npx vite build --base=/aios-demo/ --outDir=dist-demo
cd ..

# Step 4: Deploy to website repo
echo "==> Deploying to $DEMO_DIR..."
rm -rf "$DEMO_DIR/assets"
cp -r frontend/dist-demo/* "$DEMO_DIR/"

# Step 5: Commit and push
cd "$SITE_DIR"
git add -A
if git diff --cached --quiet; then
    echo "==> No changes to deploy."
else
    git commit -m "demo: rebuild $(date +%Y-%m-%d)"
    if $PUSH; then
        git push
        echo "==> Pushed to GitHub Pages."
    else
        echo "==> Committed locally (--no-push)."
    fi
fi

echo "==> Done."
