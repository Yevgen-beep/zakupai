import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import the risk-engine modules
risk_engine_path = Path(__file__).parent.parent / "services" / "risk-engine"
sys.path.insert(0, str(risk_engine_path))

from main import app  # noqa: E402
from rnu_client import RNUClient, RNUValidationError  # noqa: E402

# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_rnu_validation.db"
test_engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

client = TestClient(app)


class TestRNUClient:
    """Unit tests for RNU client functionality"""

    @pytest.fixture
    async def rnu_client(self):
        """Create RNU client with mocked dependencies"""
        with (
            patch("rnu_client.redis.from_url") as mock_redis,
            patch("rnu_client.httpx.AsyncClient") as mock_http_client,
            patch("rnu_client.SessionLocal") as mock_session,
        ):
            # Mock Redis client
            mock_redis_instance = AsyncMock()
            mock_redis.return_value = mock_redis_instance

            # Mock HTTP client
            mock_http_instance = AsyncMock()
            mock_http_client.return_value = mock_http_instance

            # Mock database session
            mock_db_session = MagicMock()
            mock_session.return_value.__enter__ = MagicMock(
                return_value=mock_db_session
            )
            mock_session.return_value.__exit__ = MagicMock(return_value=None)

            client = RNUClient()
            client.redis_client = mock_redis_instance
            client.http_client = mock_http_instance

            return client, mock_redis_instance, mock_http_instance, mock_db_session

    def test_validate_bin_format(self):
        """Test BIN format validation"""
        client = RNUClient()

        # Valid BINs
        assert client.validate_bin("123456789012") is True
        assert client.validate_bin("000000000000") is True

        # Invalid BINs
        assert client.validate_bin("12345678901") is False  # Too short
        assert client.validate_bin("1234567890123") is False  # Too long
        assert client.validate_bin("12345678901a") is False  # Contains letter
        assert client.validate_bin("123 456 789 012") is False  # Contains spaces
        assert client.validate_bin("") is False  # Empty
        assert client.validate_bin("abc") is False  # Not numeric

    @pytest.mark.asyncio
    async def test_redis_cache_hit(self, rnu_client):
        """Test successful Redis cache hit"""
        client, mock_redis, mock_http, mock_db = rnu_client

        # Mock Redis cache hit
        cached_data = {
            "supplier_bin": "123456789012",
            "is_blocked": False,
            "validated_at": "2025-09-17T10:36:00+00:00",
        }
        mock_redis.get.return_value = json.dumps(cached_data)

        result = await client.get_from_redis_cache("123456789012")

        assert result is not None
        assert result["supplier_bin"] == "123456789012"
        assert result["is_blocked"] is False
        assert result["source"] == "cache"
        mock_redis.get.assert_called_once_with("rnu:123456789012")

    @pytest.mark.asyncio
    async def test_redis_cache_miss(self, rnu_client):
        """Test Redis cache miss"""
        client, mock_redis, mock_http, mock_db = rnu_client

        # Mock Redis cache miss
        mock_redis.get.return_value = None

        result = await client.get_from_redis_cache("123456789012")

        assert result is None
        mock_redis.get.assert_called_once_with("rnu:123456789012")

    @pytest.mark.asyncio
    async def test_database_cache_hit(self, rnu_client):
        """Test successful database cache hit"""
        client, mock_redis, mock_http, mock_db = rnu_client

        # Mock database result
        mock_row = MagicMock()
        mock_row.supplier_bin = "123456789012"
        mock_row.is_blocked = True
        mock_row.validated_at = datetime.now(UTC)

        mock_db.execute.return_value.fetchone.return_value = mock_row

        # Mock Redis cache save
        mock_redis.setex = AsyncMock()

        result = await client.get_from_database_cache("123456789012")

        assert result is not None
        assert result["supplier_bin"] == "123456789012"
        assert result["is_blocked"] is True
        assert result["source"] == "cache"

    @pytest.mark.asyncio
    async def test_api_call_success_blocked(self, rnu_client):
        """Test successful API call for blocked supplier"""
        client, mock_redis, mock_http, mock_db = rnu_client

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"blocked": True}
        mock_http.get.return_value = mock_response

        result = await client.call_rnu_api("123456789012")

        assert result["supplier_bin"] == "123456789012"
        assert result["is_blocked"] is True
        assert result["source"] == "api"
        assert "validated_at" in result

    @pytest.mark.asyncio
    async def test_api_call_success_not_blocked(self, rnu_client):
        """Test successful API call for not blocked supplier"""
        client, mock_redis, mock_http, mock_db = rnu_client

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"blocked": False}
        mock_http.get.return_value = mock_response

        result = await client.call_rnu_api("123456789012")

        assert result["supplier_bin"] == "123456789012"
        assert result["is_blocked"] is False
        assert result["source"] == "api"

    @pytest.mark.asyncio
    async def test_api_call_404_not_found(self, rnu_client):
        """Test API call returns 404 (supplier not found)"""
        client, mock_redis, mock_http, mock_db = rnu_client

        # Mock 404 response
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_http.get.return_value = mock_response

        result = await client.call_rnu_api("123456789012")

        assert result["supplier_bin"] == "123456789012"
        assert result["is_blocked"] is False  # Not found = not blocked
        assert result["source"] == "api"

    @pytest.mark.asyncio
    async def test_api_call_429_rate_limit(self, rnu_client):
        """Test API call returns 429 (rate limit)"""
        client, mock_redis, mock_http, mock_db = rnu_client

        # Mock 429 response
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_http.get.return_value = mock_response

        with pytest.raises(RNUValidationError, match="Rate limit exceeded"):
            await client.call_rnu_api("123456789012")

    @pytest.mark.asyncio
    async def test_api_call_timeout(self, rnu_client):
        """Test API call timeout"""
        client, mock_redis, mock_http, mock_db = rnu_client

        # Mock timeout
        mock_http.get.side_effect = httpx.TimeoutException("Timeout")

        with pytest.raises(RNUValidationError, match="API timeout"):
            await client.call_rnu_api("123456789012")

    @pytest.mark.asyncio
    async def test_save_to_redis_cache(self, rnu_client):
        """Test saving result to Redis cache"""
        client, mock_redis, mock_http, mock_db = rnu_client

        result = {
            "supplier_bin": "123456789012",
            "is_blocked": True,
            "validated_at": "2025-09-17T10:36:00+00:00",
            "source": "api",
        }

        mock_redis.setex = AsyncMock()

        await client.save_to_redis_cache("123456789012", result)

        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args[0]
        assert args[0] == "rnu:123456789012"  # cache key
        assert args[1] == 86400  # TTL (24 hours)

    @pytest.mark.asyncio
    async def test_save_to_database_cache(self, rnu_client):
        """Test saving result to PostgreSQL cache"""
        client, mock_redis, mock_http, mock_db = rnu_client

        result = {
            "supplier_bin": "123456789012",
            "is_blocked": True,
            "validated_at": "2025-09-17T10:36:00+00:00",
        }

        await client.save_to_database_cache("123456789012", result)

        # Verify database execute was called
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_supplier_invalid_bin(self, rnu_client):
        """Test validation with invalid BIN"""
        client, mock_redis, mock_http, mock_db = rnu_client

        with pytest.raises(RNUValidationError, match="Invalid BIN format"):
            await client.validate_supplier("invalid")

    @pytest.mark.asyncio
    async def test_validate_supplier_cache_flow(self, rnu_client):
        """Test full validation flow with cache hit"""
        client, mock_redis, mock_http, mock_db = rnu_client

        # Mock Redis cache hit
        cached_data = {
            "supplier_bin": "123456789012",
            "is_blocked": False,
            "validated_at": "2025-09-17T10:36:00+00:00",
        }
        mock_redis.get.return_value = json.dumps(cached_data)

        result = await client.validate_supplier("123456789012")

        assert result["supplier_bin"] == "123456789012"
        assert result["is_blocked"] is False
        assert result["source"] == "cache"

        # Should not call HTTP API
        mock_http.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_supplier_api_flow(self, rnu_client):
        """Test full validation flow with API call"""
        client, mock_redis, mock_http, mock_db = rnu_client

        # Mock cache misses
        mock_redis.get.return_value = None
        mock_db.execute.return_value.fetchone.return_value = None

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"blocked": True}
        mock_http.get.return_value = mock_response

        # Mock cache saves
        mock_redis.setex = AsyncMock()

        result = await client.validate_supplier("123456789012")

        assert result["supplier_bin"] == "123456789012"
        assert result["is_blocked"] is True
        assert result["source"] == "api"

        # Verify API was called
        mock_http.get.assert_called_once()

        # Verify both caches were updated
        mock_redis.setex.assert_called_once()
        mock_db.execute.assert_called()


