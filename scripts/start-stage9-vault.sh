#!/bin/bash
# ============================================================================
# Stage 9 Vault Startup Script
# ============================================================================
# Purpose: Start Vault with Stage 9 configuration and verify it's working
#
# Usage:
#   ./scripts/start-stage9-vault.sh
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

info "Starting Stage 9 Vault deployment..."
echo

# ============================================================================
# 1. Validate configuration first
# ============================================================================
info "Step 1: Validating configuration..."

if ./scripts/verify-stage9-config.sh; then
    success "Configuration validation passed"
else
    error "Configuration validation failed"
    exit 1
fi

echo

# ============================================================================
# 2. Stop existing Vault if running
# ============================================================================
info "Step 2: Stopping existing Vault containers..."

if docker ps -a --format '{{.Names}}' | grep -q "zakupai-vault"; then
    warn "Stopping existing Vault container..."
    docker compose down vault 2>/dev/null || true
    docker stop zakupai-vault 2>/dev/null || true
    docker rm zakupai-vault 2>/dev/null || true
    success "Existing Vault container stopped"
else
    info "No existing Vault container found"
fi

echo

# ============================================================================
# 3. Start TLS init container and Vault with Stage 9 config
# ============================================================================
info "Step 3: Starting TLS init container and Vault with Stage 9 configuration..."

# First, start the TLS init container
info "Starting vault-tls-init container..."
docker compose -f docker-compose.yml \
    -f docker-compose.override.stage9.vault-prod.yml \
    up -d vault-tls-init

# Wait for init container to complete
info "Waiting for TLS init to complete..."
MAX_INIT_WAIT=30
INIT_WAITED=0
while [[ $INIT_WAITED -lt $MAX_INIT_WAIT ]]; do
    INIT_STATUS=$(docker inspect zakupai-vault-tls-init --format='{{.State.Status}}' 2>/dev/null || echo "not_found")
    if [[ "$INIT_STATUS" == "exited" ]]; then
        EXIT_CODE=$(docker inspect zakupai-vault-tls-init --format='{{.State.ExitCode}}' 2>/dev/null || echo "1")
        if [[ "$EXIT_CODE" == "0" ]]; then
            success "TLS init container completed successfully"
            break
        else
            error "TLS init container failed with exit code $EXIT_CODE"
            docker logs zakupai-vault-tls-init
            exit 1
        fi
    fi
    sleep 2
    ((INIT_WAITED+=2))
done

if [[ $INIT_WAITED -ge $MAX_INIT_WAIT ]]; then
    warn "TLS init container did not complete in $MAX_INIT_WAIT seconds"
fi

# Now start Vault
info "Starting Vault container..."
docker compose -f docker-compose.yml \
    -f docker-compose.override.stage9.vault-prod.yml \
    up -d vault

if [[ $? -eq 0 ]]; then
    success "Vault container started"
else
    error "Failed to start Vault container"
    exit 1
fi

echo

# ============================================================================
# 4. Wait for Vault to initialize
# ============================================================================
info "Step 4: Waiting for Vault to initialize (max 60 seconds)..."

MAX_WAIT=60
WAITED=0

while [[ $WAITED -lt $MAX_WAIT ]]; do
    if docker ps --format '{{.Names}}' | grep -q "zakupai-vault"; then
        success "Vault container is running"
        break
    fi
    sleep 2
    ((WAITED+=2))
    echo -n "."
done

if [[ $WAITED -ge $MAX_WAIT ]]; then
    error "Vault container failed to start within $MAX_WAIT seconds"
    info "Check logs with: docker logs zakupai-vault"
    exit 1
fi

echo
echo

# ============================================================================
# 5. Check Docker secrets mounted
# ============================================================================
info "Step 5: Verifying Docker secrets are mounted..."

sleep 5  # Give container time to fully initialize

if docker exec zakupai-vault ls /run/secrets/b2_access_key_id >/dev/null 2>&1; then
    success "Secret mounted: /run/secrets/b2_access_key_id"
