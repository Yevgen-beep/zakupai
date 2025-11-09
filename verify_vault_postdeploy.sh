#!/bin/bash
# Vault Post-Deployment Verification Script
# Purpose: Comprehensive validation of Vault deployment
# Usage: ./verify_vault_postdeploy.sh

set -euo pipefail

# Configuration
VAULT_ADDR="${VAULT_ADDR:-https://127.0.0.1:8200}"
VAULT_SKIP_VERIFY="${VAULT_SKIP_VERIFY:-true}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_DIR="$SCRIPT_DIR/monitoring/vault"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Test results
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_WARNING=0
TESTS_TOTAL=0

declare -a FAILED_TESTS
declare -a WARNING_TESTS

# Helper functions
log() {
    echo -e "${CYAN}[VERIFY]${NC} $*"
}

pass() {
    echo -e "  ${GREEN}✓${NC} $*"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
}

fail() {
    echo -e "  ${RED}✗${NC} $*"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    FAILED_TESTS+=("$1")
}

warn() {
    echo -e "  ${YELLOW}⚠${NC} $*"
    TESTS_WARNING=$((TESTS_WARNING + 1))
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    WARNING_TESTS+=("$1")
}

info() {
    echo -e "  ${BLUE}ℹ${NC} $*"
}

# Test 1: Docker container running
test_container_running() {
    log "Test 1: Vault container status"

    if docker ps --format '{{.Names}}' | grep -q '^vault$'; then
        local status=$(docker inspect vault --format='{{.State.Status}}')
        local health=$(docker inspect vault --format='{{.State.Health.Status}}' 2>/dev/null || echo "none")

        pass "Container running (status: $status, health: $health)"
    else
        fail "Container not running"
    fi
}

# Test 2: Vault sealed status
test_vault_sealed() {
    log "Test 2: Vault seal status"

    if docker ps | grep -q vault; then
        local sealed
        sealed=$(docker exec -e VAULT_SKIP_VERIFY="$VAULT_SKIP_VERIFY" vault \
            vault status -format=json 2>/dev/null | jq -r '.sealed' || echo "unknown")

        if [[ "$sealed" == "false" ]]; then
            pass "Vault is unsealed"
        elif [[ "$sealed" == "true" ]]; then
            fail "Vault is SEALED"
        else
            fail "Cannot determine seal status"
        fi
    else
        fail "Cannot connect to Vault"
    fi
}

# Test 3: Vault initialized
test_vault_initialized() {
    log "Test 3: Vault initialization status"

    if docker ps | grep -q vault; then
        local initialized
        initialized=$(docker exec -e VAULT_SKIP_VERIFY="$VAULT_SKIP_VERIFY" vault \
            vault status -format=json 2>/dev/null | jq -r '.initialized' || echo "unknown")

        if [[ "$initialized" == "true" ]]; then
            pass "Vault is initialized"
        else
            warn "Vault is not initialized yet"
        fi
    else
        fail "Cannot connect to Vault"
    fi
}

# Test 4: API endpoint reachability
test_api_reachable() {
    log "Test 4: API endpoint reachability"

    local proto="http"
    [[ "$VAULT_ADDR" =~ ^https ]] && proto="https"

    if curl -sk "${VAULT_ADDR}/v1/sys/health" >/dev/null 2>&1; then
        pass "API endpoint reachable ($proto)"
    else
        fail "API endpoint not reachable"
    fi
}

# Test 5: TLS configuration
test_tls_enabled() {
    log "Test 5: TLS configuration"

    if [[ "$VAULT_ADDR" =~ ^https ]]; then
        if [[ -f "$VAULT_DIR/tls/vault-cert.pem" ]]; then
            # Check certificate validity
            if openssl x509 -in "$VAULT_DIR/tls/vault-cert.pem" -noout -checkend 0 2>/dev/null; then
                local days_left
                days_left=$(( ($(date -d "$(openssl x509 -in "$VAULT_DIR/tls/vault-cert.pem" -noout -enddate | cut -d= -f2)" +%s) - $(date +%s)) / 86400 ))
                pass "TLS enabled and certificate valid ($days_left days remaining)"
            else
                fail "TLS certificate expired"
            fi
        else
            warn "TLS enabled but certificate file not found"
        fi
    else
        warn "TLS not enabled (using HTTP)"
    fi
}

# Test 6: Audit logging
test_audit_logging() {
    log "Test 6: Audit logging"

    if [[ -f "$VAULT_DIR/logs/audit.log" ]]; then
        local entries
        entries=$(wc -l < "$VAULT_DIR/logs/audit.log" 2>/dev/null || echo 0)

        if [[ "$entries" -gt 0 ]]; then
            pass "Audit log active ($entries entries)"
        else
            warn "Audit log exists but empty"
        fi
    else
        warn "Audit log not found (may not be enabled)"
    fi
}

