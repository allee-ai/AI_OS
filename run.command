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

# Check if daemon is running (background feature)
PLIST_NAME="com.aios.server"
daemon_running() {
    launchctl list 2>/dev/null | grep -q "$PLIST_NAME"
}

daemon_installed() {
    [ -f "$HOME/Library/LaunchAgents/$PLIST_NAME.plist" ]
}

# If daemon is running, just open browser
if daemon_running; then
    echo "AI OS daemon is running. Opening browser..."
    sleep 1
    open "http://localhost:5173" 2>/dev/null || open "http://127.0.0.1:5173" 2>/dev/null || true
    exit 0
fi

# If daemon is installed but not running, start it
if daemon_installed; then
    echo "Starting AI OS daemon..."
    launchctl load "$HOME/Library/LaunchAgents/$PLIST_NAME.plist" 2>/dev/null || true
    sleep 2
    if daemon_running; then
        echo "Daemon started. Opening browser..."
        open "http://localhost:5173" 2>/dev/null || open "http://127.0.0.1:5173" 2>/dev/null || true
        exit 0
    fi
fi

# Fallback: run start.sh directly (also offers daemon install)
if [ -f "./scripts/start.sh" ] && [ ! -x "./scripts/start.sh" ]; then
  chmod +x "./scripts/start.sh" 2>/dev/null || true
fi

./scripts/start.sh