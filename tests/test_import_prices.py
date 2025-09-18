"""
Unit tests for CSV import functionality
Week 4.1: Focused tests for price import with WebSocket progress
"""

import os
import sys
import tempfile
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from web.main import CSVImportProgress, SessionLocal, app, ws_manager


class TestCSVImportUnit:
    """Unit tests for CSV import functionality"""

    @pytest.fixture
    def test_client(self):
        return TestClient(app)

    @pytest.fixture
    def sample_valid_csv(self):
        """Generate valid CSV content"""
        data = {
            "product_name": [
                "Компьютер ASUS",
                "Принтер HP LaserJet",
                "Бумага А4 500л",
                "Картридж черный",
                "Мышь оптическая",
            ],
            "amount": [150000.00, 75000.50, 2500.25, 12000.00, 1500.75],
            "supplier_bin": [
                "123456789012",
                "234567890123",
                "345678901234",
                "456789012345",
                "567890123456",
            ],
        }
        df = pd.DataFrame(data)
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8")
        return csv_buffer.getvalue().encode("utf-8")

    @pytest.fixture
    def sample_cyrillic_csv(self):
        """CSV with Cyrillic characters and edge cases"""
        data = {
            "product_name": [
                "Мебель офисная стол директора",
                "Канцелярские товары набор №1",
                "Компьютерная техника ноутбук",
                "Бытовая химия моющие средства",
            ],
            "amount": [250000, 15000, 180000, 8500],
            "supplier_bin": [
                "111111111111",
                "222222222222",
                "333333333333",
                "444444444444",
            ],
        }
        df = pd.DataFrame(data)
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8")
        return csv_buffer.getvalue().encode("utf-8")

    def test_csv_validation_headers(self, test_client):
        """Test CSV header validation"""
        # Missing required columns
        invalid_csv = "wrong_column1,wrong_column2\nvalue1,value2\n"

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(invalid_csv.encode())
            tmp.flush()

            with open(tmp.name, "rb") as f:
                response = test_client.post(
                    "/web-ui/import-prices",
                    files={"file": ("invalid_headers.csv", f, "text/csv")},
                    data={"client_id": "test_headers"},
                )

            assert response.status_code == 400
            error_detail = response.json()["detail"]
            assert "Missing required columns" in error_detail
            assert "product_name" in error_detail
            assert "amount" in error_detail
            assert "supplier_bin" in error_detail

    def test_csv_validation_file_extension(self, test_client):
        """Test file extension validation"""
        txt_content = "This is not a CSV file"

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(txt_content.encode())
            tmp.flush()

            with open(tmp.name, "rb") as f:
                response = test_client.post(
                    "/web-ui/import-prices",
                    files={"file": ("test.txt", f, "text/plain")},
                    data={"client_id": "test_ext"},
                )

            assert response.status_code == 400
            assert "Only CSV files are supported" in response.json()["detail"]

    def test_csv_validation_file_size(self, test_client):
        """Test file size validation (5MB limit)"""
        # Create a large CSV that exceeds 5MB
        large_data = {
            "product_name": [
                f"Very long product name with lots of text {i}" * 100
                for i in range(10000)
            ],
            "amount": [1000.0 + i for i in range(10000)],
            "supplier_bin": [
                f"{i:012d}" for i in range(123456789000, 123456789000 + 10000)
            ],
        }
        df = pd.DataFrame(large_data)
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8")
        large_csv = csv_buffer.getvalue().encode("utf-8")

        # Ensure it's actually over 5MB
        assert len(large_csv) > 5 * 1024 * 1024

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(large_csv)
            tmp.flush()

            with open(tmp.name, "rb") as f:
                response = test_client.post(
                    "/web-ui/import-prices",
                    files={"file": ("large.csv", f, "text/csv")},
                    data={"client_id": "test_size"},
                )

            assert response.status_code == 400
            assert "File too large" in response.json()["detail"]

    def test_csv_row_validation_empty_product_name(self, test_client):
        """Test validation of empty product names"""
        invalid_data = {
            "product_name": ["Valid Product", "", "Another Valid"],
            "amount": [1000, 2000, 3000],
            "supplier_bin": ["123456789012", "234567890123", "345678901234"],
        }
        df = pd.DataFrame(invalid_data)
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8")
        csv_content = csv_buffer.getvalue().encode("utf-8")

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(csv_content)
            tmp.flush()

            with open(tmp.name, "rb") as f:
                response = test_client.post(
                    "/web-ui/import-prices",
                    files={"file": ("empty_names.csv", f, "text/csv")},
                    data={"client_id": "test_empty_names"},
                )

            assert response.status_code == 200
            data = response.json()

            # Should have partial success
            assert data["status"] == "PARTIAL"
            assert data["error_rows"] == 1
            assert data["success_rows"] == 2

            # Check error details
            errors = data["errors"]
            assert len(errors) == 1
            assert "cannot be empty" in errors[0]["error"]

    def test_csv_row_validation_negative_amount(self, test_client):
        """Test validation of negative amounts"""
        invalid_data = {
            "product_name": ["Product A", "Product B", "Product C"],
            "amount": [1000, -500, 2000],  # Negative amount
            "supplier_bin": ["123456789012", "234567890123", "345678901234"],
        }
        df = pd.DataFrame(invalid_data)
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8")
        csv_content = csv_buffer.getvalue().encode("utf-8")

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(csv_content)
            tmp.flush()

            with open(tmp.name, "rb") as f:
                response = test_client.post(
                    "/web-ui/import-prices",
                    files={"file": ("negative_amount.csv", f, "text/csv")},
                    data={"client_id": "test_negative"},
                )

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "PARTIAL"
            assert data["error_rows"] == 1
            assert data["success_rows"] == 2

            errors = data["errors"]
            assert any("must be >= 0" in err["error"] for err in errors)

    def test_csv_row_validation_invalid_bin(self, test_client):
        """Test validation of invalid BIN formats"""
        invalid_data = {
            "product_name": ["Product A", "Product B", "Product C"],
            "amount": [1000, 2000, 3000],
            "supplier_bin": ["123456789012", "12345", "not_a_number"],  # Invalid BINs
        }
        df = pd.DataFrame(invalid_data)
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8")
        csv_content = csv_buffer.getvalue().encode("utf-8")

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(csv_content)
            tmp.flush()

            with open(tmp.name, "rb") as f:
                response = test_client.post(
                    "/web-ui/import-prices",
                    files={"file": ("invalid_bin.csv", f, "text/csv")},
                    data={"client_id": "test_bin"},
                )

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "PARTIAL"
            assert data["error_rows"] == 2
            assert data["success_rows"] == 1

            errors = data["errors"]
            assert any("12 digits" in err["error"] for err in errors)

    def test_csv_cyrillic_support(self, test_client, sample_cyrillic_csv):
        """Test proper handling of Cyrillic characters"""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(sample_cyrillic_csv)
            tmp.flush()

            with open(tmp.name, "rb") as f:
                response = test_client.post(
                    "/web-ui/import-prices",
                    files={"file": ("cyrillic.csv", f, "text/csv")},
                    data={"client_id": "test_cyrillic"},
                )

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "SUCCESS"
            assert data["success_rows"] == 4
            assert data["error_rows"] == 0

            # Verify Cyrillic data was inserted correctly
            with SessionLocal() as db:
                result = db.execute(
                    text(
                        "SELECT product_name FROM prices WHERE product_name LIKE '%Мебель%'"
                    )
                ).fetchone()
                assert result is not None
                assert "Мебель офисная" in result[0]

    def test_csv_chunk_processing(self, test_client):
        """Test chunk-based processing with progress tracking"""
        # Create CSV with exactly 2500 rows (2.5 chunks of 1000)
        data = {
            "product_name": [f"Товар {i}" for i in range(2500)],
            "amount": [1000.0 + i for i in range(2500)],
            "supplier_bin": [f"{(123456789012 + i):012d}" for i in range(2500)],
        }
        df = pd.DataFrame(data)
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8")
        csv_content = csv_buffer.getvalue().encode("utf-8")

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(csv_content)
            tmp.flush()

            with open(tmp.name, "rb") as f:
                response = test_client.post(
                    "/web-ui/import-prices",
                    files={"file": ("chunks.csv", f, "text/csv")},
                    data={"client_id": "test_chunks"},
                )

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "SUCCESS"
            assert data["total_rows"] == 2500
            assert data["success_rows"] == 2500
            assert data["processing_time_ms"] > 0

    def test_import_log_creation(self, test_client, sample_valid_csv):
        """Test that import logs are created and updated correctly"""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(sample_valid_csv)
            tmp.flush()

            with open(tmp.name, "rb") as f:
                response = test_client.post(
                    "/web-ui/import-prices",
                    files={"file": ("log_test.csv", f, "text/csv")},
                    data={"client_id": "test_logging"},
                )

            assert response.status_code == 200
            data = response.json()
            log_id = data["import_log_id"]

            # Verify import log was created and updated
            with SessionLocal() as db:
                log_result = db.execute(
                    text(
                        """
                        SELECT file_name, status, total_rows, success_rows, error_rows,
                               processing_time_ms
                        FROM import_logs WHERE id = :log_id
                    """
                    ),
                    {"log_id": log_id},
                ).fetchone()

                assert log_result is not None
                assert log_result[0] == "log_test.csv"  # file_name
                assert log_result[1] in ["SUCCESS", "PARTIAL"]  # status
                assert log_result[2] == 5  # total_rows
                assert log_result[3] == 5  # success_rows (all valid)
                assert log_result[4] == 0  # error_rows
                assert log_result[5] > 0  # processing_time_ms

    def test_websocket_progress_model(self):
        """Test WebSocket progress model validation"""
        # Valid progress
        valid_progress = CSVImportProgress(
            progress=75.5,
            rows_ok=1500,
            rows_error=25,
            current_row=1525,
            message="Processing chunk 2...",
        )
        assert valid_progress.progress == 75.5
        assert valid_progress.rows_ok == 1500

        # Invalid progress (over 100%)
        with pytest.raises(ValueError):
            CSVImportProgress(progress=150.0, rows_ok=100, rows_error=0)

        # Invalid progress (negative)
        with pytest.raises(ValueError):
            CSVImportProgress(progress=-10.0, rows_ok=100, rows_error=0)

    @pytest.mark.asyncio
    async def test_websocket_manager(self):
        """Test WebSocket connection manager"""
        # Test connection management
        client_id = "test_ws_client"
        mock_websocket = AsyncMock()

        # Test connection
        await ws_manager.connect(mock_websocket, client_id)
        assert client_id in ws_manager.active_connections

        # Test progress sending
        progress = CSVImportProgress(
            progress=50.0, rows_ok=100, rows_error=5, message="Testing..."
        )

        await ws_manager.send_progress(client_id, progress)
        mock_websocket.send_text.assert_called_once()

        # Test disconnection
        ws_manager.disconnect(client_id)
        assert client_id not in ws_manager.active_connections

    def test_error_handling_database_failure(self, test_client, sample_valid_csv):
        """Test error handling when database operations fail"""
        with patch("web.main.SessionLocal") as mock_session:
            # Mock database failure on insert
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.execute.side_effect = Exception("Database connection failed")

            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                tmp.write(sample_valid_csv)
                tmp.flush()

                with open(tmp.name, "rb") as f:
                    response = test_client.post(
                        "/web-ui/import-prices",
                        files={"file": ("db_fail.csv", f, "text/csv")},
                        data={"client_id": "test_db_fail"},
                    )

                # Should return 500 error
                assert response.status_code == 500
                assert "Import failed" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
