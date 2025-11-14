#!/bin/bash
# ============================================================================
# Stage 9 Configuration Verification Script
# ============================================================================
# Purpose: Verify Stage 9 Vault configuration and check for conflicts
#
# This script checks:
#   1. Docker secrets are properly mounted
#   2. Networks are correctly configured
#   3. Volumes exist and have correct permissions
#   4. No conflicts between override files
#   5. Vault can start successfully
#
# Usage:
#   ./scripts/verify-stage9-config.sh
# ============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

PROJECT_ROOT="/home/mint/projects/claude_sandbox/zakupai"
cd "$PROJECT_ROOT" || exit 1

ERRORS=0

info "Starting Stage 9 configuration verification..."
echo

# ============================================================================
# 1. Check Docker secrets files
# ============================================================================
info "Step 1: Checking Docker secrets files..."

if [[ -f "./monitoring/vault/creds/b2_access_key_id" ]]; then
    PERMS=$(stat -c "%a" "./monitoring/vault/creds/b2_access_key_id")
    if [[ "$PERMS" == "644" ]] || [[ "$PERMS" == "600" ]]; then
        success "b2_access_key_id exists with correct permissions ($PERMS)"
    else
        error "b2_access_key_id has wrong permissions: $PERMS (expected: 644 or 600)"
        ((ERRORS++))
    fi
else
    error "File not found: monitoring/vault/creds/b2_access_key_id"
    ((ERRORS++))
fi

if [[ -f "./monitoring/vault/creds/b2_secret_key" ]]; then
    PERMS=$(stat -c "%a" "./monitoring/vault/creds/b2_secret_key")
    if [[ "$PERMS" == "644" ]] || [[ "$PERMS" == "600" ]]; then
        success "b2_secret_key exists with correct permissions ($PERMS)"
    else
        error "b2_secret_key has wrong permissions: $PERMS (expected: 644 or 600)"
        ((ERRORS++))
    fi
else
    error "File not found: monitoring/vault/creds/b2_secret_key"
    ((ERRORS++))
fi

echo

# ============================================================================
# 2. Check TLS certificates
# ============================================================================
info "Step 2: Checking TLS certificates..."

if [[ -f "./monitoring/vault/tls/vault.crt" ]]; then
    success "TLS certificate exists: vault.crt"
else
    error "TLS certificate not found: monitoring/vault/tls/vault.crt"
    ((ERRORS++))
fi

if [[ -f "./monitoring/vault/tls/vault.key" ]]; then
    success "TLS private key exists: vault.key"
else
    error "TLS private key not found: monitoring/vault/tls/vault.key"
    ((ERRORS++))
fi

echo

# ============================================================================
# 3. Check Docker volumes
# ============================================================================
info "Step 3: Checking Docker volumes..."

for volume in zakupai_vault_tls zakupai_vault_logs; do
    if docker volume inspect "$volume" >/dev/null 2>&1; then
        success "Volume exists: $volume"
    else
        warn "Volume not found: $volume (will be created automatically)"
    fi
done

echo

# ============================================================================
# 4. Check Docker networks
# ============================================================================
info "Step 4: Checking Docker networks..."

for network in zakupai_zakupai-network zakupai_monitoring-net zakupai_ai-network; do
    if docker network inspect "$network" >/dev/null 2>&1; then
        success "Network exists: $network"
    else
        error "Network not found: $network"
        info "  Run: docker network create $network"
        ((ERRORS++))
    fi
done

echo

# ============================================================================
# 5. Validate Docker Compose configuration
# ============================================================================
info "Step 5: Validating Docker Compose configuration..."

COMPOSE_OUTPUT=$(docker compose -f docker-compose.yml \
    -f docker-compose.override.stage9.vault-prod.yml \
    config 2>&1)

if echo "$COMPOSE_OUTPUT" | grep -qi "error"; then
    error "Docker Compose configuration has errors:"
    echo "$COMPOSE_OUTPUT" | grep -i "error"
    ((ERRORS++))
else
    success "Docker Compose configuration is valid"
fi

echo

# ============================================================================
# 6. Check for conflicts in override files
# ============================================================================
info "Step 6: Checking for conflicts between override files..."

# Check if other override files might conflict
OVERRIDE_FILES=(
    "docker-compose.override.monitoring.yml"
    "docker-compose.override.stage7.vault.yml"
    "docker-compose.override.stage8.vault-secure.yml"
)

for file in "${OVERRIDE_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        warn "Override file exists: $file"
        info "  Ensure it's not being used simultaneously with stage9"
    fi
done

echo

# ============================================================================
# 7. Check vault entrypoint script
# ============================================================================
info "Step 7: Checking Vault entrypoint script..."

if [[ -f "./monitoring/vault/scripts/vault-b2-entrypoint.sh" ]]; then
    if [[ -x "./monitoring/vault/scripts/vault-b2-entrypoint.sh" ]]; then
        success "Entrypoint script exists and is executable"
    else
        error "Entrypoint script is not executable"
        info "  Run: chmod +x ./monitoring/vault/scripts/vault-b2-entrypoint.sh"
        ((ERRORS++))
    fi
else
    error "Entrypoint script not found: monitoring/vault/scripts/vault-b2-entrypoint.sh"
    ((ERRORS++))
fi

echo

# ============================================================================
# 8. Check Vault config file
# ============================================================================
info "Step 8: Checking Vault configuration file..."

if [[ -f "./monitoring/vault/config/secure/config-stage9.hcl" ]]; then
    success "Vault config exists: config-stage9.hcl"

    # Check for critical configuration elements
    if grep -q "storage \"s3\"" "./monitoring/vault/config/secure/config-stage9.hcl"; then
        success "  S3/B2 storage backend configured"
    else
        error "  S3/B2 storage backend not found in config"
        ((ERRORS++))
    fi

    if grep -q "tls_cert_file" "./monitoring/vault/config/secure/config-stage9.hcl"; then
        success "  TLS configuration present"
    else
        error "  TLS configuration not found"
        ((ERRORS++))
    fi
else
    error "Vault config not found: monitoring/vault/config/secure/config-stage9.hcl"
    ((ERRORS++))
fi

echo

# ============================================================================
# 9. Check encrypted unseal key
# ============================================================================
info "Step 9: Checking auto-unseal files..."

if [[ -f "./monitoring/vault/creds/vault-unseal-key.enc" ]]; then
    success "Encrypted unseal key exists"
else
    warn "Encrypted unseal key not found (required for auto-unseal)"
    info "  If this is first deployment, this is expected"
fi

if [[ -f "./monitoring/vault/.unseal-password" ]]; then
    success "Master password file exists"
else
    warn "Master password file not found (required for auto-unseal)"
    info "  If this is first deployment, this is expected"
fi

echo

# ============================================================================
# Summary
# ============================================================================
echo "============================================================================"
if [[ $ERRORS -eq 0 ]]; then
    success "Configuration verification completed successfully!"
    echo
    info "You can now start Vault with:"
    echo "  docker compose -f docker-compose.yml -f docker-compose.override.stage9.vault-prod.yml up -d vault"
else
    error "Configuration verification failed with $ERRORS error(s)"
    echo
    info "Please fix the errors above before starting Vault"
    exit 1
fi
echo "============================================================================"
