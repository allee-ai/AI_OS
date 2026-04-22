#!/bin/bash
# One-time setup: enable lid-shut autonomy.
#
# Sets pmset -a disablesleep 1 (Apple-supported, documented flag) so
# the Mac does NOT sleep when the lid closes, even without an external
# display. Also disables idle sleep on AC so the server, LaunchAgents,
# and AppleScript keystroke paths all keep working lid-shut.
#
# Trade-offs:
#   - Battery drains while lid is shut — plug it in.
#   - Internal backlight still turns off (separate lid sensor).
#   - Thermal: M4 Air is fanless; SoC manages heat regardless of lid.
#
# Undo:   sudo pmset -a disablesleep 0
# Check:  pmset -g custom | grep -i sleep

set -eu

echo "current pmset (relevant keys):"
pmset -g custom | grep -iE "disablesleep|sleep |displaysleep|disksleep" | head -8 || true
echo
echo "about to run:"
echo "  sudo pmset -a disablesleep 1"
echo "  sudo pmset -c displaysleep 0 sleep 0 disksleep 0"
echo

sudo pmset -a disablesleep 1
sudo pmset -c displaysleep 0 sleep 0 disksleep 0

echo
echo "new pmset state:"
pmset -g custom | grep -iE "disablesleep|sleep |displaysleep|disksleep" | head -8
echo
echo "done. lid can now shut on AC without sleeping."
echo "undo:  sudo pmset -a disablesleep 0"
