# ETL Service - Upload Endpoint Testing

## 🚀 Quick Start

### 1. Build and Run the Service

```bash
# Build Docker image
docker build -t zakupai-etl-service .

# Run the service
docker run -p 7011:8000 zakupai-etl-service
```

### 2. Test with curl Commands

#### ✅ Test 1: Upload single PDF file

```bash
curl -X POST "http://localhost:7011/etl/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test_files/sample1.pdf"
```

**Expected result:**

```json
{
  "files": ["sample1.pdf"],
  "total_size_mb": 0.0,
  "message": "PDF file ready for processing"
}
```

#### ✅ Test 2: Upload ZIP with multiple PDF files

```bash
curl -X POST "http://localhost:7011/etl/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test_files/sample.zip"
```

**Expected result:**

```json
{
  "files": ["sample1.pdf", "sample2.pdf", "sample3.pdf"],
  "total_size_mb": 0.0,
  "message": "Successfully extracted 3 PDF files"
}
```

#### ❌ Test 3: Upload unsupported file type

```bash
# Create a test .exe file
echo "fake exe content" > test_malware.exe

curl -X POST "http://localhost:7011/etl/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test_malware.exe"
```

**Expected result (HTTP 400):**

```json
{
  "detail": "Unsupported file type: .exe. Allowed: .pdf, .zip"
}
```

#### ❌ Test 4: Upload file too large (>50MB)

```bash
# Create a large file (51MB)
dd if=/dev/zero of=large_file.pdf bs=1M count=51

curl -X POST "http://localhost:7011/etl/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@large_file.pdf"
```

**Expected result (HTTP 413):**

```json
{
  "detail": "File too large. Maximum size: 50MB, got: 51.0MB"
}
```

#### ✅ Test 5: OCR Health Check

```bash
curl -X GET "http://localhost:7011/etl/ocr" \
  -H "accept: application/json"
```

**Expected result:**

```json
{
  "status": "ready",
  "tesseract_available": true,
  "message": "Tesseract OCR ready for processing"
}
```

## 🧪 Run Pytest Tests

```bash
# Inside the service directory
cd services/etl-service

# Install test dependencies
pip install pytest httpx

# Run tests
pytest test_upload.py -v
```

**Expected output:**

```
test_upload.py::TestUploadEndpoint::test_upload_pdf_file PASSED
test_upload.py::TestUploadEndpoint::test_upload_zip_with_pdf_files PASSED
test_upload.py::TestUploadEndpoint::test_upload_zip_no_pdf_files PASSED
test_upload.py::TestUploadEndpoint::test_upload_unsupported_file_type PASSED
test_upload.py::TestUploadEndpoint::test_upload_file_too_large PASSED
test_upload.py::TestUploadEndpoint::test_upload_corrupted_zip PASSED
test_upload.py::TestUploadEndpoint::test_upload_no_file PASSED
test_upload.py::TestUploadEndpoint::test_ocr_health_endpoint PASSED
```

## 📋 Success Metrics

- ✅ All curl tests return expected JSON responses
- ✅ sample.zip upload returns list of 3 PDF files
- ✅ Error handling works (413 for large files, 400 for wrong types)
- ✅ OCR health check shows Tesseract available
- ✅ All pytest tests pass
- ✅ Code passes pre-commit checks (ruff, black, bandit)

## 🔧 API Documentation

Visit `http://localhost:7011/docs` for interactive Swagger documentation.

## 📁 File Structure

```
services/etl-service/
├── main.py                # Main FastAPI application with /etl/upload
├── Dockerfile             # Docker config with TesseractOCR
├── requirements.txt       # Dependencies including pytest
├── test_upload.py         # Unit tests for upload endpoint
├── test_files/
│   ├── sample1.pdf        # Test PDF file 1
│   ├── sample2.pdf        # Test PDF file 2
│   ├── sample3.pdf        # Test PDF file 3 (Russian text)
│   └── sample.zip         # Archive with all PDFs
└── TESTING.md            # This file
```

## ⚡ Quick Health Check Commands

```bash
# Service health
curl http://localhost:7011/health

# OCR readiness
curl http://localhost:7011/etl/ocr

# API docs
curl http://localhost:7011/docs
```

## 🎯 Priority 2 Checkpoint Complete

This implementation provides:

- ✅ POST /etl/upload endpoint (PDF + ZIP support)
- ✅ 50MB file size limit with proper validation
- ✅ ZIP extraction and PDF file listing
- ✅ TesseractOCR integration in Dockerfile
- ✅ OCR health check endpoint
- ✅ Comprehensive pytest test suite
- ✅ Error handling with `raise ... from e` pattern
- ✅ Logging for debugging and monitoring
- ✅ Pre-commit compatible code quality

Ready for next priority: actual OCR processing implementation!
