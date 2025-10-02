import asyncio

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import PlainTextResponse, Response

from zakupai_common.compliance import ComplianceSettings
from zakupai_common.fastapi.error_middleware import ErrorHandlerMiddleware
from zakupai_common.fastapi.health import health_router
from zakupai_common.fastapi.metrics import add_prometheus_middleware
from zakupai_common.logging import setup_logging

SERVICE_NAME = "gateway"


app = FastAPI(title="Gateway Service", version="0.1.0")

# Setup logging
setup_logging("gateway")

# Add middleware
app.add_middleware(ErrorHandlerMiddleware)
add_prometheus_middleware(app, SERVICE_NAME)


class StubStatusTracker:
    """Tracks request counters to emulate nginx stub_status output."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._active = 0
        self._accepts = 0
        self._handled = 0

    async def request_started(self) -> None:
        async with self._lock:
            self._accepts += 1
            self._active += 1

    async def request_finished(self) -> None:
        async with self._lock:
            self._handled += 1
            if self._active > 0:
                self._active -= 1

    async def snapshot(self) -> dict[str, int]:
        async with self._lock:
            return {
                "active": self._active,
                "accepts": self._accepts,
                "handled": self._handled,
            }


stub_tracker = StubStatusTracker()


@app.middleware("http")
async def track_stub_status(request: Request, call_next):
    await stub_tracker.request_started()
    try:
        response = await call_next(request)
    finally:
        await stub_tracker.request_finished()
    return response

# Health proxy router
health_proxy_router = APIRouter()

# Service health endpoints mapping
HEALTH_SERVICES = {
    "/risk/health": "http://risk-engine:8000/health",
    "/etl/health": "http://etl-service:8000/health",
    "/doc/health": "http://doc-service:8000/health",
    "/emb/health": "http://embedding-api:8000/health",
    "/calc/health": "http://calc-service:8000/health",
    "/billing/health": "http://billing-service:8000/health",
}


@health_proxy_router.get("/risk/health")
async def risk_health():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://risk-engine:8000/health", timeout=10.0)
            return response.json()
        except Exception as e:
            raise HTTPException(
                status_code=503, detail=f"Service unavailable: {str(e)}"
            ) from e


@health_proxy_router.get("/etl/health")
async def etl_health():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://etl-service:8000/health", timeout=10.0)
            return response.json()
        except Exception as e:
            raise HTTPException(
                status_code=503, detail=f"Service unavailable: {str(e)}"
            ) from e


@health_proxy_router.get("/doc/health")
async def doc_health():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://doc-service:8000/health", timeout=10.0)
            return response.json()
        except Exception as e:
            raise HTTPException(
                status_code=503, detail=f"Service unavailable: {str(e)}"
            ) from e


@health_proxy_router.get("/emb/health")
async def emb_health():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "http://embedding-api:8000/health", timeout=10.0
            )
            return response.json()
        except Exception as e:
            raise HTTPException(
                status_code=503, detail=f"Service unavailable: {str(e)}"
            ) from e


@health_proxy_router.get("/calc/health")
async def calc_health():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://calc-service:8000/health", timeout=10.0)
            return response.json()
        except Exception as e:
            raise HTTPException(
                status_code=503, detail=f"Service unavailable: {str(e)}"
            ) from e


@health_proxy_router.get("/billing/health")
async def billing_health():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "http://billing-service:8000/health", timeout=10.0
            )
            return response.json()
        except Exception as e:
            raise HTTPException(
                status_code=503, detail=f"Service unavailable: {str(e)}"
            ) from e


# Include routers
app.include_router(health_router)
app.include_router(health_proxy_router)


@app.get("/")
async def root():
    return {
        "message": "Gateway Service",
        "compliance": ComplianceSettings.REESTR_NEDOBRO_ENABLED,
    }


@app.get("/stub_status", response_class=PlainTextResponse)
async def stub_status():
    snapshot = await stub_tracker.snapshot()
    active = snapshot["active"]
    accepts = snapshot["accepts"]
    handled = snapshot["handled"]
    requests = handled
    body = (
        f"Active connections: {active}\n"
        "server accepts handled requests\n"
        f" {accepts} {handled} {requests}\n"
        f"Reading: 0 Writing: {active} Waiting: 0\n"
    )
    return PlainTextResponse(body)


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
