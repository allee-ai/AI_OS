#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# 3-Model Evolution Showdown — Deployment Script
# ─────────────────────────────────────────────────────────────
#
# Creates 3 x $6/mo DigitalOcean droplets, each running AI_OS
# with a different cloud LLM provider. The evolution loop runs
# for 24 hours, then we collect results.
#
# Prerequisites:
#   brew install doctl
#   doctl auth init          (paste your DO API token)
#   ssh-add ~/.ssh/do_droplet
#
# Usage:
#   export ANTHROPIC_API_KEY=sk-ant-...
#   export OPENAI_API_KEY=sk-...
#   export GEMINI_API_KEY=AI...
#   bash scripts/showdown_deploy.sh
#
# Teardown:
#   bash scripts/showdown_deploy.sh teardown
# ─────────────────────────────────────────────────────────────

set -euo pipefail

# ── Config ──────────────────────────────────────────────────

REGION="nyc1"
SIZE="s-1vcpu-1gb"            # $6/mo
IMAGE="ubuntu-24-04-x64"
SSH_KEY_NAME="do_droplet"
REPO="git@github.com-alleeai:allee-ai/AI_OS.git"
BRANCH="main"
EVOLVE_INTERVAL=1800          # 30 min between cycles

# Mobile dashboard token (shared across all 3)
MOBILE_TOKEN="${AIOS_MOBILE_TOKEN:-showdown2026}"

# The three contenders
declare -A PROVIDERS
PROVIDERS[claude]="claude:claude-sonnet-4-20250514:ANTHROPIC_API_KEY"
PROVIDERS[openai]="openai:gpt-4o:OPENAI_API_KEY"
PROVIDERS[gemini]="gemini:gemini-2.0-flash:GEMINI_API_KEY"

DROPLET_NAMES=("nola-claude" "nola-openai" "nola-gemini")
PROVIDER_KEYS=("claude" "openai" "gemini")

# ── Helpers ─────────────────────────────────────────────────

log()  { echo "▸ $*"; }
err()  { echo "✗ $*" >&2; }
ok()   { echo "✓ $*"; }

get_ssh_key_id() {
    doctl compute ssh-key list --format ID,Name --no-header \
        | grep "$SSH_KEY_NAME" | awk '{print $1}' | head -1
}

get_droplet_ip() {
    local name="$1"
    doctl compute droplet list --format Name,PublicIPv4 --no-header \
        | grep "^${name} " | awk '{print $2}'
}

wait_for_ssh() {
    local ip="$1"
    local max_wait=120
    local elapsed=0
    while ! ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i ~/.ssh/do_droplet "root@${ip}" "echo ok" &>/dev/null; do
        sleep 5
        elapsed=$((elapsed + 5))
        if [ $elapsed -ge $max_wait ]; then
            err "SSH timeout for $ip after ${max_wait}s"
            return 1
        fi
    done
    ok "SSH ready: $ip"
}

ssh_cmd() {
    local ip="$1"; shift
    ssh -o StrictHostKeyChecking=no -i ~/.ssh/do_droplet "root@${ip}" "$@"
}

# ── Teardown ────────────────────────────────────────────────

if [ "${1:-}" = "teardown" ]; then
    log "Tearing down showdown droplets..."
    for name in "${DROPLET_NAMES[@]}"; do
        if doctl compute droplet list --format Name --no-header | grep -q "^${name}$"; then
            log "Destroying $name..."
            doctl compute droplet delete "$name" --force
            ok "Destroyed $name"
        fi
    done
    exit 0
fi

# ── Validate ────────────────────────────────────────────────

log "Validating prerequisites..."

command -v doctl &>/dev/null || { err "doctl not installed. Run: brew install doctl"; exit 1; }

SSH_KEY_ID=$(get_ssh_key_id)
[ -n "$SSH_KEY_ID" ] || { err "SSH key '$SSH_KEY_NAME' not found in DO. Upload it first."; exit 1; }
ok "SSH key: $SSH_KEY_ID"

# Check API keys
[ -n "${ANTHROPIC_API_KEY:-}" ] || { err "ANTHROPIC_API_KEY not set"; exit 1; }
[ -n "${OPENAI_API_KEY:-}" ]    || { err "OPENAI_API_KEY not set"; exit 1; }
[ -n "${GEMINI_API_KEY:-}" ]    || { err "GEMINI_API_KEY not set"; exit 1; }
ok "All API keys present"

# ── Create Droplets ─────────────────────────────────────────

log "Creating 3 droplets..."

for i in 0 1 2; do
    name="${DROPLET_NAMES[$i]}"

    if doctl compute droplet list --format Name --no-header | grep -q "^${name}$"; then
        ok "$name already exists"
        continue
    fi

    log "Creating $name ($SIZE in $REGION)..."
    doctl compute droplet create "$name" \
        --region "$REGION" \
        --size "$SIZE" \
        --image "$IMAGE" \
        --ssh-keys "$SSH_KEY_ID" \
        --wait \
        --tag-name "showdown"
    ok "Created $name"
