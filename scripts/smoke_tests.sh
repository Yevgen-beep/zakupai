#!/bin/bash
#
# Smoke Tests for Week 4.1 ZakupAI Web UI Enhancements
# Tests: CSV import, lot TL;DR, autocomplete, RNU validation
#

set -euo pipefail

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"
RISK_ENGINE_URL="${RISK_ENGINE_URL:-http://localhost:8001}"
API_KEY="${API_KEY:-test-api-key}"
TIMEOUT="${TIMEOUT:-30}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test results
TESTS_TOTAL=0
TESTS_PASSED=0
TESTS_FAILED=0

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

# Test result functions
test_passed() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo -e "${GREEN}✓ $1${NC}"
}

test_failed() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo -e "${RED}✗ $1${NC}"
}

test_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Health check function
health_check() {
    local service_name="$1"
    local url="$2"

    log "Checking $service_name health at $url"

    if curl -s -f --connect-timeout 5 --max-time $TIMEOUT "$url/health" > /dev/null 2>&1; then
        test_passed "$service_name health check"
        return 0
    else
        test_failed "$service_name health check"
        return 1
    fi
}

# Test CSV import status endpoint
test_csv_import_status() {
    log "Testing CSV import status endpoint"

    # Test non-existent import log (should return 404)
    local response=$(curl -s -o /dev/null -w "%{http_code}" \
        "$BASE_URL/web-ui/import-status/999999")

    if [ "$response" = "404" ]; then
        test_passed "CSV import status - not found returns 404"
    else
        test_failed "CSV import status - expected 404, got $response"
    fi
}

# Test lot TL;DR endpoint
test_lot_tldr() {
    log "Testing lot TL;DR endpoint"

    # Test with non-existent lot (should return 404)
    local response=$(curl -s -o /dev/null -w "%{http_code}" \
        "$BASE_URL/web-ui/lot/999999")

    if [ "$response" = "404" ]; then
        test_passed "Lot TL;DR - not found returns 404"
    else
        test_failed "Lot TL;DR - expected 404, got $response"
    fi

    # Test with valid lot ID if exists
    log "Testing lot TL;DR with mock data"
    local test_response=$(curl -s -f --connect-timeout 5 --max-time $TIMEOUT \
        "$BASE_URL/web-ui/lot/12345" 2>/dev/null || echo "FAILED")

    if [ "$test_response" != "FAILED" ]; then
        # Check if response contains required fields
        if echo "$test_response" | jq -r '.lot_id, .summary, .source, .cached' >/dev/null 2>&1; then
            test_passed "Lot TL;DR - response structure valid"
        else
            test_failed "Lot TL;DR - invalid response structure"
        fi
    else
        test_warning "Lot TL;DR - test lot not found (expected in clean environment)"
    fi
}

# Test autocomplete endpoint
test_autocomplete() {
    log "Testing autocomplete endpoint"

    # Test with short query (should return empty suggestions)
    local response=$(curl -s -f --connect-timeout 5 --max-time $TIMEOUT \
        "$BASE_URL/api/search/autocomplete?query=к" 2>/dev/null)

    if [ $? -eq 0 ]; then
        local suggestions_count=$(echo "$response" | jq -r '.suggestions | length' 2>/dev/null)
        if [ "$suggestions_count" = "0" ]; then
            test_passed "Autocomplete - short query returns empty"
        else
            test_failed "Autocomplete - short query should return empty"
        fi
    else
        test_failed "Autocomplete - endpoint not responding"
    fi

    # Test with valid query
    local response=$(curl -s -f --connect-timeout 5 --max-time $TIMEOUT \
        "$BASE_URL/api/search/autocomplete?query=компьютер" 2>/dev/null)

    if [ $? -eq 0 ]; then
        if echo "$response" | jq -r '.suggestions' >/dev/null 2>&1; then
            test_passed "Autocomplete - valid query returns proper format"
        else
            test_failed "Autocomplete - invalid response format"
        fi
    else
        test_failed "Autocomplete - valid query endpoint error"
    fi

    # Test Cyrillic support
    local cyrillic_queries=("мебель" "канцелярские" "строительство")
    for query in "${cyrillic_queries[@]}"; do
        local response=$(curl -s -o /dev/null -w "%{http_code}" \
            "$BASE_URL/api/search/autocomplete?query=$query")

        if [ "$response" = "200" ]; then
            test_passed "Autocomplete - Cyrillic query '$query' supported"
        else
            test_failed "Autocomplete - Cyrillic query '$query' failed ($response)"
        fi
    done
}

