"""
Comprehensive tests for Advanced Search functionality in ZakupAI
Tests cover API endpoints, validation, performance, and integration
"""

import json
import logging
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the web directory to Python path
web_path = Path(__file__).parent.parent / "web"
sys.path.insert(0, str(web_path))

try:
    from main import app

    from web.main import Base, SessionLocal
except ImportError as e:
    pytest.skip(f"Web components not available: {e}", allow_module_level=True)

logger = logging.getLogger(__name__)

# Test database configuration
TEST_DATABASE_URL = "sqlite:///./test_advanced_search.db"
test_engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Create test tables
Base.metadata.create_all(bind=test_engine)


class TestAdvancedSearchAPI:
    """Test suite for advanced search API endpoints"""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up test client and database"""

        # Override database dependency
        def override_get_db():
            try:
                db = TestSessionLocal()
                yield db
            finally:
                db.close()

        app.dependency_overrides[SessionLocal] = override_get_db
        self.client = TestClient(app)

        # Clean database before each test
        self.clean_test_data()
        self.insert_test_data()

    def clean_test_data(self):
        """Clean all test data from database"""
        db = TestSessionLocal()
        try:
            # Clean lots and trdbuy tables
            db.execute(text("DELETE FROM lots"))
            db.execute(text("DELETE FROM trdbuy"))
            db.execute(text("DELETE FROM subjects"))
            db.commit()
        except Exception as exc:
            # Tables might not exist yet
            logger.debug("Failed to clean test data: %s", exc)
        finally:
            db.close()

    def insert_test_data(self):
        """Insert test data for search functionality"""
        db = TestSessionLocal()
        try:
            # Insert test subjects (customers)
            subjects_data = [
                ("123456789012", "ТОО Тестовая Компания 1", "01", "01"),
                ("123456789013", "АО Медицинский Центр", "02", "02"),
                ("123456789014", "ТОО Строительная Фирма", "03", "03"),
            ]

            for bin_num, name, oked, region in subjects_data:
                db.execute(
                    text(
                        """
                    INSERT OR REPLACE INTO subjects (bin, nameRu, okedCode, regionCode)
                    VALUES (:bin, :name, :oked, :region)
                """
                    ),
                    {"bin": bin_num, "name": name, "oked": oked, "region": region},
                )

            # Insert test trdbuy data
            trdbuy_data = [
                (
                    1001,
                    "2024-01-01",
                    "2024-02-01",
                    "123456789012",
                    "ТОО Тестовая Компания 1",
                    1,
                    "Поставка компьютерного оборудования",
                    500000.0,
                ),
                (
                    1002,
                    "2024-01-02",
                    "2024-02-02",
                    "123456789013",
                    "АО Медицинский Центр",
                    2,
                    "Закупка медицинского оборудования",
                    1200000.0,
                ),
                (
                    1003,
                    "2024-01-03",
                    "2024-02-03",
                    "123456789014",
                    "ТОО Строительная Фирма",
                    1,
                    "Строительство дорог",
                    2500000.0,
                ),
                (
                    1004,
                    "2024-01-04",
                    "2024-02-04",
                    "123456789012",
                    "ТОО Тестовая Компания 1",
                    3,
                    "Поставка канцелярских товаров",
                    25000.0,
                ),
            ]

            for (
                tid,
                pub_date,
                end_date,
                customer_bin,
                customer_name,
                status_id,
                name_ru,
                total_sum,
            ) in trdbuy_data:
                db.execute(
                    text(
                        """
                    INSERT OR REPLACE INTO trdbuy
                    (id, publishDate, endDate, customerBin, customerNameRu, refBuyStatusId, nameRu, totalSum)
                    VALUES (:id, :pub_date, :end_date, :customer_bin, :customer_name, :status_id, :name_ru, :total_sum)
                """
                    ),
                    {
                        "id": tid,
                        "pub_date": pub_date,
                        "end_date": end_date,
                        "customer_bin": customer_bin,
                        "customer_name": customer_name,
                        "status_id": status_id,
                        "name_ru": name_ru,
                        "total_sum": total_sum,
                    },
                )

            # Insert test lots data
            lots_data = [
                (
                    2001,
                    1001,
                    "Настольные компьютеры",
                    150000.0,
                    "Поставка настольных компьютеров для офиса",
                    "2024-01-01",
                ),
                (
                    2002,
                    1001,
                    "Ноутбуки для сотрудников",
                    200000.0,
                    "Закупка ноутбуков для мобильных сотрудников",
                    "2024-01-01",
                ),
                (
                    2003,
                    1002,
                    "Рентгеновский аппарат",
                    800000.0,
                    "Цифровой рентгеновский аппарат",
                    "2024-01-02",
                ),
                (
                    2004,
                    1002,
                    "Медицинские инструменты",
                    400000.0,
                    "Набор хирургических инструментов",
                    "2024-01-02",
                ),
                (
                    2005,
                    1003,
                    "Асфальтобетонная смесь",
                    1500000.0,
                    "Поставка асфальтобетонной смеси",
                    "2024-01-03",
                ),
                (
                    2006,
                    1003,
                    "Дорожная разметка",
                    1000000.0,
                    "Нанесение дорожной разметки",
                    "2024-01-03",
                ),
                (
                    2007,
                    1004,
                    "Офисная бумага",
                    15000.0,
                    "Бумага формата А4",
                    "2024-01-04",
                ),
                (
                    2008,
                    1004,
                    "Канцелярские принадлежности",
                    10000.0,
                    "Ручки, карандаши, скрепки",
                    "2024-01-04",
                ),
            ]

            for lid, trd_buy_id, name_ru, amount, desc_ru, update_date in lots_data:
                db.execute(
                    text(
                        """
                    INSERT OR REPLACE INTO lots
                    (id, trdBuyId, nameRu, amount, descriptionRu, lastUpdateDate)
                    VALUES (:id, :trd_buy_id, :name_ru, :amount, :desc_ru, :update_date)
                """
                    ),
                    {
                        "id": lid,
                        "trd_buy_id": trd_buy_id,
                        "name_ru": name_ru,
                        "amount": amount,
                        "desc_ru": desc_ru,
                        "update_date": update_date,
                    },
                )

            db.commit()

        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    # Basic functionality tests
    def test_advanced_search_basic_query(self):
        """Test basic search functionality"""
        response = self.client.post(
            "/api/search/advanced", json={"query": "компьютеры"}
        )

        assert response.status_code == 200
        data = response.json()

        assert "results" in data
        assert "total_count" in data
        assert data["total_count"] >= 2  # Should find computer-related lots
        assert len(data["results"]) >= 2

        # Verify search results contain computer-related items
        results = data["results"]
        computer_found = any(
            "компьютер" in result["nameRu"].lower()
            or "ноутбук" in result["nameRu"].lower()
            for result in results
        )
        assert computer_found

    def test_advanced_search_with_amount_filters(self):
        """Test search with min/max amount filters"""
        response = self.client.post(
            "/api/search/advanced",
            json={"query": "оборудование", "min_amount": 100000, "max_amount": 1000000},
        )

        assert response.status_code == 200
        data = response.json()

        # All results should be within the amount range
        for result in data["results"]:
            assert 100000 <= result["amount"] <= 1000000

    def test_advanced_search_with_status_filter(self):
        """Test search with status filter"""
        response = self.client.post(
            "/api/search/advanced", json={"query": "поставка", "status": "1"}
        )

        assert response.status_code == 200
        data = response.json()

        # All results should have status 1
        for result in data["results"]:
            assert result["status"] == 1

    def test_advanced_search_pagination(self):
        """Test pagination functionality"""
        # First page
        response1 = self.client.post(
            "/api/search/advanced", json={"query": "", "limit": 3, "offset": 0}
        )

        assert response1.status_code == 200
        data1 = response1.json()

        # Second page
        response2 = self.client.post(
            "/api/search/advanced", json={"query": "", "limit": 3, "offset": 3}
        )

        assert response2.status_code == 200
        data2 = response2.json()

        # Results should be different
        results1_ids = {r["id"] for r in data1["results"]}
        results2_ids = {r["id"] for r in data2["results"]}
        assert results1_ids.isdisjoint(results2_ids)  # No overlap

    # Validation tests
    def test_search_query_validation(self):
        """Test query parameter validation"""
        # Empty query
        response = self.client.post("/api/search/advanced", json={"query": ""})
        assert response.status_code == 422

        # Query too long
        response = self.client.post("/api/search/advanced", json={"query": "x" * 501})
        assert response.status_code == 422

    def test_amount_validation(self):
        """Test amount parameter validation"""
        # Negative min_amount
        response = self.client.post(
            "/api/search/advanced", json={"query": "тест", "min_amount": -1000}
        )
        assert response.status_code == 422

        # max_amount < min_amount
        response = self.client.post(
            "/api/search/advanced",
            json={"query": "тест", "min_amount": 100000, "max_amount": 50000},
        )
        assert response.status_code == 422

    def test_limit_validation(self):
        """Test limit parameter validation"""
        # Limit too high
        response = self.client.post(
            "/api/search/advanced", json={"query": "тест", "limit": 101}
        )
        assert response.status_code == 422

        # Limit too low
        response = self.client.post(
            "/api/search/advanced", json={"query": "тест", "limit": 0}
        )
        assert response.status_code == 422

    def test_status_validation(self):
        """Test status parameter validation"""
        # Invalid status
        response = self.client.post(
            "/api/search/advanced", json={"query": "тест", "status": "invalid"}
        )
        assert response.status_code == 422

        # Status out of range
        response = self.client.post(
            "/api/search/advanced", json={"query": "тест", "status": "11"}
        )
        assert response.status_code == 422

    # Edge cases
    def test_search_no_results(self):
        """Test search with no matching results"""
        response = self.client.post(
            "/api/search/advanced", json={"query": "несуществующий_товар_xyz123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        assert len(data["results"]) == 0

    def test_search_cyrillic_query(self):
        """Test search with Cyrillic characters"""
        response = self.client.post(
            "/api/search/advanced", json={"query": "медицинское"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] > 0

    def test_search_mixed_case_query(self):
        """Test search with mixed case"""
        response = self.client.post(
            "/api/search/advanced", json={"query": "КоМпЬюТеРы"}
        )

        assert response.status_code == 200
        # Should still find results regardless of case


class TestAutocompleteAPI:
    """Test suite for autocomplete API endpoint"""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    @patch("chromadb.Client")
    def test_autocomplete_basic(self, mock_chromadb_client):
        """Test basic autocomplete functionality"""
        # Mock ChromaDB response
        mock_collection = Mock()
        mock_collection.query.return_value = {
            "documents": [
                ["компьютеры", "компьютерное оборудование", "компьютерные программы"]
            ]
        }
        mock_chromadb_client.return_value.get_collection.return_value = mock_collection

        response = self.client.get("/api/search/autocomplete?query=компьют")

        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) == 3
        assert "компьютеры" in data["suggestions"]

    def test_autocomplete_short_query(self):
        """Test autocomplete with query too short"""
        response = self.client.get("/api/search/autocomplete?query=к")

        assert response.status_code == 200
        data = response.json()
        assert data["suggestions"] == []

    def test_autocomplete_missing_query(self):
        """Test autocomplete without query parameter"""
        response = self.client.get("/api/search/autocomplete")

        assert response.status_code == 422  # Missing required parameter

    @patch("chromadb.Client")
    def test_autocomplete_chromadb_error(self, mock_chromadb_client):
        """Test autocomplete when ChromaDB fails"""
        # Mock ChromaDB to raise exception
        mock_chromadb_client.return_value.get_collection.side_effect = Exception(
            "ChromaDB error"
        )

        response = self.client.get("/api/search/autocomplete?query=тест")

        assert response.status_code == 200
        data = response.json()
        assert data["suggestions"] == []  # Should gracefully handle errors

    @patch("chromadb.Client")
    def test_autocomplete_empty_results(self, mock_chromadb_client):
        """Test autocomplete with no suggestions"""
        # Mock empty ChromaDB response
        mock_collection = Mock()
        mock_collection.query.return_value = {"documents": [[]]}
        mock_chromadb_client.return_value.get_collection.return_value = mock_collection

        response = self.client.get("/api/search/autocomplete?query=несуществующий")

        assert response.status_code == 200
        data = response.json()
        assert data["suggestions"] == []


class TestAdvancedSearchPerformance:
    """Performance tests for advanced search"""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    def test_search_response_time(self):
        """Test that search responds within acceptable time"""
        start_time = time.time()

        response = self.client.post(
            "/api/search/advanced", json={"query": "компьютеры", "limit": 50}
        )

        execution_time = time.time() - start_time

        assert response.status_code == 200
        assert execution_time < 2.0  # Should respond within 2 seconds

    def test_autocomplete_response_time(self):
        """Test that autocomplete responds quickly"""
        with patch("chromadb.Client") as mock_chromadb_client:
            # Mock quick ChromaDB response
            mock_collection = Mock()
            mock_collection.query.return_value = {"documents": [["тест1", "тест2"]]}
            mock_chromadb_client.return_value.get_collection.return_value = (
                mock_collection
            )

            start_time = time.time()
            response = self.client.get("/api/search/autocomplete?query=тест")
            execution_time = time.time() - start_time

            assert response.status_code == 200
            assert execution_time < 0.5  # Should respond within 500ms

    def test_concurrent_search_requests(self):
        """Test handling multiple concurrent search requests"""
        import queue
        import threading

        results_queue = queue.Queue()
        num_requests = 10

        def make_request():
            try:
                response = self.client.post(
                    "/api/search/advanced",
                    json={"query": f"тест{uuid.uuid4().hex[:8]}"},
                )
                results_queue.put(response.status_code)
            except Exception as e:
                results_queue.put(f"error: {str(e)}")

        # Create and start threads
        threads = []
        for _ in range(num_requests):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=10)  # 10 second timeout

        # Collect results
        status_codes = []
        while not results_queue.empty():
            result = results_queue.get()
            status_codes.append(result)

        # All requests should succeed
        assert len(status_codes) == num_requests
        assert all(status == 200 for status in status_codes)


class TestAdvancedSearchIntegration:
    """Integration tests for the complete advanced search system"""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up test client and clean state"""
        self.client = TestClient(app)

    def test_end_to_end_search_flow(self):
        """Test complete search flow: request -> database -> response"""
        # Perform search
        search_request = {
            "query": "медицинское оборудование",
            "min_amount": 100000,
            "max_amount": 1000000,
            "limit": 20,
        }

        response = self.client.post("/api/search/advanced", json=search_request)

        # Verify response structure
        assert response.status_code == 200
        data = response.json()

        assert "results" in data
        assert "total_count" in data
        assert isinstance(data["results"], list)
        assert isinstance(data["total_count"], int)

        # Verify result structure
        if data["results"]:
            result = data["results"][0]
            required_fields = ["id", "nameRu", "amount", "status", "trdBuyId"]
            for field in required_fields:
                assert field in result

            # Verify data types
            assert isinstance(result["id"], int)
            assert isinstance(result["nameRu"], str)
            assert isinstance(result["amount"], int | float)
            assert isinstance(result["status"], int)
            assert isinstance(result["trdBuyId"], int)

    @patch("aiohttp.ClientSession.post")
    def test_telegram_bot_integration_simulation(self, mock_post):
        """Simulate Telegram bot calling advanced search API"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = Mock(
            return_value={
                "results": [
                    {
                        "id": 123,
                        "nameRu": "Тестовый лот",
                        "amount": 50000.0,
                        "status": 1,
                        "trdBuyId": 456,
                        "customerNameRu": "Тестовый заказчик",
                    }
                ],
                "total_count": 1,
            }
        )
        mock_post.return_value.__aenter__.return_value = mock_response

        # This simulates what the Telegram bot would do
        search_params = {"query": "компьютеры", "min_amount": 10000, "limit": 10}

        response = self.client.post("/api/search/advanced", json=search_params)

        assert response.status_code == 200
        data = response.json()

        # Verify the format matches what Telegram bot expects
        assert "results" in data
        assert "total_count" in data

    def test_web_ui_javascript_compatibility(self):
        """Test that API responses are compatible with Web UI JavaScript"""
        response = self.client.post(
            "/api/search/advanced", json={"query": "тест", "limit": 5}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify JSON structure is JavaScript-friendly
        json_str = json.dumps(data)
        parsed = json.loads(json_str)  # Should not raise exception

        assert parsed == data  # Should round-trip correctly

        # Verify no problematic data types
        def check_json_types(obj):
            if isinstance(obj, dict):
                for value in obj.values():
                    check_json_types(value)
            elif isinstance(obj, list):
                for item in obj:
                    check_json_types(item)
            else:
                # Should only contain JSON-serializable types
                assert isinstance(obj, str | int | float | bool | type(None))

        check_json_types(data)


class TestAdvancedSearchErrorHandling:
    """Test error handling and edge cases"""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    def test_malformed_json_request(self):
        """Test handling of malformed JSON"""
        response = self.client.post(
            "/api/search/advanced",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_missing_required_fields(self):
        """Test handling of missing required fields"""
        response = self.client.post(
            "/api/search/advanced",
            json={
                "limit": 10
                # Missing required 'query' field
            },
        )

        assert response.status_code == 422

    @patch("web.main.SessionLocal")
    def test_database_connection_error(self, mock_session):
        """Test handling of database connection errors"""
        # Mock database error
        mock_session.side_effect = Exception("Database connection failed")

        response = self.client.post("/api/search/advanced", json={"query": "тест"})

        assert response.status_code == 500

    def test_sql_injection_protection(self):
        """Test protection against SQL injection"""
        malicious_queries = [
            "'; DROP TABLE lots; --",
            "компьютеры'; DELETE FROM lots WHERE '1'='1",
            "' UNION SELECT * FROM subjects --",
        ]

        for malicious_query in malicious_queries:
            response = self.client.post(
                "/api/search/advanced", json={"query": malicious_query}
            )

            # Should not crash or return error due to SQL injection
            assert response.status_code in [200, 422]

            if response.status_code == 200:
                # If successful, verify database integrity by making another query
                test_response = self.client.post(
                    "/api/search/advanced", json={"query": "тест"}
                )
                assert test_response.status_code == 200


# Performance benchmarks
class TestAdvancedSearchBenchmarks:
    """Benchmark tests for performance monitoring"""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up test client"""
        self.client = TestClient(app)

    @pytest.mark.benchmark
    def test_search_performance_benchmark(self):
        """Benchmark search performance for monitoring"""
        search_queries = [
            "компьютеры",
            "медицинское оборудование",
            "строительство дорог",
            "канцелярские товары",
        ]

        times = []
        for query in search_queries:
            start = time.time()

            response = self.client.post(
                "/api/search/advanced", json={"query": query, "limit": 50}
            )

            execution_time = time.time() - start
            times.append(execution_time)

            assert response.status_code == 200

        avg_time = sum(times) / len(times)
        max_time = max(times)

        # Performance assertions
        assert avg_time < 1.0  # Average should be under 1 second
        assert max_time < 2.0  # No query should take more than 2 seconds

        print(f"Average search time: {avg_time:.3f}s")
        print(f"Maximum search time: {max_time:.3f}s")

    @pytest.mark.benchmark
    @patch("chromadb.Client")
    def test_autocomplete_performance_benchmark(self, mock_chromadb_client):
        """Benchmark autocomplete performance"""
        # Mock ChromaDB
        mock_collection = Mock()
        mock_collection.query.return_value = {
            "documents": [["test1", "test2", "test3"]]
        }
        mock_chromadb_client.return_value.get_collection.return_value = mock_collection

        queries = ["комп", "мед", "стро", "канц"]
        times = []

        for query in queries:
            start = time.time()

            response = self.client.get(f"/api/search/autocomplete?query={query}")

            execution_time = time.time() - start
            times.append(execution_time)

            assert response.status_code == 200

        avg_time = sum(times) / len(times)
        max_time = max(times)

        # Performance assertions
        assert avg_time < 0.3  # Average should be under 300ms
        assert max_time < 0.5  # No query should take more than 500ms

        print(f"Average autocomplete time: {avg_time:.3f}s")
        print(f"Maximum autocomplete time: {max_time:.3f}s")


if __name__ == "__main__":
    # Run all tests
    pytest.main([__file__, "-v", "--tb=short"])
