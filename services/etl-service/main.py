import math
import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from etl import ETLService
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from zakupai_common.compliance import ComplianceSettings
from zakupai_common.fastapi.error_middleware import ErrorHandlerMiddleware
from zakupai_common.fastapi.health import health_router
from zakupai_common.logging import setup_logging

load_dotenv()

app = FastAPI(
    title="ETL Service",
    description="ETL service for ZakupAI platform - loads data from Kazakhstan Government Procurement GraphQL API to PostgreSQL",
    version="1.0.0",
)

# Setup logging
setup_logging("etl-service")

# Add middleware
app.add_middleware(ErrorHandlerMiddleware)

# Include routers
app.include_router(health_router)


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


class Attachment(BaseModel):
    id: int
    lot_id: str | None = None
    filename: str | None = None
    file_size: int | None = None
    content: str | None = None
    processed_at: str | None = None
    file_hash: str | None = None


class AttachmentsResponse(BaseModel):
    attachments: list[Attachment]
    total: int
    page: int
    limit: int
    pages: int


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


@app.get("/attachments", response_model=AttachmentsResponse)
async def get_attachments(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Full-text search query"),
    _: bool = Depends(check_env_variables),
):
    """Get paginated list of OCR attachments with optional full-text search"""
    try:
        database_url = os.getenv("DATABASE_URL")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Calculate offset
        offset = (page - 1) * limit

        # Base query
        if search:
            # Full-text search query with Russian language support
            count_query = """
                SELECT COUNT(*) as total
                FROM attachments
                WHERE to_tsvector('russian', content) @@ plainto_tsquery('russian', %s)
            """

            main_query = """
                SELECT id, lot_id, filename, file_size, content, processed_at, file_hash,
                       ts_rank(to_tsvector('russian', content), plainto_tsquery('russian', %s)) as rank
                FROM attachments
                WHERE to_tsvector('russian', content) @@ plainto_tsquery('russian', %s)
                ORDER BY rank DESC, processed_at DESC
                LIMIT %s OFFSET %s
            """

            # Get total count
            cursor.execute(count_query, (search,))
            total = cursor.fetchone()["total"]

            # Get attachments
            cursor.execute(main_query, (search, search, limit, offset))

        else:
            # Regular query without search
            count_query = "SELECT COUNT(*) as total FROM attachments"
            main_query = """
                SELECT id, lot_id, filename, file_size, content, processed_at, file_hash
                FROM attachments
                ORDER BY processed_at DESC
                LIMIT %s OFFSET %s
            """

            # Get total count
            cursor.execute(count_query)
            total = cursor.fetchone()["total"]

            # Get attachments
            cursor.execute(main_query, (limit, offset))

        rows = cursor.fetchall()

        # Convert to Attachment models
        attachments = []
        for row in rows:
            # Truncate content for list view (first 200 chars)
            content = row["content"]
            if content and len(content) > 200:
                content = content[:200] + "..."

            attachments.append(
                Attachment(
                    id=row["id"],
                    lot_id=row["lot_id"],
                    filename=row["filename"],
                    file_size=row["file_size"],
                    content=content,
                    processed_at=(
                        str(row["processed_at"]) if row["processed_at"] else None
                    ),
                    file_hash=row["file_hash"],
                )
            )

        cursor.close()
        conn.close()

        # Calculate total pages
        pages = math.ceil(total / limit) if total > 0 else 0

        return AttachmentsResponse(
            attachments=attachments, total=total, page=page, limit=limit, pages=pages
        )

    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}") from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.get("/attachments/{attachment_id}", response_model=Attachment)
async def get_attachment(attachment_id: int, _: bool = Depends(check_env_variables)):
    """Get full attachment details by ID"""
    try:
        database_url = os.getenv("DATABASE_URL")
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cursor.execute(
            "SELECT id, lot_id, filename, file_size, content, processed_at, file_hash FROM attachments WHERE id = %s",
            (attachment_id,),
        )

        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Attachment not found")

        cursor.close()
        conn.close()

        return Attachment(
            id=row["id"],
            lot_id=row["lot_id"],
            filename=row["filename"],
            file_size=row["file_size"],
            content=row["content"],  # Full content for detail view
            processed_at=str(row["processed_at"]) if row["processed_at"] else None,
            file_hash=row["file_hash"],
        )

    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}") from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        ) from e


@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": "ETL Service",
        "description": "Loads data from Kazakhstan Government Procurement GraphQL API to PostgreSQL",
        "compliance": {
            "excluded_procurements_filtering": ComplianceSettings.EXCLUDED_PROCUREMENTS,
            "single_source_enabled": ComplianceSettings.SINGLE_SOURCE_LIST_ENABLED,
        },
        "endpoints": {
            "/health": "Health check",
            "/run": "Run ETL process",
            "/attachments": "Get OCR processed attachments",
            "/docs": "API documentation",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104
