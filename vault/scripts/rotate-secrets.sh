#!/bin/bash
set -euo pipefail

# ============================================================================
# Secrets Rotation Script
# ============================================================================
# This script rotates AppRole SECRET_IDs and optionally JWT secrets
#
# Prerequisites:
# - Vault must be running and unsealed
# - VAULT_ADDR must be set
# - VAULT_TOKEN must be set (admin token with approle management permissions)
#
# Usage:
#   # Rotate all service SECRET_IDs
#   ./rotate-secrets.sh
#
#   # Rotate specific service
#   ./rotate-secrets.sh etl-service
#
#   # Rotate JWT secrets (requires confirmation)
#   ./rotate-secrets.sh --jwt
#
# Schedule:
#   Recommended: Weekly via cron or n8n workflow
#   0 2 * * 0  /vault/scripts/rotate-secrets.sh  # Every Sunday at 2 AM
# ============================================================================

ROTATE_JWT=false
SPECIFIC_SERVICE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --jwt)
      ROTATE_JWT=true
      shift
      ;;
    *)
      SPECIFIC_SERVICE="$1"
      shift
      ;;
  esac
done

echo "🔄 Starting secrets rotation..."
echo "   Date: $(date)"

# Check prerequisites
if [ -z "${VAULT_ADDR:-}" ]; then
  echo "❌ ERROR: VAULT_ADDR not set"
  exit 1
fi

if [ -z "${VAULT_TOKEN:-}" ]; then
  echo "❌ ERROR: VAULT_TOKEN not set"
  exit 1
fi

# Output file for new credentials
CREDS_FILE="/vault/data/approle-credentials-rotated.env"
> "$CREDS_FILE"
chmod 600 "$CREDS_FILE"

echo "$(date '+%Y-%m-%d %H:%M:%S') - Rotation started" >> "$CREDS_FILE"
echo "" >> "$CREDS_FILE"

# Define services to rotate
if [ -n "$SPECIFIC_SERVICE" ]; then
  SERVICES=("$SPECIFIC_SERVICE")
  echo "🎯 Rotating SECRET_ID for: $SPECIFIC_SERVICE"
else
  SERVICES=("etl-service" "calc-service" "risk-engine" "telegram-bot")
  echo "🎯 Rotating SECRET_IDs for all services"
fi

# Rotate AppRole SECRET_IDs
for SERVICE in "${SERVICES[@]}"; do
  echo ""
  echo "📝 Rotating SECRET_ID for $SERVICE..."

  ROLE_NAME="$SERVICE"

  # Check if role exists
  if ! vault read "auth/approle/role/$ROLE_NAME" >/dev/null 2>&1; then
    echo "   ⚠️  AppRole '$ROLE_NAME' not found, skipping"
    continue
  fi

  # Get current Role ID (doesn't change)
  ROLE_ID=$(vault read -field=role_id "auth/approle/role/$ROLE_NAME/role-id")

  # Generate new Secret ID
  SECRET_ID=$(vault write -field=secret_id -f "auth/approle/role/$ROLE_NAME/secret-id")

  # Note: Old SECRET_IDs remain valid until their TTL expires
  # This allows for graceful rotation without immediate service disruption

  # Save to credentials file
  SERVICE_UPPER=$(echo "$SERVICE" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
  echo "# $SERVICE (rotated: $(date))" >> "$CREDS_FILE"
  echo "VAULT_${SERVICE_UPPER}_ROLE_ID=$ROLE_ID" >> "$CREDS_FILE"
  echo "VAULT_${SERVICE_UPPER}_SECRET_ID=$SECRET_ID" >> "$CREDS_FILE"
  echo "" >> "$CREDS_FILE"

  echo "   ✅ New SECRET_ID generated"
  echo "      Role ID: $ROLE_ID (unchanged)"
  echo "      Secret ID: ${SECRET_ID:0:20}... (new)"
  echo "      ⚠️  Old SECRET_IDs remain valid for 24h (TTL)"
done

# Rotate JWT secrets (optional, requires confirmation)
if [ "$ROTATE_JWT" = true ]; then
  echo ""
  echo "🔐 Rotating JWT secrets..."
  echo "   ⚠️  WARNING: This will invalidate all existing JWT tokens!"
  echo "   ⚠️  All users will be logged out!"

  read -p "   Are you sure? (yes/no): " -r
  echo
  if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    echo "   Skipping JWT rotation"
  else
    # Generate new JWT secret
    NEW_JWT_SECRET=$(openssl rand -hex 64)
    NEW_SESSION_SECRET=$(openssl rand -hex 32)

    # Update in Vault
    vault kv put zakupai/shared/jwt \
      JWT_SECRET_KEY="$NEW_JWT_SECRET" \
      SESSION_SECRET="$NEW_SESSION_SECRET"

    echo "   ✅ JWT secrets rotated"
    echo "   ⚠️  Restart all services to apply new secrets"
    echo ""
    echo "# JWT Secrets (rotated: $(date))" >> "$CREDS_FILE"
    echo "# These are stored in Vault and services will pick them up automatically" >> "$CREDS_FILE"
    echo "# JWT_SECRET_KEY=<stored in Vault>" >> "$CREDS_FILE"
    echo "# SESSION_SECRET=<stored in Vault>" >> "$CREDS_FILE"
    echo "" >> "$CREDS_FILE"
  fi
fi

echo ""
echo "✅ Rotation complete!"
echo ""
echo "📄 New credentials saved to: $CREDS_FILE"
echo ""
echo "📋 Next steps:"
echo ""
echo "1. Update service configurations with new SECRET_IDs:"
echo "   # Option A: Update docker-compose environment"
echo "   docker-compose down"
echo "   # Copy new credentials to .env.vault"
echo "   cat $CREDS_FILE >> .env.vault"
echo "   docker-compose up -d"
echo ""
echo "   # Option B: Rolling update (zero downtime)"
echo "   for service in etl-service calc-service risk-engine; do"
echo "     docker-compose up -d --no-deps \$service"
echo "     sleep 10  # Wait for service to be healthy"
echo "   done"
echo ""
echo "2. Verify services are authenticating successfully:"
echo "   docker-compose logs -f etl-service | grep -i vault"
echo ""
echo "3. Monitor for any authentication failures:"
echo "   # Check Vault audit log"
echo "   tail -f /vault/logs/audit.log"
echo ""
echo "4. Old SECRET_IDs remain valid for 24h"
echo "   Services can continue using old credentials during this period"
echo ""
echo "5. Archive rotation log:"
echo "   mv $CREDS_FILE /vault/data/rotation-logs/approle-$(date +%Y%m%d_%H%M%S).env"
echo ""
echo "⚠️  SECURITY REMINDERS:"
echo "   - Test in staging environment first"
echo "   - Keep rotation logs for audit trail"
echo "   - Notify team before JWT rotation"
echo "   - Monitor service health during rotation"
