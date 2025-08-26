import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app

client = TestClient(app)


def test_tldr_validation_invalid_lot_id():
    response = client.post(
        "/tldr", json={"lot_id": 0}, headers={"X-API-Key": "changeme"}
    )
    assert response.status_code == 422


def test_render_validation_invalid_template():
    response = client.post(
        "/letters/generate",
        json={"template": "invalid/template", "context": {"test": "value"}},
        headers={"X-API-Key": "changeme"},
    )
    assert response.status_code == 422


def test_render_validation_long_string():
    response = client.post(
        "/letters/generate",
        json={"template": "letters/guarantee", "context": {"long_field": "x" * 501}},
        headers={"X-API-Key": "changeme"},
    )
    assert response.status_code == 422


def test_render_validation_large_list():
    response = client.post(
        "/letters/generate",
        json={"template": "letters/guarantee", "context": {"items": ["item"] * 51}},
        headers={"X-API-Key": "changeme"},
    )
    assert response.status_code == 422


def test_audit_log_created():
    """Test that audit log is created after a valid request"""
    from main import get_conn

    # Count before
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM audit_logs WHERE service = 'doc-service'")
            count_before = cur.fetchone()[0]

    # Make a request
    client.post("/tldr", json={"lot_id": 999}, headers={"X-API-Key": "changeme"})

    # Count after
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM audit_logs WHERE service = 'doc-service'")
            count_after = cur.fetchone()[0]

    assert count_after == count_before + 1
