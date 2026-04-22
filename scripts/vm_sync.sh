#!/usr/bin/env bash
# scripts/vm_sync.sh — push local → pull VM → verify.
#
# One command to keep the AIOS VM in lockstep with local main.
# Usage:
#   scripts/vm_sync.sh                   # push + pull + ritual check
#   scripts/vm_sync.sh --no-push         # skip push (VM pulls whatever is on origin)
#   scripts/vm_sync.sh --restart         # also restart the VM aios service
#
# Requires: ~/.ssh/config entry named 'AIOS', /opt/aios/.venv on VM.

set -euo pipefail

DO_PUSH=1
DO_RESTART=0
for arg in "$@"; do
    case "$arg" in
        --no-push) DO_PUSH=0 ;;
        --restart) DO_RESTART=1 ;;
        -h|--help)
            grep '^#' "$0" | head -20
            exit 0 ;;
    esac
done

# ---------- local push ----------
if [[ $DO_PUSH -eq 1 ]]; then
    echo "[local] git push origin main"
    unpushed=$(git log origin/main..HEAD --oneline || true)
    if [[ -n "$unpushed" ]]; then
        echo "        unpushed commits:"
        echo "$unpushed" | sed 's/^/          /'
    fi
    git push origin main
else
    echo "[local] skipping push (--no-push)"
fi

# ---------- remote pull ----------
echo ""
echo "[vm] ssh AIOS — pulling into /opt/aios"
ssh -o BatchMode=yes -o ConnectTimeout=8 AIOS bash -s <<'REMOTE'
set -e
cd /opt/aios

dirty=$(git status --porcelain | grep -E '^ M|^M |^ D|^D ' || true)
if [[ -n "$dirty" ]]; then
    stamp=$(date +%Y-%m-%d_%H%M%S)
    echo "  [warn] VM has tracked-file changes — stashing as 'vm_sync_auto_${stamp}'"
    echo "$dirty" | sed 's/^/         /'
    git stash push -m "vm_sync_auto_${stamp}" -- $(echo "$dirty" | awk '{print $2}' | xargs)
fi

git fetch origin main --quiet
behind=$(git rev-list --count HEAD..origin/main)
if [[ "$behind" == "0" ]]; then
    echo "  VM already at origin/main ($(git rev-parse --short HEAD))"
else
    echo "  pulling $behind commit(s)"
    git pull --ff-only
fi
echo "  head: $(git log -1 --oneline)"
REMOTE

# ---------- optional restart ----------
if [[ $DO_RESTART -eq 1 ]]; then
    echo ""
    echo "[vm] restarting aios service (requires sudo on VM)"
    ssh AIOS 'sudo systemctl restart aios || echo "(service not found — skipping)"'
fi

# ---------- ritual check ----------
echo ""
echo "[vm] ritual check"
ssh AIOS '/opt/aios/.venv/bin/python /opt/aios/scripts/turn_start.py "vm_sync post-pull check" 2>&1 | head -8'

echo ""
echo "[done] vm_sync complete."
