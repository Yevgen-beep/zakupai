from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# Mock database connection for tests
@patch("main.get_conn")
class TestBillingService:
    def test_health_check(self, mock_get_conn):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "service": "billing"}

    def test_create_key_new_user(self, mock_get_conn):
        """Test creating API key for new user"""
        # Mock database responses
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda x: mock_cursor
        mock_conn.cursor.return_value.__exit__ = lambda x, y, z, w: None
        mock_get_conn.return_value = mock_conn

        # Mock user creation (user doesn't exist, then create)
        mock_cursor.fetchone.side_effect = [
            None,  # User doesn't exist
            (1, "free", "active"),  # Created user
            ("test-api-key-uuid",),  # Created API key
        ]

        response = client.post(
            "/billing/create_key",
            json={"tg_id": 123456789, "email": "test@example.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["api_key"] == "test-api-key-uuid"
        assert data["plan"] == "free"
        assert data["expires_at"] is None

    def test_create_key_existing_user(self, mock_get_conn):
        """Test creating API key for existing user"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda x: mock_cursor
        mock_conn.cursor.return_value.__exit__ = lambda x, y, z, w: None
        mock_get_conn.return_value = mock_conn

        # Mock existing user
        mock_cursor.fetchone.side_effect = [
            (1, "premium", "active"),  # Existing user
            ("test-api-key-uuid",),  # Created API key
        ]

        response = client.post("/billing/create_key", json={"tg_id": 123456789})

        assert response.status_code == 200
        data = response.json()
        assert data["plan"] == "premium"

    def test_validate_key_valid(self, mock_get_conn):
        """Test validating valid API key"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda x: mock_cursor
        mock_conn.cursor.return_value.__exit__ = lambda x, y, z, w: None
        mock_get_conn.return_value = mock_conn

        # Mock valid key with low usage
        mock_cursor.fetchone.side_effect = [
            (1, 1, "active", None, "free", "active"),  # Valid key info
            10,  # Daily usage
            2,  # Hourly usage
        ]

        response = client.post(
            "/billing/validate_key",
            json={"api_key": "valid-key", "endpoint": "/calc/margin"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["plan"] == "free"
        assert data["remaining_requests"] == 89  # 100 - 10 - 1

    def test_validate_key_daily_limit_exceeded(self, mock_get_conn):
        """Test validating API key with daily limit exceeded"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda x: mock_cursor
        mock_conn.cursor.return_value.__exit__ = lambda x, y, z, w: None
        mock_get_conn.return_value = mock_conn

        # Mock key with high daily usage
        mock_cursor.fetchone.side_effect = [
            (1, 1, "active", None, "free", "active"),  # Valid key info
            100,  # Daily usage at limit
        ]

        response = client.post(
            "/billing/validate_key",
            json={"api_key": "limited-key", "endpoint": "/calc/margin"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "Daily limit exceeded" in data["message"]
        assert data["plan"] == "free"

    def test_validate_key_invalid(self, mock_get_conn):
        """Test validating invalid API key"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda x: mock_cursor
        mock_conn.cursor.return_value.__exit__ = lambda x, y, z, w: None
        mock_get_conn.return_value = mock_conn

        # Mock invalid key (not found)
        mock_cursor.fetchone.return_value = None

        response = client.post(
            "/billing/validate_key",
            json={"api_key": "invalid-key", "endpoint": "/calc/margin"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["message"] == "Invalid API key"

    def test_log_usage(self, mock_get_conn):
        """Test logging usage"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda x: mock_cursor
        mock_conn.cursor.return_value.__exit__ = lambda x, y, z, w: None
        mock_get_conn.return_value = mock_conn

        # Mock successful key lookup
        mock_cursor.fetchone.return_value = (1,)  # API key ID

        response = client.post(
            "/billing/usage",
            json={"api_key": "valid-key", "endpoint": "/calc/margin", "requests": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["logged"] is True

    def test_log_usage_invalid_key(self, mock_get_conn):
        """Test logging usage with invalid key"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda x: mock_cursor
        mock_conn.cursor.return_value.__exit__ = lambda x, y, z, w: None
        mock_get_conn.return_value = mock_conn

        # Mock key not found
        mock_cursor.fetchone.return_value = None

        response = client.post(
            "/billing/usage",
            json={"api_key": "invalid-key", "endpoint": "/calc/margin", "requests": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["logged"] is False


def test_create_key_validation():
    """Test request validation for create_key"""
    response = client.post("/billing/create_key", json={"tg_id": "not_a_number"})
    assert response.status_code == 422


def test_validate_key_validation():
    """Test request validation for validate_key"""
    response = client.post(
        "/billing/validate_key",
        json={
            "api_key": "valid-key"
            # Missing endpoint
        },
    )
    assert response.status_code == 422


def test_usage_validation():
    """Test request validation for usage logging"""
    response = client.post(
        "/billing/usage",
        json={
            "api_key": "valid-key",
            "endpoint": "/calc/margin",
            "requests": -1,  # Invalid negative requests
        },
    )
    # Should still process, but with default value
    assert response.status_code in [200, 422]
