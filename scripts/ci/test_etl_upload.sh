#!/bin/bash

# Test script for ETL upload endpoint
# Validates Priority 2 checkpoint 1: /etl/upload functionality

set -e
REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
SERVICE_DIR="$REPO_ROOT/services/etl-service"
TEST_FILES_DIR="$SERVICE_DIR/test_files"
cd "$SERVICE_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test configuration
ETL_HOST="http://localhost:7011"
CONTAINER_NAME="zakupai-etl-service"
TEST_TIMEOUT=30

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✅]${NC} $1"
}

log_error() {
    echo -e "${RED}[❌]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[⚠️]${NC} $1"
}

# Function to check if container is running
check_container() {
    if docker ps --format "table {{.Names}}" | grep -q "^$CONTAINER_NAME$"; then
        log_success "Container $CONTAINER_NAME is running"
        return 0
    else
        return 1
    fi
}

# Function to start container if not running
start_container() {
    log_info "Starting ETL service container..."
    cd "$SERVICE_DIR"

    # Build and start container
    docker build -t zakupai-etl-service . || {
        log_error "Failed to build ETL service container"
        exit 1
    }

    # Stop existing container if running
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true

    # Start new container
    docker run -d --name "$CONTAINER_NAME" -p 7011:8000 zakupai-etl-service || {
        log_error "Failed to start ETL service container"
        exit 1
    }

    # Wait for service to be ready
    log_info "Waiting for service to start..."
    for i in {1..30}; do
        if curl -sf "$ETL_HOST/health" >/dev/null 2>&1; then
            log_success "ETL service is ready"
            return 0
        fi
        echo -n "."
        sleep 1
    done

    log_error "ETL service failed to start within $TEST_TIMEOUT seconds"
    docker logs "$CONTAINER_NAME" 2>/dev/null || true
    exit 1
}

# Function to create test files
create_test_files() {
    log_info "Creating test files..."

    mkdir -p "$TEST_FILES_DIR"

    # Create sample PDF files if they don't exist
    if [[ ! -f "$TEST_FILES_DIR/sample1.pdf" ]]; then
        # Create minimal PDF with reportlab
        python3 -c "
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import os

# Create sample1.pdf
c = canvas.Canvas('$TEST_FILES_DIR/sample1.pdf', pagesize=letter)
c.drawString(100, 750, 'Sample PDF Document 1')
c.drawString(100, 730, 'This is a test document for ETL upload testing.')
c.save()

# Create sample2.pdf
c = canvas.Canvas('$TEST_FILES_DIR/sample2.pdf', pagesize=letter)
c.drawString(100, 750, 'Sample PDF Document 2')
c.drawString(100, 730, 'Another test document for ZIP testing.')
c.save()

# Create sample3.pdf with Russian text
c = canvas.Canvas('$TEST_FILES_DIR/sample3.pdf', pagesize=letter)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
# Use default font for Russian text
c.drawString(100, 750, 'Образец PDF документа 3')
c.drawString(100, 730, 'Тестовый документ на русском языке.')
c.save()

print('PDF files created successfully')
" || {
            log_warning "Failed to create PDFs with reportlab, using simple text files"
            # Fallback: create simple text files with PDF extension
            echo "%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/Contents 4 0 R>>endobj
4 0 obj<</Length 44>>stream
BT/F1 12 Tf 100 700 Td(Sample PDF 1)Tj ET
endstream endobj
xref 0 5 trailer<</Size 5/Root 1 0 R>>startxref 200 %%EOF" > "$TEST_FILES_DIR/sample1.pdf"

            echo "%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/Contents 4 0 R>>endobj
4 0 obj<</Length 44>>stream
BT/F1 12 Tf 100 700 Td(Sample PDF 2)Tj ET
endstream endobj
xref 0 5 trailer<</Size 5/Root 1 0 R>>startxref 200 %%EOF" > "$TEST_FILES_DIR/sample2.pdf"

            echo "%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/Contents 4 0 R>>endobj
4 0 obj<</Length 44>>stream
BT/F1 12 Tf 100 700 Td(Образец PDF 3)Tj ET
endstream endobj
xref 0 5 trailer<</Size 5/Root 1 0 R>>startxref 200 %%EOF" > "$TEST_FILES_DIR/sample3.pdf"
        }
    fi

    # Create sample.zip if it doesn't exist
    if [[ ! -f "$TEST_FILES_DIR/sample.zip" ]]; then
        log_info "Creating sample.zip..."
        cd "$TEST_FILES_DIR"
        zip -q sample.zip sample1.pdf sample2.pdf sample3.pdf
    cd "$SERVICE_DIR"
    fi

    # Create test files for error cases
    echo "This is a text file" > "$TEST_FILES_DIR/test.txt"

    # Create large file for size limit testing
    if [[ ! -f "$TEST_FILES_DIR/large.pdf" ]]; then
        log_info "Creating large test file..."
        dd if=/dev/zero of="$TEST_FILES_DIR/large.pdf" bs=1M count=51 2>/dev/null
    fi

    log_success "Test files created/verified"
}

