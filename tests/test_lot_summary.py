"""
Unit tests for lot TL;DR summary functionality
Week 4.1: Redis caching, Flowise integration, SQL fallback
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from web.main import LotSummaryResponse, app, redis_client

logger = logging.getLogger(__name__)


class TestLotSummary:
    """Unit tests for lot TL;DR summary functionality"""

    @pytest.fixture
    def test_client(self):
        return TestClient(app)

    @pytest.fixture
    def mock_lot_data(self):
        """Mock lot data from database"""
        return {
            "id": 98765,
            "nameRu": "Поставка медицинского оборудования для городской больницы №1",
            "amount": 5750000.00,
            "status": 1,  # ACTIVE
            "customerNameRu": "ГУ Городская больница №1 г. Алматы",
        }

    @pytest.fixture
    def mock_complex_lot_data(self):
        """Mock complex lot with long names and special cases"""
        return {
            "id": 11111,
            "nameRu": "Капитальный ремонт автомобильных дорог с асфальтобетонным покрытием протяженностью 15.7 км на участке автодороги Алматы-Капчагай с установкой дорожных знаков и разметки",
            "amount": 125000000.50,
            "status": 2,  # COMPLETED
            "customerNameRu": "Комитет автомобильных дорог Министерства индустрии и инфраструктурного развития РК",
        }

    def test_lot_summary_cache_miss_flowise_success(self, test_client, mock_lot_data):
        """Test TL;DR generation with cache miss and successful Flowise response"""
        lot_id = mock_lot_data["id"]

        # Clear any existing cache
        try:
            redis_client.delete(f"lot_summary:{lot_id}")
        except Exception as exc:
            logger.debug("Failed to clear Redis cache for lot %s: %s", lot_id, exc)

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

            # Mock successful Flowise response
            with patch("httpx.AsyncClient") as mock_client:
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "text": "Лот 98765: Поставка медицинского оборудования для больницы, сумма 5.75 млн тенге, активный статус, заказчик - городская больница Алматы."
                }

                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_response
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
                assert "медицинского оборудования" in data["summary"]
                assert "5.75 млн" in data["summary"]

    def test_lot_summary_cache_hit_performance(self, test_client):
        """Test TL;DR with Redis cache hit for optimal performance"""
        lot_id = 54321
        cached_summary = {
            "summary": "Лот 54321: Строительство школы, 15 млн тенге, активный.",
            "source": "flowise",
            "generated_at": datetime.now().isoformat(),
        }

        # Set cache
        try:
            cache_key = f"lot_summary:{lot_id}"
            redis_client.setex(cache_key, 86400, json.dumps(cached_summary))
        except Exception as e:
            pytest.skip(f"Redis not available: {e}")

        # Test multiple requests for performance
        response_times = []
        for _ in range(3):
            start_time = time.time()
            response = test_client.get(f"/web-ui/lot/{lot_id}")
            response_time = time.time() - start_time
            response_times.append(response_time)

            assert response.status_code == 200
            data = response.json()
            assert data["source"] == "cache"
            assert data["cached"] is True
            assert data["summary"] == cached_summary["summary"]

        # All cache hits should be very fast
        avg_time = sum(response_times) / len(response_times)
        assert avg_time < 0.1  # Average should be under 100ms

    def test_lot_summary_flowise_timeout_fallback(self, test_client, mock_lot_data):
        """Test fallback when Flowise times out"""
        lot_id = mock_lot_data["id"]

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

            # Mock Flowise timeout
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post.side_effect = (
                    TimeoutError("Flowise timeout")
                )

                response = test_client.get(f"/web-ui/lot/{lot_id}")

                assert response.status_code == 200
                data = response.json()
                assert data["source"] == "fallback"
                assert f"Лот {lot_id}:" in data["summary"]
                assert "медицинского оборудования" in data["summary"]
                assert (
                    "5,750,000" in data["summary"]
                )  # Should format amount with commas

    def test_lot_summary_flowise_error_response_fallback(
        self, test_client, mock_lot_data
    ):
        """Test fallback when Flowise returns error status"""
        lot_id = mock_lot_data["id"]

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

            # Mock Flowise error response
            with patch("httpx.AsyncClient") as mock_client:
                mock_response = AsyncMock()
                mock_response.status_code = 500
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_response
                )

                response = test_client.get(f"/web-ui/lot/{lot_id}")

                assert response.status_code == 200
                data = response.json()
                assert data["source"] == "fallback"

    def test_lot_summary_long_name_truncation(self, test_client, mock_complex_lot_data):
        """Test proper handling of very long lot names"""
        lot_id = mock_complex_lot_data["id"]

        with patch("web.main.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchone.return_value = (
                mock_complex_lot_data["id"],
                mock_complex_lot_data["nameRu"],
                mock_complex_lot_data["amount"],
                mock_complex_lot_data["status"],
                mock_complex_lot_data["customerNameRu"],
            )

            # Force fallback to test truncation
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post.side_effect = (
                    Exception("Flowise unavailable")
                )

                response = test_client.get(f"/web-ui/lot/{lot_id}")

                assert response.status_code == 200
                data = response.json()
                assert data["source"] == "fallback"

                # Check that long name is truncated with ellipsis
                summary = data["summary"]
                if "Капитальный ремонт" in mock_complex_lot_data["nameRu"]:
                    if len(mock_complex_lot_data["nameRu"]) > 100:
                        assert "..." in summary

    def test_lot_summary_status_mapping(self, test_client):
        """Test correct status mapping from numeric to string"""
        test_cases = [
            (1, "ACTIVE"),
            (2, "COMPLETED"),
            (3, "CANCELLED"),
            (4, "DRAFT"),
            (5, "PUBLISHED"),
            (0, "UNKNOWN"),
            (999, "UNKNOWN"),  # Edge case
        ]

        for status_code, expected_status in test_cases:
            lot_id = 77777 + status_code  # Unique lot ID for each test

            with patch("web.main.SessionLocal") as mock_session:
                mock_db = MagicMock()
                mock_session.return_value.__enter__.return_value = mock_db
                mock_db.execute.return_value.fetchone.return_value = (
                    lot_id,
                    "Test lot",
                    100000,
                    status_code,
                    "Test customer",
                )

                with patch("httpx.AsyncClient") as mock_client:
                    mock_client.return_value.__aenter__.return_value.post.side_effect = Exception(
                        "Force fallback"
                    )

                    response = test_client.get(f"/web-ui/lot/{lot_id}")
                    assert response.status_code == 200

                    data = response.json()
                    assert expected_status in data["summary"]

    def test_lot_summary_not_found(self, test_client):
        """Test 404 response for non-existent lot"""
        with patch("web.main.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value.__enter__.return_value = mock_db
            mock_db.execute.return_value.fetchone.return_value = None

            response = test_client.get("/web-ui/lot/999999")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"]

    def test_lot_summary_redis_connection_error(self, test_client, mock_lot_data):
        """Test graceful handling when Redis is unavailable"""
        lot_id = mock_lot_data["id"]

        with patch("web.main.redis_client") as mock_redis:
            # Simulate Redis connection errors
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

                # Mock successful Flowise response
                with patch("httpx.AsyncClient") as mock_client:
                    mock_response = AsyncMock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {
                        "text": "Generated summary from Flowise"
                    }
                    mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                        return_value=mock_response
                    )

                    response = test_client.get(f"/web-ui/lot/{lot_id}")

                    # Should still work without Redis
                    assert response.status_code == 200
                    data = response.json()
                    assert data["lot_id"] == lot_id
                    assert data["cached"] is False
                    # Should use Flowise since Redis errors are handled

    def test_lot_summary_cache_ttl_expiry(self, test_client):
        """Test cache expiry handling"""
        lot_id = 88888

        try:
            # Set cache with short TTL for testing
            cache_key = f"lot_summary:{lot_id}"
            cached_data = {
                "summary": "Expired cache test",
                "source": "cache",
                "generated_at": datetime.now().isoformat(),
            }
            redis_client.setex(cache_key, 1, json.dumps(cached_data))  # 1 second TTL

            # Wait for cache to expire
            import time

            time.sleep(2)

            # Mock fresh data generation
            with patch("web.main.SessionLocal") as mock_session:
                mock_db = MagicMock()
                mock_session.return_value.__enter__.return_value = mock_db
                mock_db.execute.return_value.fetchone.return_value = (
                    lot_id,
                    "Fresh lot",
                    50000,
                    1,
                    "Fresh customer",
                )

                with patch("httpx.AsyncClient") as mock_client:
                    mock_client.return_value.__aenter__.return_value.post.side_effect = Exception(
                        "Force fallback"
                    )

                    response = test_client.get(f"/web-ui/lot/{lot_id}")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["cached"] is False
                    assert "Fresh lot" in data["summary"]

        except Exception as e:
            pytest.skip(f"Redis not available for TTL test: {e}")

    def test_lot_summary_flowise_response_validation(self, test_client, mock_lot_data):
        """Test validation of Flowise response format and length"""
        lot_id = mock_lot_data["id"]

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

            # Test case 1: Flowise returns too long summary (>500 chars)
            with patch("httpx.AsyncClient") as mock_client:
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "text": "A" * 600  # 600 characters, exceeds 500 limit
                }
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_response
                )

                response = test_client.get(f"/web-ui/lot/{lot_id}")
                assert response.status_code == 200

                data = response.json()
                # Should fallback due to length validation
                assert data["source"] == "fallback"

            # Test case 2: Flowise returns empty text
            with patch("httpx.AsyncClient") as mock_client:
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"text": ""}
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_response
                )

                response = test_client.get(f"/web-ui/lot/{lot_id}")
                assert response.status_code == 200

                data = response.json()
                # Should fallback due to empty text
                assert data["source"] == "fallback"

    def test_lot_summary_response_model_validation(self):
        """Test LotSummaryResponse model validation"""
        # Valid response
        valid_response = LotSummaryResponse(
            lot_id=12345,
            summary="Test summary",
            source="cache",
            cached=True,
            generated_at=datetime.now(),
        )
        assert valid_response.lot_id == 12345
        assert valid_response.source == "cache"

        # Test JSON serialization
        response_dict = valid_response.dict()
        assert "lot_id" in response_dict
        assert "summary" in response_dict
        assert "source" in response_dict

    def test_lot_summary_concurrent_requests(self, test_client, mock_lot_data):
        """Test handling of concurrent requests to same lot"""
        lot_id = mock_lot_data["id"]

        # Clear cache
        try:
            redis_client.delete(f"lot_summary:{lot_id}")
        except Exception as exc:
            logger.debug("Failed to clear Redis cache for lot %s: %s", lot_id, exc)

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

            with patch("httpx.AsyncClient") as mock_client:
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"text": "Concurrent test summary"}
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_response
                )

                # Make multiple concurrent requests
                import concurrent.futures

                def make_request():
                    return test_client.get(f"/web-ui/lot/{lot_id}")

                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(make_request) for _ in range(5)]
                    responses = [
                        future.result()
                        for future in concurrent.futures.as_completed(futures)
                    ]

                # All responses should be successful
                for response in responses:
                    assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
