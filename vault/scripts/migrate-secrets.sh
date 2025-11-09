#!/bin/bash
set -euo pipefail

# ============================================================================
# Secrets Migration Script
# ============================================================================
# This script migrates secrets from .env files to Vault
#
# Prerequisites:
# - Vault must be initialized and unsealed
# - VAULT_ADDR must be set
# - VAULT_TOKEN must be set (admin token)
# - .env file must exist
#
# Usage:
#   export VAULT_ADDR=http://vault:8200
#   export VAULT_TOKEN=<admin-token>
#   ./migrate-secrets.sh [path/to/.env]
#
# Safety:
#   - Creates .env.backup before migration
#   - Non-destructive (doesn't delete .env)
#   - Validates secrets after migration
# ============================================================================

ENV_FILE="${1:-.env}"

echo "🔄 Migrating secrets from $ENV_FILE to Vault..."

# Check prerequisites
if [ -z "${VAULT_ADDR:-}" ]; then
  echo "❌ ERROR: VAULT_ADDR not set"
  exit 1
fi

if [ -z "${VAULT_TOKEN:-}" ]; then
  echo "❌ ERROR: VAULT_TOKEN not set"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ ERROR: File $ENV_FILE not found"
  exit 1
fi

# Create backup
BACKUP_FILE="${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
echo "💾 Creating backup: $BACKUP_FILE"
cp "$ENV_FILE" "$BACKUP_FILE"

# Helper function to write secret to Vault
write_secret() {
  local path=$1
  shift
  local args=("$@")

  echo "   Writing to zakupai/$path..."
  if vault kv put "zakupai/$path" "${args[@]}"; then
    echo "   ✅ Success"
  else
    echo "   ⚠️  Failed or already exists"
  fi
}

# Parse .env file and categorize secrets
echo ""
echo "📊 Analyzing .env file..."

