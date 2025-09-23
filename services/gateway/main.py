from fastapi import FastAPI
from zakupai_common.compliance import ComplianceSettings
from zakupai_common.fastapi.error_middleware import ErrorHandlerMiddleware
from zakupai_common.fastapi.health import health_router
from zakupai_common.logging import setup_logging

app = FastAPI(title="Gateway Service", version="0.1.0")

# Setup logging
setup_logging("gateway")

# Add middleware
app.add_middleware(ErrorHandlerMiddleware)

# Include routers
app.include_router(health_router)


@app.get("/")
async def root():
    return {
        "message": "Gateway Service",
        "compliance": ComplianceSettings.REESTR_NEDOBRO_ENABLED,
    }
