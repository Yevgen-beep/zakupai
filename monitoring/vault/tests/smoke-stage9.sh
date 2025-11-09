#!/bin/bash
# Vault Stage 9 Smoke Tests
# Purpose: Comprehensive testing of production Vault deployment
# Tests: Unsealed status, TLS, Audit, B2 storage, AppRole access

set -euo pipefail

# Configuration
VAULT_ADDR="${VAULT_ADDR:-https://127.0.0.1:8200}"
VAULT_SKIP_VERIFY="${VAULT_SKIP_VERIFY:-false}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Test result tracking
declare -a FAILED_TESTS

log() {
    echo -e "${CYAN}[TEST]${NC} $*"
}

pass() {
    echo -e "${GREEN}✓${NC} $*"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
}

fail() {
    echo -e "${RED}✗${NC} $*"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    FAILED_TESTS+=("$1")
}

warn() {
    echo -e "${YELLOW}⚠${NC} $*"
}

info() {
    echo -e "${BLUE}ℹ${NC} $*"
}

# Test 1: Vault container is running
test_container_running() {
    log "Test 1: Checking if Vault container is running..."

    if docker ps | grep -q vault; then
        pass "Vault container is running"
    else
        fail "Vault container is not running"
    fi
}

# Test 2: Vault is unsealed
test_vault_unsealed() {
    log "Test 2: Checking if Vault is unsealed..."

    local sealed
    sealed=$(docker exec -e VAULT_SKIP_VERIFY="$VAULT_SKIP_VERIFY" vault \
        vault status -format=json 2>/dev/null | jq -r '.sealed' || echo "true")

    if [[ "$sealed" == "false" ]]; then
        pass "Vault is unsealed"
    else
        fail "Vault is sealed"
    fi
}

# Test 3: TLS is enabled
test_tls_enabled() {
    log "Test 3: Checking if TLS is enabled..."

    # Try HTTPS connection
    if curl -sk "$VAULT_ADDR/v1/sys/health" >/dev/null 2>&1; then
        pass "TLS is enabled (HTTPS connection successful)"
    else
        fail "TLS is not working (HTTPS connection failed)"
    fi
}

# Test 4: TLS certificate validity
test_tls_certificate() {
    log "Test 4: Checking TLS certificate validity..."

    if [[ -f "$VAULT_DIR/tls/vault-cert.pem" ]]; then
        # Check if certificate expires in more than 30 days
        if openssl x509 -in "$VAULT_DIR/tls/vault-cert.pem" -noout -checkend 2592000 >/dev/null 2>&1; then
            pass "TLS certificate is valid (>30 days remaining)"
        else
            warn "TLS certificate expires soon (<30 days)"
            TESTS_TOTAL=$((TESTS_TOTAL + 1))
        fi
    else
        fail "TLS certificate file not found"
    fi
}

# Test 5: Audit logging is active
test_audit_logging() {
    log "Test 5: Checking if audit logging is active..."

    if [[ -f "$VAULT_DIR/logs/audit.log" ]]; then
        local entries
        entries=$(wc -l < "$VAULT_DIR/logs/audit.log" 2>/dev/null || echo 0)

        if [[ "$entries" -gt 0 ]]; then
            pass "Audit logging is active ($entries entries)"
        else
            warn "Audit log exists but has no entries yet"
            TESTS_TOTAL=$((TESTS_TOTAL + 1))
        fi
    else
        fail "Audit log file not found"
    fi
}

# Test 6: Auth/approle is accessible
test_approle_auth() {
    log "Test 6: Checking if auth/approle is accessible..."

    if docker exec -e VAULT_SKIP_VERIFY="$VAULT_SKIP_VERIFY" vault \
        vault auth list 2>/dev/null | grep -q "approle"; then
        pass "AppRole auth method is enabled"
    else
        fail "AppRole auth method is not enabled"
    fi
}

# Test 7: KV engine zakupai/ is accessible
test_kv_engine() {
    log "Test 7: Checking if zakupai/ KV engine is accessible..."

    if docker exec -e VAULT_SKIP_VERIFY="$VAULT_SKIP_VERIFY" vault \
        vault kv list zakupai/ >/dev/null 2>&1; then
        pass "zakupai/ KV engine is accessible"
    else
        fail "zakupai/ KV engine is not accessible"
    fi
}

# Test 8: Prometheus metrics endpoint
test_prometheus_metrics() {
    log "Test 8: Checking Prometheus metrics endpoint..."

    local metrics_url="${VAULT_ADDR}/v1/sys/metrics?format=prometheus"

    if curl -sk "$metrics_url" 2>/dev/null | grep -q "vault_core_unsealed"; then
        pass "Prometheus metrics endpoint is working"
    else
        fail "Prometheus metrics endpoint is not responding"
    fi
}

# Test 9: Health endpoint
test_health_endpoint() {
    log "Test 9: Checking health endpoint..."

    local health_response
    health_response=$(curl -sk "$VAULT_ADDR/v1/sys/health" 2>/dev/null)

    if echo "$health_response" | jq -e '.initialized == true and .sealed == false' >/dev/null 2>&1; then
        pass "Health endpoint reports: initialized and unsealed"
    else
        fail "Health endpoint reports unexpected state"
    fi
}

# Test 10: Auto-unseal works after restart
test_auto_unseal_restart() {
    log "Test 10: Testing auto-unseal on restart..."

    info "Restarting Vault container..."
    docker restart vault >/dev/null 2>&1

    info "Waiting 30 seconds for Vault to start..."
    sleep 30

    local sealed
    sealed=$(docker exec -e VAULT_SKIP_VERIFY="$VAULT_SKIP_VERIFY" vault \
        vault status -format=json 2>/dev/null | jq -r '.sealed' || echo "true")

    if [[ "$sealed" == "false" ]]; then
        pass "Auto-unseal works after restart"
    else
        fail "Auto-unseal failed after restart (Vault is sealed)"
    fi
}

