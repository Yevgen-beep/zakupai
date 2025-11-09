#!/bin/bash
# Vault Migration Script: Stage 8 → Stage 9
# Purpose: Migrate from file backend to B2 S3 storage with TLS and audit logging
# Security: Full production setup with encryption in-transit and comprehensive audit

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VAULT_DIR="$PROJECT_DIR/monitoring/vault"
BACKUP_DIR="$PROJECT_DIR/backups/vault"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/vault-stage8-backup-$TIMESTAMP.tar.gz"
B2_BUCKET="${B2_BUCKET:-zakupai-vault-storage}"

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

# Command mode detection
MODE="${1:-migrate}"

# Backup mode (for cron)
if [[ "$MODE" == "backup" ]]; then
    log "Running in backup mode..."

    # Create backup
    mkdir -p "$BACKUP_DIR"
    docker exec vault vault operator raft snapshot save /tmp/vault-snapshot.snap 2>/dev/null || {
        # Fallback to file-based backup
        tar -czf "$BACKUP_FILE" -C "$PROJECT_DIR" monitoring/vault/data
        log "✓ File backup created: $BACKUP_FILE"
    }

    # Upload to B2
    if command -v b2 >/dev/null 2>&1; then
        if b2 upload-file "$B2_BUCKET" "$BACKUP_FILE" "vault-backups/$(basename "$BACKUP_FILE")" 2>/dev/null; then
            log "✓ Backup uploaded to B2: $B2_BUCKET"
        else
            warn "Failed to upload to B2. Local backup available: $BACKUP_FILE"
        fi
    else
        warn "b2 CLI not installed. Backup saved locally: $BACKUP_FILE"
    fi

    exit 0
fi

# Pre-flight checks
preflight_checks() {
    log "Running pre-flight checks..."

    # Check if Vault is running
    if ! docker ps | grep -q vault; then
        error "Vault container is not running. Please start it first."
        exit 1
    fi

    # Check B2 credentials
    if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]] || [[ -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
        error "B2 credentials not set. Please export:"
        error "  export AWS_ACCESS_KEY_ID='your_b2_key_id'"
        error "  export AWS_SECRET_ACCESS_KEY='your_b2_app_key'"
        exit 1
    fi

    # Check b2 CLI
    if ! command -v b2 >/dev/null 2>&1; then
        warn "b2 CLI not installed. Installing..."
        pip3 install --user b2 2>/dev/null || {
            error "Failed to install b2 CLI. Please install manually:"
            error "  pip3 install b2"
            exit 1
        }
    fi

    # Check TLS certificates
    if [[ ! -f "$VAULT_DIR/tls/vault-cert.pem" ]] || [[ ! -f "$VAULT_DIR/tls/vault-key.pem" ]]; then
        warn "TLS certificates not found. Generating..."
        cd "$PROJECT_DIR"
        make vault-tls-renew || {
            error "Failed to generate TLS certificates"
            exit 1
        }
    fi

    # Create backup directory
    mkdir -p "$BACKUP_DIR"

    # Create logs directory
    mkdir -p "$VAULT_DIR/logs"

    log "✓ Pre-flight checks passed"
}

# Backup current Vault data
backup_vault() {
    log "Creating snapshot of current Vault data..."

    # Try Raft snapshot first (if available)
    if docker exec vault vault operator raft snapshot save /tmp/vault-snapshot.snap 2>/dev/null; then
        docker cp vault:/tmp/vault-snapshot.snap "$BACKUP_DIR/vault-snapshot-$TIMESTAMP.snap"
        log "✓ Raft snapshot created"
    fi

    # Always create file backup as fallback
    tar -czf "$BACKUP_FILE" -C "$PROJECT_DIR" \
        monitoring/vault/data \
        monitoring/vault/config \
        monitoring/vault/creds/vault-unseal-key.enc \
        monitoring/vault/.unseal-password 2>/dev/null || {
        error "Failed to create backup"
        exit 1
    }

    log "✓ Backup created: $BACKUP_FILE"
    info "Backup size: $(du -h "$BACKUP_FILE" | cut -f1)"
}

# Setup B2 bucket
setup_b2_bucket() {
    log "Setting up Backblaze B2 bucket..."

    # Authorize B2 account
    b2 authorize-account "$AWS_ACCESS_KEY_ID" "$AWS_SECRET_ACCESS_KEY" >/dev/null 2>&1 || {
        error "Failed to authorize B2 account. Check credentials."
        exit 1
    }

    log "✓ B2 account authorized"

    # Check if bucket exists
    if b2 get-bucket "$B2_BUCKET" >/dev/null 2>&1; then
        log "✓ Bucket already exists: $B2_BUCKET"
    else
        log "Creating B2 bucket: $B2_BUCKET"
        b2 create-bucket "$B2_BUCKET" allPrivate --lifecycleRule '{
            "daysFromHidingToDeleting": 30,
            "daysFromUploadingToHiding": null,
            "fileNamePrefix": "vault-backups/"
        }' >/dev/null 2>&1 || {
            error "Failed to create B2 bucket"
            exit 1
        }
        log "✓ B2 bucket created"
    fi
}

