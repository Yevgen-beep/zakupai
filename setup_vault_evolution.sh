#!/bin/bash
# Vault Evolution Automatic Installer
# Purpose: Automated migration from Stage 7 → Stage 8 → Stage 9
# Usage: ./setup_vault_evolution.sh [--stage7-only|--stage8-only|--stage9-final|--verify|--rollback]

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_DIR="$SCRIPT_DIR/monitoring/vault"
BACKUP_DIR="$SCRIPT_DIR/backups/vault"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Flags
DRY_RUN=false
SKIP_CONFIRM=false
TARGET_STAGE="9"
MODE="install"

# Progress tracking
STEPS_TOTAL=0
STEPS_COMPLETED=0

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

success() {
    echo -e "${CYAN}[$(date +'%Y-%m-%d %H:%M:%S')] SUCCESS:${NC} $*"
}

step() {
    STEPS_COMPLETED=$((STEPS_COMPLETED + 1))
    echo -e "${MAGENTA}[Step $STEPS_COMPLETED/$STEPS_TOTAL]${NC} $*"
}

# Parse arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --stage7-only)
                TARGET_STAGE="7"
                shift
                ;;
            --stage8-only)
                TARGET_STAGE="8"
                shift
                ;;
            --stage9-final)
                TARGET_STAGE="9"
                shift
                ;;
            --verify)
                MODE="verify"
                shift
                ;;
            --rollback)
                MODE="rollback"
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --yes|-y)
                SKIP_CONFIRM=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat <<EOF
Vault Evolution Automatic Installer

Usage: ./setup_vault_evolution.sh [OPTIONS]

Options:
  --stage7-only       Apply Stage 7 configuration only (manual unseal)
  --stage8-only       Apply Stage 8 configuration only (auto-unseal file)
  --stage9-final      Apply Stage 9 configuration (B2 + TLS + audit) [default]
  --verify            Run post-deployment verification only
  --rollback          Interactive rollback menu
  --dry-run           Show what would be done without making changes
  --yes, -y           Skip confirmation prompts
  --help, -h          Show this help message

Examples:
  ./setup_vault_evolution.sh                    # Full migration to Stage 9
  ./setup_vault_evolution.sh --stage8-only      # Migrate to Stage 8 only
  ./setup_vault_evolution.sh --verify           # Verify current deployment
  ./setup_vault_evolution.sh --rollback         # Rollback wizard

EOF
}

# Banner
show_banner() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${CYAN}        🔐 Vault Evolution Automatic Installer 🔐${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    echo -e "  ${BLUE}Target Stage:${NC} Stage $TARGET_STAGE"
    echo -e "  ${BLUE}Mode:${NC} $MODE"
    echo -e "  ${BLUE}Dry Run:${NC} $DRY_RUN"
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
}

# Pre-flight checks
preflight_checks() {
    step "Running pre-flight checks..."

    # Check required commands
    local missing_deps=()
    for cmd in docker docker-compose jq openssl curl; do
        if ! command -v $cmd >/dev/null 2>&1; then
            missing_deps+=("$cmd")
        fi
    done

    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        error "Missing required dependencies: ${missing_deps[*]}"
        error "Please install them and try again."
        exit 1
    fi

    # Check if running as correct user
    if [[ $EUID -eq 0 ]]; then
        warn "Running as root. This is not recommended."
        if [[ "$SKIP_CONFIRM" != "true" ]]; then
            read -rp "Continue anyway? (yes/no): " confirm
            [[ "$confirm" != "yes" ]] && exit 1
        fi
    fi

    # Check if docker is running
    if ! docker info >/dev/null 2>&1; then
        error "Docker is not running. Please start Docker first."
        exit 1
    fi

    # Create necessary directories
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$VAULT_DIR"/{config,creds,logs,tls,tests}

    success "Pre-flight checks passed"
}

# Setup permissions
setup_permissions() {
    step "Setting up secure permissions..."

    if [[ -d "$VAULT_DIR/creds" ]]; then
        chmod 700 "$VAULT_DIR/creds"
    fi

    if [[ -f "$VAULT_DIR/.unseal-password" ]]; then
        chmod 600 "$VAULT_DIR/.unseal-password"
    fi

    if [[ -f "$VAULT_DIR/creds/vault-unseal-key.enc" ]]; then
        chmod 600 "$VAULT_DIR/creds/vault-unseal-key.enc"
    fi

    if [[ -d "$VAULT_DIR/tls" ]]; then
        chmod 755 "$VAULT_DIR/tls"
        find "$VAULT_DIR/tls" -name "*.key" -exec chmod 600 {} \; 2>/dev/null || true
        find "$VAULT_DIR/tls" -name "*.pem" -type f -exec chmod 644 {} \; 2>/dev/null || true
    fi

    success "Permissions configured"
}

