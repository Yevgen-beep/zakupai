#!/bin/bash
set -euo pipefail

# ============================================================================
# Vault AppRole Setup Script
# ============================================================================
# This script creates policies and AppRoles for all ZakupAI services
#
# Prerequisites:
# - Vault must be initialized and unsealed
# - VAULT_ADDR must be set
# - VAULT_TOKEN must be set (root token or admin token)
# - Policy files must exist in /vault/config/policies/
#
# Usage:
#   export VAULT_ADDR=http://vault:8200
#   export VAULT_TOKEN=<root-token>
#   ./setup-approles.sh
#
# Output:
#   Creates approle-credentials.env with ROLE_ID and SECRET_ID for each service
# ============================================================================

echo "🔐 Setting up AppRoles for ZakupAI services..."

# Check prerequisites
if [ -z "${VAULT_ADDR:-}" ]; then
  echo "❌ ERROR: VAULT_ADDR not set"
  exit 1
fi

if [ -z "${VAULT_TOKEN:-}" ]; then
  echo "❌ ERROR: VAULT_TOKEN not set"
  exit 1
fi

# Define services
SERVICES=("etl-service" "calc-service" "risk-engine" "telegram-bot" "admin")

# Output file for credentials
CREDS_FILE="/vault/data/approle-credentials.env"
> "$CREDS_FILE"  # Clear file
chmod 600 "$CREDS_FILE"

echo "⚠️  WARNING: This will create SECRET_IDs that should be kept secure!"
echo ""

for SERVICE in "${SERVICES[@]}"; do
  echo "📝 Processing $SERVICE..."

  # Policy name
  POLICY_NAME="$SERVICE"
  POLICY_FILE="/vault/config/policies/${SERVICE}.hcl"

  # Check if policy file exists
  if [ ! -f "$POLICY_FILE" ]; then
    echo "   ❌ Policy file not found: $POLICY_FILE"
    continue
  fi

  # Create/update policy
  echo "   Creating policy '$POLICY_NAME'..."
  vault policy write "$POLICY_NAME" "$POLICY_FILE"

  # Create/update AppRole
  ROLE_NAME="$SERVICE"
  echo "   Creating AppRole '$ROLE_NAME'..."

  # Token TTL settings
  TOKEN_TTL="1h"      # 1 hour default TTL
  TOKEN_MAX_TTL="4h"  # 4 hour maximum TTL

  # For admin, use longer TTLs
  if [ "$SERVICE" = "admin" ]; then
    TOKEN_TTL="24h"
    TOKEN_MAX_TTL="168h"  # 1 week
  fi

  vault write "auth/approle/role/$ROLE_NAME" \
    token_policies="$POLICY_NAME" \
    token_ttl="$TOKEN_TTL" \
    token_max_ttl="$TOKEN_MAX_TTL" \
    token_num_uses=0 \
    secret_id_num_uses=0 \
    secret_id_ttl="24h"

  # Get Role ID
  ROLE_ID=$(vault read -field=role_id "auth/approle/role/$ROLE_NAME/role-id")

  # Generate Secret ID
  SECRET_ID=$(vault write -field=secret_id -f "auth/approle/role/$ROLE_NAME/secret-id")

  # Save to credentials file
  SERVICE_UPPER=$(echo "$SERVICE" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
  echo "" >> "$CREDS_FILE"
  echo "# $SERVICE" >> "$CREDS_FILE"
  echo "VAULT_${SERVICE_UPPER}_ROLE_ID=$ROLE_ID" >> "$CREDS_FILE"
  echo "VAULT_${SERVICE_UPPER}_SECRET_ID=$SECRET_ID" >> "$CREDS_FILE"

  echo "   ✅ AppRole '$ROLE_NAME' created"
  echo "      Role ID: $ROLE_ID"
  echo "      Secret ID: ${SECRET_ID:0:20}..."
done

echo ""
echo "✅ AppRole setup complete!"
echo ""
echo "📄 Credentials saved to: $CREDS_FILE"
echo ""
echo "📋 Next steps:"
echo "1. Copy credentials to your .env.vault file:"
echo "   cat $CREDS_FILE >> .env.vault"
echo ""
echo "2. Update docker-compose.override.stage7.vault.yml with:"
echo "   env_file:"
echo "     - .env.vault"
echo ""
echo "3. SECURE THE CREDENTIALS FILE:"
echo "   chmod 600 .env.vault"
echo "   # Add to .gitignore (already done)"
echo ""
echo "⚠️  SECURITY WARNING:"
echo "   - Store $CREDS_FILE securely"
echo "   - Never commit to Git"
echo "   - Rotate SECRET_IDs regularly (use rotate-secrets.sh)"
echo "   - Each service should only have access to its own credentials"
