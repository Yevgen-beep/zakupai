#!/bin/sh
set -euo pipefail

# ============================================================================
# SECURITY WARNING: This script writes sensitive secrets to the filesystem
# ============================================================================
# - init.json contains unseal keys and root token
# - .env.vault contains root token for application use
#
# CRITICAL: Use Docker VOLUMES, not bind mounts!
#   ✅ SAFE:   volumes: - vault-data:/vault/data
#   ❌ DANGER: volumes: - ./vault/data:/vault/data
#
# Bind mounts write secrets to your host filesystem and may leak into Git!
# ============================================================================

# Configurable secrets path (default: /vault/data)
VAULT_SECRETS_PATH="${VAULT_SECRETS_PATH:-/vault/data}"

# Graceful shutdown handler
term() { kill -TERM "$VAULT_PID" 2>/dev/null || true; }
trap term INT TERM

echo "🚀 Starting Vault server..."
vault server -config=/vault/config/vault.hcl &
VAULT_PID=$!
sleep 5

export VAULT_ADDR='http://127.0.0.1:8200'
echo "👤 Vault init script running as $(id -u):$(id -g) ($(whoami))"

# Auto-init если первый запуск
if [ ! -f "$VAULT_SECRETS_PATH/init.json" ]; then
  echo "🔐 Initializing Vault..."
  echo "⚠️  Secrets will be written to: $VAULT_SECRETS_PATH"
  vault operator init -key-shares=1 -key-threshold=1 -format=json > "$VAULT_SECRETS_PATH/init.json"

  # 💡 Надёжный парсинг: убираем переносы строк, затем извлекаем ключи
  UNSEAL_KEY=$(tr -d '\n' < "$VAULT_SECRETS_PATH/init.json" | sed -n 's/.*"unseal_keys_b64":\s*\[\s*"\([^"]*\)".*/\1/p')
  ROOT_TOKEN=$(tr -d '\n' < "$VAULT_SECRETS_PATH/init.json" | sed -n 's/.*"root_token":\s*"\([^"]*\)".*/\1/p')

  # Проверка что парсинг сработал
  if [ -z "$UNSEAL_KEY" ] || [ -z "$ROOT_TOKEN" ]; then
    echo "❌ ERROR: Failed to parse init.json - empty values"
    echo "DEBUG: init.json content (first 20 lines):"
    head -20 "$VAULT_SECRETS_PATH/init.json"
    exit 1
  fi

  echo "✅ Keys extracted successfully"
  vault operator unseal "$UNSEAL_KEY"

  # Записываем токены в .env.vault
  { echo "ROOT_TOKEN=$ROOT_TOKEN"; echo "VAULT_TOKEN=$ROOT_TOKEN"; } > "$VAULT_SECRETS_PATH/.env.vault"
  chmod 600 "$VAULT_SECRETS_PATH/.env.vault"
  echo "✅ Vault initialized and unsealed"
  echo "📝 Tokens saved to $VAULT_SECRETS_PATH/.env.vault"
else
  echo "🔓 Unsealing existing Vault..."
  UNSEAL_KEY=$(tr -d '\n' < "$VAULT_SECRETS_PATH/init.json" | sed -n 's/.*"unseal_keys_b64":\s*\[\s*"\([^"]*\)".*/\1/p')

  if [ -z "$UNSEAL_KEY" ]; then
    echo "❌ ERROR: Cannot read unseal key from init.json"
    exit 1
  fi

  vault operator unseal "$UNSEAL_KEY"
  echo "✅ Vault unsealed"
fi

echo "🎉 Vault is ready at http://vault:8200"
wait "$VAULT_PID"
