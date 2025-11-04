#!/bin/bash
set -euo pipefail

# ============================================================================
# Vault Initialization Script
# ============================================================================
# This script initializes Vault with KV v2 engine and audit logging
#
# Prerequisites:
# - Vault must be running and unsealed
# - VAULT_ADDR must be set
# - VAULT_TOKEN must be set (root token or admin token)
#
# Usage:
#   export VAULT_ADDR=http://vault:8200
#   export VAULT_TOKEN=<root-token>
#   ./init-vault.sh
# ============================================================================

echo "🚀 Initializing Vault for ZakupAI..."

# Check prerequisites
if [ -z "${VAULT_ADDR:-}" ]; then
  echo "❌ ERROR: VAULT_ADDR not set"
  exit 1
fi

if [ -z "${VAULT_TOKEN:-}" ]; then
  echo "❌ ERROR: VAULT_TOKEN not set"
  exit 1
fi

# Wait for Vault to be ready
echo "⏳ Waiting for Vault to be ready..."
for i in {1..30}; do
  if vault status >/dev/null 2>&1; then
    echo "✅ Vault is ready"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "❌ ERROR: Vault did not become ready in time"
    exit 1
  fi
  echo "   Attempt $i/30..."
  sleep 2
done

# Enable KV v2 engine for Zakupai secrets
echo "📦 Enabling KV v2 secrets engine..."
if vault secrets list | grep -q "^zakupai/"; then
  echo "   KV engine 'zakupai' already exists"
else
  vault secrets enable -path=zakupai kv-v2
  echo "✅ KV v2 engine 'zakupai' enabled"
fi

# Enable audit logging
echo "📝 Enabling audit logging..."
mkdir -p /vault/logs
if vault audit list | grep -q "^file/"; then
  echo "   Audit logging already enabled"
else
  vault audit enable file file_path=/vault/logs/audit.log
  echo "✅ Audit logging enabled at /vault/logs/audit.log"
fi

# Enable AppRole auth method
echo "🔐 Enabling AppRole auth method..."
if vault auth list | grep -q "^approle/"; then
  echo "   AppRole auth method already enabled"
else
  vault auth enable approle
  echo "✅ AppRole auth method enabled"
fi

# Create KV structure
echo "📁 Creating KV secret structure..."

# Create shared secrets placeholders
echo "   Creating shared secrets structure..."
vault kv put zakupai/shared/db \
  POSTGRES_HOST="postgres" \
  POSTGRES_PORT="5432" \
  POSTGRES_USER="zakupai_user" \
  POSTGRES_PASSWORD="CHANGE_ME" \
  POSTGRES_DB="zakupai" \
  DATABASE_URL="postgresql+asyncpg://zakupai_user:CHANGE_ME@postgres:5432/zakupai" \
  || echo "   shared/db already exists or failed to create"

vault kv put zakupai/shared/redis \
  REDIS_URL="redis://redis:6379/0" \
  REDIS_PASSWORD="" \
  || echo "   shared/redis already exists or failed to create"

vault kv put zakupai/shared/jwt \
  JWT_SECRET_KEY="CHANGE_ME_GENERATE_WITH_OPENSSL" \
  SESSION_SECRET="CHANGE_ME_GENERATE_WITH_OPENSSL" \
  || echo "   shared/jwt already exists or failed to create"

vault kv put zakupai/shared/goszakup \
  GOSZAKUP_TOKEN="CHANGE_ME" \
  GOSZAKUP_BASE="https://ows.goszakup.gov.kz" \
  || echo "   shared/goszakup already exists or failed to create"

vault kv put zakupai/shared/n8n \
  N8N_WEBHOOK_URL="http://n8n:5678/webhook/search-lots" \
  N8N_API_KEY="CHANGE_ME" \
  N8N_BASE_URL="http://n8n:5678" \
  || echo "   shared/n8n already exists or failed to create"

vault kv put zakupai/shared/flowise \
  FLOWISE_BASE_URL="http://flowise:3000" \
  FLOWISE_API_KEY="CHANGE_ME" \
  FLOWISE_USER="admin" \
  FLOWISE_PASSWORD="CHANGE_ME" \
  || echo "   shared/flowise already exists or failed to create"

# Create service-specific secrets
echo "   Creating service-specific secrets..."
vault kv put zakupai/services/etl/openai \
  OPENAI_API_KEY="CHANGE_ME" \
  || echo "   services/etl/openai already exists or failed to create"

vault kv put zakupai/services/etl/telegram \
  TELEGRAM_BOT_TOKEN="CHANGE_ME" \
  TELEGRAM_ADMIN_ID="CHANGE_ME" \
  || echo "   services/etl/telegram already exists or failed to create"

vault kv put zakupai/services/calc/config \
  CALC_SERVICE_URL="http://calc-service:7001" \
  || echo "   services/calc/config already exists or failed to create"

vault kv put zakupai/services/risk/config \
  RISK_SERVICE_URL="http://risk-engine:7002" \
  || echo "   services/risk/config already exists or failed to create"

# Create backup secrets
echo "   Creating backup secrets..."
vault kv put zakupai/backup/b2 \
  B2_KEY_ID="CHANGE_ME" \
  B2_APP_KEY="CHANGE_ME" \
  B2_BUCKET="zakupai-backups" \
  B2_ENDPOINT="https://s3.us-west-000.backblazeb2.com" \
  || echo "   backup/b2 already exists or failed to create"

echo ""
echo "✅ Vault initialization complete!"
echo ""
echo "📋 Next steps:"
echo "1. Run ./setup-approles.sh to create AppRoles and policies"
echo "2. Run ./migrate-secrets.sh to migrate secrets from .env"
echo "3. Update service configurations with VAULT_ROLE_ID and VAULT_SECRET_ID"
echo ""
echo "⚠️  IMPORTANT: Update all 'CHANGE_ME' values with actual secrets!"
echo "   Use: vault kv put zakupai/path/to/secret KEY=value"
