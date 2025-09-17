import io
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import the ETL service modules
etl_service_path = Path(__file__).parent.parent / "services" / "etl-service"
sys.path.insert(0, str(etl_service_path))

from main import app, get_db  # noqa: E402
from models import Base, ETLBatchUpload  # noqa: E402

# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_etl_batch.db"
test_engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

Base.metadata.create_all(bind=test_engine)


def override_get_db():
    try:
        db = TestSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function")
def clean_db():
    """Clean database before each test"""
    db = TestSessionLocal()
    try:
        db.query(ETLBatchUpload).delete()
        db.commit()
    finally:
        db.close()


def create_test_csv(data, filename="test.csv"):
    """Helper function to create test CSV files"""
    df = pd.DataFrame(data)
    csv_content = df.to_csv(index=False)
    return io.StringIO(csv_content).getvalue().encode("utf-8")


def create_test_excel(data, filename="test.xlsx"):
    """Helper function to create test Excel files"""
    df = pd.DataFrame(data)
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    return buffer.getvalue()


class TestBatchUpload:
    """Test cases for batch upload functionality"""

    def test_upload_valid_csv_small_file(self, clean_db):
        """Test uploading a small valid CSV file"""
        # Create test data
        test_data = [
            {"bin": "123456789012", "amount": 1000.50, "status": "NEW"},
            {"bin": "123456789013", "amount": 2500.00, "status": "APPROVED"},
            {"bin": "123456789014", "amount": 750.25, "status": "REJECTED"},
        ]

        csv_content = create_test_csv(test_data)

        # Upload file
        response = client.post(
            "/etl/upload-batch", files={"file": ("test.csv", csv_content, "text/csv")}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["rows_processed"] == 3
        assert len(data["errors"]) == 0
        assert "batch_id" in data

        # Verify data was saved to database
        db = TestSessionLocal()
        try:
            records = db.query(ETLBatchUpload).all()
            assert len(records) == 3

            # Check first record
            first_record = records[0]
            assert first_record.bin == "123456789012"
            assert float(first_record.amount) == 1000.50
            assert first_record.status == "NEW"
        finally:
            db.close()

    def test_upload_valid_excel_file(self, clean_db):
        """Test uploading a valid Excel file"""
        test_data = [
            {"bin": "123456789012", "amount": 1500.00, "status": "NEW"},
            {"bin": "123456789013", "amount": 3000.75, "status": "APPROVED"},
        ]

        excel_content = create_test_excel(test_data)

        response = client.post(
            "/etl/upload-batch",
            files={
                "file": (
                    "test.xlsx",
                    excel_content,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["rows_processed"] == 2
        assert len(data["errors"]) == 0

    def test_upload_csv_with_validation_errors(self, clean_db):
        """Test uploading CSV with validation errors"""
        test_data = [
            {"bin": "123456789012", "amount": 1000.50, "status": "NEW"},  # Valid
            {
                "bin": "12345",
                "amount": 2500.00,
                "status": "APPROVED",
            },  # Invalid BIN (too short)
            {
                "bin": "123456789014",
                "amount": -100,
                "status": "REJECTED",
            },  # Invalid amount (negative)
            {
                "bin": "123456789015",
                "amount": 500.00,
                "status": "INVALID",
            },  # Invalid status
        ]

        csv_content = create_test_csv(test_data)

        response = client.post(
            "/etl/upload-batch", files={"file": ("test.csv", csv_content, "text/csv")}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["rows_processed"] == 1  # Only one valid record
        assert len(data["errors"]) == 3  # Three validation errors

        # Check that errors have correct row numbers and messages
        errors = {error["row"]: error["error"] for error in data["errors"]}
        assert 3 in errors  # Row 3 has invalid BIN
        assert 4 in errors  # Row 4 has negative amount
        assert 5 in errors  # Row 5 has invalid status

    def test_upload_unsupported_file_type(self, clean_db):
        """Test uploading unsupported file type"""
        response = client.post(
            "/etl/upload-batch",
            files={"file": ("test.txt", b"some text content", "text/plain")},
        )

        assert response.status_code == 400
        assert "Only CSV and XLSX files are supported" in response.json()["detail"]

    def test_upload_malformed_csv(self, clean_db):
        """Test uploading malformed CSV"""
        malformed_csv = b"bin,amount,status\n123456789012,invalid_amount,NEW\n"

        response = client.post(
            "/etl/upload-batch", files={"file": ("test.csv", malformed_csv, "text/csv")}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["rows_processed"] == 0  # No valid records
        assert len(data["errors"]) > 0  # Should have validation errors

    @patch("main.pd.read_csv")
    def test_chunk_processing_for_large_csv(self, mock_read_csv, clean_db):
        """Test chunk processing for large CSV files (>1MB)"""
        # Create test data that would be processed in chunks
        test_data = [
            {"bin": f"12345678901{i%10}", "amount": 1000.0 + i, "status": "NEW"}
            for i in range(5)
        ]

        # Mock pandas to return chunks
        chunk1 = pd.DataFrame(test_data[:3])
        chunk2 = pd.DataFrame(test_data[3:])
        mock_read_csv.return_value = [chunk1, chunk2]

        # Create a file that appears large (>1MB)
        large_csv_content = b"x" * (1024 * 1024 + 1)  # Just over 1MB

        with patch("main.process_csv_chunk") as mock_process_chunk:
            # Mock the chunk processing to return valid results
            mock_process_chunk.side_effect = [
                (
                    [
                        ETLBatchUpload(
                            bin="123456789010",
                            amount=1000.0,
                            status="NEW",
                            batch_id="test-id",
                        )
                    ],
                    [],
                ),
                (
                    [
                        ETLBatchUpload(
                            bin="123456789011",
                            amount=1001.0,
                            status="NEW",
                            batch_id="test-id",
                        )
                    ],
                    [],
                ),
            ]

            client.post(
                "/etl/upload-batch",
                files={"file": ("large_test.csv", large_csv_content, "text/csv")},
            )

            assert mock_process_chunk.call_count == 2  # Should process 2 chunks

    def test_empty_csv_file(self, clean_db):
        """Test uploading empty CSV file"""
        empty_csv = b"bin,amount,status\n"

        response = client.post(
            "/etl/upload-batch", files={"file": ("empty.csv", empty_csv, "text/csv")}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["rows_processed"] == 0
        assert len(data["errors"]) == 0

    @patch("main.MAX_FILE_SIZE_BYTES", 100)  # Mock small file size limit
    def test_file_size_middleware(self, clean_db):
        """Test file size middleware restriction"""
        large_content = b"x" * 200  # Exceeds mocked limit

        with patch("main.FileSizeMiddleware.dispatch") as mock_middleware:
            mock_middleware.side_effect = Exception("File size exceeds maximum")

            client.post(
                "/etl/upload-batch",
                files={"file": ("large.csv", large_content, "text/csv")},
            )

            # The middleware should prevent processing
            assert mock_middleware.called

    def test_batch_id_generation(self, clean_db):
        """Test that each upload gets a unique batch_id"""
        test_data = [{"bin": "123456789012", "amount": 1000.50, "status": "NEW"}]
        csv_content = create_test_csv(test_data)

        # Upload same file twice
        response1 = client.post(
            "/etl/upload-batch", files={"file": ("test1.csv", csv_content, "text/csv")}
        )

        response2 = client.post(
            "/etl/upload-batch", files={"file": ("test2.csv", csv_content, "text/csv")}
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Batch IDs should be different
        assert data1["batch_id"] != data2["batch_id"]

        # Both should be valid UUIDs
        uuid.UUID(data1["batch_id"])
        uuid.UUID(data2["batch_id"])


class TestBatchUploadIntegration:
    """Integration tests for batch upload functionality"""

    def test_end_to_end_csv_processing(self, clean_db):
        """Test complete end-to-end CSV processing"""
        test_data = [
            {"bin": "100000000001", "amount": 1500.00, "status": "NEW"},
            {"bin": "100000000002", "amount": 2500.50, "status": "APPROVED"},
            {"bin": "invalid_bin", "amount": 1000.00, "status": "NEW"},  # Invalid
            {"bin": "100000000003", "amount": 3500.75, "status": "REJECTED"},
        ]

        csv_content = create_test_csv(test_data)

        response = client.post(
            "/etl/upload-batch",
            files={"file": ("integration_test.csv", csv_content, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()

        # Should process 3 valid records, 1 error
        assert data["success"] is True
        assert data["rows_processed"] == 3
        assert len(data["errors"]) == 1
        assert data["errors"][0]["row"] == 4  # Invalid BIN on row 4

        # Verify database state
        db = TestSessionLocal()
        try:
            records = (
                db.query(ETLBatchUpload)
                .filter(ETLBatchUpload.batch_id == data["batch_id"])
                .all()
            )

            assert len(records) == 3

            bins = {record.bin for record in records}
            assert "100000000001" in bins
            assert "100000000002" in bins
            assert "100000000003" in bins
            assert "invalid_bin" not in bins  # Invalid BIN should not be saved

        finally:
            db.close()
