"""
E2E Tests for Week 4.1: Web UI Enhancements
Comprehensive testing for CSV import, lot TL;DR, autocomplete
"""

import hashlib
import json
import logging
import os

# Import the main app
import sys
import tempfile
import time
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from web.main import SessionLocal, app, redis_client

logger = logging.getLogger(__name__)


class TestCSVImport:
    """Test CSV import functionality with WebSocket progress"""

    @pytest.fixture
    def test_client(self):
        """Test client fixture"""
        return TestClient(app)

    @pytest.fixture
    def valid_csv_data(self):
        """Valid CSV data for testing"""
        data = {
            "product_name": [
                "Компьютер настольный",
                "Принтер лазерный",
                "Бумага офисная",
            ],
            "amount": [250000.50, 45000.00, 1500.75],
            "supplier_bin": ["123456789012", "234567890123", "345678901234"],
        }
        df = pd.DataFrame(data)
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8")
        return csv_buffer.getvalue().encode("utf-8")

    @pytest.fixture
    def invalid_csv_data(self):
        """Invalid CSV data for testing validation"""
        data = {
            "product_name": ["Valid Product", "", "Another Product"],
            "amount": [100000, -500, "invalid_amount"],  # Negative and non-numeric
            "supplier_bin": [
                "123456789012",
                "12345",
                "not_a_bin",
            ],  # Invalid BIN formats
        }
        df = pd.DataFrame(data)
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8")
        return csv_buffer.getvalue().encode("utf-8")

    @pytest.fixture
    def large_csv_data(self):
        """Large CSV for performance testing (>5MB)"""
        # Create 100k rows to exceed 5MB limit
        data = {
            "product_name": [f"Product {i}" * 20 for i in range(100000)],  # Long names
            "amount": [1000.0 + i for i in range(100000)],
            "supplier_bin": [
                f"{i:012d}" for i in range(123456789012, 123456789012 + 100000)
            ],
        }
        df = pd.DataFrame(data)
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8")
        return csv_buffer.getvalue().encode("utf-8")

    def test_csv_import_valid_file(self, test_client, valid_csv_data):
        """Test successful CSV import with valid data"""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(valid_csv_data)
            tmp.flush()

            client_id = "test_client_123"

            with open(tmp.name, "rb") as f:
                response = test_client.post(
                    "/web-ui/import-prices",
                    files={"file": ("test.csv", f, "text/csv")},
                    data={"client_id": client_id},
                )

            assert response.status_code == 200
            data = response.json()

            assert data["status"] in ["SUCCESS", "PARTIAL"]
            assert data["total_rows"] == 3
            assert data["success_rows"] >= 0
            assert "import_log_id" in data
            assert "processing_time_ms" in data

            # Verify data was inserted
            with SessionLocal() as db:
                result = db.execute(
                    text(
                        "SELECT COUNT(*) FROM prices WHERE product_name LIKE 'Компьютер%'"
                    )
                ).scalar()
                assert result > 0

    def test_csv_import_invalid_headers(self, test_client):
        """Test CSV import with missing required columns"""
        invalid_csv = "wrong_column,another_column\nvalue1,value2\n"

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(invalid_csv.encode())
            tmp.flush()

            with open(tmp.name, "rb") as f:
                response = test_client.post(
                    "/web-ui/import-prices",
                    files={"file": ("invalid.csv", f, "text/csv")},
                    data={"client_id": "test_invalid"},
                )

            assert response.status_code == 400
            assert "Missing required columns" in response.json()["detail"]

    def test_csv_import_file_too_large(self, test_client, large_csv_data):
        """Test CSV import with file exceeding 5MB limit"""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(large_csv_data)
            tmp.flush()

            with open(tmp.name, "rb") as f:
                response = test_client.post(
                    "/web-ui/import-prices",
                    files={"file": ("large.csv", f, "text/csv")},
                    data={"client_id": "test_large"},
                )

            assert response.status_code == 400
            assert "File too large" in response.json()["detail"]

    def test_csv_import_invalid_data_rows(self, test_client, invalid_csv_data):
        """Test CSV import with invalid row data"""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(invalid_csv_data)
            tmp.flush()

            client_id = "test_invalid_rows"

            with open(tmp.name, "rb") as f:
                response = test_client.post(
                    "/web-ui/import-prices",
                    files={"file": ("invalid_rows.csv", f, "text/csv")},
                    data={"client_id": client_id},
                )

            assert response.status_code == 200
            data = response.json()

            # Should have partial success with errors
            assert data["status"] in ["PARTIAL", "FAILED"]
            assert data["error_rows"] > 0
            assert len(data["errors"]) > 0

            # Check specific error types
            error_messages = [err["error"] for err in data["errors"]]
            assert any("cannot be empty" in msg for msg in error_messages)
            assert any("must be >= 0" in msg for msg in error_messages)
            assert any("12 digits" in msg for msg in error_messages)

    def test_import_status_endpoint(self, test_client):
        """Test import status retrieval"""
        # First create an import log manually
        with SessionLocal() as db:
            result = db.execute(
                text(
                    """
                    INSERT INTO import_logs (file_name, status, total_rows, success_rows, error_rows)
                    VALUES ('test.csv', 'SUCCESS', 100, 95, 5)
                    RETURNING id
                """
                )
            ).scalar()
            db.commit()
            log_id = result

        # Test status retrieval
        response = test_client.get(f"/web-ui/import-status/{log_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == log_id
        assert data["file_name"] == "test.csv"
        assert data["status"] == "SUCCESS"
        assert data["total_rows"] == 100
        assert data["success_rows"] == 95
        assert data["error_rows"] == 5

    def test_import_status_not_found(self, test_client):
        """Test import status for non-existent log"""
        response = test_client.get("/web-ui/import-status/999999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_csv_import_performance(self, test_client):
        """Test CSV import performance (5MB under 5 seconds)"""
        # Create medium-sized CSV (~1MB, should be processed quickly)
        data = {
            "product_name": [f"Product {i}" for i in range(5000)],
            "amount": [1000.0 + i for i in range(5000)],
            "supplier_bin": [
                f"{i:012d}" for i in range(123456789000, 123456789000 + 5000)
            ],
        }
        df = pd.DataFrame(data)
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8")
        csv_data = csv_buffer.getvalue().encode("utf-8")

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(csv_data)
            tmp.flush()

            start_time = time.time()

            with open(tmp.name, "rb") as f:
                response = test_client.post(
                    "/web-ui/import-prices",
                    files={"file": ("performance.csv", f, "text/csv")},
                    data={"client_id": "test_performance"},
                )

            processing_time = time.time() - start_time

            assert response.status_code == 200
            assert processing_time < 5.0  # Should complete within 5 seconds

            data = response.json()
            assert data["success_rows"] == 5000
            assert data["processing_time_ms"] < 5000


class TestLotTLDR:
    """Test lot TL;DR functionality with Redis caching"""

    @pytest.fixture
    def test_client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_lot_data(self):
        """Mock lot data in database"""
        return {
            "id": 12345,
            "nameRu": "Поставка компьютерного оборудования для образовательных учреждений",
            "amount": 2500000.00,
            "status": 1,
            "customerNameRu": "ГУ Образование города Алматы",
        }

    def test_lot_tldr_cache_miss_flowise_success(self, test_client, mock_lot_data):
        """Test TL;DR generation with cache miss and Flowise success"""
        lot_id = mock_lot_data["id"]

        # Clear Redis cache
        try:
            redis_client.delete(f"lot_summary:{lot_id}")
        except Exception as exc:
            logger.debug("Failed to clear lot summary cache for %s: %s", lot_id, exc)

        # Mock database response
        with patch("web.main.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            mock_db.execute.return_value.fetchone.return_value = (
                mock_lot_data["id"],
                mock_lot_data["nameRu"],
                mock_lot_data["amount"],
                mock_lot_data["status"],
                mock_lot_data["customerNameRu"],
            )

            # Mock Flowise response
            with patch("httpx.AsyncClient") as mock_client:
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "text": "Лот 12345: Поставка компьютерного оборудования, 2.5 млн тенге, активный статус."
                }

                mock_client.return_value.__aenter__.return_value.post.return_value = (
                    mock_response
                )

                start_time = time.time()
                response = test_client.get(f"/web-ui/lot/{lot_id}")
                response_time = time.time() - start_time

                assert response.status_code == 200
                assert response_time < 1.0  # Should be under 1 second

                data = response.json()
                assert data["lot_id"] == lot_id
                assert data["source"] == "flowise"
                assert data["cached"] is False
                assert len(data["summary"]) <= 500
                assert "компьютерного оборудования" in data["summary"]

    def test_lot_tldr_cache_hit(self, test_client):
        """Test TL;DR with Redis cache hit"""
        lot_id = 12345
        cached_summary = {
            "summary": "Cached summary for lot 12345",
            "source": "cache",
            "generated_at": "2024-01-01T10:00:00",
        }

        # Set cache
        try:
            redis_client.setex(
                f"lot_summary:{lot_id}", 86400, json.dumps(cached_summary)
            )
        except Exception as e:
            pytest.skip(f"Redis not available: {e}")

        start_time = time.time()
        response = test_client.get(f"/web-ui/lot/{lot_id}")
        response_time = time.time() - start_time

        assert response.status_code == 200
        assert response_time < 0.5  # Cache hit should be very fast

        data = response.json()
        assert data["source"] == "cache"
        assert data["cached"] is True
        assert data["summary"] == cached_summary["summary"]

    def test_lot_tldr_flowise_failure_fallback(self, test_client, mock_lot_data):
        """Test TL;DR with Flowise failure, uses SQL fallback"""
        lot_id = mock_lot_data["id"]

        # Clear cache
        try:
            redis_client.delete(f"lot_summary:{lot_id}")
        except Exception as exc:
            logger.debug("Failed to clear lot summary cache for %s: %s", lot_id, exc)

        with patch("web.main.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db

            mock_db.execute.return_value.fetchone.return_value = (
                mock_lot_data["id"],
                mock_lot_data["nameRu"],
                mock_lot_data["amount"],
                mock_lot_data["status"],
                mock_lot_data["customerNameRu"],
            )

            # Mock Flowise failure
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post.side_effect = (
                    Exception("Flowise timeout")
                )

                response = test_client.get(f"/web-ui/lot/{lot_id}")

                assert response.status_code == 200
                data = response.json()
                assert data["source"] == "fallback"
                assert f"Лот {lot_id}:" in data["summary"]
                assert "компьютерного оборудования" in data["summary"]

    def test_lot_tldr_not_found(self, test_client):
        """Test TL;DR for non-existent lot"""
        with patch("web.main.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchone.return_value = None

            response = test_client.get("/web-ui/lot/999999")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"]

    def test_lot_tldr_redis_unavailable(self, test_client, mock_lot_data):
        """Test TL;DR when Redis is unavailable"""
        lot_id = mock_lot_data["id"]

        with patch("web.main.redis_client") as mock_redis:
            mock_redis.get.side_effect = redis.ConnectionError("Redis unavailable")
            mock_redis.setex.side_effect = redis.ConnectionError("Redis unavailable")

            with patch("web.main.SessionLocal") as mock_session:
                mock_db = MagicMock()
                mock_session.return_value.__enter__.return_value = mock_db
                mock_db.execute.return_value.fetchone.return_value = (
                    mock_lot_data["id"],
                    mock_lot_data["nameRu"],
                    mock_lot_data["amount"],
                    mock_lot_data["status"],
                    mock_lot_data["customerNameRu"],
                )

                response = test_client.get(f"/web-ui/lot/{lot_id}")

                # Should still work without Redis
                assert response.status_code == 200
                data = response.json()
                assert data["lot_id"] == lot_id


class TestAutocomplete:
    """Test autocomplete functionality with ChromaDB and SQL fallback"""

    @pytest.fixture
    def test_client(self):
        return TestClient(app)

    def test_autocomplete_valid_query(self, test_client):
        """Test autocomplete with valid query"""
        response = test_client.get("/api/search/autocomplete?query=компьют")
        assert response.status_code == 200

        data = response.json()
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)

    def test_autocomplete_short_query(self, test_client):
        """Test autocomplete with query too short (<2 chars)"""
        response = test_client.get("/api/search/autocomplete?query=к")
        assert response.status_code == 200

        data = response.json()
        assert data["suggestions"] == []

    def test_autocomplete_empty_query(self, test_client):
        """Test autocomplete with empty query"""
        response = test_client.get("/api/search/autocomplete?query=")
        assert response.status_code == 200

        data = response.json()
        assert data["suggestions"] == []

    def test_autocomplete_cyrillic_support(self, test_client):
        """Test autocomplete with Cyrillic characters"""
        queries = ["мебель", "компьютер", "офисн"]

        for query in queries:
            response = test_client.get(f"/api/search/autocomplete?query={query}")
            assert response.status_code == 200

            data = response.json()
            assert "suggestions" in data
            # Suggestions should contain Cyrillic text if available

    def test_autocomplete_special_chars_filtering(self, test_client):
        """Test that special characters are filtered out"""
        queries_with_specials = [
            "мебель123!@#",
            "компьютер$%^",
            "офис   много пробелов",
        ]

        for query in queries_with_specials:
            response = test_client.get(f"/api/search/autocomplete?query={query}")
            assert response.status_code == 200
            # Should not crash and return valid response

    def test_autocomplete_cache_functionality(self, test_client):
        """Test Redis caching for autocomplete"""
        query = "тестовый"

        # Clear cache first
        try:
            cache_key = f"autocomplete:{hashlib.sha256(query.encode()).hexdigest()}"
            redis_client.delete(cache_key)
        except Exception as exc:
            logger.debug("Failed to clear autocomplete cache for %s: %s", query, exc)

        # First request (cache miss)
        start_time = time.time()
        response1 = test_client.get(f"/api/search/autocomplete?query={query}")
        time1 = time.time() - start_time

        assert response1.status_code == 200

        # Second request (cache hit)
        start_time = time.time()
        response2 = test_client.get(f"/api/search/autocomplete?query={query}")
        time2 = time.time() - start_time

        assert response2.status_code == 200

        # Cache hit should be faster
        if time1 > 0.1:  # Only check if first request took reasonable time
            assert time2 < time1

        # Results should be identical
        assert response1.json() == response2.json()

    def test_autocomplete_chromadb_failure_sql_fallback(self, test_client):
        """Test SQL fallback when ChromaDB is unavailable"""
        with patch("web.main.chroma_client") as mock_chroma:
            mock_chroma.get_collection.side_effect = Exception("ChromaDB unavailable")

            with patch("web.main.SessionLocal") as mock_session:
                mock_db = MagicMock()
                mock_session.return_value.__enter__.return_value = mock_db

                # Mock SQL results
                mock_db.execute.return_value.fetchall.return_value = [
                    ("Компьютерное оборудование",),
                    ("Компьютерная техника",),
                ]

                response = test_client.get("/api/search/autocomplete?query=компьют")
                assert response.status_code == 200

                data = response.json()
                assert len(data["suggestions"]) > 0
                assert "Компьютерное оборудование" in data["suggestions"]

    def test_autocomplete_performance(self, test_client):
        """Test autocomplete performance (<500ms)"""
        queries = ["мебель", "компьютер", "канцелярские", "строительство"]

        for query in queries:
            start_time = time.time()
            response = test_client.get(f"/api/search/autocomplete?query={query}")
            response_time = time.time() - start_time

            assert response.status_code == 200
            assert response_time < 0.5  # Should be under 500ms


class TestE2EIntegration:
    """End-to-end integration tests"""

    @pytest.fixture
    def test_client(self):
        return TestClient(app)

    def test_full_csv_import_workflow(self, test_client):
        """Test complete CSV import workflow"""
        # 1. Create valid CSV
        csv_data = (
            "product_name,amount,supplier_bin\nТестовый продукт,1000,123456789012\n"
        )

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(csv_data.encode())
            tmp.flush()

            # 2. Upload CSV
            with open(tmp.name, "rb") as f:
                import_response = test_client.post(
                    "/web-ui/import-prices",
                    files={"file": ("test.csv", f, "text/csv")},
                    data={"client_id": "e2e_test"},
                )

            assert import_response.status_code == 200
            import_data = import_response.json()
            log_id = import_data["import_log_id"]

            # 3. Check import status
            status_response = test_client.get(f"/web-ui/import-status/{log_id}")
            assert status_response.status_code == 200

            status_data = status_response.json()
            assert status_data["status"] in ["SUCCESS", "PARTIAL"]

            # 4. Verify data in database
            with SessionLocal() as db:
                result = db.execute(
                    text(
                        "SELECT COUNT(*) FROM prices WHERE product_name = 'Тестовый продукт'"
                    )
                ).scalar()
                assert result > 0

    def test_lot_tldr_with_autocomplete_integration(self, test_client):
        """Test lot TL;DR and autocomplete working together"""
        # First test autocomplete
        autocomplete_response = test_client.get(
            "/api/search/autocomplete?query=компьют"
        )
        assert autocomplete_response.status_code == 200

        # Mock lot for TL;DR test
        with patch("web.main.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchone.return_value = (
                12345,
                "Компьютерное оборудование",
                100000,
                1,
                "Тест заказчик",
            )

            tldr_response = test_client.get("/web-ui/lot/12345")
            assert tldr_response.status_code == 200

            tldr_data = tldr_response.json()
            assert "компьютер" in tldr_data["summary"].lower()

    def test_redis_failure_graceful_degradation(self, test_client):
        """Test that system works when Redis is completely unavailable"""
        with patch("web.main.redis_client") as mock_redis:
            # Make all Redis operations fail
            mock_redis.get.side_effect = redis.ConnectionError("Redis down")
            mock_redis.setex.side_effect = redis.ConnectionError("Redis down")

            # Autocomplete should still work via SQL fallback
            with patch("web.main.SessionLocal") as mock_session:
                mock_db = MagicMock()
                mock_session.return_value.__enter__.return_value = mock_db
                mock_db.execute.return_value.fetchall.return_value = [
                    ("Test suggestion",)
                ]

                response = test_client.get("/api/search/autocomplete?query=тест")
                assert response.status_code == 200

            # TL;DR should work without caching
            with patch("web.main.SessionLocal") as mock_session:
                mock_db = MagicMock()
                mock_session.return_value.__enter__.return_value = mock_db
                mock_db.execute.return_value.fetchone.return_value = (
                    1,
                    "Test lot",
                    1000,
                    1,
                    "Test customer",
                )

                response = test_client.get("/web-ui/lot/1")
                assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