# Test 7: Auth methods
test_auth_methods() {
    log "Test 7: Authentication methods"

    if docker ps | grep -q vault; then
        local auth_output
        auth_output=$(docker exec -e VAULT_SKIP_VERIFY="$VAULT_SKIP_VERIFY" vault \
            vault auth list 2>/dev/null || echo "")

        if echo "$auth_output" | grep -q "approle"; then
            pass "AppRole auth method enabled"
        else
            warn "AppRole auth method not found"
        fi

        if echo "$auth_output" | grep -q "token"; then
            pass "Token auth method enabled"
        else
            fail "Token auth method not found"
        fi
    else
        fail "Cannot connect to Vault"
    fi
}

# Test 8: KV engine
test_kv_engine() {
    log "Test 8: KV secret engine"

    if docker ps | grep -q vault; then
        if docker exec -e VAULT_SKIP_VERIFY="$VAULT_SKIP_VERIFY" vault \
            vault secrets list 2>/dev/null | grep -q "zakupai"; then
            pass "zakupai/ KV engine accessible"
        else
            warn "zakupai/ KV engine not found"
        fi
    else
        fail "Cannot connect to Vault"
    fi
}

# Test 9: Test KV operations
test_kv_operations() {
    log "Test 9: KV read/write operations"

    if docker ps | grep -q vault; then
        local test_path="zakupai/verify-test/deployment-$(date +%s)"

        # Try to write
        if docker exec -e VAULT_SKIP_VERIFY="$VAULT_SKIP_VERIFY" vault \
            vault kv put "$test_path" test=true timestamp="$(date -Iseconds)" >/dev/null 2>&1; then

            # Try to read
            if docker exec -e VAULT_SKIP_VERIFY="$VAULT_SKIP_VERIFY" vault \
                vault kv get "$test_path" >/dev/null 2>&1; then
                pass "KV read/write operations working"

                # Cleanup
                docker exec -e VAULT_SKIP_VERIFY="$VAULT_SKIP_VERIFY" vault \
                    vault kv delete "$test_path" >/dev/null 2>&1 || true
            else
                fail "KV read operation failed"
            fi
        else
            fail "KV write operation failed"
        fi
    else
        fail "Cannot connect to Vault"
    fi
}

# Test 10: Prometheus metrics
test_prometheus_metrics() {
    log "Test 10: Prometheus metrics endpoint"

    local metrics_url="${VAULT_ADDR}/v1/sys/metrics?format=prometheus"

    if curl -sk "$metrics_url" 2>/dev/null | grep -q "vault_core_unsealed"; then
        pass "Prometheus metrics available"
    else
        warn "Prometheus metrics not available"
    fi
}

# Test 11: Storage backend
test_storage_backend() {
    log "Test 11: Storage backend configuration"

    if docker ps | grep -q vault; then
        # Check environment variables for B2
        if docker exec vault env 2>/dev/null | grep -q "AWS_ACCESS_KEY_ID"; then
            pass "B2 S3 storage configured (Stage 9)"
        else
            info "File storage configured (Stage 7/8)"
        fi
    else
        fail "Cannot connect to Vault"
    fi
}

# Test 12: Auto-unseal configuration
test_auto_unseal() {
    log "Test 12: Auto-unseal configuration"

    if [[ -f "$VAULT_DIR/creds/vault-unseal-key.enc" ]]; then
        if [[ -f "$VAULT_DIR/.unseal-password" ]]; then
            pass "Auto-unseal configured (encrypted key + password present)"
        else
            warn "Encrypted key found but password missing"
        fi
    else
        info "Auto-unseal not configured (manual unseal)"
    fi
}

# Test 13: Backup configuration
test_backup_config() {
    log "Test 13: Backup configuration"

    if crontab -l 2>/dev/null | grep -q "vault-migrate-stage9.sh backup"; then
        pass "Automated backups configured (cron)"
    else
        warn "Automated backups not configured"
    fi
}

# Test 14: File permissions
test_file_permissions() {
    log "Test 14: Security file permissions"

    local issues=0

    if [[ -f "$VAULT_DIR/.unseal-password" ]]; then
        local perms=$(stat -c "%a" "$VAULT_DIR/.unseal-password" 2>/dev/null || stat -f "%A" "$VAULT_DIR/.unseal-password" 2>/dev/null)
        if [[ "$perms" != "600" ]]; then
            warn "Insecure permissions on .unseal-password: $perms (should be 600)"
            issues=$((issues + 1))
        fi
    fi

    if [[ -f "$VAULT_DIR/creds/vault-unseal-key.enc" ]]; then
        local perms=$(stat -c "%a" "$VAULT_DIR/creds/vault-unseal-key.enc" 2>/dev/null || stat -f "%A" "$VAULT_DIR/creds/vault-unseal-key.enc" 2>/dev/null)
        if [[ "$perms" != "600" ]]; then
            warn "Insecure permissions on vault-unseal-key.enc: $perms (should be 600)"
            issues=$((issues + 1))
        fi
    fi

    if [[ $issues -eq 0 ]]; then
        pass "File permissions secure"
    else
        warn "$issues file(s) with insecure permissions"
    fi
}

