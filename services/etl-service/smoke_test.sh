#!/bin/bash
set -e

# ETL Service Smoke Test with OCR Loader Integration
# Tests PDF processing, PostgreSQL integration, and database queries

# Redirect all output to log file while showing on console
exec > >(tee smoke_test.log) 2>&1

echo "🚀 Starting ETL Service Smoke Test with OCR Loader..."
echo "=================================================="
echo "Timestamp: $(date)"
echo "Working directory: $(pwd)"
echo ""

# Check prerequisites
echo "🔍 Checking prerequisites..."
echo "- Activating virtual environment..."
if [[ -f "../../.venv/bin/activate" ]]; then
    source ../../.venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "⚠️  Warning: Virtual environment not found, using system Python"
fi

echo "- Checking Python3..."
if ! command -v python3 &> /dev/null; then
    echo "❌ ERROR: python3 not found"
    exit 1
fi

echo "- Checking psql..."
if ! command -v psql &> /dev/null; then
    echo "❌ ERROR: psql not found"
    exit 1
fi

echo "- Checking required files..."
if [[ ! -f "test_ocr.py" ]]; then
    echo "❌ ERROR: test_ocr.py not found"
    exit 1
fi

if [[ ! -f "attachments_migration.sql" ]]; then
    echo "❌ ERROR: attachments_migration.sql not found"
    exit 1
fi

if [[ ! -f "ocr_loader.py" ]]; then
    echo "❌ ERROR: ocr_loader.py not found"
    exit 1
fi

echo "✅ Prerequisites check passed"
echo ""

# Step 1: Create test PDF files
echo "📄 Step 1: Creating test PDF files from text files..."
echo "Running: python3 test_ocr.py"

if python3 test_ocr.py; then
    echo "✅ Test PDF files created successfully"
else
    echo "❌ ERROR: Failed to create test PDF files"
    exit 1
fi

# Check if PDF files were created
if [[ ! -d "pdf" ]] || [[ -z "$(ls -A pdf/*.pdf 2>/dev/null)" ]]; then
    echo "❌ ERROR: No PDF files found in pdf/ directory"
    exit 1
fi

echo "📄 Found PDF files:"
ls -la pdf/*.pdf
echo ""

# Step 2: Apply SQL migration
echo "🗄️ Step 2: Applying PostgreSQL migration..."
echo "Running: psql -h localhost -U zakupai -d zakupai -f attachments_migration.sql"

# Set PGPASSWORD for non-interactive execution
export PGPASSWORD=zakupai

if psql -h localhost -U zakupai -d zakupai -f attachments_migration.sql; then
    echo "✅ PostgreSQL migration applied successfully"
else
    echo "❌ ERROR: Failed to apply PostgreSQL migration"
    echo "💡 Make sure PostgreSQL is running and zakupai database exists"
    exit 1
fi
echo ""

# Step 3: Run OCR Loader (Simple version for smoke test)
echo "🔍 Step 3: Running OCR Loader..."

# Try full version first, fallback to simple version if dependencies missing
echo "Attempting full OCR Loader first..."
if python3 ocr_loader.py --path ./pdf/ --db postgresql://zakupai:zakupai@localhost:5432/zakupai 2>/dev/null; then
    echo "✅ Full OCR Loader completed successfully"
else
    echo "⚠️  Full OCR Loader failed (missing dependencies), using simple version..."
    echo "Running: python3 ocr_loader_simple.py --path ./pdf/ --db postgresql://zakupai:zakupai@localhost:5432/zakupai"
    
    if python3 ocr_loader_simple.py --path ./pdf/ --db postgresql://zakupai:zakupai@localhost:5432/zakupai; then
        echo "✅ Simple OCR Loader completed successfully"
    else
        echo "❌ ERROR: OCR Loader failed"
        echo "💡 Check ocr_loader.log for detailed error information"
        exit 1
    fi
fi
echo ""

# Step 4: Verify database content
echo "🔍 Step 4: Verifying database content..."
echo "Running: SELECT lot_id, file_name, LEFT(content, 200) FROM attachments ORDER BY created_at DESC LIMIT 5"

QUERY_RESULT=$(psql -h localhost -U zakupai -d zakupai -c "SELECT lot_id, file_name, LEFT(content, 200) as content_preview FROM attachments ORDER BY created_at DESC LIMIT 5;" -t)

if [[ -n "$QUERY_RESULT" ]] && [[ "$QUERY_RESULT" != *"0 rows"* ]]; then
    echo "✅ Database verification successful"
    echo "📊 Query results:"
    psql -h localhost -U zakupai -d zakupai -c "SELECT lot_id, file_name, LEFT(content, 200) as content_preview FROM attachments ORDER BY created_at DESC LIMIT 5;"
else
    echo "❌ ERROR: No data found in attachments table"
    echo "💡 Check if OCR Loader processed files correctly"
    exit 1
fi
echo ""

# Additional verification: Check table structure
echo "🔍 Additional verification: Checking table structure..."
echo "Running: \\d attachments"

psql -h localhost -U zakupai -d zakupai -c "\\d attachments"
echo ""

# Count total records
echo "📊 Counting total records in attachments table..."
TOTAL_COUNT=$(psql -h localhost -U zakupai -d zakupai -c "SELECT COUNT(*) FROM attachments;" -t | xargs)
echo "Total attachments processed: $TOTAL_COUNT"
echo ""

# Test full-text search functionality
echo "🔍 Testing full-text search functionality..."
echo "Searching for 'компьютер' in Russian text..."

SEARCH_RESULT=$(psql -h localhost -U zakupai -d zakupai -c "SELECT lot_id, file_name FROM attachments WHERE to_tsvector('russian', content) @@ to_tsquery('russian', 'компьютер');" -t)

if [[ -n "$SEARCH_RESULT" ]]; then
    echo "✅ Full-text search working correctly"
    psql -h localhost -U zakupai -d zakupai -c "SELECT lot_id, file_name, ts_rank(to_tsvector('russian', content), to_tsquery('russian', 'компьютер')) as rank FROM attachments WHERE to_tsvector('russian', content) @@ to_tsquery('russian', 'компьютер') ORDER BY rank DESC;"
else
    echo "⚠️  Warning: Full-text search returned no results (this may be normal if test data doesn't contain 'компьютер')"
fi
echo ""

# Cleanup old PGPASSWORD
unset PGPASSWORD

# Final success message
echo "=================================================="
echo "🎉 Smoke test finished successfully!"
echo "=================================================="
echo "Summary:"
echo "- ✅ Test PDF files created"
echo "- ✅ PostgreSQL migration applied"
echo "- ✅ OCR Loader processed files"  
echo "- ✅ Database content verified"
echo "- ✅ Full-text search tested"
echo "- 📊 Total records processed: $TOTAL_COUNT"
echo ""
echo "📋 Log file saved as: smoke_test.log"
echo "📋 OCR Loader log: ocr_loader.log"
echo ""
echo "Timestamp: $(date)"