else
    error "Secret NOT mounted: /run/secrets/b2_access_key_id"
    error "Docker secrets mounting failed!"
    info "Check logs with: docker logs zakupai-vault"
    exit 1
fi

if docker exec zakupai-vault ls /run/secrets/b2_secret_key >/dev/null 2>&1; then
    success "Secret mounted: /run/secrets/b2_secret_key"
else
    error "Secret NOT mounted: /run/secrets/b2_secret_key"
    error "Docker secrets mounting failed!"
    info "Check logs with: docker logs zakupai-vault"
    exit 1
fi

# Check permissions
info "Checking secret file permissions..."
docker exec zakupai-vault ls -la /run/secrets/ || true

echo

# ============================================================================
# 6. Check Vault logs
# ============================================================================
info "Step 6: Checking Vault logs for errors..."

sleep 5

LOGS=$(docker logs zakupai-vault --tail=50 2>&1)

if echo "$LOGS" | grep -qi "permission denied"; then
    error "Found 'permission denied' errors in logs"
    echo "$LOGS" | grep -i "permission denied"
    exit 1
elif echo "$LOGS" | grep -qi "cat: can't open"; then
    error "Found 'can't open' errors in logs"
    echo "$LOGS" | grep -i "can't open"
    exit 1
elif echo "$LOGS" | grep -qi "error"; then
    warn "Found potential errors in logs (review manually):"
    echo "$LOGS" | grep -i "error" | head -5
else
    success "No critical errors found in logs"
fi

echo

# ============================================================================
# 7. Wait for Vault to unseal (if auto-unseal is configured)
# ============================================================================
info "Step 7: Waiting for Vault to unseal (max 90 seconds)..."

MAX_WAIT=90
WAITED=0

while [[ $WAITED -lt $MAX_WAIT ]]; do
    STATUS=$(docker exec zakupai-vault vault status -format=json 2>/dev/null || echo "{}")

    if echo "$STATUS" | jq -e '.sealed == false' >/dev/null 2>&1; then
        success "Vault is unsealed and ready!"
        break
    elif echo "$STATUS" | jq -e '.initialized == false' >/dev/null 2>&1; then
        warn "Vault is not initialized yet"
        info "This is expected for first deployment"
        break
    fi

    sleep 5
    ((WAITED+=5))
    echo -n "."
done

echo
echo

# ============================================================================
# 8. Display Vault status
# ============================================================================
info "Step 8: Displaying Vault status..."
echo

docker exec zakupai-vault vault status 2>&1 || true

echo

# ============================================================================
# 9. Verify B2 backend is active
# ============================================================================
info "Step 9: Verifying B2 storage backend..."

if docker logs zakupai-vault --tail=100 2>&1 | grep -qi "s3.*backblaze"; then
    success "Backblaze B2 backend detected in logs"
elif docker logs zakupai-vault --tail=100 2>&1 | grep -qi "storage.*s3"; then
    success "S3 storage backend detected in logs"
else
    warn "Could not confirm B2/S3 backend from logs"
    info "Check manually: docker logs zakupai-vault | grep storage"
fi

echo

# ============================================================================
# Summary
# ============================================================================
echo "============================================================================"
success "Stage 9 Vault deployment completed!"
echo
info "Useful commands:"
echo "  • View logs:       docker logs zakupai-vault --tail=50 -f"
echo "  • Check status:    docker exec zakupai-vault vault status"
echo "  • List secrets:    docker exec zakupai-vault ls -la /run/secrets/"
echo "  • Stop Vault:      docker compose down vault"
echo "  • Restart Vault:   docker compose restart vault"
echo
info "Next steps:"
echo "  1. If Vault is sealed, check auto-unseal configuration"
echo "  2. If Vault is not initialized, run vault operator init"
echo "  3. Monitor logs for B2 connectivity issues"
echo "============================================================================"
