#!/usr/bin/env bash
# Deploy a static site directory to /var/www/<DOMAIN>/public on the AI_OS droplet.
#
# Usage:
#   ./infra/deploy_site.sh <DOMAIN> <LOCAL_SOURCE_DIR>
#
# Examples:
#   ./infra/deploy_site.sh allee-ai.com workspace/allee-ai.github.io
#   ./infra/deploy_site.sh bycade.com workspace/bycade-site
#
# Prerequisites on droplet:
#   - SSH host alias 'AIOS' resolves to the droplet (already configured)
#   - /var/www/<DOMAIN>/public exists and is writable by the SSH user
#       sudo mkdir -p /var/www/<DOMAIN>/public
#       sudo chown -R $USER:caddy /var/www/<DOMAIN>
#       sudo chmod 755 /var/www/<DOMAIN> /var/www/<DOMAIN>/public
#   - Caddyfile on droplet has a site block for <DOMAIN> (use Caddyfile.site.template)
#
# What this script does:
#   - rsync local source → droplet, deleting orphan files
#   - excludes git metadata, node_modules, .DS_Store, build caches
#   - prints a summary + one-line verification curl
#
# What it does NOT do:
#   - touch DNS
#   - touch the Caddyfile
#   - issue certs (Caddy does that on first request)
#   - take a snapshot before deploying
#
# Standing rule: this is a script, not an inline command. Edit it; don't paste
# rsync flags into the terminal directly.

set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "usage: $0 <DOMAIN> <LOCAL_SOURCE_DIR>" >&2
    echo "example: $0 allee-ai.com workspace/allee-ai.github.io" >&2
    exit 2
fi

DOMAIN="$1"
SRC="$2"
DROPLET_HOST="${AIOS_DROPLET_HOST:-AIOS}"
REMOTE_PATH="/var/www/${DOMAIN}/public/"

if [[ ! -d "$SRC" ]]; then
    echo "error: source dir does not exist: $SRC" >&2
    exit 1
fi

# Trim trailing slash for consistent rsync semantics, then add one
SRC="${SRC%/}/"

echo "── Deploying ──"
echo "  domain : $DOMAIN"
echo "  source : $SRC"
echo "  remote : ${DROPLET_HOST}:${REMOTE_PATH}"
echo

rsync -avz --delete --human-readable \
    --exclude '.git/' \
    --exclude '.gitignore' \
    --exclude '.github/' \
    --exclude 'node_modules/' \
    --exclude '.next/' \
    --exclude '.cache/' \
    --exclude '.DS_Store' \
    --exclude '*.log' \
    --exclude 'aios-demo/node_modules/' \
    --exclude 'aios-demo/.next/' \
    "$SRC" \
    "${DROPLET_HOST}:${REMOTE_PATH}"

echo
echo "── Done — verify ──"
echo "  curl -sI https://${DOMAIN}/ | head -5"
echo "  (if DNS not yet cut over, test via Host header):"
echo "  curl -sI -H 'Host: ${DOMAIN}' http://24.144.115.72/ | head -5"
