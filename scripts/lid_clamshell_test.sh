#!/bin/bash
# Lid-shut clamshell keystroke test.
#
# Arms a delayed AppleScript paste into VS Code Copilot chat. After you
# run this:
#   1. Close the lid immediately (script has a 90s grace period)
#   2. Wait until the 'armed:done' ntfy ping hits your phone (~3 min)
#   3. Open the lid and look at the Copilot chat in VS Code
#
# Expected if clamshell clamp works as documented: the paste never runs
# because the Mac sleeps → no response token in chat.
#
# What we're testing: whether AppleScript System Events keystroke
# delivery still functions while the lid is shut on a MacBook Air M4
# running macOS 15.7.3 Sequoia on AC power with `caffeinate -s` active.
set -eu
cd "$(dirname "$0")/.."

TOKEN="LIDTEST_$(date +%s)"
PROMPT="respond with only this exact token and nothing else: ${TOKEN}"
GRACE=90
POST_WAIT=60
LOG="data/logs/lid_test_${TOKEN}.log"
mkdir -p data/logs

echo "=== lid clamshell test ${TOKEN} ==="                           | tee "$LOG"
echo "start: $(date '+%F %T')"                                       | tee -a "$LOG"
pmset -g | head -3                                                   | tee -a "$LOG"
pmset -g ps | head -1                                                | tee -a "$LOG"
pmset -g assertions | grep -E "System|Display|clamshell" | head -5   | tee -a "$LOG"

# Fire a "go close the lid now" ping.
.venv/bin/python scripts/ping.py "lid test ${TOKEN} armed — close lid now, wait 3min, open it. expect token in chat." \
    --priority urgent --source lid_test >/dev/null 2>&1 || true

echo "sleeping ${GRACE}s (close lid NOW)..." | tee -a "$LOG"
sleep "$GRACE"

echo "paste attempt at $(date '+%F %T')" | tee -a "$LOG"
pmset -g assertions | grep -E "System|Display|clamshell" | head -5 | tee -a "$LOG"

# Fire the paste. --submit is the default, so Copilot should actually receive.
.venv/bin/python scripts/send_to_vs.py "$PROMPT" --idle-seconds 0 > "${LOG}.stdout" 2> "${LOG}.stderr"
RC=$?
echo "send_to_vs rc=$RC" | tee -a "$LOG"
[[ -s "${LOG}.stderr" ]] && { echo "stderr:"; cat "${LOG}.stderr"; } | tee -a "$LOG"

# Wait a bit for Copilot to respond (if the paste landed at all).
echo "waiting ${POST_WAIT}s for Copilot response..." | tee -a "$LOG"
sleep "$POST_WAIT"

# Final ping so your phone knows to open the lid and check.
.venv/bin/python scripts/ping.py "lid test ${TOKEN} done — open lid, look for '${TOKEN}' in Copilot chat. rc=$RC" \
    --priority high --source lid_test >/dev/null 2>&1 || true

echo "end: $(date '+%F %T')" | tee -a "$LOG"
echo "log: $LOG"
echo "TOKEN to look for in chat: $TOKEN"
