#!/usr/bin/env bash
# scripts/run_eval_bg.sh — launch state-vs-bare eval detached, with clean logging.
set -u
cd "$(dirname "$0")/.."

LOG=data/logs/state_vs_bare_run.log
: > "$LOG"

nohup .venv/bin/python scripts/run_state_vs_bare.py >> "$LOG" 2>&1 &
PID=$!
disown || true
echo "started PID=$PID log=$LOG"
