#!/usr/bin/env bash
#
# scripts/sleep_off.sh — make the Mac never sleep, lid close included.
#
# Two levers:
#   1. LaunchAgent (no sudo): runs caffeinate -dimsu forever, survives reboot.
#   2. pmset disablesleep (sudo): the ONLY setting that truly ignores lid close
#      on battery too. Without this, clamshell sleep can still override caffeinate.
#
# Usage:
#   bash scripts/sleep_off.sh on     # install launchagent + disablesleep=1
#   bash scripts/sleep_off.sh off    # revert both
#   bash scripts/sleep_off.sh status # show current state
#
# Verify after `on`:
#   pmset -g | grep -E "SleepDisabled|sleep"
#   launchctl list | grep aios
#   pgrep -fl caffeinate
#
set -u

LABEL="com.aios.caffeinate"
SRC="$(cd "$(dirname "$0")" && pwd)/launchagents/${LABEL}.plist"
DST="$HOME/Library/LaunchAgents/${LABEL}.plist"

case "${1:-status}" in
  on)
    echo "[sleep_off] installing launchagent -> $DST"
    mkdir -p "$HOME/Library/LaunchAgents"
    cp "$SRC" "$DST"
    launchctl unload "$DST" 2>/dev/null || true
    launchctl load "$DST"
    launchctl start "$LABEL" 2>/dev/null || true
    echo "[sleep_off] requesting sudo to set pmset disablesleep=1 (lid-close ignored)"
    sudo pmset -a disablesleep 1
    sudo pmset -a sleep 0 displaysleep 0 disksleep 0 2>/dev/null || true
    echo "[sleep_off] done. current pmset:"
    pmset -g | grep -E "SleepDisabled|^ sleep|displaysleep|disksleep" | head -6
    echo "[sleep_off] caffeinate:"
    pgrep -fl caffeinate | head -3
    ;;
  off)
    echo "[sleep_off] unloading launchagent"
    if [ -f "$DST" ]; then
      launchctl unload "$DST" 2>/dev/null || true
      rm -f "$DST"
    fi
    echo "[sleep_off] requesting sudo to restore pmset defaults"
    sudo pmset -a disablesleep 0
    sudo pmset -a sleep 1 displaysleep 10 disksleep 10 2>/dev/null || true
    echo "[sleep_off] done. current pmset:"
    pmset -g | grep -E "SleepDisabled|^ sleep|displaysleep|disksleep" | head -6
    ;;
  status)
    echo "[sleep_off] launchagent file: $([ -f "$DST" ] && echo INSTALLED || echo missing)"
    echo "[sleep_off] launchctl list:"
    launchctl list | grep aios || echo "  (none)"
    echo "[sleep_off] caffeinate procs:"
    pgrep -fl caffeinate | head -3 || echo "  (none)"
    echo "[sleep_off] pmset:"
    pmset -g | grep -E "SleepDisabled|^ sleep|displaysleep|disksleep" | head -6
    ;;
  *)
    echo "usage: $0 {on|off|status}" >&2
    exit 2
    ;;
esac