# Test RNU validation (from Week 3)
test_rnu_validation() {
    log "Testing RNU validation endpoint"

    # Test with valid BIN format
    local response=$(curl -s -f --connect-timeout 5 --max-time $TIMEOUT \
        "$RISK_ENGINE_URL/risk/validate_rnu/123456789012" 2>/dev/null)

    if [ $? -eq 0 ]; then
        if echo "$response" | jq -r '.supplier_bin, .status, .is_blocked, .source' >/dev/null 2>&1; then
            test_passed "RNU validation - response structure valid"
        else
            test_failed "RNU validation - invalid response structure"
        fi
    else
        test_warning "RNU validation - endpoint not responding (may be external API issue)"
    fi

    # Test with invalid BIN format
    local response=$(curl -s -o /dev/null -w "%{http_code}" \
        "$RISK_ENGINE_URL/risk/validate_rnu/invalid")

    if [ "$response" = "422" ] || [ "$response" = "400" ]; then
        test_passed "RNU validation - invalid BIN rejected"
    else
        test_warning "RNU validation - invalid BIN response: $response"
    fi
}

# Test advanced search (from Week 3)
test_advanced_search() {
    log "Testing advanced search endpoint"

    # Test basic search
    local search_payload='{"query": "компьютеры", "limit": 10}'
    local response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$search_payload" \
        --connect-timeout 5 --max-time $TIMEOUT \
        "$BASE_URL/api/search/advanced" 2>/dev/null)

    if [ $? -eq 0 ]; then
        if echo "$response" | jq -r '.results, .total_count' >/dev/null 2>&1; then
            test_passed "Advanced search - basic search works"
        else
            test_failed "Advanced search - invalid response format"
        fi
    else
        test_failed "Advanced search - endpoint not responding"
    fi

    # Test search with filters
    local filtered_payload='{"query": "мебель", "min_amount": 1000, "max_amount": 100000, "limit": 5}'
    local response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$filtered_payload" \
        --connect-timeout 5 --max-time $TIMEOUT \
        "$BASE_URL/api/search/advanced" 2>/dev/null)

    if [ $? -eq 0 ]; then
        test_passed "Advanced search - filtered search works"
    else
        test_failed "Advanced search - filtered search failed"
    fi

    # Test validation (max_amount < min_amount)
    local invalid_payload='{"query": "test", "min_amount": 100000, "max_amount": 50000}'
    local response=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$invalid_payload" \
        "$BASE_URL/api/search/advanced")

    if [ "$response" = "422" ]; then
        test_passed "Advanced search - validation works"
    else
        test_failed "Advanced search - validation failed ($response)"
    fi
}

# Test CSV import functionality (simplified smoke test)
test_csv_import_smoke() {
    log "Testing CSV import smoke test"

    # Create minimal valid CSV
    local csv_file="/tmp/smoke_test.csv"
    cat > "$csv_file" << EOF
product_name,amount,supplier_bin
Тестовый продукт,1000,123456789012
EOF

    # Test file upload (without actual processing due to complexity)
    local response=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST \
        -F "file=@$csv_file" \
        -F "client_id=smoke_test" \
        --connect-timeout 5 --max-time $TIMEOUT \
        "$BASE_URL/web-ui/import-prices" 2>/dev/null)

    # Clean up
    rm -f "$csv_file"

    if [ "$response" = "200" ] || [ "$response" = "422" ]; then
        test_passed "CSV import - endpoint accepts requests"
    else
        test_failed "CSV import - endpoint error ($response)"
    fi
}