done

# Wait for IPs to propagate
sleep 10

# ── Provision Each Droplet ──────────────────────────────────

for i in 0 1 2; do
    name="${DROPLET_NAMES[$i]}"
    key="${PROVIDER_KEYS[$i]}"
    IFS=: read -r provider model key_env <<< "${PROVIDERS[$key]}"
    api_key="${!key_env}"

    ip=$(get_droplet_ip "$name")
    [ -n "$ip" ] || { err "No IP for $name"; continue; }
    log "Provisioning $name ($ip) — provider=$provider model=$model"

    wait_for_ssh "$ip"

    # Upload provisioning script
    ssh_cmd "$ip" "cat > /root/provision.sh" <<PROVISION_SCRIPT
#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# ── System deps ─────────────────────────────────────
apt-get update -qq
apt-get install -y -qq git curl build-essential python3.12 python3.12-venv nodejs npm

# ── Install uv ──────────────────────────────────────
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="\$HOME/.local/bin:\$PATH"

# ── Clone repo ──────────────────────────────────────
if [ ! -d /opt/aios ]; then
    # Set up SSH key for GitHub (copy from root)
    mkdir -p /root/.ssh
    ssh-keyscan github.com >> /root/.ssh/known_hosts 2>/dev/null
    git clone --depth 1 --branch "$BRANCH" "$REPO" /opt/aios || {
        # Fallback: clone via HTTPS if SSH not configured
        echo "SSH clone failed, trying HTTPS..."
        git clone --depth 1 --branch "$BRANCH" \
            https://github.com/allee-ai/AI_OS.git /opt/aios
    }
fi
cd /opt/aios

# ── Python deps ─────────────────────────────────────
uv sync --frozen --no-dev --no-editable

# ── Build frontend ──────────────────────────────────
cd frontend
npm ci
npm run build
cd ..

# ── Create .env ─────────────────────────────────────
cat > /opt/aios/.env <<ENV
AIOS_MODE=personal
AIOS_MODEL_PROVIDER=$provider
AIOS_MODEL_NAME=$model
${key_env}=${api_key}
AIOS_MOBILE_TOKEN=$MOBILE_TOKEN
AIOS_EVOLVE=1
AIOS_EVOLVE_INTERVAL=$EVOLVE_INTERVAL
AIOS_LLM_ENABLED=true
AIOS_LOOPS=1
# Reduce non-evolution loop noise during experiment
AIOS_HEALTH_INTERVAL=86400
AIOS_MEMORY_INTERVAL=86400
AIOS_THOUGHT_INTERVAL=86400
AIOS_CONSOLIDATION_INTERVAL=86400
AIOS_SYNC_INTERVAL=172800
AIOS_GOAL_INTERVAL=172800
AIOS_SELF_IMPROVE=0
AIOS_TRAINING_GEN=0
AIOS_DEMO_AUDIT=0
AIOS_WORKSPACE_QA=0
ENV

# ── Git config for evolution commits ────────────────
cd /opt/aios
git config user.email "nola-${provider}@showdown.local"
git config user.name "Nola (${provider}/${model})"

# ── Systemd service ─────────────────────────────────
cat > /etc/systemd/system/aios.service <<SERVICE
[Unit]
Description=AI_OS ($provider)
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

# Allow aios service to restart itself
echo "root ALL=(ALL) NOPASSWD: /bin/systemctl restart aios" > /etc/sudoers.d/aios-restart

systemctl daemon-reload
systemctl enable aios
systemctl start aios

echo "✓ Provisioned: $provider / $model"
PROVISION_SCRIPT

    ssh_cmd "$ip" "chmod +x /root/provision.sh && bash /root/provision.sh"
    ok "$name provisioned ($ip)"
done

# ── Summary ─────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  🏁  SHOWDOWN DEPLOYED"
echo "═══════════════════════════════════════════════════════════"

for i in 0 1 2; do
    name="${DROPLET_NAMES[$i]}"
    key="${PROVIDER_KEYS[$i]}"
    IFS=: read -r provider model key_env <<< "${PROVIDERS[$key]}"
    ip=$(get_droplet_ip "$name")
    echo ""
    echo "  $provider ($model)"
    echo "    Dashboard: http://${ip}:8000"
    echo "    Mobile:    http://${ip}:8000/api/mobile/"
    echo "    Evolution: http://${ip}:8000/api/subconscious/evolution"
    echo "    SSH:       ssh -i ~/.ssh/do_droplet root@${ip}"
done

echo ""
echo "  Token: $MOBILE_TOKEN"
echo "  Evolution interval: ${EVOLVE_INTERVAL}s ($(( EVOLVE_INTERVAL / 60 )) min)"
echo "  Expected cycles in 24h: $(( 86400 / EVOLVE_INTERVAL ))"
echo ""
echo "  Collect results:"
echo "    python3 scripts/showdown_collect.py"
echo ""
echo "  Teardown:"
echo "    bash scripts/showdown_deploy.sh teardown"
echo "═══════════════════════════════════════════════════════════"
