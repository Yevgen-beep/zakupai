#!/bin/bash
# ============================================================================
# Stage 9 Vault Preparation Script
# ============================================================================
# Purpose: Prepare TLS certificates and secrets for Stage 9 Vault deployment
#
# This script:
#   1. Creates vault_tls volume if not exists
#   2. Copies TLS certificates to volume
#   3. Fixes file permissions for Docker secrets
#   4. Validates configuration
#
# Usage:
#   sudo ./scripts/prepare-stage9-vault.sh
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

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   error "This script must be run as root (use sudo)"
   exit 1
fi

PROJECT_ROOT="/home/mint/projects/claude_sandbox/zakupai"
cd "$PROJECT_ROOT" || exit 1

info "Starting Stage 9 Vault preparation..."
echo

# ============================================================================
# 1. Fix Docker secrets file permissions
# ============================================================================
info "Step 1: Fixing B2 secrets file permissions..."

if [[ -f "./monitoring/vault/creds/b2_access_key_id" ]]; then
    chmod 644 "./monitoring/vault/creds/b2_access_key_id"
    success "Fixed permissions: b2_access_key_id (644)"
else
    error "File not found: monitoring/vault/creds/b2_access_key_id"
    exit 1
fi

if [[ -f "./monitoring/vault/creds/b2_secret_key" ]]; then
    chmod 644 "./monitoring/vault/creds/b2_secret_key"
    success "Fixed permissions: b2_secret_key (644)"
else
    error "File not found: monitoring/vault/creds/b2_secret_key"
    exit 1
fi

echo

# ============================================================================
# 2. Create vault_tls volume if not exists
# ============================================================================
info "Step 2: Checking vault_tls volume..."

if docker volume inspect zakupai_vault_tls >/dev/null 2>&1; then
    warn "Volume 'zakupai_vault_tls' already exists"
else
    docker volume create zakupai_vault_tls
    success "Created volume: zakupai_vault_tls"
fi

echo

# ============================================================================
# 3. Copy TLS certificates to volume
# ============================================================================
info "Step 3: Copying TLS certificates to volume..."

# Check if certificates exist
if [[ ! -f "./monitoring/vault/tls/vault.crt" ]] || [[ ! -f "./monitoring/vault/tls/vault.key" ]]; then
    error "TLS certificates not found in monitoring/vault/tls/"
    error "Run: ./monitoring/vault/tls/generate-certs.sh"
    exit 1
fi

# Use temporary container to copy files to volume
docker run --rm \
    -v zakupai_vault_tls:/vault/tls \
    -v "$PROJECT_ROOT/monitoring/vault/tls:/source:ro" \
    alpine:latest \
    sh -c "
        cp /source/vault.crt /vault/tls/vault.crt && \
        cp /source/vault.key /vault/tls/vault.key && \
        chown -R 100:100 /vault/tls && \
        chmod 640 /vault/tls/vault.key && \
        chmod 644 /vault/tls/vault.crt && \
        ls -la /vault/tls/
    "

success "TLS certificates copied to vault_tls volume"
echo

# ============================================================================
# 4. Create vault_logs volume if not exists
# ============================================================================
info "Step 4: Checking vault_logs volume..."

if docker volume inspect zakupai_vault_logs >/dev/null 2>&1; then
    warn "Volume 'zakupai_vault_logs' already exists"
else
    docker volume create zakupai_vault_logs
    success "Created volume: zakupai_vault_logs"
fi

# Fix permissions
docker run --rm \
    -v zakupai_vault_logs:/vault/logs \
    alpine:latest \
    sh -c "chown -R 100:100 /vault/logs && chmod 755 /vault/logs"

success "vault_logs volume ready"
echo

# ============================================================================
# 5. Validate configuration
# ============================================================================
info "Step 5: Validating Docker Compose configuration..."

if docker compose -f docker-compose.yml \
    -f docker-compose.override.stage9.vault-prod.yml \
    config -q 2>&1; then
    success "Docker Compose configuration is valid"
else
    error "Docker Compose configuration has errors"
    exit 1
fi

echo

# ============================================================================
# 6. Verify networks exist
# ============================================================================
info "Step 6: Verifying Docker networks..."

for network in zakupai_zakupai-network zakupai_monitoring-net zakupai_ai-network; do
    if docker network inspect "$network" >/dev/null 2>&1; then
        success "Network exists: $network"
    else
        error "Network not found: $network"
        info "Creating network: $network"
        docker network create "$network"
        success "Created network: $network"
    fi
done

echo

# ============================================================================
# Summary
# ============================================================================
success "Stage 9 Vault preparation completed successfully!"
echo
info "Next steps:"
echo "  1. Start Vault:"
echo "     docker compose -f docker-compose.yml -f docker-compose.override.stage9.vault-prod.yml up -d vault"
echo
echo "  2. Check logs:"
echo "     docker logs zakupai-vault --tail=50 -f"
echo
echo "  3. Verify secrets mounted:"
echo "     docker exec zakupai-vault ls -la /run/secrets/"
echo
echo "  4. Check Vault status:"
echo "     docker exec zakupai-vault vault status"
echo
