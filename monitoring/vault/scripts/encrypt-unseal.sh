#!/bin/bash
# Vault Unseal Key Encryption Script
# Purpose: Encrypt Vault unseal keys with AES-256 for Stage 8 auto-unseal
# Security: PBKDF2 with 250,000 iterations, secure key derivation

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_DIR="${VAULT_DIR:-$(dirname "$SCRIPT_DIR")}"
CREDS_DIR="$VAULT_DIR/creds"
PASSWORD_FILE="$VAULT_DIR/.unseal-password"
UNSEAL_KEY_FILE="$CREDS_DIR/vault-unseal-key.txt"
ENCRYPTED_KEY_FILE="$CREDS_DIR/vault-unseal-key.enc"

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

# Check prerequisites
check_prerequisites() {
    if ! command -v openssl >/dev/null 2>&1; then
        error "openssl is not installed. Please install it first."
        exit 1
    fi

    if [[ ! -d "$CREDS_DIR" ]]; then
        log "Creating credentials directory: $CREDS_DIR"
        mkdir -p "$CREDS_DIR"
        chmod 700 "$CREDS_DIR"
    fi
}

# Generate master password
generate_master_password() {
    if [[ -f "$PASSWORD_FILE" ]]; then
        warn "Master password file already exists: $PASSWORD_FILE"
        read -rp "Do you want to regenerate it? (y/N): " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            log "Using existing master password."
            return 0
        fi
    fi

    log "Generating new master password (32 bytes, base64 encoded)..."
    openssl rand -base64 32 > "$PASSWORD_FILE"
    chmod 600 "$PASSWORD_FILE"

    info "Master password saved to: $PASSWORD_FILE"
    warn "IMPORTANT: Keep this file secure and backed up!"
    echo
}

# Input unseal key
input_unseal_key() {
    if [[ -f "$UNSEAL_KEY_FILE" ]]; then
        warn "Plain-text unseal key file already exists: $UNSEAL_KEY_FILE"
        read -rp "Do you want to use it? (Y/n): " confirm
        if [[ ! "$confirm" =~ ^[Nn]$ ]]; then
            return 0
        fi
    fi

    echo
    info "Please enter your Vault unseal key:"
    info "(You can find it in the output of 'vault operator init')"
    echo
    read -rsp "Unseal Key: " unseal_key
    echo

    if [[ -z "$unseal_key" ]]; then
        error "Unseal key cannot be empty."
        exit 1
    fi

    echo -n "$unseal_key" > "$UNSEAL_KEY_FILE"
    chmod 600 "$UNSEAL_KEY_FILE"

    log "Unseal key saved temporarily to: $UNSEAL_KEY_FILE"
}

# Encrypt unseal key
encrypt_unseal_key() {
    if [[ ! -f "$UNSEAL_KEY_FILE" ]]; then
        error "Unseal key file not found: $UNSEAL_KEY_FILE"
        exit 1
    fi

    if [[ ! -f "$PASSWORD_FILE" ]]; then
        error "Master password file not found: $PASSWORD_FILE"
        exit 1
    fi

    log "Encrypting unseal key with AES-256-CBC + PBKDF2 (250,000 iterations)..."

    openssl enc -aes-256-cbc -md sha256 -pbkdf2 -iter 250000 \
        -in "$UNSEAL_KEY_FILE" \
        -out "$ENCRYPTED_KEY_FILE" \
        -pass file:"$PASSWORD_FILE" || {
        error "Failed to encrypt unseal key"
        exit 1
    }

    chmod 600 "$ENCRYPTED_KEY_FILE"

    log "✓ Unseal key encrypted successfully!"
    info "Encrypted key saved to: $ENCRYPTED_KEY_FILE"
}

# Verify encryption
verify_encryption() {
    log "Verifying encryption..."

    local decrypted
    decrypted=$(openssl enc -d -aes-256-cbc -md sha256 -pbkdf2 -iter 250000 \
        -in "$ENCRYPTED_KEY_FILE" \
        -pass file:"$PASSWORD_FILE" 2>/dev/null) || {
        error "Failed to decrypt. Verification failed!"
        exit 1
    }

    local original
    original=$(cat "$UNSEAL_KEY_FILE")

    if [[ "$decrypted" == "$original" ]]; then
        log "✓ Encryption verified successfully!"
    else
        error "Decrypted content does not match original. Something went wrong!"
        exit 1
    fi
}

# Cleanup plain-text key
cleanup_plaintext() {
    if [[ -f "$UNSEAL_KEY_FILE" ]]; then
        warn "Removing plain-text unseal key file for security..."

        # Secure deletion (overwrite with random data before deletion)
        shred -vfz -n 3 "$UNSEAL_KEY_FILE" 2>/dev/null || {
            # Fallback if shred is not available
            dd if=/dev/urandom of="$UNSEAL_KEY_FILE" bs=1k count=1 2>/dev/null || true
            rm -f "$UNSEAL_KEY_FILE"
        }

        log "✓ Plain-text unseal key securely deleted."
    fi
}

# Display summary
display_summary() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}✓ Unseal Key Encryption Complete${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    echo -e "${BLUE}Encrypted Key:${NC} $ENCRYPTED_KEY_FILE"
    echo -e "${BLUE}Master Password:${NC} $PASSWORD_FILE"
    echo
    echo -e "${YELLOW}⚠️  IMPORTANT SECURITY NOTES:${NC}"
    echo
    echo "  1. Keep '$PASSWORD_FILE' SECURE and BACKED UP!"
    echo "  2. Without it, you CANNOT decrypt your unseal key."
    echo "  3. This file is in .gitignore - do NOT commit it."
    echo "  4. Store a backup in a secure location (1Password, encrypted USB, etc.)."
    echo "  5. Plain-text unseal key has been securely deleted."
    echo
    echo -e "${GREEN}Next Steps:${NC}"
    echo
    echo "  1. Apply Stage 8 configuration:"
    echo "     $ make stage8"
    echo
    echo "  2. Restart Vault (auto-unseal will work):"
    echo "     $ docker restart vault"
    echo
    echo "  3. Verify Vault is unsealed:"
    echo "     $ vault status"
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
}

# Main execution
main() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BLUE}   Vault Unseal Key Encryption Tool - Stage 8${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    check_prerequisites
    generate_master_password
    input_unseal_key
    encrypt_unseal_key
    verify_encryption
    cleanup_plaintext
    display_summary
}

# Run
main "$@"
