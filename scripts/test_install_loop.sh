#!/bin/bash
# Test Install Loop - Simulates fresh user experience
# Run this to test the installer repeatedly

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║            🧪 AI OS Install Test Loop                     ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Function to clean everything
clean_install() {
    echo "🧹 Cleaning previous install..."
    
    # Remove install marker
    rm -f "$REPO_ROOT/.aios_installed"
    
    # Remove generated app bundle
    rm -rf "$REPO_ROOT/AI OS.app"
    rm -rf "$REPO_ROOT/scripts/AIOS.app"
    
    # Remove databases (fresh state)
    rm -f "$REPO_ROOT/data/db/"*.db
    rm -f "$REPO_ROOT/data/db/"*.db-shm
    rm -f "$REPO_ROOT/data/db/"*.db-wal
    
    # Remove node_modules and venv (full clean)
    # Uncomment these for FULL reset (slower):
    # rm -rf "$REPO_ROOT/frontend/node_modules"
    # rm -rf "$REPO_ROOT/.venv"
    
    # Remove any cached Python files
    find "$REPO_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$REPO_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true
    
    # Remove Feeds conversations
    rm -rf "$REPO_ROOT/Feeds/conversations/"*.json 2>/dev/null || true
    
    echo "✅ Clean complete"
}

# Function to simulate download (reset permissions like a fresh download)
simulate_download() {
    echo "📦 Simulating fresh download (resetting permissions)..."
    
    # Remove execute permissions (like a fresh .tar/.zip download)
    chmod -x "$REPO_ROOT/run.command" 2>/dev/null || true
    chmod -x "$REPO_ROOT/scripts/"*.sh 2>/dev/null || true
    chmod -x "$REPO_ROOT/scripts/"*.command 2>/dev/null || true
    
    echo "✅ Permissions reset (simulating downloaded archive)"
}

# Main loop
while true; do
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  TEST CYCLE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Step 1: Clean
    clean_install
    
    # Step 2: Simulate download
    simulate_download
    
    echo ""
    echo "🚀 Ready for testing!"
    echo ""
    echo "   Now manually test:"
    echo "   1. Double-click run.command in Finder"
    echo "   2. (First time: Right-click → Open to bypass Gatekeeper)"
    echo "   3. Watch the install process"
    echo "   4. Test the app"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    read -p "Press ENTER when done testing to run another cycle (Ctrl+C to exit)... "
done
