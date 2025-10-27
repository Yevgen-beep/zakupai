import os
import sys
import time

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app

client = TestClient(app, raise_server_exceptions=False)


def test_vat_validation_negative_amount():
    response = client.post("/calc/vat", json={"amount": -100})
    assert response.status_code == 422, "Expected 422 status for negative amount"


def test_vat_validation_high_rate():
    response = client.post("/calc/vat", json={"amount": 100, "vat_rate": 25})
    assert response.status_code == 422, "Expected 422 status for invalid VAT rate"


def test_vat_validation_invalid_lot_id():
    response = client.post("/calc/vat", json={"amount": 100, "lot_id": 0})
    assert response.status_code == 422, "Expected 422 status for invalid lot_id"


def test_margin_validation_negative_cost():
    response = client.post(
        "/calc/margin", json={"lot_price": 100, "cost": -50, "logistics": 10}
    )
    assert response.status_code == 422, "Expected 422 status for negative cost"


def test_penalty_validation_high_rate():
    response = client.post(
        "/calc/penalty",
        json={"contract_sum": 1000, "days_overdue": 5, "daily_rate_pct": 10},
    )
    assert response.status_code == 422, "Expected 422 status for invalid penalty rate"


def test_audit_log_created():
    """Test that audit log is created after a valid request"""
    from main import get_conn

    # Count before
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE service = 'calc-service'"
            )
            count_before = cur.fetchone()[0]

    # Make a request
    response = client.post("/calc/vat", json={"amount": 100})
    assert response.status_code == 200, "Expected 200 status for valid VAT calculation"

    # Count after
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE service = 'calc-service'"
            )
            count_after = cur.fetchone()[0]

    assert (
        count_after == count_before + 1
    ), f"Expected audit log count to increase by 1, got {count_after} vs {count_before}"


# ========== Stage 7 Phase 1: Security Quick Wins Tests ==========


def test_profit_validation_invalid_lot_id():
    """Test 422 validation error for invalid lot_id in profit endpoint"""
    response = client.post("/calc/profit", json={"lot_id": "abc", "supplier_id": 1, "region": "Almaty"})
    assert response.status_code == 422, f"Expected 422 for invalid lot_id, got {response.status_code}"
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Validation error"


def test_profit_validation_negative_lot_id():
    """Test 422 validation error for negative lot_id"""
    response = client.post("/calc/profit", json={"lot_id": -1, "supplier_id": 1, "region": "Almaty"})
    assert response.status_code == 422, f"Expected 422 for negative lot_id, got {response.status_code}"


def test_profit_validation_zero_lot_id():
    """Test 422 validation error for zero lot_id"""
    response = client.post("/calc/profit", json={"lot_id": 0, "supplier_id": 1, "region": "Almaty"})
    assert response.status_code == 422, f"Expected 422 for zero lot_id, got {response.status_code}"


def test_profit_validation_invalid_region():
    """Test 422 validation error for too long region"""
    response = client.post("/calc/profit", json={
        "lot_id": 1,
        "supplier_id": 1,
        "region": "A" * 51  # Exceeds max_length=50
    })
    assert response.status_code == 422, f"Expected 422 for too long region, got {response.status_code}"


def test_risk_score_validation_invalid_bin():
    """Test 422 validation error for invalid BIN format"""
    response = client.post("/calc/risk-score", json={"supplier_bin": "123", "year": 2024})
    assert response.status_code == 422, f"Expected 422 for invalid BIN, got {response.status_code}"
    data = response.json()
    assert "detail" in data


def test_risk_score_validation_non_digit_bin():
    """Test 422 validation error for non-digit BIN"""
    response = client.post("/calc/risk-score", json={"supplier_bin": "12345678901A", "year": 2024})
    assert response.status_code == 422, f"Expected 422 for non-digit BIN, got {response.status_code}"


def test_risk_score_validation_invalid_year():
    """Test 422 validation error for year out of range"""
    response = client.post("/calc/risk-score", json={"supplier_bin": "123456789012", "year": 2040})
    assert response.status_code == 422, f"Expected 422 for year out of range, got {response.status_code}"


def test_payload_too_large():
    """Test 413 error for payload size > 2MB"""
    # Create a large payload (2.5 MB of data)
    large_region = "A" * (2 * 1024 * 1024 + 1000)  # > 2MB
    response = client.post(
        "/calc/profit",
        json={"lot_id": 1, "supplier_id": 1, "region": large_region},
        headers={"Content-Length": str(2 * 1024 * 1024 + 1000)}
    )
    assert response.status_code == 413, f"Expected 413 for large payload, got {response.status_code}"
    data = response.json()
    assert data["detail"] == "Payload Too Large"


def test_rate_limit_exceeded():
    """Test 429 error when rate limit is exceeded (30 requests/minute)"""
    # Make 31 rapid requests to trigger rate limit
    responses = []
    for i in range(35):
        response = client.post("/calc/profit", json={
            "lot_id": i + 1,
            "supplier_id": 1,
            "region": "Almaty"
        })
        responses.append(response)
        if response.status_code == 429:
            break

    # Check that we got at least one 429
    status_codes = [r.status_code for r in responses]
    assert 429 in status_codes, f"Expected at least one 429 status, got: {status_codes}"

    # Verify the 429 response content
    rate_limited = [r for r in responses if r.status_code == 429]
    assert len(rate_limited) > 0, "Should have at least one rate-limited response"
    data = rate_limited[0].json()
    assert "detail" in data
    assert data["detail"] == "Too Many Requests"


def test_profit_endpoint_success():
    """Test successful profit calculation with valid data"""
    response = client.post("/calc/profit", json={
        "lot_id": 123,
        "supplier_id": 456,
        "region": "Almaty"
    })
    assert response.status_code == 200, f"Expected 200 for valid request, got {response.status_code}"
    data = response.json()
    assert "profit" in data
    assert data["lot_id"] == 123
    assert data["supplier_id"] == 456
    assert data["region"] == "Almaty"


def test_risk_score_endpoint_success():
    """Test successful risk score calculation with valid data"""
    response = client.post("/calc/risk-score", json={
        "supplier_bin": "123456789012",
        "year": 2024
    })
    assert response.status_code == 200, f"Expected 200 for valid request, got {response.status_code}"
    data = response.json()
    assert "risk_score" in data
    assert "risk_level" in data
    assert data["supplier_bin"] == "123456789012"
    assert data["year"] == 2024
