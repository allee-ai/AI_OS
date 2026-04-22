#!/usr/bin/env bash
# scripts/mobile_url.sh — print the current bookmark URL for the phone.
#
# Walks the obvious reachability layers (Tailscale → LAN → localhost) and
# prints the first that's actually live. Token is appended as ?key= so the
# phone logs in on first open.
#
# Usage:
#   bash scripts/mobile_url.sh          # just print the URL
#   bash scripts/mobile_url.sh --ping   # also fire an ntfy with it

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOKEN=""
if [[ -f "$ROOT/.env" ]]; then
  TOKEN="$(grep '^AIOS_API_TOKEN=' "$ROOT/.env" | head -1 | cut -d= -f2- | tr -d ' "')"
fi
if [[ -z "$TOKEN" ]]; then
  echo "error: AIOS_API_TOKEN not set in .env" >&2
  exit 1
fi

PORT="${AIOS_PORT:-8000}"

host=""
# 1) Tailscale if running and logged in
if command -v tailscale >/dev/null 2>&1; then
  ts_ip="$(tailscale ip -4 2>/dev/null | head -1 || true)"
  if [[ -n "$ts_ip" ]]; then
    host="$ts_ip"
    scope="tailscale (works anywhere)"
  fi
fi

# 2) Local wifi IP
if [[ -z "$host" ]]; then
  lan_ip="$(ipconfig getifaddr en0 2>/dev/null || true)"
  if [[ -z "$lan_ip" ]]; then
    lan_ip="$(ipconfig getifaddr en1 2>/dev/null || true)"
  fi
  if [[ -n "$lan_ip" ]]; then
    host="$lan_ip"
    scope="LAN (same wifi only)"
  fi
fi

# 3) Localhost (will only work on the laptop itself)
if [[ -z "$host" ]]; then
  host="localhost"
  scope="localhost (laptop only)"
fi

URL="http://${host}:${PORT}/api/mobile/?key=${TOKEN}"

echo "$URL"
echo "scope: $scope" >&2

if [[ "${1:-}" == "--ping" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    "$ROOT/.venv/bin/python" "$ROOT/scripts/ping.py" \
      "aios mobile URL ($scope): $URL" \
      --priority high --source mobile_url
  fi
fi
