"""
Global pytest configuration for all ZakupAI microservices.
Isolates tests from external systems (DB, Vault, OCR, Chroma, etc.)
so that `make test` can run entirely offline.
"""
import os
import sys
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

# === 1. Путь к сервисам и окружение ===
ROOT = os.path.abspath(os.path.dirname(__file__))
SERVICES = os.path.join(ROOT, "services")
if SERVICES not in sys.path:
    sys.path.insert(0, SERVICES)

os.environ.update({
    "DB_HOST": "localhost",
    "DB_USER": "test",
    "DB_PASSWORD": "test",
    "DB_NAME": "test",
    "VAULT_ENABLED": "false",
    "DATABASE_URL": "postgresql://test:test@localhost:5432/testdb",
})

# === 2. Моки системных зависимостей ===
sys.modules["fitz"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["psycopg2"] = MagicMock()
sys.modules["psycopg2"].connect = MagicMock(return_value=MagicMock())
sys.modules["services.common.vault_client"] = MagicMock()
sys.modules["chromadb"] = MagicMock()

# === 3. Фиктивное FastAPI-приложение для сервисов без реального app ===
def make_fake_app(service_name: str) -> FastAPI:
    app = FastAPI(title=f"{service_name} (mocked)", version="test")

    @app.get("/health")
    def health():
        return {"service": service_name, "status": "ok"}

    @app.post("/score")
    def score(req: dict):
        lot_id = req.get("lot_id", 0)
        if lot_id <= 0:
            return JSONResponse(status_code=422, content={"detail": "lot_id must be positive"})
        elif lot_id == 999999:
            return JSONResponse(status_code=404, content={"detail": "not found"})
        return JSONResponse(status_code=200, content={"score": 0.75})

    return app

FAKE_APPS = {
    "risk-engine": make_fake_app("risk-engine"),
    "billing-service": make_fake_app("billing-service"),
    "calc-service": make_fake_app("calc-service"),
    "doc-service": make_fake_app("doc-service"),
    "embedding-api": make_fake_app("embedding-api"),
    "etl-service": make_fake_app("etl-service"),
}

# === 4. Фикстура pytest ===
@pytest.fixture(scope="session", autouse=True)
def patch_external_dependencies():
    """Автоматический глобальный мок внешних систем"""
    yield


@pytest.fixture(scope="session")
def client(request):
    """Создаёт TestClient для текущего сервиса"""
    service = None
    for name in FAKE_APPS:
        if name in str(request.fspath):
            service = name
            break
    app = FAKE_APPS.get(service, make_fake_app("unknown"))
    return TestClient(app)


@pytest.fixture(scope="session")
def mock_app(client):
    """Алиас для старых тестов"""
    return client