# Function to run curl test
run_curl_test() {
    local test_name="$1"
    local url="$2"
    local method="${3:-GET}"
    local data="$4"
    local expected_code="${5:-200}"
    local file_param="$6"

    log_info "Running test: $test_name"

    local curl_cmd="curl -s -w '%{http_code}'"

    if [[ "$method" == "POST" && -n "$file_param" ]]; then
        curl_cmd="$curl_cmd -X POST -F \"file=@$file_param\" \"$url\""
    elif [[ "$method" == "POST" && -n "$data" ]]; then
        curl_cmd="$curl_cmd -X POST -H 'Content-Type: application/json' -d '$data' \"$url\""
    else
        curl_cmd="$curl_cmd \"$url\""
    fi

    local response
    response=$(eval "$curl_cmd")
    local http_code="${response: -3}"
    local body="${response%???}"

    if [[ "$http_code" == "$expected_code" ]]; then
        log_success "$test_name - HTTP $http_code ✅"
        if [[ -n "$body" && "$body" != "null" ]]; then
            echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
        fi
        return 0
    else
        log_error "$test_name - Expected HTTP $expected_code, got $http_code ❌"
        echo "Response body: $body"
        return 1
    fi
}

# Function to run all tests
run_tests() {
    local failed_tests=0

    log_info "🚀 Starting ETL Upload Endpoint Tests (with OCR)"
    echo "=================================================="

    # Test 1: Health check
    if ! run_curl_test "Health Check" "$ETL_HOST/health" "GET" "" "200"; then
        ((failed_tests++))
    fi
    echo ""

    # Test 2: OCR Health Check
    if ! run_curl_test "OCR Health Check" "$ETL_HOST/etl/ocr" "GET" "" "200"; then
        ((failed_tests++))
    fi
    echo ""

    # Test 3: Upload single PDF
    if ! run_curl_test "Upload Single PDF" "$ETL_HOST/etl/upload" "POST" "" "200" "$TEST_FILES_DIR/sample1.pdf"; then
        ((failed_tests++))
    fi
    echo ""

    # Test 4: Upload ZIP with PDFs
    if ! run_curl_test "Upload ZIP with PDFs" "$ETL_HOST/etl/upload" "POST" "" "200" "$TEST_FILES_DIR/sample.zip"; then
        ((failed_tests++))
    fi
    echo ""

    # Test 5: Upload unsupported file type (.txt)
    if ! run_curl_test "Upload Unsupported File (.txt)" "$ETL_HOST/etl/upload" "POST" "" "400" "$TEST_FILES_DIR/test.txt"; then
        ((failed_tests++))
    fi
    echo ""

    # Test 6: Upload file too large (51MB)
    if ! run_curl_test "Upload Large File (51MB)" "$ETL_HOST/etl/upload" "POST" "" "413" "$TEST_FILES_DIR/large.pdf"; then
        ((failed_tests++))
    fi
    echo ""

    # Test 7: Empty POST request
    log_info "Running test: Empty POST Request"
    local response
    response=$(curl -s -w '%{http_code}' -X POST "$ETL_HOST/etl/upload")
    local http_code="${response: -3}"

    if [[ "$http_code" == "422" ]]; then
        log_success "Empty POST Request - HTTP $http_code ✅"
    else
        log_error "Empty POST Request - Expected HTTP 422, got $http_code ❌"
        ((failed_tests++))
    fi
    echo ""

    # Test 8: Test URL upload endpoint
    log_info "Running test: URL Upload Endpoint Test"

    # Mock URL for testing (would normally be a real Goszakup file URL)
    test_url="https://httpbin.org/base64/JVBERi0xLjQKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+PmVuZG9iago=="

    url_upload_response=$(curl -s -X POST "$ETL_HOST/etl/upload-url" \
        -H "Content-Type: application/json" \
        -d "{\"file_url\":\"$test_url\",\"file_name\":\"test_from_url.pdf\",\"lot_id\":\"TEST_LOT_123\"}" 2>/dev/null)

    url_upload_http_code=$(curl -s -w '%{http_code}' -X POST "$ETL_HOST/etl/upload-url" \
        -H "Content-Type: application/json" \
        -d "{\"file_url\":\"$test_url\",\"file_name\":\"test_from_url.pdf\",\"lot_id\":\"TEST_LOT_123\"}" \
        -o /dev/null 2>/dev/null)

    if [[ "$url_upload_http_code" == "200" ]]; then
        log_success "URL Upload Test - HTTP 200 ✅"
        echo "$url_upload_response" | python3 -m json.tool 2>/dev/null | head -10
    else
        log_warning "URL Upload Test - HTTP $url_upload_http_code (may be expected if httpbin is not available) ⚠️"
    fi
    echo ""

    # Test 9: Test ETL service search endpoint
    log_info "Running test: ETL Search Endpoint Test"

    # First, wait a moment for indexing to complete after uploads
    sleep 3

    # Test search for common Russian terms
    for search_term in "тест" "документ" "text"; do
        log_info "Testing search for: $search_term"
        search_response=$(curl -s -X POST "$ETL_HOST/search" \
            -H "Content-Type: application/json" \
            -d "{\"query\":\"$search_term\",\"top_k\":3,\"collection\":\"etl_documents\"}" 2>/dev/null)

        search_http_code=$(curl -s -w '%{http_code}' -X POST "$ETL_HOST/search" \
            -H "Content-Type: application/json" \
            -d "{\"query\":\"$search_term\",\"top_k\":3,\"collection\":\"etl_documents\"}" \
            -o /dev/null 2>/dev/null)

        if [[ "$search_http_code" == "200" ]]; then
            log_success "Search for '$search_term' - HTTP 200 ✅"

            # Parse results count
            results_count=$(echo "$search_response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('total_found', 0))
except:
    print(0)
" 2>/dev/null)

            if [[ "$results_count" -gt 0 ]]; then
                log_success "Found $results_count results for '$search_term' 🔍"
            else
                log_warning "No results found for '$search_term' (may be expected for first runs)"
            fi

            # Show formatted results
            echo "$search_response" | python3 -m json.tool 2>/dev/null | head -20

        elif [[ "$search_http_code" == "503" ]]; then
            log_warning "Search for '$search_term' - Service unavailable (ChromaDB not ready) ⚠️"
        else
            log_error "Search for '$search_term' - HTTP $search_http_code ❌"
            ((failed_tests++))
        fi
        echo ""
    done

    # Summary
    echo "=================================================="
    if [[ $failed_tests -eq 0 ]]; then
        log_success "🎉 All tests passed! (9 tests)"
        return 0
    else
        log_error "❌ $failed_tests test(s) failed out of 9"
        return 1
    fi
}

# Main execution
main() {
    log_info "🧪 ETL Upload Endpoint Test Suite"
    echo "=================================="

    # Check if container is running, start if needed
    if ! check_container; then
        log_info "Container not running, starting..."
        start_container
    fi

    # Create test files
    create_test_files

    # Run tests
    if run_tests; then
        log_success "✅ Priority 2 Checkpoint 2 OCR pipeline validation complete!"
        exit 0
    else
        log_error "❌ Some tests failed"
        exit 1
    fi
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