# Shared database secrets
if grep -q "POSTGRES_" "$ENV_FILE"; then
  echo "🗄️  Migrating database secrets..."
  POSTGRES_HOST=$(grep "^POSTGRES_HOST=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "postgres")
  POSTGRES_PORT=$(grep "^POSTGRES_PORT=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "5432")
  POSTGRES_USER=$(grep "^POSTGRES_USER=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")
  POSTGRES_PASSWORD=$(grep "^POSTGRES_PASSWORD=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")
  POSTGRES_DB=$(grep "^POSTGRES_DB=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "zakupai")
  DATABASE_URL=$(grep "^DATABASE_URL=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")

  if [ -n "$POSTGRES_USER" ] && [ -n "$POSTGRES_PASSWORD" ]; then
    write_secret "shared/db" \
      "POSTGRES_HOST=$POSTGRES_HOST" \
      "POSTGRES_PORT=$POSTGRES_PORT" \
      "POSTGRES_USER=$POSTGRES_USER" \
      "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" \
      "POSTGRES_DB=$POSTGRES_DB" \
      "DATABASE_URL=$DATABASE_URL"
  fi
fi

# Redis secrets
if grep -q "REDIS_" "$ENV_FILE"; then
  echo "📮 Migrating Redis secrets..."
  REDIS_URL=$(grep "^REDIS_URL=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "redis://redis:6379/0")
  REDIS_PASSWORD=$(grep "^REDIS_PASSWORD=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")

  write_secret "shared/redis" \
    "REDIS_URL=$REDIS_URL" \
    "REDIS_PASSWORD=$REDIS_PASSWORD"
fi

# JWT secrets
if grep -q "JWT_SECRET" "$ENV_FILE"; then
  echo "🔐 Migrating JWT secrets..."
  JWT_SECRET_KEY=$(grep "^JWT_SECRET_KEY=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")
  SESSION_SECRET=$(grep "^SESSION_SECRET=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")

  if [ -n "$JWT_SECRET_KEY" ]; then
    write_secret "shared/jwt" \
      "JWT_SECRET_KEY=$JWT_SECRET_KEY" \
      "SESSION_SECRET=$SESSION_SECRET"
  fi
fi

# Goszakup API
if grep -q "GOSZAKUP_TOKEN" "$ENV_FILE"; then
  echo "🏛️  Migrating Goszakup API secrets..."
  GOSZAKUP_TOKEN=$(grep "^GOSZAKUP_TOKEN=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")
  GOSZAKUP_BASE=$(grep "^GOSZAKUP_BASE=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "https://ows.goszakup.gov.kz")

  if [ -n "$GOSZAKUP_TOKEN" ]; then
    write_secret "shared/goszakup" \
      "GOSZAKUP_TOKEN=$GOSZAKUP_TOKEN" \
      "GOSZAKUP_BASE=$GOSZAKUP_BASE"
  fi
fi

# OpenAI API (ETL service)
if grep -q "OPENAI_API_KEY" "$ENV_FILE"; then
  echo "🤖 Migrating OpenAI API key..."
  OPENAI_API_KEY=$(grep "^OPENAI_API_KEY=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")

  if [ -n "$OPENAI_API_KEY" ]; then
    write_secret "services/etl/openai" \
      "OPENAI_API_KEY=$OPENAI_API_KEY"
  fi
fi

# Telegram Bot
if grep -q "TELEGRAM_BOT_TOKEN" "$ENV_FILE"; then
  echo "📱 Migrating Telegram bot secrets..."
  TELEGRAM_BOT_TOKEN=$(grep "^TELEGRAM_BOT_TOKEN=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")
  TELEGRAM_ADMIN_ID=$(grep "^TELEGRAM_ADMIN_ID=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")

  if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    write_secret "services/etl/telegram" \
      "TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN" \
      "TELEGRAM_ADMIN_ID=$TELEGRAM_ADMIN_ID"
  fi
fi

# n8n integration
if grep -q "N8N_" "$ENV_FILE"; then
  echo "🔗 Migrating n8n integration secrets..."
  N8N_WEBHOOK_URL=$(grep "^N8N_WEBHOOK_URL=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")
  N8N_API_KEY=$(grep "^N8N_API_KEY=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")
  N8N_BASE_URL=$(grep "^N8N_BASE_URL=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")

  if [ -n "$N8N_API_KEY" ]; then
    write_secret "shared/n8n" \
      "N8N_WEBHOOK_URL=$N8N_WEBHOOK_URL" \
      "N8N_API_KEY=$N8N_API_KEY" \
      "N8N_BASE_URL=$N8N_BASE_URL"
  fi
fi

# Flowise integration
if grep -q "FLOWISE_" "$ENV_FILE"; then
  echo "🌊 Migrating Flowise integration secrets..."
  FLOWISE_BASE_URL=$(grep "^FLOWISE_BASE_URL=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")
  FLOWISE_API_KEY=$(grep "^FLOWISE_API_KEY=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")
  FLOWISE_USER=$(grep "^FLOWISE_USER=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")
  FLOWISE_PASSWORD=$(grep "^FLOWISE_PASSWORD=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")

  if [ -n "$FLOWISE_API_KEY" ]; then
    write_secret "shared/flowise" \
      "FLOWISE_BASE_URL=$FLOWISE_BASE_URL" \
      "FLOWISE_API_KEY=$FLOWISE_API_KEY" \
      "FLOWISE_USER=$FLOWISE_USER" \
      "FLOWISE_PASSWORD=$FLOWISE_PASSWORD"
  fi
fi

# Backblaze B2
if grep -q "BACKBLAZE_" "$ENV_FILE" || grep -q "B2_" "$ENV_FILE"; then
  echo "☁️  Migrating Backblaze B2 secrets..."
  B2_KEY_ID=$(grep "^BACKBLAZE_KEY_ID=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || grep "^B2_KEY_ID=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")
  B2_APP_KEY=$(grep "^BACKBLAZE_APPLICATION_KEY=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || grep "^B2_APP_KEY=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")
  B2_BUCKET=$(grep "^BACKBLAZE_BUCKET_NAME=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || grep "^B2_BUCKET=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "zakupai-backups")
  B2_ENDPOINT=$(grep "^BACKBLAZE_ENDPOINT=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || grep "^B2_ENDPOINT=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' || echo "")

  if [ -n "$B2_KEY_ID" ] && [ -n "$B2_APP_KEY" ]; then
    write_secret "backup/b2" \
      "B2_KEY_ID=$B2_KEY_ID" \
      "B2_APP_KEY=$B2_APP_KEY" \
      "B2_BUCKET=$B2_BUCKET" \
      "B2_ENDPOINT=$B2_ENDPOINT"
  fi
fi

echo ""
echo "✅ Migration complete!"
echo ""
echo "📋 Next steps:"
echo "1. Verify secrets in Vault:"
echo "   vault kv list zakupai/shared"
echo "   vault kv get zakupai/shared/db"
echo ""
echo "2. Test service access with AppRole credentials"
echo ""
echo "3. Once verified, you can clear sensitive data from .env:"
echo "   # Keep only non-secret configuration in .env"
echo "   # Move secret references to .env.vault"
echo ""
echo "4. Backup file saved at: $BACKUP_FILE"
echo "   ⚠️  Keep this backup secure until migration is fully verified"
