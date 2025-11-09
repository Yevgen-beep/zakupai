#!/bin/bash
# Vault Auto-Unseal Script - Stage 8
# Purpose: Automatically unseal Vault on container startup using AES-256 encrypted keys
# Security: PBKDF2 with 250,000 iterations, no plain-text keys in filesystem

set -euo pipefail

# Configuration
VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
VAULT_CONFIG="${VAULT_CONFIG:-/vault/config/vault-config.hcl}"
ENCRYPTED_KEY_FILE="${ENCRYPTED_KEY_FILE:-/vault/creds/vault-unseal-key.enc}"
PASSWORD_FILE="${PASSWORD_FILE:-/vault/.unseal-password}"
MAX_UNSEAL_RETRIES=30
RETRY_DELAY=2

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $*"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $*" >&2
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $*"
}

# Decrypt unseal key using OpenSSL
decrypt_unseal_key() {
    local encrypted_file="$1"
    local password_file="$2"

    if [[ ! -f "$encrypted_file" ]]; then
        error "Encrypted key file not found: $encrypted_file"
        return 1
    fi

    if [[ ! -f "$password_file" ]]; then
        error "Password file not found: $password_file"
        return 1
    fi

    log "Decrypting unseal key..."

    # AES-256-CBC with PBKDF2 (250,000 iterations)
    openssl enc -d -aes-256-cbc -md sha256 -pbkdf2 -iter 250000 \
        -in "$encrypted_file" \
        -pass file:"$password_file" 2>/dev/null || {
        error "Failed to decrypt unseal key"
        return 1
    }
}

# Check if Vault is sealed
is_vault_sealed() {
    local status
    status=$(vault status -format=json 2>/dev/null | jq -r '.sealed' || echo "true")
    [[ "$status" == "true" ]]
}

# Wait for Vault to be ready
wait_for_vault() {
    local retries=0

    log "Waiting for Vault to be ready..."

    while [[ $retries -lt $MAX_UNSEAL_RETRIES ]]; do
        if curl -sf "${VAULT_ADDR}/v1/sys/health" >/dev/null 2>&1; then
            log "Vault is responding"
            return 0
        fi

        retries=$((retries + 1))
        if [[ $retries -lt $MAX_UNSEAL_RETRIES ]]; then
            sleep "$RETRY_DELAY"
        fi
    done

    error "Vault did not become ready after $MAX_UNSEAL_RETRIES retries"
    return 1
}

# Unseal Vault
unseal_vault() {
    local unseal_key="$1"

    log "Attempting to unseal Vault..."

    echo "$unseal_key" | vault operator unseal - >/dev/null 2>&1 || {
        error "Failed to unseal Vault"
        return 1
    }

    log "Vault unseal command executed successfully"
}

# Main execution
main() {
    log "Starting Vault auto-unseal process..."

    # Start Vault server in background
    log "Starting Vault server..."
    vault server -config="$VAULT_CONFIG" &
    VAULT_PID=$!

    log "Vault server started (PID: $VAULT_PID)"

    # Wait for Vault to be ready
    if ! wait_for_vault; then
        error "Vault failed to start"
        kill "$VAULT_PID" 2>/dev/null || true
        exit 1
    fi

    # Check if Vault is initialized
    if ! vault status >/dev/null 2>&1; then
        warn "Vault is not initialized yet. Please run 'vault operator init' first."
        warn "Vault will remain sealed until initialized and unseal keys are encrypted."
        wait "$VAULT_PID"
        exit 0
    fi

    # Check if Vault is already unsealed
    if ! is_vault_sealed; then
        log "Vault is already unsealed. Nothing to do."
        wait "$VAULT_PID"
        exit 0
    fi

    # Decrypt and unseal
    log "Vault is sealed. Attempting auto-unseal..."

    if [[ -f "$ENCRYPTED_KEY_FILE" ]]; then
        UNSEAL_KEY=$(decrypt_unseal_key "$ENCRYPTED_KEY_FILE" "$PASSWORD_FILE")

        if [[ -n "$UNSEAL_KEY" ]]; then
            if unseal_vault "$UNSEAL_KEY"; then
                # Verify unsealed
                if ! is_vault_sealed; then
                    log "✓ Vault successfully unsealed!"
                else
                    warn "Vault unseal command succeeded but Vault is still sealed."
                    warn "This may indicate that threshold is not met (need more keys)."
                fi
            fi

            # Clear unseal key from memory
            unset UNSEAL_KEY
        fi
    else
        warn "Encrypted unseal key file not found: $ENCRYPTED_KEY_FILE"
        warn "Vault will remain sealed. Please unseal manually or provide encrypted key."
    fi

    # Keep Vault running
    log "Auto-unseal process completed. Vault server is running."
    wait "$VAULT_PID"
}

# Trap signals
trap 'log "Received signal, shutting down..."; kill $VAULT_PID 2>/dev/null || true; exit 0' SIGTERM SIGINT

# Run main
main "$@"
