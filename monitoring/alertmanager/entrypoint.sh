#!/bin/sh
# ===========================================
# Alertmanager Entrypoint with Vault Integration
# ===========================================
# This script loads Telegram credentials from Vault before starting Alertmanager.
#
# ⚠️ DO NOT RUN AUTOMATICALLY — Manual configuration only
#
# Usage:
#   1. Set VAULT_ADDR and VAULT_TOKEN in environment
#   2. Run this script as container entrypoint
#   3. Alertmanager will start with credentials loaded

set -e

echo "🚨 Alertmanager starting..."

# ===========================================
# Step 1: Check if Vault integration is enabled
# ===========================================

if [ -n "$VAULT_ADDR" ] && [ -n "$VAULT_TOKEN" ]; then
  echo "🔐 Vault integration enabled"
  echo "   Vault Address: ${VAULT_ADDR}"

  # ===========================================
  # Step 2: Load Telegram credentials from Vault
  # ===========================================
  # MANUAL STEPS (do not execute automatically):
  #
  # 1. Install vault CLI in container:
  #    apk add --no-cache vault
  #
  # 2. Export Vault environment:
  #    export VAULT_ADDR=https://vault:8200
  #    export VAULT_TOKEN=$(cat /run/secrets/monitoring-token)
  #    export VAULT_SKIP_VERIFY=true  # for dev without TLS
  #
  # 3. Read secrets from Vault:
  #    TELEGRAM_BOT_TOKEN=$(vault kv get -field=TELEGRAM_BOT_TOKEN zakupai/monitoring)
  #    TELEGRAM_CHAT_ID=$(vault kv get -field=TELEGRAM_CHAT_ID zakupai/monitoring)
  #
  # 4. Export for Alertmanager config template:
  #    export TELEGRAM_BOT_TOKEN
  #    export TELEGRAM_CHAT_ID
  #
  # 5. Substitute environment variables in alertmanager.yml:
  #    envsubst < /etc/alertmanager/alertmanager.yml.tmpl > /etc/alertmanager/alertmanager.yml
  #
  # 6. Verify configuration:
  #    amtool config show

  echo "⚠️  Vault integration steps documented above (manual execution required)"
  echo "   For now, using environment variables from docker-compose"

else
  echo "⚠️  Vault integration disabled (VAULT_ADDR or VAULT_TOKEN not set)"
  echo "   Using environment variables from docker-compose"
fi

# ===========================================
# Step 3: Validate required environment variables
# ===========================================

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
  echo "⚠️  WARNING: TELEGRAM_BOT_TOKEN not set"
  echo "   Alertmanager will start but Telegram notifications will fail"
fi

if [ -z "$TELEGRAM_CHAT_ID" ]; then
  echo "⚠️  WARNING: TELEGRAM_CHAT_ID not set"
  echo "   Alertmanager will start but Telegram notifications will fail"
fi

# ===========================================
# Step 4: Start Alertmanager
# ===========================================

echo "✅ Starting Alertmanager with configuration:"
echo "   Config: /etc/alertmanager/alertmanager.yml"
echo "   Storage: /alertmanager"

exec /bin/alertmanager \
  --config.file=/etc/alertmanager/alertmanager.yml \
  --storage.path=/alertmanager \
  "$@"