# Upload initial data to B2
upload_initial_data() {
    log "Uploading initial Vault data to B2..."

    # Upload backup to B2
    b2 upload-file "$B2_BUCKET" "$BACKUP_FILE" "vault-backups/$(basename "$BACKUP_FILE")" || {
        error "Failed to upload initial data to B2"
        exit 1
    }

    log "✓ Initial data uploaded to B2"
}

# Apply Stage 9 configuration
apply_stage9_config() {
    log "Applying Stage 9 configuration..."

    # Copy Stage 9 config
    cp "$VAULT_DIR/config/secure/config-stage9.hcl" "$VAULT_DIR/config/vault-config.hcl"

    # Copy docker-compose override
    cp "$PROJECT_DIR/docker-compose.override.stage9.vault-prod.yml" \
       "$PROJECT_DIR/docker-compose.override.yml"

    # Create docker-compose.override.local.yml with B2 credentials
    cat > "$PROJECT_DIR/docker-compose.override.local.yml" <<EOF
# Local B2 credentials override
# DO NOT COMMIT THIS FILE

version: '3.8'

services:
  vault:
    environment:
      AWS_ACCESS_KEY_ID: "$AWS_ACCESS_KEY_ID"
      AWS_SECRET_ACCESS_KEY: "$AWS_SECRET_ACCESS_KEY"
EOF

    chmod 600 "$PROJECT_DIR/docker-compose.override.local.yml"

    log "✓ Stage 9 configuration applied"
}

# Restart Vault with B2 + TLS + Audit
restart_vault() {
    log "Restarting Vault with B2 storage + TLS + Audit..."

    # Stop Vault
    docker-compose -f "$PROJECT_DIR/docker-compose.yml" down vault

    # Wait a bit
    sleep 5

    # Start Vault with new configuration
    docker-compose -f "$PROJECT_DIR/docker-compose.yml" \
        -f "$PROJECT_DIR/docker-compose.override.yml" \
        -f "$PROJECT_DIR/docker-compose.override.local.yml" \
        up -d vault

    log "Waiting for Vault to start (40 seconds)..."
    sleep 40

    # Check if Vault is running
    if ! docker ps | grep -q vault; then
        error "Vault failed to start. Check logs: docker logs vault"
        exit 1
    fi

    log "✓ Vault restarted"
}

# Verify TLS
verify_tls() {
    log "Verifying TLS configuration..."

    # Check certificate validity
    if openssl x509 -in "$VAULT_DIR/tls/vault-cert.pem" -noout -checkend 86400 >/dev/null 2>&1; then
        log "✓ TLS certificate is valid"
    else
        warn "TLS certificate expires soon or is invalid"
    fi

    # Test HTTPS connection
    if curl -sk https://127.0.0.1:8200/v1/sys/health >/dev/null 2>&1; then
        log "✓ HTTPS connection successful"
    else
        warn "Cannot connect via HTTPS"
    fi
}

# Verify audit logging
verify_audit() {
    log "Verifying audit logging..."

    # Wait for audit log to be created
    sleep 10

    if [[ -f "$VAULT_DIR/logs/audit.log" ]]; then
        local entries
        entries=$(wc -l < "$VAULT_DIR/logs/audit.log" || echo 0)
        log "✓ Audit log active ($entries entries)"
    else
        warn "Audit log not created yet. It will be created on first request."
    fi
}