# Stage 7: Manual unseal
install_stage7() {
    step "Installing Stage 7 (Manual File Backend)..."

    if [[ "$DRY_RUN" == "true" ]]; then
        info "[DRY RUN] Would apply Stage 7 configuration"
        return 0
    fi

    make stage7

    success "Stage 7 installed (manual unseal required)"
}

# Stage 8: Auto-unseal
install_stage8() {
    step "Installing Stage 8 (Auto-Unseal File Backend)..."

    # Generate master password if not exists
    if [[ ! -f "$VAULT_DIR/.unseal-password" ]]; then
        info "Generating master password..."
        openssl rand -base64 32 > "$VAULT_DIR/.unseal-password"
        chmod 600 "$VAULT_DIR/.unseal-password"
        success "Master password generated"
    else
        info "Master password already exists"
    fi

    # Check if Vault is initialized
    if docker ps | grep -q vault; then
        export VAULT_ADDR='http://127.0.0.1:8200'
        if docker exec vault vault status >/dev/null 2>&1; then
            info "Vault is already initialized"

            # Check if unseal key is encrypted
            if [[ ! -f "$VAULT_DIR/creds/vault-unseal-key.enc" ]]; then
                warn "Unseal key is not encrypted yet."
                info "Please run: ./monitoring/vault/scripts/encrypt-unseal.sh"

                if [[ "$SKIP_CONFIRM" != "true" ]]; then
                    read -rp "Run encryption now? (yes/no): " confirm
                    if [[ "$confirm" == "yes" ]]; then
                        cd "$VAULT_DIR"
                        ./scripts/encrypt-unseal.sh
                    fi
                fi
            fi
        fi
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        info "[DRY RUN] Would apply Stage 8 configuration"
        return 0
    fi

    # Apply Stage 8
    if [[ -f "$VAULT_DIR/creds/vault-unseal-key.enc" ]]; then
        make stage8
        success "Stage 8 installed (auto-unseal enabled)"
    else
        error "Cannot proceed without encrypted unseal key"
        exit 1
    fi
}

# Stage 9: Production
install_stage9() {
    step "Installing Stage 9 (Production B2 + TLS + Audit)..."

    # Check B2 credentials
    if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]] || [[ -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
        warn "B2 credentials not found in environment."

        if [[ "$SKIP_CONFIRM" != "true" ]]; then
            echo
            info "Please enter your Backblaze B2 credentials:"
            read -rp "B2 Application Key ID: " b2_key_id
            read -rsp "B2 Application Key: " b2_key
            echo

            export AWS_ACCESS_KEY_ID="$b2_key_id"
            export AWS_SECRET_ACCESS_KEY="$b2_key"
        else
            error "B2 credentials required for Stage 9. Export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"
            exit 1
        fi
    else
        info "B2 credentials found in environment"
    fi

    # Install b2 CLI if needed
    if ! command -v b2 >/dev/null 2>&1; then
        warn "b2 CLI not installed. Installing..."
        pip3 install --user b2 || {
            error "Failed to install b2 CLI"
            exit 1
        }
    fi

    # Generate TLS certificates
    if [[ ! -f "$VAULT_DIR/tls/vault-cert.pem" ]]; then
        info "Generating TLS certificates..."
        make vault-tls-renew
        success "TLS certificates generated"
    else
        info "TLS certificates already exist"

        # Check expiry
        if ! openssl x509 -in "$VAULT_DIR/tls/vault-cert.pem" -noout -checkend 2592000 2>/dev/null; then
            warn "TLS certificate expires soon. Regenerating..."
            make vault-tls-renew
        fi
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        info "[DRY RUN] Would apply Stage 9 configuration"
        return 0
    fi

    # Apply Stage 9
    make stage9

    success "Stage 9 installed (production ready)"
}

# Setup cron backup
setup_backup_cron() {
    step "Setting up automated backups..."

    local cron_cmd="0 2 * * * cd $SCRIPT_DIR && ./scripts/vault-migrate-stage9.sh backup >> /var/log/vault-backup.log 2>&1"

    # Check if cron job exists
    if crontab -l 2>/dev/null | grep -q "vault-migrate-stage9.sh backup"; then
        info "Backup cron job already exists"
    else
        if [[ "$DRY_RUN" == "true" ]]; then
            info "[DRY RUN] Would add cron job: $cron_cmd"
        else
            (crontab -l 2>/dev/null; echo "$cron_cmd") | crontab - || {
                warn "Failed to setup cron job automatically"
                warn "Please add manually: $cron_cmd"
                return 0
            }
            success "Daily backup cron job added (2 AM)"
        fi
    fi
}

# Run smoke tests
run_smoke_tests() {
    step "Running smoke tests..."

    if [[ ! -f "$VAULT_DIR/tests/smoke-stage9.sh" ]]; then
        warn "Smoke test script not found. Skipping."
        return 0
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        info "[DRY RUN] Would run smoke tests"
        return 0
    fi

    # Wait for Vault to be ready
    info "Waiting 10 seconds for Vault to stabilize..."
    sleep 10

    if "$VAULT_DIR/tests/smoke-stage9.sh"; then
        success "Smoke tests passed"
        return 0
    else
        error "Smoke tests failed"
        return 1
    fi
}

# Verification mode
run_verification() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${CYAN}   Running Post-Deployment Verification${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    if [[ -f "$SCRIPT_DIR/verify_vault_postdeploy.sh" ]]; then
        "$SCRIPT_DIR/verify_vault_postdeploy.sh"
    else
        error "Verification script not found: verify_vault_postdeploy.sh"
        exit 1
    fi
}

# Rollback mode
run_rollback() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${YELLOW}   Vault Rollback Wizard${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    echo "Select rollback target:"
    echo "  1) Stage 9 → Stage 8 (B2 → File backend, disable TLS)"
    echo "  2) Stage 8 → Stage 7 (Auto-unseal → Manual unseal)"
    echo "  3) Cancel"
    echo

    read -rp "Choice [1-3]: " choice

    case $choice in
        1)
            warn "Rolling back from Stage 9 to Stage 8..."
            make rollback-stage9
            ;;
        2)
            warn "Rolling back from Stage 8 to Stage 7..."
            make rollback-stage8
            ;;
        3)
            info "Rollback cancelled."
            exit 0
            ;;
        *)
            error "Invalid choice"
            exit 1
            ;;
    esac
}