# Performance test
test_performance() {
    log "Testing response times"

    # Test autocomplete performance (<500ms)
    local start_time=$(date +%s%3N)
    curl -s -f "$BASE_URL/api/search/autocomplete?query=компьютер" >/dev/null 2>&1
    local end_time=$(date +%s%3N)
    local duration=$((end_time - start_time))

    if [ "$duration" -lt 500 ]; then
        test_passed "Performance - autocomplete under 500ms ($duration ms)"
    else
        test_failed "Performance - autocomplete too slow ($duration ms)"
    fi

    # Test search performance
    local start_time=$(date +%s%3N)
    curl -s -X POST \
        -H "Content-Type: application/json" \
        -d '{"query": "тест", "limit": 10}' \
        "$BASE_URL/api/search/advanced" >/dev/null 2>&1
    local end_time=$(date +%s%3N)
    local duration=$((end_time - start_time))

    if [ "$duration" -lt 2000 ]; then
        test_passed "Performance - search under 2000ms ($duration ms)"
    else
        test_failed "Performance - search too slow ($duration ms)"
    fi
}

# Test Redis connectivity (optional)
test_redis_connectivity() {
    log "Testing Redis connectivity"

    # Check if Redis is responding through health endpoint
    local response=$(curl -s -f --connect-timeout 2 --max-time 5 \
        "$BASE_URL/health" 2>/dev/null)

    if [ $? -eq 0 ]; then
        if echo "$response" | grep -q "redis" 2>/dev/null; then
            test_passed "Redis - connectivity through health check"
        else
            test_warning "Redis - no explicit health check found"
        fi
    else
        test_warning "Redis - cannot verify through health endpoint"
    fi
}

# Test ChromaDB connectivity (optional)
test_chromadb_connectivity() {
    log "Testing ChromaDB connectivity"

    # Test autocomplete which uses ChromaDB
    local response=$(curl -s -f --connect-timeout 5 --max-time $TIMEOUT \
        "$BASE_URL/api/search/autocomplete?query=компьютер" 2>/dev/null)

    if [ $? -eq 0 ]; then
        test_passed "ChromaDB - connectivity through autocomplete"
    else
        test_warning "ChromaDB - connectivity issues or service down"
    fi
}

# Main execution
main() {
    log "Starting Week 4.1 ZakupAI Smoke Tests"
    log "Base URL: $BASE_URL"
    log "Risk Engine URL: $RISK_ENGINE_URL"
    log "Timeout: ${TIMEOUT}s"
    echo

    # Health checks first
    health_check "Web UI" "$BASE_URL"
    health_check "Risk Engine" "$RISK_ENGINE_URL"

    echo
    log "Running functional tests..."

    # Core functionality tests
    test_csv_import_status
    test_csv_import_smoke
    test_lot_tldr
    test_autocomplete
    test_advanced_search
    test_rnu_validation

    echo
    log "Running performance tests..."
    test_performance

    echo
    log "Running connectivity tests..."
    test_redis_connectivity
    test_chromadb_connectivity

    echo
    echo "========================================"
    echo "SMOKE TESTS SUMMARY"
    echo "========================================"
    echo "Total tests: $TESTS_TOTAL"
    echo -e "Passed: ${GREEN}$TESTS_PASSED${NC}"
    echo -e "Failed: ${RED}$TESTS_FAILED${NC}"
    echo "Success rate: $(( (TESTS_PASSED * 100) / TESTS_TOTAL ))%"

    if [ "$TESTS_FAILED" -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        exit 0
    else
        echo -e "${RED}Some tests failed!${NC}"
        exit 1
    fi
}

# Check dependencies
if ! command -v curl >/dev/null 2>&1; then
    echo "Error: curl is required but not installed"
    exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
    echo "Error: jq is required but not installed"
    exit 1
fi

# Run tests
main "$@"
