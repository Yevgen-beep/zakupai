import os

from dotenv import load_dotenv
from etl import ETLService
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(
    title="ETL Service",
    description="ETL service for ZakupAI platform - loads data from Kazakhstan Government Procurement GraphQL API to PostgreSQL",
    version="1.0.0",
)


class ETLRequest(BaseModel):
    days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Number of days to fetch data for (fixed at 7 for testing)",
    )


class ETLResponse(BaseModel):
    status: str
    records: dict
    errors: list


class HealthResponse(BaseModel):
    status: str


def check_env_variables():
    """Check if required environment variables are present"""
    api_token = os.getenv("API_TOKEN")
    database_url = os.getenv("DATABASE_URL")

    if not api_token:
        raise HTTPException(
            status_code=500, detail="API_TOKEN environment variable not found"
        )

    if not database_url:
        raise HTTPException(
            status_code=500, detail="DATABASE_URL environment variable not found"
        )

    return True


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="ok")


@app.post("/run", response_model=ETLResponse)
async def run_etl(
    request: ETLRequest = ETLRequest(), _: bool = Depends(check_env_variables)
):
    """
    Run ETL process to load data from Kazakhstan Government Procurement GraphQL API

    - **days**: Number of days to fetch data for (fixed at 7 for testing)

    The ETL process will:
    1. Fetch Lots for the specified days
    2. Fetch TrdBuy for the specified days
    3. Fetch Contract for the specified days
    4. Fetch all Subjects (reference data)
    5. Fetch all RNU (reference data)
    6. Insert data into PostgreSQL with conflict handling
    """

    # For testing, fix days to 7
    if request.days != 7:
        raise HTTPException(
            status_code=400, detail="For testing, days parameter must be 7"
        )

    try:
        async with ETLService() as etl_service:
            # Use test_limit=3 for initial testing, change to 200 for production
            result = await etl_service.run_etl(days=request.days, test_limit=3)

            return ETLResponse(
                status=result["status"],
                records=result["records"],
                errors=result["errors"],
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"ETL process failed: {str(e)}"
        ) from e


@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "ETL Service",
        "description": "Loads data from Kazakhstan Government Procurement GraphQL API to PostgreSQL",
        "endpoints": {
            "/health": "Health check",
            "/run": "Run ETL process",
            "/docs": "API documentation",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104
