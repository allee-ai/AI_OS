#!/bin/bash
set -e
# Change to the directory where this launcher lives (repo root)
cd "$(dirname "$0")"

# Ensure start.sh is executable if possible
if [ -f "./start.sh" ] && [ ! -x "./start.sh" ]; then
  chmod +x "./start.sh" 2>/dev/null || true
fi

# Run the start script
./start.sh

echo
read -n 1 -s -r -p "Press any key to close..."
