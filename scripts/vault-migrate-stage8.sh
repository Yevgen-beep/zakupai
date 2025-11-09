#!/bin/bash
# Vault Migration Script: Stage 7 → Stage 8
# Purpose: Migrate from manual unseal to auto-unseal with encrypted keys
# Security: AES-256 + PBKDF2 ≥250k iterations

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VAULT_DIR="$PROJECT_DIR/monitoring/vault"
BACKUP_DIR="$PROJECT_DIR/backups/vault"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/vault-stage7-backup-$TIMESTAMP.tar.gz"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $*"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $*" >&2
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $*"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO:${NC} $*"
}

# Pre-flight checks
preflight_checks() {
    log "Running pre-flight checks..."

    # Check if Vault is running
    if ! docker ps | grep -q vault; then
        error "Vault container is not running. Please start it first."
        exit 1
    fi

    # Check if we can connect to Vault
    export VAULT_ADDR='http://127.0.0.1:8200'
    if ! docker exec vault vault status >/dev/null 2>&1; then
        error "Cannot connect to Vault. Check if Vault is initialized and unsealed."
        exit 1
    fi

    # Create backup directory
    mkdir -p "$BACKUP_DIR"

    log "✓ Pre-flight checks passed"
}

# Backup current Vault data
backup_vault() {
    log "Creating backup of current Vault data..."

    # Backup directories
    local backup_paths=(
        "$VAULT_DIR/data"
        "$VAULT_DIR/config"
    )

    # Create tarball
    tar -czf "$BACKUP_FILE" -C "$PROJECT_DIR" \
        monitoring/vault/data \
        monitoring/vault/config 2>/dev/null || {
        error "Failed to create backup"
        exit 1
    }

    log "✓ Backup created: $BACKUP_FILE"
    info "Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"
}

# Verify Vault is unsealed
verify_unsealed() {
    log "Verifying Vault is unsealed..."

    local sealed
    sealed=$(docker exec vault vault status -format=json | jq -r '.sealed')

    if [[ "$sealed" == "true" ]]; then
        error "Vault is sealed. Please unseal it before migration."
        exit 1
    fi

    log "✓ Vault is unsealed"
}

# Export AppRole credentials for verification
export_approle_test() {
    log "Exporting AppRole test data for verification..."

    # Test reading a secret
    if docker exec vault vault kv list zakupai/ >/dev/null 2>&1; then
        log "✓ AppRole data accessible"
    else
        warn "Cannot access AppRole data. Continuing anyway..."
    fi
}

# Encrypt unseal keys
encrypt_keys() {
    log "Encrypting unseal keys..."

    # Check if encryption script exists
    if [[ ! -f "$VAULT_DIR/scripts/encrypt-unseal.sh" ]]; then
        error "Encryption script not found: $VAULT_DIR/scripts/encrypt-unseal.sh"
        exit 1
    fi

    # Run encryption script
    info "Please follow the prompts to encrypt your unseal keys..."
    echo

    cd "$VAULT_DIR"
    ./scripts/encrypt-unseal.sh || {
        error "Failed to encrypt unseal keys"
        exit 1
    }

    log "✓ Unseal keys encrypted"
}

# Apply Stage 8 configuration
apply_stage8_config() {
    log "Applying Stage 8 configuration..."

    # Copy Stage 8 config
    cp "$VAULT_DIR/config/secure/config.hcl" "$VAULT_DIR/config/vault-config.hcl"

    # Copy docker-compose override
    cp "$PROJECT_DIR/docker-compose.override.stage8.vault-secure.yml" \
       "$PROJECT_DIR/docker-compose.override.yml"

    log "✓ Stage 8 configuration applied"
}

# Restart Vault with auto-unseal
restart_vault() {
    log "Restarting Vault with auto-unseal..."

    # Stop Vault
    docker-compose -f "$PROJECT_DIR/docker-compose.yml" down vault

    # Wait a bit
    sleep 5

    # Start Vault with new configuration
    docker-compose -f "$PROJECT_DIR/docker-compose.yml" up -d vault

    log "Waiting for Vault to start (30 seconds)..."
    sleep 30

    # Check if Vault is running
    if ! docker ps | grep -q vault; then
        error "Vault failed to start. Check logs: docker logs vault"
        exit 1
    fi

    log "✓ Vault restarted"
}

# Verify auto-unseal
verify_auto_unseal() {
    log "Verifying auto-unseal functionality..."

    # Check Vault status
    local sealed
    sealed=$(docker exec vault vault status -format=json 2>/dev/null | jq -r '.sealed' || echo "true")

    if [[ "$sealed" == "false" ]]; then
        log "✓ Vault is unsealed automatically!"
    else
        error "Vault is still sealed. Auto-unseal may have failed."
        warn "Check logs: docker logs vault"
        exit 1
    fi

    # Test restart
    log "Testing auto-unseal on restart..."
    docker restart vault
    sleep 20

    sealed=$(docker exec vault vault status -format=json 2>/dev/null | jq -r '.sealed' || echo "true")

    if [[ "$sealed" == "false" ]]; then
        log "✓ Auto-unseal works on restart!"
    else
        error "Auto-unseal failed on restart"
        exit 1
    fi
}

# Verify AppRole access
verify_approle_access() {
    log "Verifying AppRole access..."

    if docker exec vault vault kv list zakupai/ >/dev/null 2>&1; then
        log "✓ AppRole data still accessible"
    else
        error "Cannot access AppRole data after migration"
        warn "You may need to restore from backup: $BACKUP_FILE"
        exit 1
    fi
}

# Display summary
display_summary() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}✓ Stage 8 Migration Complete${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    echo -e "${BLUE}Backup Location:${NC} $BACKUP_FILE"
    echo -e "${BLUE}Vault Status:${NC} Auto-Unseal Enabled"
    echo
    echo -e "${GREEN}Verification Tests:${NC}"
    echo "  ✓ Vault unsealed automatically"
    echo "  ✓ Auto-unseal works on restart"
    echo "  ✓ AppRole data accessible"
    echo
    echo -e "${YELLOW}Next Steps:${NC}"
    echo
    echo "  1. Test Vault access:"
    echo "     $ make vault-secure-status"
    echo
    echo "  2. Test AppRole access:"
    echo "     $ make vault-secure-test"
    echo
    echo "  3. Monitor Vault logs:"
    echo "     $ docker logs vault -f"
    echo
    echo "  4. Proceed to Stage 9 when ready:"
    echo "     $ ./scripts/vault-migrate-stage9.sh"
    echo
    echo -e "${YELLOW}⚠️  Rollback (if needed):${NC}"
    echo "     $ make rollback-stage8"
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
}

# Main execution
main() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BLUE}   Vault Migration: Stage 7 → Stage 8${NC}"
    echo -e "${BLUE}   (Manual Unseal → Auto-Unseal)${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    warn "This script will:"
    warn "  1. Backup current Vault data"
    warn "  2. Encrypt your unseal keys"
    warn "  3. Apply Stage 8 configuration"
    warn "  4. Restart Vault with auto-unseal"
    warn "  5. Verify everything works"
    echo

    read -rp "Continue with migration? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        log "Migration cancelled."
        exit 0
    fi

    echo

    preflight_checks
    backup_vault
    verify_unsealed
    export_approle_test
    encrypt_keys
    apply_stage8_config
    restart_vault
    verify_auto_unseal
    verify_approle_access
    display_summary
}

# Run
main "$@"
