import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app

client = TestClient(app)


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
