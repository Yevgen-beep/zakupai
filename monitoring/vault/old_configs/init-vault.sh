#!/bin/bash
# ===========================================
# Vault Initialization Script — ZakupAI
# ===========================================
# Usage: ./monitoring/vault/init-vault.sh
#
# This script:
# 1. Initializes Vault
# 2. Enables KV v2 secrets engine
# 3. Creates sample secrets for development
# 4. Outputs root token to .vault-token file
#
# IMPORTANT: Run this script ONCE after starting Vault container

set -e

VAULT_ADDR=${VAULT_ADDR:-http://localhost:8200}
VAULT_TOKEN_FILE=".vault-token"

echo "🔐 Initializing Vault at ${VAULT_ADDR}..."

# Wait for Vault to be ready
echo "⏳ Waiting for Vault to become available..."
until curl -sf "${VAULT_ADDR}/v1/sys/health" >/dev/null 2>&1 || [ $? -eq 2 ]; do
  echo "   Vault not ready yet, retrying in 2s..."
  sleep 2
done
echo "✅ Vault is available"

# Check if Vault is already initialized
if curl -sf "${VAULT_ADDR}/v1/sys/init" | grep -q '"initialized":true'; then
  echo "⚠️  Vault is already initialized"

  if [ ! -f "${VAULT_TOKEN_FILE}" ]; then
    echo "❌ ERROR: Vault is initialized but ${VAULT_TOKEN_FILE} not found."
    echo "   Please set VAULT_TOKEN manually or re-initialize Vault."
    exit 1
  fi

  VAULT_TOKEN=$(cat "${VAULT_TOKEN_FILE}")
  echo "📖 Using existing token from ${VAULT_TOKEN_FILE}"
else
  echo "🔧 Initializing Vault..."

  # Initialize Vault with 1 key share and threshold 1 (dev mode)
  INIT_OUTPUT=$(docker exec zakupai-vault vault operator init \
    -key-shares=1 \
    -key-threshold=1 \
    -format=json)

  # Extract root token and unseal key
  VAULT_TOKEN=$(echo "${INIT_OUTPUT}" | jq -r '.root_token')
  UNSEAL_KEY=$(echo "${INIT_OUTPUT}" | jq -r '.unseal_keys_b64[0]')

  echo "✅ Vault initialized successfully"
  echo "   Root Token: ${VAULT_TOKEN}"
  echo "   Unseal Key: ${UNSEAL_KEY}"

  # Save to file
  echo "${VAULT_TOKEN}" > "${VAULT_TOKEN_FILE}"
  echo "${UNSEAL_KEY}" > .vault-unseal-key

  echo "💾 Credentials saved to:"
  echo "   - ${VAULT_TOKEN_FILE}"
  echo "   - .vault-unseal-key"

  # Unseal Vault
  echo "🔓 Unsealing Vault..."
  docker exec zakupai-vault vault operator unseal "${UNSEAL_KEY}"
fi

# Export token for subsequent commands
export VAULT_TOKEN

echo ""
echo "🔧 Configuring Vault secrets engine..."

# Enable KV v2 secrets engine at zakupai/
if docker exec -e VAULT_TOKEN="${VAULT_TOKEN}" zakupai-vault \
  vault secrets list -format=json | grep -q '"zakupai/"'; then
  echo "✅ KV secrets engine already enabled at zakupai/"
else
  echo "📦 Enabling KV v2 secrets engine..."
  docker exec -e VAULT_TOKEN="${VAULT_TOKEN}" zakupai-vault \
    vault secrets enable -path=zakupai kv-v2
  echo "✅ KV v2 secrets engine enabled"
fi

echo ""
echo "📝 Creating sample secrets for development..."

# DB secrets
echo "🗄️  Creating db secrets..."
docker exec -e VAULT_TOKEN="${VAULT_TOKEN}" zakupai-vault \
  vault kv put zakupai/db \
    POSTGRES_USER="zakupai_user" \
    POSTGRES_PASSWORD="zakupai_pass" \
    POSTGRES_DB="zakupai" \
    POSTGRES_HOST="zakupai-db" \
    POSTGRES_PORT="5432" \
    DATABASE_URL="postgresql://zakupai_user:zakupai_pass@zakupai-db:5432/zakupai"

# API secrets
echo "🔑 Creating api secrets..."
docker exec -e VAULT_TOKEN="${VAULT_TOKEN}" zakupai-vault \
  vault kv put zakupai/api \
    API_KEY="changeme-development-key" \
    ZAKUPAI_API_KEY="changeme-development-key"

# Goszakup secrets
echo "🏛️  Creating goszakup secrets..."
docker exec -e VAULT_TOKEN="${VAULT_TOKEN}" zakupai-vault \
  vault kv put zakupai/goszakup \
    GOSZAKUP_TOKEN="your-goszakup-token-here"

# Monitoring secrets (Telegram bot for alerts)
echo "📢 Creating monitoring secrets..."
docker exec -e VAULT_TOKEN="${VAULT_TOKEN}" zakupai-vault \
  vault kv put zakupai/monitoring \
    TELEGRAM_BOT_TOKEN="your-telegram-bot-token" \
    TELEGRAM_CHAT_ID="your-telegram-chat-id"

echo ""
echo "✅ Vault initialization complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Set VAULT_TOKEN in your environment:"
echo "      export VAULT_TOKEN=${VAULT_TOKEN}"
echo ""
echo "   2. Update service environment variables:"
echo "      export VAULT_ADDR=http://vault:8200"
echo "      export VAULT_TOKEN=${VAULT_TOKEN}"
echo ""
echo "   3. Restart services to load secrets from Vault:"
echo "      docker-compose restart calc-service risk-engine etl-service"
echo ""
echo "   4. Update secrets with production values:"
echo "      docker exec -e VAULT_TOKEN=\${VAULT_TOKEN} zakupai-vault \\"
echo "        vault kv put zakupai/goszakup GOSZAKUP_TOKEN=<your-token>"
echo ""
echo "   5. View secrets:"
echo "      docker exec -e VAULT_TOKEN=\${VAULT_TOKEN} zakupai-vault \\"
echo "        vault kv get zakupai/db"
echo ""
echo "⚠️  SECURITY WARNING:"
echo "   - ${VAULT_TOKEN_FILE} contains the root token"
echo "   - Do NOT commit this file to git"
echo "   - Rotate credentials in production"
echo "   - Use AppRole or Kubernetes auth in production"
