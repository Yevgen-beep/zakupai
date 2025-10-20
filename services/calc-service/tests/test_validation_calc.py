import logging
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from starlette.requests import Request
import json
import pytest
import asyncio

from services.calc_service.main import app  # Исправлено

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@pytest.fixture(scope="function")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
def client():
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client

def test_vat_validation_negative_amount(client):
    logger.debug("Starting test_vat_validation_negative_amount")
    with patch('services.calc_service.main.save_audit_log') as mocked_save:
        response = client.post("/calc/vat", json={"amount": "-100.0"})
        logger.debug(f"Response received: status={response.status_code}, body={response.text}, url={response.request.url}")
        assert response.status_code == 422, f"Expected 422 status for negative amount, got {response.status_code}: {response.text}"
        mocked_save.assert_not_called()
    logger.debug("Finished test_vat_validation_negative_amount")

def test_vat_validation_high_rate(client):
    logger.debug("Starting test_vat_validation_high_rate")
    with patch('services.calc_service.main.save_audit_log') as mocked_save:
        response = client.post("/calc/vat", json={"amount": "100.0", "vat_rate": "25.0"})
        logger.debug(f"Response received: status={response.status_code}, body={response.text}, url={response.request.url}")
        assert response.status_code == 422, f"Expected 422 status for invalid VAT rate, got {response.status_code}: {response.text}"
        mocked_save.assert_not_called()
    logger.debug("Finished test_vat_validation_high_rate")

def test_vat_validation_invalid_lot_id(client):
    logger.debug("Starting test_vat_validation_invalid_lot_id")
    with patch('services.calc_service.main.save_audit_log') as mocked_save:
        response = client.post("/calc/vat", json={"amount": "100.0", "lot_id": 0})
        logger.debug(f"Response received: status={response.status_code}, body={response.text}, url={response.request.url}")
        assert response.status_code == 422, f"Expected 422 status for invalid lot_id, got {response.status_code}: {response.text}"
        mocked_save.assert_not_called()
    logger.debug("Finished test_vat_validation_invalid_lot_id")

def test_margin_validation_negative_cost(client):
    logger.debug("Starting test_margin_validation_negative_cost")
    with patch('services.calc_service.main.save_audit_log') as mocked_save:
        response = client.post(
            "/calc/margin", json={"lot_price": "100.0", "cost": "-50.0", "logistics": "10.0"}
        )
        logger.debug(f"Response received: status={response.status_code}, body={response.text}, url={response.request.url}")
        assert response.status_code == 422, f"Expected 422 status for negative cost, got {response.status_code}: {response.text}"
        mocked_save.assert_not_called()
    logger.debug("Finished test_margin_validation_negative_cost")

def test_penalty_validation_high_rate(client):
    logger.debug("Starting test_penalty_validation_high_rate")
    with patch('services.calc_service.main.save_audit_log') as mocked_save:
        response = client.post(
            "/calc/penalty",
            json={"contract_sum": "1000.0", "days_overdue": 5, "daily_rate_pct": "10.0"},
        )
        logger.debug(f"Response received: status={response.status_code}, body={response.text}, url={response.request.url}")
        assert response.status_code == 422, f"Expected 422 status for invalid penalty rate, got {response.status_code}: {response.text}"
        mocked_save.assert_not_called()
    logger.debug("Finished test_penalty_validation_high_rate")

@patch('services.calc_service.main.save_audit_log')
@patch('starlette.requests.Request.body', new_callable=AsyncMock)
def test_audit_log_created(mocked_body, mocked_save, client):
    logger.debug("Starting test_audit_log_created")
    mocked_body.return_value = json.dumps({"amount": "100.0", "vat_rate": "12.0"}).encode('utf-8')
    response = client.post("/calc/vat", json={"amount": "100.0", "vat_rate": "12.0"})
    logger.debug(f"Response received: status={response.status_code}, body={response.json()}, url={response.request.url}")
    assert response.status_code == 200, f"Expected 200 status for valid VAT calculation, got {response.status_code}: {response.text}"
    mocked_save.assert_not_called()
    logger.debug("Finished test_audit_log_created")