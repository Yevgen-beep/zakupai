import httpx
from fastapi import APIRouter, FastAPI, HTTPException
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

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


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
