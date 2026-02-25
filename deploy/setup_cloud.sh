#!/usr/bin/env bash
# setup_cloud.sh — One-shot bootstrap for an Ubuntu/Debian cloud VM.
#
# Prerequisites (must be set in shell before running):
#   GIT_VAULT_REMOTE  — git remote URL for the vault repo
#   GIT_AGENT_REMOTE  — git remote URL for the agent code repo
#
# .env is NOT provisioned here — copy it to /app/.env manually or via secrets manager.
#
# Usage:
#   export GIT_VAULT_REMOTE=git@github.com:you/vault.git
#   export GIT_AGENT_REMOTE=git@github.com:you/ai_employee.git
#   bash setup_cloud.sh

set -euo pipefail

: "${GIT_VAULT_REMOTE:?GIT_VAULT_REMOTE must be set}"
: "${GIT_AGENT_REMOTE:?GIT_AGENT_REMOTE must be set}"

echo "=== [1/5] Installing Docker and git ==="
apt-get update -qq
apt-get install -y --no-install-recommends \
    docker.io \
    docker-compose-plugin \
    git \
    ca-certificates

systemctl enable --now docker

echo "=== [2/5] Cloning vault repo → /vault ==="
if [ -d /vault/.git ]; then
    git -C /vault pull --rebase
else
    git clone "$GIT_VAULT_REMOTE" /vault
fi

echo "=== [3/5] Cloning agent code repo → /app ==="
if [ -d /app/.git ]; then
    git -C /app pull --rebase
else
    git clone "$GIT_AGENT_REMOTE" /app
fi

echo "=== [4/5] Reminder: provision /app/.env before starting ==="
echo "    Copy your .env file to /app/.env (never commit secrets to git)"

echo "=== [5/5] Starting services with Docker Compose ==="
cd /app
docker compose -f deploy/docker-compose.yml up -d --build

echo ""
echo "Cloud setup complete."
echo "  Odoo:  http://localhost:8069"
echo "  Agent: docker compose -f deploy/docker-compose.yml logs -f agent"
