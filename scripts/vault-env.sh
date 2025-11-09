#!/bin/bash
# ===========================================
# Vault Environment Loader for Flowise/n8n
# ===========================================
# This script loads secrets from Vault and exports them as environment variables
# for services that don't support hvac client (Flowise, n8n).
#
# Usage:
#   source ./scripts/vault-env.sh
#   docker-compose up flowise n8n
#
# ⚠️ DO NOT RUN AUTOMATICALLY — Manual execution only

set -e

# ===========================================
# Configuration
# ===========================================

VAULT_ADDR=${VAULT_ADDR:-http://localhost:8200}
VAULT_TOKEN=${VAULT_TOKEN:-$(cat .vault-token 2>/dev/null || cat monitoring/vault/creds/monitoring.token 2>/dev/null)}
VAULT_KV_MOUNT=${VAULT_KV_MOUNT:-zakupai}

if [ -z "$VAULT_TOKEN" ]; then
  echo "❌ ERROR: VAULT_TOKEN not set and no token file found"
  echo "   Set VAULT_TOKEN or create .vault-token / monitoring/vault/creds/monitoring.token"
  exit 1
fi

export VAULT_ADDR
export VAULT_TOKEN

echo "🔐 Loading secrets from Vault..."
echo "   Vault Address: ${VAULT_ADDR}"
echo "   KV Mount: ${VAULT_KV_MOUNT}"

# ===========================================
# Helper Functions
# ===========================================

# Load secret from Vault and export to environment
# Usage: load_secret_path <path> [prefix]
load_secret_path() {
  local secret_path=$1
  local prefix=${2:-}

  echo "📦 Loading ${secret_path}..."

  # Read secret from Vault
  local secret_json
  if ! secret_json=$(vault kv get -format=json "${VAULT_KV_MOUNT}/${secret_path}" 2>&1); then
    echo "⚠️  Failed to load ${secret_path}: ${secret_json}"
    return 1
  fi

  # Extract data.data (KV v2 structure)
  local data
  data=$(echo "$secret_json" | jq -r '.data.data')

  if [ "$data" = "null" ]; then
    echo "⚠️  No data found in ${secret_path}"
    return 1
  fi

  # Export each key-value pair
  local count=0
  while IFS='=' read -r key value; do
    if [ -n "$key" ] && [ -n "$value" ]; then
      local env_var="${prefix}${key}"
      export "${env_var}=${value}"
      echo "   ✓ ${env_var}"
      count=$((count + 1))
    fi
  done < <(echo "$data" | jq -r 'to_entries | .[] | "\(.key)=\(.value)"')

  echo "   ✓ Loaded $count variables from ${secret_path}"
}

# ===========================================
# Load Secrets
# ===========================================

# Database credentials
load_secret_path "db" ""

# API keys
load_secret_path "api" ""

# Goszakup token
load_secret_path "goszakup" ""

# Monitoring credentials
load_secret_path "monitoring" ""

# ===========================================
# Service-Specific Exports
# ===========================================

# Flowise environment variables
echo ""
echo "🌊 Exporting Flowise-specific variables..."
export FLOWISE_USERNAME=${FLOWISE_USERNAME:-admin}
export FLOWISE_PASSWORD=${FLOWISE_PASSWORD:-admin123}
export DATABASE_PATH=${DATABASE_PATH:-/root/.flowise/flowise.sqlite}
export SECRETKEY_PATH=${SECRETKEY_PATH:-/root/.flowise}
export LOG_LEVEL=${LOG_LEVEL:-info}
export LOG_PATH=${LOG_PATH:-/root/.flowise/logs}
export BLOB_STORAGE_PATH=${BLOB_STORAGE_PATH:-/root/.flowise/storage}
echo "   ✓ FLOWISE_USERNAME"
echo "   ✓ FLOWISE_PASSWORD"
echo "   ✓ DATABASE_PATH"

# n8n environment variables
echo ""
echo "📊 Exporting n8n-specific variables..."
export GENERIC_TIMEZONE=${GENERIC_TIMEZONE:-Asia/Almaty}
export N8N_BASIC_AUTH_ACTIVE=${N8N_BASIC_AUTH_ACTIVE:-false}
export N8N_HOST=${N8N_HOST:-0.0.0.0}
export N8N_PORT=${N8N_PORT:-5678}
export N8N_PROTOCOL=${N8N_PROTOCOL:-https}
export N8N_EDITOR_BASE_URL=${N8N_EDITOR_BASE_URL:-https://n8n.exomind.site}
export WEBHOOK_URL=${WEBHOOK_URL:-https://n8n.exomind.site}
export N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY:-mySecretEncryptionKey123456}
export N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=${N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS:-false}
export DB_SQLITE_POOL_SIZE=${DB_SQLITE_POOL_SIZE:-10}
export N8N_RUNNERS_ENABLED=${N8N_RUNNERS_ENABLED:-true}
export N8N_SECURE_COOKIE=${N8N_SECURE_COOKIE:-false}
echo "   ✓ GENERIC_TIMEZONE"
echo "   ✓ N8N_BASIC_AUTH_ACTIVE"
echo "   ✓ N8N_HOST"

echo ""
echo "✅ All secrets loaded successfully!"
echo ""
echo "📋 Next steps:"
echo "   1. Verify environment variables:"
echo "      env | grep -E '(POSTGRES|API_KEY|GOSZAKUP|TELEGRAM)'"
echo ""
echo "   2. Start services:"
echo "      docker-compose up -d flowise n8n"
echo ""
echo "   3. Check service logs:"
echo "      docker-compose logs -f flowise"
echo "      docker-compose logs -f n8n"
echo ""
echo "⚠️  Security reminder:"
echo "   - This shell session now contains sensitive secrets"
echo "   - Close terminal after use"
echo "   - Do not share history or logs"
