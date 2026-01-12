#!/bin/bash
# macOS Double-Click Launcher for AI_OS
# This file enables double-clicking in Finder to start AI_OS

set -e

# Change to the directory where this launcher lives (repo root)
cd "$(dirname "$0")"

# First time setup - run installer if not yet installed
if [ ! -f ".nola_installed" ]; then
    echo "🎉 First time setup detected!"
    chmod +x install.sh 2>/dev/null || true
    ./install.sh
    exit 0
fi

# Ensure start.sh is executable
if [ -f "./start.sh" ] && [ ! -x "./start.sh" ]; then
  chmod +x "./start.sh" 2>/dev/null || true
fi

# Execute the universal launcher (now integrated into start.sh)
./start.sh