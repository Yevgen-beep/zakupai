from datetime import date

from fastapi.testclient import TestClient
from main import _compute_flags, _score, app


def test_short_deadline_flag():
    """Unit test for short deadline heuristic"""
    lot = {"deadline": date.today()}  # today's deadline
    market_sum = None

    flags = _compute_flags(lot, market_sum)

    assert flags["days_left"] == 0
    assert flags["short_deadline"] is True  # 0 <= 3 days threshold


def test_score_calculation():
    """Unit test for risk score calculation"""
    flags = {"short_deadline": True, "over_market": False, "no_plan_id": True}

    score = _score(flags)

    # Score should be > 0 since we have short_deadline and no_plan_id flags
    assert score > 0
    assert 0 <= score <= 100


def test_health_endpoint():
    """API test for /health endpoint"""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "risk-engine"}