# Display final status
show_final_status() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}✓ Vault Evolution Setup Complete${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    echo -e "${BLUE}Current Configuration:${NC}"
    echo "  - Stage: $TARGET_STAGE"
    echo "  - Vault Address: ${VAULT_ADDR:-http://127.0.0.1:8200}"
    echo

    echo -e "${GREEN}Next Steps:${NC}"
    echo

    case $TARGET_STAGE in
        7)
            echo "  1. Start Vault:"
            echo "     $ docker-compose up -d vault"
            echo
            echo "  2. Initialize Vault (if not already):"
            echo "     $ make vault-secure-init"
            echo
            echo "  3. Unseal Vault manually:"
            echo "     $ vault operator unseal <key1>"
            echo "     $ vault operator unseal <key2>"
            echo "     $ vault operator unseal <key3>"
            ;;
        8)
            echo "  1. Check Vault status:"
            echo "     $ make vault-secure-status"
            echo
            echo "  2. Test auto-unseal:"
            echo "     $ docker restart vault && sleep 10 && vault status"
            echo
            echo "  3. Test AppRole access:"
            echo "     $ make vault-secure-test"
            echo
            echo "  4. Proceed to Stage 9:"
            echo "     $ ./setup_vault_evolution.sh --stage9-final"
            ;;
        9)
            echo "  1. Run verification:"
            echo "     $ ./verify_vault_postdeploy.sh"
            echo
            echo "  2. Check production status:"
            echo "     $ make vault-prod-status"
            echo
            echo "  3. Run smoke tests:"
            echo "     $ make smoke-stage9"
            echo
            echo "  4. Monitor Vault:"
            echo "     $ docker logs vault -f"
            echo
            echo "  5. Check audit logs:"
            echo "     $ tail -f monitoring/vault/logs/audit.log"
            ;;
    esac

    echo
    echo -e "${YELLOW}Documentation:${NC}"
    echo "  - Full Guide: docs/VAULT_MIGRATION_STAGE7_TO_STAGE9.md"
    echo "  - Admin Guide: docs/VAULT_ADMIN_GUIDE.md"
    echo "  - Operations: docs/VAULT_OPERATIONS.md"
    echo "  - Quick Start: README-final.md"
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
}

# Main execution
main() {
    parse_args "$@"
    show_banner

    # Handle special modes
    case $MODE in
        verify)
            run_verification
            exit 0
            ;;
        rollback)
            run_rollback
            exit 0
            ;;
    esac

    # Calculate total steps
    case $TARGET_STAGE in
        7) STEPS_TOTAL=4 ;;
        8) STEPS_TOTAL=5 ;;
        9) STEPS_TOTAL=8 ;;
    esac

    # Confirmation
    if [[ "$SKIP_CONFIRM" != "true" ]]; then
        warn "This will install Vault Stage $TARGET_STAGE configuration."
        read -rp "Continue? (yes/no): " confirm
        if [[ "$confirm" != "yes" ]]; then
            info "Installation cancelled."
            exit 0
        fi
        echo
    fi

    # Run installation
    preflight_checks
    setup_permissions

    case $TARGET_STAGE in
        7)
            install_stage7
            ;;
        8)
            install_stage7
            install_stage8
            ;;
        9)
            install_stage7
            install_stage8
            install_stage9
            setup_backup_cron
            run_smoke_tests || warn "Smoke tests failed, but installation completed"
            ;;
    esac

    show_final_status
}

# Run
main "$@"
