#!/bin/bash
# macOS Double-Click Launcher for AI_OS
# This file enables double-clicking in Finder to start AI_OS

set -e

# Change to the directory where this launcher lives (repo root)
cd "$(dirname "$0")"

# First time setup - run installer if not yet installed
if [ ! -f ".aios_installed" ]; then
    echo "First time setup detected!"
    chmod +x scripts/install.sh 2>/dev/null || true
    ./scripts/install.sh
    exit 0
fi

# Cross-platform browser opener
open_url() {
    local url="$1"
    case "$(uname -s)" in
        Darwin*)  open "$url" 2>/dev/null || true ;;
        Linux*)   xdg-open "$url" 2>/dev/null || sensible-browser "$url" 2>/dev/null || true ;;
        MINGW*|MSYS*|CYGWIN*)  start "$url" 2>/dev/null || true ;;
    esac
}

# Check if daemon is running (macOS LaunchAgent feature)
PLIST_NAME="com.aios.server"
daemon_running() {
    command -v launchctl >/dev/null 2>&1 && launchctl list 2>/dev/null | grep -q "$PLIST_NAME"
}

daemon_installed() {
    [ -f "$HOME/Library/LaunchAgents/$PLIST_NAME.plist" ]
}

# Daemon serves built frontend on port 8000 (no Vite/Node needed)
AIOS_URL="http://localhost:8000"

wait_for_server() {
    local attempts=0
    while [ $attempts -lt 15 ]; do
        if curl -sf "$AIOS_URL/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
        attempts=$((attempts + 1))
    done
    return 1
}

# If daemon is running, just open browser
if daemon_running; then
    echo "AI OS daemon is running. Opening browser..."
    open_url "$AIOS_URL"
    exit 0
fi

# If daemon is installed but not running, start it
if daemon_installed; then
    echo "Starting AI OS daemon..."
    launchctl load "$HOME/Library/LaunchAgents/$PLIST_NAME.plist" 2>/dev/null || true
    if wait_for_server; then
        echo "Daemon started. Opening browser..."
        open_url "$AIOS_URL"
        exit 0
    fi
fi

# Install daemon if not present, then start
if [ -f "./scripts/install_daemon.sh" ]; then
    echo "Installing AI OS daemon for always-on operation..."
    chmod +x "./scripts/install_daemon.sh" 2>/dev/null || true
    ./scripts/install_daemon.sh install
    if wait_for_server; then
        echo "Daemon installed and running. Opening browser..."
        open_url "$AIOS_URL"
        exit 0
    fi
fi

# Final fallback: run start.sh directly
if [ -f "./scripts/start.sh" ] && [ ! -x "./scripts/start.sh" ]; then
  chmod +x "./scripts/start.sh" 2>/dev/null || true
fi

./scripts/start.sh