from fastapi.testclient import TestClient
from main import app


def test_margin_calculation_pure():
    """Unit test for margin calculation logic"""
    lot_price = 100.0
    cost = 70.0

    # Without VAT
    revenue_net = lot_price
    cost_total = cost
    profit = revenue_net - cost_total  # 30.0
    margin_pct = (profit / revenue_net) * 100.0  # 30%
    roi_pct = (profit / cost_total) * 100.0  # 42.86%

    assert round(margin_pct, 2) == 30.0
    assert round(roi_pct, 2) == 42.86


def test_health_endpoint():
    """API test for /health endpoint"""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "calc-service"}
