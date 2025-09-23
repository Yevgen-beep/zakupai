import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app

client = TestClient(app)


def test_score_validation_invalid_lot_id():
    response = client.post("/risk/score", json={"lot_id": 0})
    assert response.status_code == 422, "Expected 422 status for invalid lot_id 0"


def test_score_validation_negative_lot_id():
    response = client.post("/risk/score", json={"lot_id": -1})
    assert response.status_code == 422, "Expected 422 status for negative lot_id"


def test_score_not_found():
    """Test 404 for non-existent lot"""
    response = client.post("/risk/score", json={"lot_id": 999999})
    assert response.status_code == 404, "Expected 404 status for non-existent lot"


def test_audit_log_created():
    """Test that audit log is created after a request"""
    from main import _get_conn_and_host

    # Count before
    conn, _ = _get_conn_and_host()
    with conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM audit_logs WHERE service = 'risk-engine'")
        count_before = cur.fetchone()[0]

    # Make a request (will result in 404 but still logged)
    client.post("/risk/score", json={"lot_id": 999999})

    # Count after
    with conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM audit_logs WHERE service = 'risk-engine'")
        count_after = cur.fetchone()[0]

    assert (
        count_after == count_before + 1
    ), f"Expected audit log count to increase by 1, got {count_after} vs {count_before}"
