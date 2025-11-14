#!/bin/sh
set -e

echo "🔧 Stage 9 Vault B2 Entrypoint - Starting..."

# -------------------------------
# Load B2 Credentials via Docker secrets
# -------------------------------

if [ ! -f /run/secrets/b2_access_key_id ] || [ ! -f /run/secrets/b2_secret_key ]; then
    echo "❌ B2 secrets not found"
    ls -l /run/secrets || true
    exit 1
fi

AWS_ACCESS_KEY_ID=$(cat /run/secrets/b2_access_key_id)
AWS_SECRET_ACCESS_KEY=$(cat /run/secrets/b2_secret_key)

export AWS_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY

echo "✓ AWS_ACCESS_KEY_ID loaded (len: ${#AWS_ACCESS_KEY_ID})"
echo "✓ AWS_SECRET_ACCESS_KEY loaded (len: ${#AWS_SECRET_ACCESS_KEY})"

# -------------------------------
# Show environment (for debugging)
# -------------------------------

echo "Environment now contains:"
env | grep AWS_

# -------------------------------
# Start Vault server
# -------------------------------

echo "🚀 Launching Vault server..."
exec vault server -config="$VAULT_CONFIG"
