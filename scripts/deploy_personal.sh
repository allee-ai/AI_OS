#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Deploy personal Nola instance to a $6/mo DigitalOcean droplet
# ─────────────────────────────────────────────────────────────
#
# Usage:
#   1. doctl auth init                    (paste your DO API token)
#   2. export ANTHROPIC_API_KEY=sk-ant-...
#   3. bash scripts/deploy_personal.sh
#
# What it does:
#   - Creates a 1GB Ubuntu droplet ($6/mo)
#   - Installs Python 3.12, uv, Node, npm
#   - Clones repo, builds frontend, syncs deps
#   - Sets up systemd service with Claude as provider
#   - Prints your dashboard URL
#
# SSH in:   ssh -i ~/.ssh/do_droplet root@<IP>
# Logs:     ssh ... journalctl -u aios -f
# Teardown: doctl compute droplet delete nola-personal --force
# ─────────────────────────────────────────────────────────────

set -euo pipefail

# ── Config ──────────────────────────────────────────────────

DROPLET_NAME="nola-personal"
REGION="nyc1"
SIZE="s-1vcpu-1gb"          # $6/mo
IMAGE="ubuntu-24-04-x64"
SSH_KEY_NAME="do_droplet"
SSH_KEY_PATH="$HOME/.ssh/do_droplet"
REPO="https://github.com/allee-ai/AI_OS.git"
BRANCH="main"
MOBILE_TOKEN="${AIOS_MOBILE_TOKEN:-$(openssl rand -hex 16)}"
PROVIDER="claude"
MODEL="claude-sonnet-4-20250514"

# ── Helpers ─────────────────────────────────────────────────

log()  { echo "▸ $*"; }
ok()   { echo "✓ $*"; }
err()  { echo "✗ $*" >&2; }

ssh_cmd() {
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
        -i "$SSH_KEY_PATH" "root@${DROPLET_IP}" "$@"
}

# ── Validate ────────────────────────────────────────────────

log "Checking prerequisites..."

command -v doctl &>/dev/null || { err "doctl not found. Run: brew install doctl && doctl auth init"; exit 1; }
doctl account get &>/dev/null || { err "doctl not authenticated. Run: doctl auth init"; exit 1; }
ok "doctl authenticated"

[ -f "$SSH_KEY_PATH" ] || { err "SSH key not found at $SSH_KEY_PATH"; exit 1; }
ok "SSH key found"

[ -n "${ANTHROPIC_API_KEY:-}" ] || { err "ANTHROPIC_API_KEY not set. Run: export ANTHROPIC_API_KEY=sk-ant-..."; exit 1; }
ok "Anthropic key set"

# Get SSH key ID from DO
SSH_KEY_ID=$(doctl compute ssh-key list --format ID,Name --no-header | grep "$SSH_KEY_NAME" | awk '{print $1}' | head -1)
if [ -z "$SSH_KEY_ID" ]; then
    log "Uploading SSH key to DigitalOcean..."
    SSH_KEY_ID=$(doctl compute ssh-key import "$SSH_KEY_NAME" --public-key-file "${SSH_KEY_PATH}.pub" --format ID --no-header)
fi
ok "SSH key ID: $SSH_KEY_ID"

# ── Create Droplet ──────────────────────────────────────────

if doctl compute droplet list --format Name --no-header | grep -q "^${DROPLET_NAME}$"; then
    log "$DROPLET_NAME already exists"
    DROPLET_IP=$(doctl compute droplet list --format Name,PublicIPv4 --no-header | grep "^${DROPLET_NAME} " | awk '{print $2}')
else
    log "Creating $DROPLET_NAME ($SIZE in $REGION)..."
    doctl compute droplet create "$DROPLET_NAME" \
        --region "$REGION" \
        --size "$SIZE" \
        --image "$IMAGE" \
        --ssh-keys "$SSH_KEY_ID" \
        --wait \
        --tag-name "nola"
    ok "Droplet created"

    sleep 10  # wait for IP assignment
    DROPLET_IP=$(doctl compute droplet list --format Name,PublicIPv4 --no-header | grep "^${DROPLET_NAME} " | awk '{print $2}')
