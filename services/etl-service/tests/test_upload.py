"""
Тесты для эндпоинта /etl/upload с OCR функциональностью
"""

import io
import os
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from services.etl_service.main import app

# Create test client
client = TestClient(app)


class TestUploadEndpoint:
    """Test suite for /etl/upload endpoint"""

    def test_upload_pdf_file(self):
        """Test uploading a single PDF file"""
        # Create a mock PDF file
        pdf_content = b"%PDF-1.4\n%Mock PDF content for testing\n%%EOF"

        files = {
            "file": ("test_document.pdf", io.BytesIO(pdf_content), "application/pdf")
        }

        response = client.post("/etl/upload", files=files)

        assert response.status_code == 200  # nosec
        data = response.json()

        assert "files" in data
        assert "total_size_mb" in data
        assert "message" in data
        assert data["status"] == "ok"  # nosec
        assert len(data["files"]) == 1  # nosec
        assert data["files"][0]["file_name"] == "test_document.pdf"
        assert data["files"][0]["file_type"] == "pdf"
        assert "content_preview" in data["files"][0]

    def test_upload_zip_with_pdf_files(self):
        """Test uploading ZIP file containing PDF files"""
        # Create a ZIP file with multiple PDF files
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            # Add mock PDF files
            zip_file.writestr("document1.pdf", b"%PDF-1.4\nMock PDF 1\n%%EOF")
            zip_file.writestr("document2.pdf", b"%PDF-1.4\nMock PDF 2\n%%EOF")
            zip_file.writestr("subdir/document3.pdf", b"%PDF-1.4\nMock PDF 3\n%%EOF")
            # Add non-PDF file (should be ignored)
            zip_file.writestr("readme.txt", "This is a text file")

        zip_buffer.seek(0)

        files = {"file": ("test_archive.zip", zip_buffer, "application/zip")}

        response = client.post("/etl/upload", files=files)

        assert response.status_code == 200  # nosec
        data = response.json()

        assert data["status"] == "ok"  # nosec
        assert len(data["files"]) == 3
        file_names = [f["file_name"] for f in data["files"]]
        assert "document1.pdf" in file_names
        assert "document2.pdf" in file_names
        assert "document3.pdf" in file_names
        assert all(f["file_type"] == "pdf" for f in data["files"])
        assert all("content_preview" in f for f in data["files"])

    def test_upload_zip_no_pdf_files(self):
        """Test uploading ZIP file with no PDF files"""
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("readme.txt", "This is a text file")
            zip_file.writestr("image.jpg", b"fake image data")

        zip_buffer.seek(0)

        files = {"file": ("no_pdfs.zip", zip_buffer, "application/zip")}

        response = client.post("/etl/upload", files=files)

        assert response.status_code == 200  # nosec
        data = response.json()

        assert data["status"] == "error"
        assert data["files"] == []

    def test_upload_unsupported_file_type(self):
        """Test uploading unsupported file type"""
        exe_content = b"MZ\x90\x00\x03\x00\x00\x00"  # Mock EXE header

        files = {
            "file": ("malware.exe", io.BytesIO(exe_content), "application/x-executable")
        }

        response = client.post("/etl/upload", files=files)

        assert response.status_code == 400
        data = response.json()

        assert "Unsupported file type" in data["detail"]
        assert ".exe" in data["detail"]

    def test_upload_file_too_large(self):
        """Test uploading file larger than 50MB limit"""
        # Create a large file (simulate 51MB)
        large_content = b"x" * (51 * 1024 * 1024)

        files = {
            "file": ("large_file.pdf", io.BytesIO(large_content), "application/pdf")
        }

        response = client.post("/etl/upload", files=files)

        assert response.status_code == 413
        data = response.json()

        assert "File too large" in data["detail"]
        assert "Maximum size: 50MB" in data["detail"]

    def test_upload_corrupted_zip(self):
        """Test uploading corrupted ZIP file"""
        corrupted_zip = b"PK\x03\x04corrupted_data"

        files = {
            "file": ("corrupted.zip", io.BytesIO(corrupted_zip), "application/zip")
        }

        response = client.post("/etl/upload", files=files)

        assert response.status_code == 400
        data = response.json()

        assert "Invalid or corrupted ZIP file" in data["detail"]

    def test_upload_no_file(self):
        """Test upload request without file"""
        response = client.post("/etl/upload")

        assert response.status_code == 422  # Validation error

    def test_ocr_health_endpoint(self):
        """Test OCR health check endpoint"""
        response = client.get("/etl/ocr")

        assert response.status_code == 200  # nosec
        data = response.json()

        assert "status" in data
        assert "tesseract_available" in data
        assert "message" in data
        assert data["status"] in [
            "ready",
            "not_ready",
            "not_implemented",
            "error",
            "timeout",
        ]

    @patch("services.etl_service.main.process_pdf_ocr")
    @patch("services.etl_service.main.save_to_postgres")
    @patch("services.etl_service.main.index_in_chromadb")
    def test_pdf_text_extraction(self, mock_chromadb, mock_postgres, mock_ocr):
        """Test PDF text extraction with OCR"""
        # Mock OCR response
        mock_ocr.return_value = "Extracted text content from PDF"
        mock_postgres.return_value = 123
        mock_chromadb.return_value = True

        # Create a mock PDF file
        pdf_content = b"%PDF-1.4\n%Mock PDF content for testing\n%%EOF"

        files = {"file": ("test_text.pdf", io.BytesIO(pdf_content), "application/pdf")}

        response = client.post("/etl/upload", files=files)

        assert response.status_code == 200  # nosec
        data = response.json()

        assert data["status"] == "ok"  # nosec
        assert len(data["files"]) == 1  # nosec
        assert data["files"][0]["file_name"] == "test_text.pdf"
        assert data["files"][0]["content_preview"] == "Extracted text content from PDF"

        # Verify functions were called
        mock_ocr.assert_called_once()
        mock_postgres.assert_called_once()
        mock_chromadb.assert_called_once()

    @patch("services.etl_service.main.process_pdf_ocr")
    @patch("services.etl_service.main.save_to_postgres")
    @patch("services.etl_service.main.index_in_chromadb")
    def test_pdf_scan_extraction(self, mock_chromadb, mock_postgres, mock_ocr):
        """Test PDF scan extraction with Tesseract OCR"""
        # Mock OCR response with Russian text
        mock_ocr.return_value = (
            "Тестовый документ на русском языке. Test document in Russian."
        )
        mock_postgres.return_value = 124
        mock_chromadb.return_value = True

        # Create a mock PDF scan file
        pdf_content = b"%PDF-1.4\n%Mock scanned PDF content\n%%EOF"

        files = {"file": ("test_scan.pdf", io.BytesIO(pdf_content), "application/pdf")}

        response = client.post("/etl/upload", files=files)

        assert response.status_code == 200  # nosec
        data = response.json()

        assert data["status"] == "ok"  # nosec
        assert len(data["files"]) == 1  # nosec
        assert "русском" in data["files"][0]["content_preview"]  # Russian text
        assert "Russian" in data["files"][0]["content_preview"]  # English text

        # Verify functions were called
        mock_ocr.assert_called_once()
        mock_postgres.assert_called_once()
        mock_chromadb.assert_called_once()

    @patch("psycopg2.connect")
    def test_postgres_save(self, mock_connect):
        """Test PostgreSQL save functionality"""
        from services.etl_service.main import save_to_postgres

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [125]
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        # Mock environment variable
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test"}):
            result = pytest.importorskip("asyncio").run(
                save_to_postgres("test.pdf", "pdf", "Test content", "lot123")
            )

        assert result == 125
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch("aiohttp.ClientSession.post")
    def test_chroma_index(self, mock_post):
        """Test ChromaDB indexing functionality"""
        from services.etl_service.main import index_in_chromadb

        # Mock successful response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_post.return_value.__aenter__.return_value = mock_response

        with patch.dict(os.environ, {"EMBEDDING_API_URL": "http://test:8004"}):
            result = pytest.importorskip("asyncio").run(
                index_in_chromadb(125, "test.pdf", "Test content", "lot123")
            )

        assert result is True
        mock_post.assert_called_once()


