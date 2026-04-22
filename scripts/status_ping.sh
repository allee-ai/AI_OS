#!/usr/bin/env bash
# scripts/status_ping.sh — Assemble a short status snapshot and send it
# through the notify tool so it hits mac + phone.

set -u
cd "$(dirname "$0")/.."

# Collect signals. Keep it terse; ntfy pushes truncate aggressively.
eval_proc=$(pgrep -fl run_state_vs_bare 2>/dev/null | head -1 || true)
eval_json=$(ls -t eval/state_vs_bare_*.json 2>/dev/null | head -1 || true)
eval_tail=$(tail -1 data/logs/state_vs_bare_run.log 2>/dev/null | head -c 120)
battery=$(pmset -g ps 2>/dev/null | awk '/InternalBattery/ {print $3 $4}' | tr -d ';' | head -c 40)
caffeinate=$(pgrep -fl "caffeinate" 2>/dev/null | head -1 | awk '{print $1}')
uptime_load=$(uptime | awk -F'load averages:' '{print $2}' | head -c 40)

if [ -n "$eval_proc" ]; then
  eval_status="eval running"
elif [ -n "$eval_json" ]; then
  eval_status="eval done: $(basename "$eval_json")"
else
  eval_status="eval not running / no results"
fi

msg="STATUS: ${eval_status} | last log: ${eval_tail} | battery: ${battery} | caff: ${caffeinate:-none} | load:${uptime_load}"

# Use notify tool so it writes to dashboard + chimes + phone buzzes.
.venv/bin/python scripts/aios.py notify alert \
  message="$msg" \
  priority=high 2>&1 | tail -2