fi

[ -n "$DROPLET_IP" ] || { err "Could not get IP for $DROPLET_NAME"; exit 1; }
ok "IP: $DROPLET_IP"

# ── Wait for SSH ────────────────────────────────────────────

log "Waiting for SSH..."
elapsed=0
while ! ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i "$SSH_KEY_PATH" "root@${DROPLET_IP}" "echo ok" &>/dev/null; do
    sleep 5
    elapsed=$((elapsed + 5))
    if [ $elapsed -ge 120 ]; then
        err "SSH timeout after 120s"
        exit 1
    fi
done
ok "SSH ready"

# ── Provision ───────────────────────────────────────────────

log "Provisioning (this takes 2-3 min)..."

# Clone repo first (needs variable interpolation)
ssh_cmd "if [ ! -d /opt/aios ]; then git clone --depth 1 --branch $BRANCH $REPO /opt/aios; else cd /opt/aios && git pull --ff-only; fi"

ssh_cmd bash <<'PROVISION'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "▸ Installing system packages..."
apt-get update -qq
apt-get install -y -qq git curl build-essential python3.12 python3.12-venv nodejs npm > /dev/null

echo "▸ Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

cd /opt/aios

echo "▸ Installing Python deps..."
$HOME/.local/bin/uv sync --frozen --no-dev --no-editable

echo "▸ Building frontend..."
cd frontend && npm ci --silent && npm run build && cd ..

echo "▸ Creating data dirs..."
mkdir -p /opt/aios/data/db /opt/aios/data/logs

echo "✓ Provision complete"
PROVISION

# ── Configure ───────────────────────────────────────────────

log "Writing .env..."
ssh_cmd "cat > /opt/aios/.env" <<ENV
AIOS_MODE=personal
AIOS_MODEL_PROVIDER=$PROVIDER
AIOS_MODEL_NAME=$MODEL
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
AIOS_MOBILE_TOKEN=$MOBILE_TOKEN
AIOS_LLM_ENABLED=true
AIOS_LOOPS=1
ENV

log "Configuring git identity..."
ssh_cmd "cd /opt/aios && git config user.email 'nola@personal.local' && git config user.name 'Nola'"

log "Setting up systemd service..."
ssh_cmd "cat > /etc/systemd/system/aios.service" <<SERVICE
[Unit]
Description=AI_OS (Nola Personal)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/aios
EnvironmentFile=/opt/aios/.env
ExecStart=/root/.local/bin/uv run uvicorn scripts.server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

ssh_cmd "echo 'root ALL=(ALL) NOPASSWD: /bin/systemctl restart aios' > /etc/sudoers.d/aios-restart"
ssh_cmd "systemctl daemon-reload && systemctl enable aios && systemctl restart aios"

# ── Wait for Health ─────────────────────────────────────────

log "Waiting for service to start..."
sleep 5
for i in $(seq 1 12); do
    if ssh_cmd "curl -sf http://localhost:8000/health" &>/dev/null; then
        ok "Service healthy!"
        break
    fi
    sleep 5
done

# ── Done ────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  ✓  NOLA DEPLOYED"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  Dashboard:  http://${DROPLET_IP}:8000"
echo "  Mobile:     http://${DROPLET_IP}:8000/api/mobile/"
echo "  API:        http://${DROPLET_IP}:8000/api/"
echo "  Health:     http://${DROPLET_IP}:8000/health"
echo ""
echo "  SSH:        ssh -i ~/.ssh/do_droplet root@${DROPLET_IP}"
echo "  Logs:       ssh -i ~/.ssh/do_droplet root@${DROPLET_IP} journalctl -u aios -f"
echo ""
echo "  Mobile Token: $MOBILE_TOKEN"
echo "  Provider:     $PROVIDER ($MODEL)"
echo ""
echo "  Cost: \$6/mo (\$0.20/day)"
echo "═══════════════════════════════════════════════════════════"