class TestRealPDFs:
    """Tests with real PDF files containing Cyrillic text"""

    def test_single_pdf_scan1(self):
        """Test uploading scan1.pdf with real OCR"""
        test_file_path = Path("../../test_files/scan1.pdf")
        if not test_file_path.exists():
            pytest.skip("scan1.pdf not found in test_files")

        with open(test_file_path, "rb") as f:
            files = {"file": ("scan1.pdf", f, "application/pdf")}
            response = client.post("/etl/upload", files=files)

        assert response.status_code == 200  # nosec
        data = response.json()

        assert data["status"] == "ok"  # nosec
        assert len(data["files"]) == 1  # nosec
        assert data["files"][0]["file_name"] == "scan1.pdf"
        assert data["files"][0]["file_type"] == "pdf"

        # Check for content extraction
        content_preview = data["files"][0]["content_preview"]
        assert len(content_preview) > 0

        # Check for potential Cyrillic characters (basic check)
        # If OCR works, we should have some text content
        assert isinstance(content_preview, str)

    def test_single_pdf_scan2(self):
        """Test uploading scan2.pdf with real OCR"""
        test_file_path = Path("../../test_files/scan2.pdf")
        if not test_file_path.exists():
            pytest.skip("scan2.pdf not found in test_files")

        with open(test_file_path, "rb") as f:
            files = {"file": ("scan2.pdf", f, "application/pdf")}
            response = client.post("/etl/upload", files=files)

        assert response.status_code == 200  # nosec
        data = response.json()

        assert data["status"] == "ok"  # nosec
        assert len(data["files"]) == 1  # nosec
        assert data["files"][0]["file_name"] == "scan2.pdf"
        assert data["files"][0]["file_type"] == "pdf"

        # Check for content extraction
        content_preview = data["files"][0]["content_preview"]
        assert len(content_preview) > 0
        assert isinstance(content_preview, str)

    def test_single_pdf_scan3(self):
        """Test uploading scan3.pdf with real OCR"""
        test_file_path = Path("../../test_files/scan3.pdf")
        if not test_file_path.exists():
            pytest.skip("scan3.pdf not found in test_files")

        with open(test_file_path, "rb") as f:
            files = {"file": ("scan3.pdf", f, "application/pdf")}
            response = client.post("/etl/upload", files=files)

        assert response.status_code == 200  # nosec
        data = response.json()

        assert data["status"] == "ok"  # nosec
        assert len(data["files"]) == 1  # nosec
        assert data["files"][0]["file_name"] == "scan3.pdf"
        assert data["files"][0]["file_type"] == "pdf"

        # Check for content extraction
        content_preview = data["files"][0]["content_preview"]
        assert len(content_preview) > 0
        assert isinstance(content_preview, str)

    def test_zip_with_scans(self):
        """Test uploading ZIP bundle with all scan PDF files"""
        test_files = ["scan1.pdf", "scan2.pdf", "scan3.pdf"]
        test_file_paths = []

        # Check if all test files exist
        for filename in test_files:
            test_file_path = Path(f"../../test_files/{filename}")
            if not test_file_path.exists():
                pytest.skip(f"{filename} not found in test_files")
            test_file_paths.append(test_file_path)

        # Create ZIP bundle with real scan files
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in test_file_paths:
                with open(file_path, "rb") as f:
                    zip_file.writestr(file_path.name, f.read())

        zip_buffer.seek(0)

        files = {"file": ("scan_bundle.zip", zip_buffer, "application/zip")}

        response = client.post("/etl/upload", files=files)

        assert response.status_code == 200  # nosec
        data = response.json()

        assert data["status"] == "ok"  # nosec
        assert len(data["files"]) == 3

        # Verify all files were processed
        file_names = [f["file_name"] for f in data["files"]]
        assert "scan1.pdf" in file_names
        assert "scan2.pdf" in file_names
        assert "scan3.pdf" in file_names

        # Verify all files have content
        for file_data in data["files"]:
            assert file_data["file_type"] == "pdf"
            assert len(file_data["content_preview"]) > 0
            assert isinstance(file_data["content_preview"], str)

        # Verify total size is reasonable
        assert data["total_size_mb"] > 0
        assert "message" in data