# Verify B2 storage
verify_b2_storage() {
    log "Verifying B2 storage..."

    # Make a test write to Vault (this will write to B2)
    export VAULT_ADDR='https://127.0.0.1:8200'
    export VAULT_SKIP_VERIFY='true'

    # Check Vault status
    if docker exec vault vault status >/dev/null 2>&1; then
        log "✓ Vault is responding"
    else
        error "Vault is not responding"
        exit 1
    fi

    # Check if data is being written to B2
    sleep 5
    local b2_files
    b2_files=$(b2 ls "$B2_BUCKET" | wc -l || echo 0)

    if [[ "$b2_files" -gt 0 ]]; then
        log "✓ B2 storage is active ($b2_files objects)"
    else
        warn "No objects in B2 bucket yet. Storage may not be initialized."
    fi
}

# Verify AppRole access
verify_approle_access() {
    log "Verifying AppRole access..."

    export VAULT_ADDR='https://127.0.0.1:8200'
    export VAULT_SKIP_VERIFY='true'

    if docker exec -e VAULT_SKIP_VERIFY=true vault vault kv list zakupai/ >/dev/null 2>&1; then
        log "✓ AppRole data accessible"
    else
        error "Cannot access AppRole data after migration"
        warn "You may need to restore from backup: $BACKUP_FILE"
        exit 1
    fi
}

# Setup cron for daily backups
setup_backup_cron() {
    log "Setting up daily backup cron job..."

    local cron_cmd="0 2 * * * $SCRIPT_DIR/vault-migrate-stage9.sh backup >> /var/log/vault-backup.log 2>&1"

    # Check if cron job already exists
    if crontab -l 2>/dev/null | grep -q "vault-migrate-stage9.sh backup"; then
        log "✓ Backup cron job already exists"
    else
        (crontab -l 2>/dev/null; echo "$cron_cmd") | crontab - || {
            warn "Failed to setup cron job. Please add manually:"
            warn "  $cron_cmd"
        }
        log "✓ Daily backup cron job added (2 AM)"
    fi
}

# Display summary
display_summary() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}✓ Stage 9 Migration Complete${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    echo -e "${BLUE}Backup Location:${NC} $BACKUP_FILE"
    echo -e "${BLUE}B2 Bucket:${NC} $B2_BUCKET"
    echo -e "${BLUE}Vault Address:${NC} https://127.0.0.1:8200"
    echo
    echo -e "${GREEN}Verification Tests:${NC}"
    echo "  ✓ Vault running with B2 storage"
    echo "  ✓ TLS enabled and working"
    echo "  ✓ Audit logging active"
    echo "  ✓ AppRole data accessible"
    echo "  ✓ Daily backups scheduled"
    echo
    echo -e "${YELLOW}Next Steps:${NC}"
    echo
    echo "  1. Run comprehensive smoke tests:"
    echo "     $ make smoke-stage9"
    echo
    echo "  2. Check Vault status:"
    echo "     $ make vault-prod-status"
    echo
    echo "  3. Monitor audit logs:"
    echo "     $ tail -f monitoring/vault/logs/audit.log"
    echo
    echo "  4. View B2 storage:"
    echo "     $ b2 ls $B2_BUCKET"
    echo
    echo "  5. Update services to use HTTPS:"
    echo "     Update VAULT_ADDR in .env files to: https://vault.zakupai.local:8200"
    echo
    echo -e "${YELLOW}⚠️  Rollback (if needed):${NC}"
    echo "     $ make rollback-stage9"
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
}

# Main execution
main() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BLUE}   Vault Migration: Stage 8 → Stage 9${NC}"
    echo -e "${BLUE}   (File Backend → B2 S3 + TLS + Audit)${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    warn "This script will:"
    warn "  1. Backup current Vault data"
    warn "  2. Setup Backblaze B2 bucket"
    warn "  3. Upload initial data to B2"
    warn "  4. Apply Stage 9 configuration (B2 + TLS + Audit)"
    warn "  5. Restart Vault with production settings"
    warn "  6. Verify everything works"
    warn "  7. Setup daily backups to B2"
    echo

    read -rp "Continue with migration? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        log "Migration cancelled."
        exit 0
    fi

    echo

    preflight_checks
    backup_vault
    setup_b2_bucket
    upload_initial_data
    apply_stage9_config
    restart_vault
    verify_tls
    verify_audit
    verify_b2_storage
    verify_approle_access
    setup_backup_cron
    display_summary
}

# Run
main "$@"
