from fastapi.testclient import TestClient

from services.embedding_api.main import app

client = TestClient(app)


def test_index_validation_long_ref_id():
    response = client.post("/index", json={"ref_id": "x" * 129, "text": "test text"})
    assert response.status_code == 422


def test_index_validation_long_text():
    response = client.post("/index", json={"ref_id": "test", "text": "x" * 8001})
    assert response.status_code == 413


def test_search_validation_long_query():
    response = client.post("/search", json={"query": "x" * 2001})
    assert response.status_code == 422


def test_search_validation_invalid_top_k():
    response = client.post("/search", json={"query": "test", "top_k": 25})
    assert response.status_code == 422


def test_audit_log_created():
    """Test that audit log is created after a request"""
    from services.embedding_api.main import get_conn

    # Count before
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE service = 'embedding-api'"
            )
            count_before = cur.fetchone()[0]

    # Make a request
    response = client.post("/embed", json={"text": "test text"})
    assert response.status_code == 200

    # Count after
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE service = 'embedding-api'"
            )
            count_after = cur.fetchone()[0]

    assert count_after == count_before + 1