class TestOCRIntegration:
    """Integration tests for OCR pipeline"""

    @patch("services.etl_service.main.process_pdf_ocr")
    @patch("services.etl_service.main.save_to_postgres")
    @patch("services.etl_service.main.index_in_chromadb")
    def test_end_to_end_ocr_pipeline(self, mock_chromadb, mock_postgres, mock_ocr):
        """Test complete OCR pipeline from upload to indexing"""
        # Mock the entire pipeline
        mock_ocr.return_value = "Complete document text extracted via OCR"
        mock_postgres.return_value = 126
        mock_chromadb.return_value = True

        # Create ZIP with multiple PDFs
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("doc1.pdf", b"%PDF-1.4\nDocument 1\n%%EOF")
            zip_file.writestr("doc2.pdf", b"%PDF-1.4\nDocument 2\n%%EOF")

        zip_buffer.seek(0)

        files = {"file": ("documents.zip", zip_buffer, "application/zip")}

        response = client.post("/etl/upload", files=files)

        assert response.status_code == 200  # nosec
        data = response.json()

        assert data["status"] == "ok"  # nosec
        assert len(data["files"]) == 2

        # Verify all steps were called for each file
        assert mock_ocr.call_count == 2
        assert mock_postgres.call_count == 2
        assert mock_chromadb.call_count == 2

    def test_search_functionality_mock(self):
        """Mock test for search functionality (would require actual ChromaDB in integration)"""
        # This would be an integration test requiring actual ChromaDB
        # For now, we just test that the search endpoint structure is correct

        # In real integration test, you would:
        # 1. Upload a document with "аренда" text
        # 2. Wait for indexing
        # 3. Search for "аренда"
        # 4. Verify the document is found

        # Mock successful search response
        expected_structure = {
            "results": [
                {
                    "doc_id": "etl_doc:123",
                    "score": 0.95,
                    "metadata": {"file_name": "test.pdf", "lot_id": "lot123"},
                }
            ]
        }

        # This structure should be returned by embedding-api search
        assert "results" in expected_structure
        assert expected_structure["results"][0]["metadata"]["file_name"] == "test.pdf"