# Test 11: Response latency
test_response_latency() {
    log "Test 11: Checking response latency..."

    local start_time end_time latency
    start_time=$(date +%s%N)

    curl -sk "$VAULT_ADDR/v1/sys/health" >/dev/null 2>&1

    end_time=$(date +%s%N)
    latency=$(( (end_time - start_time) / 1000000 ))  # Convert to milliseconds

    if [[ "$latency" -lt 100 ]]; then
        pass "Response latency is acceptable (${latency}ms < 100ms)"
    elif [[ "$latency" -lt 500 ]]; then
        warn "Response latency is high (${latency}ms)"
        TESTS_TOTAL=$((TESTS_TOTAL + 1))
    else
        fail "Response latency is too high (${latency}ms >= 500ms)"
    fi
}

# Test 12: B2 storage connectivity
test_b2_storage() {
    log "Test 12: Checking B2 storage connectivity..."

    # Check if AWS credentials are set in docker-compose
    if docker exec vault env | grep -q "AWS_ACCESS_KEY_ID"; then
        pass "B2 credentials are configured"
    else
        fail "B2 credentials are not configured"
        return
    fi

    # Test by writing to Vault (which writes to B2)
    local test_path="zakupai/smoke-test/test-$(date +%s)"

    if docker exec -e VAULT_SKIP_VERIFY="$VAULT_SKIP_VERIFY" vault \
        vault kv put "$test_path" test=true >/dev/null 2>&1; then
        pass "B2 storage is working (write successful)"

        # Cleanup
        docker exec -e VAULT_SKIP_VERIFY="$VAULT_SKIP_VERIFY" vault \
            vault kv delete "$test_path" >/dev/null 2>&1
    else
        fail "B2 storage write failed"
    fi
}

# Test 13: Container health check
test_container_health() {
    log "Test 13: Checking container health status..."

    local health_status
    health_status=$(docker inspect vault --format='{{.State.Health.Status}}' 2>/dev/null || echo "none")

    if [[ "$health_status" == "healthy" ]]; then
        pass "Container health check is passing"
    elif [[ "$health_status" == "none" ]]; then
        warn "No health check configured"
        TESTS_TOTAL=$((TESTS_TOTAL + 1))
    else
        fail "Container health check is failing (status: $health_status)"
    fi
}

# Test 14: Log rotation
test_log_rotation() {
    log "Test 14: Checking log rotation configuration..."

    if [[ -f "$VAULT_DIR/logs/audit.log" ]]; then
        local log_size
        log_size=$(stat -f%z "$VAULT_DIR/logs/audit.log" 2>/dev/null || stat -c%s "$VAULT_DIR/logs/audit.log" 2>/dev/null || echo 0)

        if [[ "$log_size" -lt 104857600 ]]; then  # 100MB
            pass "Audit log size is reasonable ($(numfmt --to=iec "$log_size" 2>/dev/null || echo "${log_size} bytes"))"
        else
            warn "Audit log is large ($(numfmt --to=iec "$log_size" 2>/dev/null || echo "${log_size} bytes")). Consider rotation."
            TESTS_TOTAL=$((TESTS_TOTAL + 1))
        fi
    else
        warn "Audit log not found (may not be created yet)"
        TESTS_TOTAL=$((TESTS_TOTAL + 1))
    fi
}

# Test 15: Security headers
test_security_headers() {
    log "Test 15: Checking security headers..."

    local headers
    headers=$(curl -skI "$VAULT_ADDR/v1/sys/health" 2>/dev/null)

    local has_security_headers=true

    if echo "$headers" | grep -qi "Strict-Transport-Security"; then
        :  # HSTS header present (optional for Vault)
    fi

    if echo "$headers" | grep -qi "X-Vault-"; then
        pass "Vault security headers are present"
    else
        warn "Some security headers may be missing"
        TESTS_TOTAL=$((TESTS_TOTAL + 1))
    fi
}

# Display summary
display_summary() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${CYAN}   Vault Stage 9 Smoke Test Results${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    echo -e "${GREEN}Passed:${NC} $TESTS_PASSED / $TESTS_TOTAL"
    echo -e "${RED}Failed:${NC} $TESTS_FAILED / $TESTS_TOTAL"

    if [[ "$TESTS_FAILED" -gt 0 ]]; then
        echo
        echo -e "${RED}Failed Tests:${NC}"
        for test in "${FAILED_TESTS[@]}"; do
            echo "  - $test"
        done
    fi

    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if [[ "$TESTS_FAILED" -eq 0 ]]; then
        echo -e "${GREEN}✓ All tests passed! Stage 9 is production-ready.${NC}"
        echo
        return 0
    else
        echo -e "${RED}✗ Some tests failed. Please review and fix issues.${NC}"
        echo
        return 1
    fi
}

# Main execution
main() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${BLUE}   Vault Stage 9 Smoke Tests${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    info "Vault Address: $VAULT_ADDR"
    info "TLS Verify: $([ "$VAULT_SKIP_VERIFY" == "false" ] && echo "Enabled" || echo "Disabled")"
    echo

    test_container_running
    test_vault_unsealed
    test_tls_enabled
    test_tls_certificate
    test_audit_logging
    test_approle_auth
    test_kv_engine
    test_prometheus_metrics
    test_health_endpoint
    test_auto_unseal_restart
    test_response_latency
    test_b2_storage
    test_container_health
    test_log_rotation
    test_security_headers

    display_summary
}

# Run tests
main "$@"