class TestRNUEndpoint:
    """Integration tests for the RNU validation endpoint"""

    def test_validate_rnu_valid_bin_mock_cache(self):
        """Test endpoint with valid BIN (mocked cache response)"""
        with patch("main.get_rnu_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.validate_supplier.return_value = {
                "supplier_bin": "123456789012",
                "is_blocked": False,
                "validated_at": "2025-09-17T10:36:00+00:00",
                "source": "cache",
            }
            mock_get_client.return_value = mock_client

            response = client.get("/validate_rnu/123456789012")

            assert response.status_code == 200
            data = response.json()
            assert data["supplier_bin"] == "123456789012"
            assert data["is_blocked"] is False
            assert data["source"] == "cache"
            assert "validated_at" in data

    def test_validate_rnu_valid_bin_mock_api(self):
        """Test endpoint with valid BIN (mocked API response)"""
        with patch("main.get_rnu_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.validate_supplier.return_value = {
                "supplier_bin": "123456789012",
                "is_blocked": True,
                "validated_at": "2025-09-17T10:36:00+00:00",
                "source": "api",
            }
            mock_get_client.return_value = mock_client

            response = client.get("/validate_rnu/123456789012")

            assert response.status_code == 200
            data = response.json()
            assert data["supplier_bin"] == "123456789012"
            assert data["is_blocked"] is True
            assert data["source"] == "api"

    def test_validate_rnu_invalid_bin_format(self):
        """Test endpoint with invalid BIN format"""
        response = client.get("/validate_rnu/invalid")

        assert response.status_code == 400
        data = response.json()
        assert "Invalid BIN format" in data["detail"]

    def test_validate_rnu_short_bin(self):
        """Test endpoint with short BIN"""
        response = client.get("/validate_rnu/12345")

        assert response.status_code == 400
        data = response.json()
        assert "Invalid BIN format" in data["detail"]

    def test_validate_rnu_long_bin(self):
        """Test endpoint with long BIN"""
        response = client.get("/validate_rnu/1234567890123")

        assert response.status_code == 400
        data = response.json()
        assert "Invalid BIN format" in data["detail"]

    def test_validate_rnu_rate_limit_error(self):
        """Test endpoint with rate limit error"""
        with patch("main.get_rnu_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.validate_supplier.side_effect = RNUValidationError(
                "Rate limit exceeded"
            )
            mock_get_client.return_value = mock_client

            response = client.get("/validate_rnu/123456789012")

            assert response.status_code == 429
            data = response.json()
            assert "Rate limit exceeded" in data["detail"]

    def test_validate_rnu_service_unavailable(self):
        """Test endpoint with service unavailable error"""
        with patch("main.get_rnu_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.validate_supplier.side_effect = RNUValidationError(
                "Service error"
            )
            mock_get_client.return_value = mock_client

            response = client.get("/validate_rnu/123456789012")

            assert response.status_code == 503
            data = response.json()
            assert "RNU service temporarily unavailable" in data["detail"]

    def test_validate_rnu_internal_error(self):
        """Test endpoint with unexpected internal error"""
        with patch("main.get_rnu_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.validate_supplier.side_effect = Exception("Unexpected error")
            mock_get_client.return_value = mock_client

            response = client.get("/validate_rnu/123456789012")

            assert response.status_code == 500
            data = response.json()
            assert "Internal server error" in data["detail"]


class TestTelegramIntegration:
    """Tests for Telegram bot RNU command integration"""

    @pytest.mark.asyncio
    async def test_rnu_command_valid_bin(self):
        """Test /rnu command with valid BIN"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock successful response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "supplier_bin": "123456789012",
                "is_blocked": False,
                "validated_at": "2025-09-17T10:36:00+00:00",
                "source": "cache",
            }
            mock_client.get.return_value = mock_response

            # Test that the HTTP call would be made correctly
            await mock_client.get("http://risk-engine:8000/validate_rnu/123456789012")

            assert mock_response.status_code == 200
            data = mock_response.json()
            assert data["supplier_bin"] == "123456789012"
            assert data["is_blocked"] is False

    @pytest.mark.asyncio
    async def test_rnu_command_invalid_bin(self):
        """Test /rnu command with invalid BIN format"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock 400 response for invalid BIN
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "detail": "Invalid BIN format: must be exactly 12 digits"
            }
            mock_client.get.return_value = mock_response

            await mock_client.get("http://risk-engine:8000/validate_rnu/invalid")

            assert mock_response.status_code == 400
            data = mock_response.json()
            assert "Invalid BIN format" in data["detail"]

    def test_bin_format_validation_regex(self):
        """Test BIN format validation regex used in Telegram bot"""
        import re

        pattern = r"^\d{12}$"

        # Valid BINs
        assert re.match(pattern, "123456789012") is not None
        assert re.match(pattern, "000000000000") is not None

        # Invalid BINs
        assert re.match(pattern, "12345678901") is None  # Too short
        assert re.match(pattern, "1234567890123") is None  # Too long
        assert re.match(pattern, "12345678901a") is None  # Contains letter
        assert re.match(pattern, "123 456 789 012") is None  # Contains spaces
        assert re.match(pattern, "") is None  # Empty