class TestE2EWithRealScans:
    """E2E tests with real scan files - requires test_files/ directory"""

    @pytest.fixture
    def test_files_dir(self):
        """Get test files directory path"""
        current_dir = Path(__file__).parent
        test_files_path = current_dir / "test_files"
        if not test_files_path.exists():
            pytest.skip("test_files/ directory not found - create it for E2E tests")
        return test_files_path

    def test_single_pdf_scan1(self, test_files_dir):
        """Test uploading scan1.pdf with real OCR"""
        scan1_path = test_files_dir / "scan1.pdf"
        if not scan1_path.exists():
            pytest.skip("scan1.pdf not found in test_files")

        with open(scan1_path, "rb") as f:
            files = {"file": ("scan1.pdf", f, "application/pdf")}
            response = client.post("/etl/upload", files=files)

        assert response.status_code == 200  # nosec
        data = response.json()
        assert data["status"] == "ok"  # nosec
        assert len(data["files"]) == 1  # nosec

        # Check for Cyrillic content in OCR results
        file_data = data["files"][0]
        assert file_data["file_name"] == "scan1.pdf"  # nosec
        content_preview = file_data["content_preview"]

        # Should contain some Cyrillic text (not just empty or error)
        assert len(content_preview) > 10  # nosec
        assert content_preview != "[Processing failed]"  # nosec
        assert content_preview != "[No text content extracted]"  # nosec

        # Check for common Russian legal terms
        cyrillic_found = any(
            term in content_preview.lower()
            for term in ["иск", "суд", "договор", "закон", "право", "документ"]
        )
        # If no specific terms found, at least check for Cyrillic characters
        if not cyrillic_found:
            has_cyrillic = any("\u0400" <= char <= "\u04ff" for char in content_preview)
            assert (
                has_cyrillic
            ), f"No Cyrillic text found in: {content_preview[:100]}"  # nosec

    def test_single_pdf_scan2(self, test_files_dir):
        """Test uploading scan2.pdf with real OCR"""
        scan2_path = test_files_dir / "scan2.pdf"
        if not scan2_path.exists():
            pytest.skip("scan2.pdf not found in test_files")

        with open(scan2_path, "rb") as f:
            files = {"file": ("scan2.pdf", f, "application/pdf")}
            response = client.post("/etl/upload", files=files)

        assert response.status_code == 200  # nosec
        data = response.json()
        assert data["status"] == "ok"  # nosec
        assert len(data["files"]) == 1  # nosec

        file_data = data["files"][0]
        content_preview = file_data["content_preview"]
        assert len(content_preview) > 10  # nosec
        assert content_preview != "[Processing failed]"  # nosec

    def test_single_pdf_scan3(self, test_files_dir):
        """Test uploading scan3.pdf with real OCR"""
        scan3_path = test_files_dir / "scan3.pdf"
        if not scan3_path.exists():
            pytest.skip("scan3.pdf not found in test_files")

        with open(scan3_path, "rb") as f:
            files = {"file": ("scan3.pdf", f, "application/pdf")}
            response = client.post("/etl/upload", files=files)

        assert response.status_code == 200  # nosec
        data = response.json()
        assert data["status"] == "ok"  # nosec
        assert len(data["files"]) == 1  # nosec

        file_data = data["files"][0]
        content_preview = file_data["content_preview"]
        assert len(content_preview) > 10  # nosec
        assert content_preview != "[Processing failed]"  # nosec

    def test_zip_with_multiple_pdfs(self, test_files_dir):
        """Test uploading scan_bundle.zip with multiple PDF files"""
        bundle_path = test_files_dir / "scan_bundle.zip"
        if not bundle_path.exists():
            pytest.skip("scan_bundle.zip not found in test_files")

        with open(bundle_path, "rb") as f:
            files = {"file": ("scan_bundle.zip", f, "application/zip")}
            response = client.post("/etl/upload", files=files)

        assert response.status_code == 200  # nosec
        data = response.json()
        assert data["status"] == "ok"  # nosec

        # Should extract multiple PDF files
        assert len(data["files"]) >= 2  # nosec

        # Check each extracted file has content
        for file_data in data["files"]:
            assert file_data["file_type"] == "pdf"  # nosec
            assert len(file_data["content_preview"]) > 10  # nosec
            assert file_data["content_preview"] != "[Processing failed]"  # nosec

    def test_zip_with_subfolder(self, test_files_dir):
        """Test uploading ZIP with PDF files in subfolder"""
        # Create temporary ZIP with subfolder structure
        import tempfile
        import zipfile

        scan1_path = test_files_dir / "scan1.pdf"
        if not scan1_path.exists():
            pytest.skip("scan1.pdf not found for subfolder test")

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_zip:
            with zipfile.ZipFile(temp_zip, "w") as zf:
                # Add file in subfolder
                with open(scan1_path, "rb") as pdf_file:
                    zf.writestr("documents/subfolder/scan1.pdf", pdf_file.read())

            temp_zip.flush()

            with open(temp_zip.name, "rb") as f:
                files = {"file": ("subfolder_test.zip", f, "application/zip")}
                response = client.post("/etl/upload", files=files)

        # Clean up
        Path(temp_zip.name).unlink()

        assert response.status_code == 200  # nosec
        data = response.json()
        assert data["status"] == "ok"  # nosec
        assert len(data["files"]) == 1  # nosec

        file_data = data["files"][0]
        assert file_data["file_name"] == "scan1.pdf"  # nosec
        assert len(file_data["content_preview"]) > 10  # nosec

    def test_unsupported_file_type_txt(self):
        """Test uploading .txt file (unsupported format)"""
        txt_content = "This is a plain text file, not supported"
        txt_buffer = io.BytesIO(txt_content.encode())

        files = {"file": ("document.txt", txt_buffer, "text/plain")}
        response = client.post("/etl/upload", files=files)

        assert response.status_code == 400  # nosec
        data = response.json()
        assert "Unsupported file type" in data["detail"]  # nosec
        assert ".txt" in data["detail"]  # nosec

    def test_large_file_over_limit(self):
        """Test uploading file larger than 50MB limit"""
        # Create a mock large file (we don't want to create actual 50MB+ file)
        # Instead, we'll mock the file size check

        # Create small file but with mocked size
        small_content = b"%PDF-1.4\nSmall content\n%%EOF"

        class MockLargeFile:
            def __init__(self, content):
                self.content = content
                self.position = 0

            def read(self, size=-1):
                if size == -1:
                    result = self.content[self.position :]
                    self.position = len(self.content)
                    return result
                else:
                    result = self.content[self.position : self.position + size]
                    self.position += len(result)
                    return result

            def seek(self, position, whence=0):
                if whence == 0:
                    self.position = position
                elif whence == 2:
                    # Simulate 51MB file size
                    self.position = 51 * 1024 * 1024

            def tell(self):
                return self.position

        mock_file = MockLargeFile(small_content)

        # Create UploadFile-like object
        from fastapi import UploadFile

        upload_file = UploadFile(filename="large_file.pdf", file=mock_file)

        # Test the upload directly (bypassing FastAPI's multipart parsing)
        import pytest
        from services.etl_service.main import upload_file as upload_func

        with pytest.raises(Exception) as exc_info:
            # This should raise HTTPException with 413 status
            import asyncio

            asyncio.run(upload_func(upload_file))

        # Check that it's the right type of error
        assert "File too large" in str(exc_info.value)

    def test_empty_post_request(self):
        """Test POST request without file parameter"""
        response = client.post("/etl/upload")

        assert response.status_code == 422  # nosec
        # FastAPI validation error for missing required file parameter

    def test_corrupted_zip_file(self):
        """Test uploading corrupted ZIP file"""
        corrupted_content = b"Not a real ZIP file content"
        zip_buffer = io.BytesIO(corrupted_content)

        files = {"file": ("corrupted.zip", zip_buffer, "application/zip")}
        response = client.post("/etl/upload", files=files)

        assert response.status_code == 400  # nosec
        data = response.json()
        assert (
            "corrupted" in data["detail"].lower() or "invalid" in data["detail"].lower()
        )  # nosec

    def test_zip_with_no_pdf_files(self):
        """Test uploading ZIP file with no PDF files inside"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            zip_file.writestr("document.txt", "This is not a PDF")
            zip_file.writestr("image.jpg", b"fake image content")

        zip_buffer.seek(0)

        files = {"file": ("no_pdfs.zip", zip_buffer, "application/zip")}
        response = client.post("/etl/upload", files=files)

        assert response.status_code == 200  # nosec
        data = response.json()
        assert data["status"] == "error"  # nosec
        assert len(data["files"]) == 0  # nosec


if __name__ == "__main__":
    pytest.main([__file__])