# Test 15: Response time
test_response_time() {
    log "Test 15: API response time"

    local start_time end_time latency
    start_time=$(date +%s%N)

    curl -sk "${VAULT_ADDR}/v1/sys/health" >/dev/null 2>&1

    end_time=$(date +%s%N)
    latency=$(( (end_time - start_time) / 1000000 ))

    if [[ "$latency" -lt 100 ]]; then
        pass "Response time acceptable (${latency}ms)"
    elif [[ "$latency" -lt 500 ]]; then
        warn "Response time high (${latency}ms)"
    else
        fail "Response time too high (${latency}ms)"
    fi
}

# Display summary
display_summary() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${CYAN}   Vault Post-Deployment Verification Results${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    local total_checks=$((TESTS_PASSED + TESTS_FAILED + TESTS_WARNING))

    echo -e "${GREEN}Passed:${NC}   $TESTS_PASSED / $total_checks"
    echo -e "${RED}Failed:${NC}   $TESTS_FAILED / $total_checks"
    echo -e "${YELLOW}Warnings:${NC} $TESTS_WARNING / $total_checks"

    if [[ "$TESTS_FAILED" -gt 0 ]]; then
        echo
        echo -e "${RED}Failed Tests:${NC}"
        for test in "${FAILED_TESTS[@]}"; do
            echo "  - $test"
        done
    fi

    if [[ "$TESTS_WARNING" -gt 0 ]]; then
        echo
        echo -e "${YELLOW}Warnings:${NC}"
        for test in "${WARNING_TESTS[@]}"; do
            echo "  - $test"
        done
    fi

    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if [[ "$TESTS_FAILED" -eq 0 ]]; then
        if [[ "$TESTS_WARNING" -eq 0 ]]; then
            echo -e "${GREEN}✓ All checks passed! Vault is production-ready.${NC}"
        else
            echo -e "${YELLOW}⚠ Checks passed with $TESTS_WARNING warning(s). Review recommended.${NC}"
        fi
        echo
        return 0
    else
        echo -e "${RED}✗ $TESTS_FAILED critical check(s) failed. Please fix issues before production use.${NC}"
        echo
        return 1
    fi
}

# Display recommendations
display_recommendations() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BLUE}   Recommendations${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    if [[ "$TESTS_WARNING" -gt 0 ]] || [[ "$TESTS_FAILED" -gt 0 ]]; then
        echo "Next steps to resolve issues:"
        echo

        for test in "${FAILED_TESTS[@]}" "${WARNING_TESTS[@]}"; do
            case $test in
                *"sealed"*)
                    echo "  → Unseal Vault: vault operator unseal <key>"
                    ;;
                *"not initialized"*)
                    echo "  → Initialize Vault: make vault-secure-init"
                    ;;
                *"TLS"*)
                    echo "  → Generate TLS certs: make vault-tls-renew"
                    ;;
                *"Audit"*)
                    echo "  → Check audit config in config-stage9.hcl"
                    ;;
                *"AppRole"*)
                    echo "  → Enable AppRole: vault auth enable approle"
                    ;;
                *"KV"*)
                    echo "  → Enable KV engine: vault secrets enable -path=zakupai kv-v2"
                    ;;
                *"backup"*)
                    echo "  → Setup backups: ./setup_vault_evolution.sh --stage9-final"
                    ;;
                *"permissions"*)
                    echo "  → Fix permissions: chmod 600 monitoring/vault/creds/* monitoring/vault/.unseal-password"
                    ;;
            esac
        done
    else
        echo "  ✓ No issues found"
        echo
        echo "  Ongoing maintenance:"
        echo "    - Monitor Vault logs: docker logs vault -f"
        echo "    - Check audit logs: tail -f monitoring/vault/logs/audit.log"
        echo "    - Verify backups: ls -lh backups/vault/"
        echo "    - Run smoke tests: make smoke-stage9"
    fi

    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
}

# Main execution
main() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${CYAN}   🔐 Vault Post-Deployment Verification 🔐${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    info "Vault Address: $VAULT_ADDR"
    info "Timestamp: $(date -Iseconds)"
    echo

    # Run all tests
    test_container_running
    test_vault_sealed
    test_vault_initialized
    test_api_reachable
    test_tls_enabled
    test_audit_logging
    test_auth_methods
    test_kv_engine
    test_kv_operations
    test_prometheus_metrics
    test_storage_backend
    test_auto_unseal
    test_backup_config
    test_file_permissions
    test_response_time

    # Display results
    display_summary
    local exit_code=$?

    display_recommendations

    exit $exit_code
}

# Run
main "$@"