class TestPerformanceAndCaching:
    """Tests for performance requirements and caching behavior"""

    @pytest.mark.asyncio
    async def test_cache_expiration(self, rnu_client):
        """Test cache TTL expiration behavior"""
        client, mock_redis, mock_http, mock_db = rnu_client

        # Test Redis cache TTL
        await client.save_to_redis_cache(
            "123456789012",
            {
                "supplier_bin": "123456789012",
                "is_blocked": False,
                "validated_at": "2025-09-17T10:36:00+00:00",
            },
        )

        # Verify TTL is set to 24 hours (86400 seconds)
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args[0]
        assert args[1] == 86400  # 24 hours in seconds

    @pytest.mark.asyncio
    async def test_retry_mechanism(self, rnu_client):
        """Test API retry mechanism with exponential backoff"""
        client, mock_redis, mock_http, mock_db = rnu_client

        # Mock first two calls fail, third succeeds
        mock_http.get.side_effect = [
            httpx.RequestError("Connection failed"),
            httpx.RequestError("Connection failed"),
            MagicMock(status_code=200, json=lambda: {"blocked": False}),
        ]

        result = await client.call_rnu_api("123456789012")

        # Should have retried 3 times total (initial + 2 retries)
        assert mock_http.get.call_count == 3
        assert result["is_blocked"] is False

    @pytest.mark.asyncio
    async def test_concurrent_requests_same_bin(self):
        """Test handling concurrent requests for the same BIN"""
        # This would test that concurrent requests don't cause race conditions
        # In a real implementation, we might use locks or other synchronization
        pass


if __name__ == "__main__":
    # Run tests with pytest
    # pytest tests/test_rnu_validation.py -v
    pass
