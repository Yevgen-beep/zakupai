import asyncio
import os
import time
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

import chromadb
import httpx
import pandas as pd
import structlog
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, validator
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware

# Load environment variables from .env
load_dotenv()

# Setup structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Database setup
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://zakupai:password123@localhost:5432/zakupai"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ChromaDB setup
CHROMADB_URL = os.getenv("CHROMADB_URL", "http://chromadb:8000")
chroma_client = chromadb.HttpClient(host="chromadb", port=8000)

# Configuration
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway")
API_KEY = os.getenv("ZAKUPAI_API_KEY", "changeme")
GOSZAKUP_TOKEN = os.getenv("GOSZAKUP_TOKEN")
GOSZAKUP_API_URL = os.getenv("GOSZAKUP_API_URL", "http://goszakup-api:8001")

if not GOSZAKUP_TOKEN:
    logger.warning("GOSZAKUP_TOKEN not set - goszakup-api integration may not work")

if not GOSZAKUP_API_URL:
    logger.warning("GOSZAKUP_API_URL not set - using default goszakup-api:8001")

# ETL Service URL (internal network)
ETL_SERVICE_URL = "http://etl-service:8000"

# Flowise configuration
FLOWISE_API_URL = os.getenv("FLOWISE_API_URL", "http://flowise:3000")
FLOWISE_API_KEY = os.getenv("FLOWISE_API_KEY", "")

# Mock Satu.kz API for supplier search
SATU_API_URL = os.getenv("SATU_API_URL", "mock")

# FastAPI app
app = FastAPI(
    title="ZakupAI Web Panel",
    description="Web interface for ZakupAI tender analysis",
    version="1.0.0",
)

# CORS configuration - secure for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8080",
        "https://n8n.exomind.site",
        "https://zakupai.exomind.site",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Templates and static files
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# HTTP client for API calls
client = httpx.AsyncClient(timeout=30.0, headers={"X-API-Key": API_KEY})


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s"
        )
        return response


app.add_middleware(LoggingMiddleware)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page with search and upload forms"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/lot/{lot_id}", response_class=HTMLResponse)
async def lot_page(request: Request, lot_id: str):
    """Lot analysis page"""
    try:
        # Get lot data from Goszakup
        lot_response = await client.get(f"{GATEWAY_URL}/goszakup/lot/{lot_id}")
        if lot_response.status_code != 200:
            raise HTTPException(404, "Лот не найден")

        lot_data = lot_response.json()

        # Get TL;DR
        tldr_response = await client.post(
            f"{GATEWAY_URL}/doc/tldr", json={"lot_id": lot_id}
        )
        tldr_data = tldr_response.json() if tldr_response.status_code == 200 else {}

        # Get risk score
        risk_response = await client.post(
            f"{GATEWAY_URL}/risk/score", json={"lot_id": lot_id}
        )
        risk_data = risk_response.json() if risk_response.status_code == 200 else {}

        # Calculate margin (if we have price data)
        margin_data = {}
        if lot_data.get("price"):
            margin_response = await client.post(
                f"{GATEWAY_URL}/calc/margin",
                json={
                    "cost_price": lot_data["price"] * 0.8,  # Mock 80% cost
                    "selling_price": lot_data["price"],
                    "quantity": 1,
                },
            )
            margin_data = (
                margin_response.json() if margin_response.status_code == 200 else {}
            )

        return templates.TemplateResponse(
            "lot.html",
            {
                "request": request,
                "lot_id": lot_id,
                "lot_data": lot_data,
                "tldr_data": tldr_data,
                "risk_data": risk_data,
                "margin_data": margin_data,
            },
        )

    except httpx.RequestError as e:
        logger.error(f"API request failed: {e}")
        raise HTTPException(500, "Ошибка подключения к API") from e
    except Exception as e:
        logger.error(f"Lot page error: {e}")
        raise HTTPException(500, "Внутренняя ошибка сервера") from e


@app.get("/api/lot/{lot_id}")
async def api_get_lot(lot_id: str):
    """API endpoint to get lot data as JSON"""
    try:
        # Get full lot analysis
        tasks = [
            client.get(f"{GATEWAY_URL}/goszakup/lot/{lot_id}"),
            client.post(f"{GATEWAY_URL}/doc/tldr", json={"lot_id": lot_id}),
            client.post(f"{GATEWAY_URL}/risk/score", json={"lot_id": lot_id}),
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        result = {"lot_id": lot_id}

        # Process Goszakup data
        if not isinstance(responses[0], Exception) and responses[0].status_code == 200:
            result["goszakup"] = responses[0].json()

        # Process TL;DR
        if not isinstance(responses[1], Exception) and responses[1].status_code == 200:
            result["tldr"] = responses[1].json()

        # Process risk
        if not isinstance(responses[2], Exception) and responses[2].status_code == 200:
            result["risk"] = responses[2].json()

        return result

    except Exception as e:
        logger.error(f"API lot error: {e}")
        raise HTTPException(500, "API error") from e


@app.post("/upload-prices")
async def upload_prices(
    file: UploadFile = File(...),
    source_name: str = Form(...),
):
    """Upload CSV/XLSX price data"""
    if not file.filename:
        raise HTTPException(400, "Файл не выбран")

    # Validate file type
    allowed_extensions = {".csv", ".xlsx", ".xls"}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            400,
            f"Неподдерживаемый формат файла. Разрешены: {', '.join(allowed_extensions)}",
        )

    try:
        # Read file content
        content = await file.read()

        # Parse based on file type
        if file_ext == ".csv":
            df = pd.read_csv(BytesIO(content))
        else:  # Excel files
            df = pd.read_excel(BytesIO(content))

        # Validate required columns
        required_cols = ["sku", "price"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise HTTPException(
                400, f"Отсутствуют обязательные колонки: {', '.join(missing_cols)}"
            )

        # Clean and prepare data
        df = df.dropna(subset=required_cols)
        df["source"] = source_name
        df["captured_at"] = pd.Timestamp.now()

        # Convert to records for API call
        records = df.to_dict("records")

        # Send to prices service
        import_response = await client.post(
            f"{GATEWAY_URL}/prices/bulk-import",
            json={"source": source_name, "prices": records},
        )

        if import_response.status_code != 200:
            raise HTTPException(500, "Ошибка импорта данных")

        result = import_response.json()

        return {
            "status": "success",
            "total_rows": len(df),
            "added": result.get("added", 0),
            "updated": result.get("updated", 0),
            "skipped": result.get("skipped", 0),
            "source": source_name,
            "filename": file.filename,
        }

    except pd.errors.EmptyDataError as e:
        raise HTTPException(400, "Файл пуст или поврежден") from e
    except pd.errors.ParserError as e:
        raise HTTPException(400, f"Ошибка парсинга файла: {str(e)}") from e
    except httpx.RequestError as e:
        logger.error(f"API request failed during import: {e}")
        raise HTTPException(500, "Ошибка подключения к API") from e
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(500, "Ошибка обработки файла") from e


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Price upload page"""
    return templates.TemplateResponse("upload.html", {"request": request})


@app.get("/attachments", response_class=HTMLResponse)
async def attachments_page(request: Request, search: str = None, page: int = 1):
    """OCR attachments page with search and pagination"""
    try:
        # Get attachments from ETL service
        params = {"page": page, "limit": 20}
        if search:
            params["search"] = search

        attachments_response = await client.get(
            f"{GATEWAY_URL}/etl/attachments", params=params
        )

        if attachments_response.status_code == 200:
            attachments_data = attachments_response.json()
        else:
            # Fallback to direct database connection if ETL service is unavailable
            attachments_data = {"attachments": [], "total": 0, "pages": 0}

        return templates.TemplateResponse(
            "attachments.html",
            {
                "request": request,
                "attachments": attachments_data.get("attachments", []),
                "total": attachments_data.get("total", 0),
                "pages": attachments_data.get("pages", 0),
                "current_page": page,
                "search_query": search or "",
            },
        )

    except httpx.RequestError as e:
        logger.error(f"ETL service request failed: {e}")
        # Return empty results with error message
        return templates.TemplateResponse(
            "attachments.html",
            {
                "request": request,
                "attachments": [],
                "total": 0,
                "pages": 0,
                "current_page": 1,
                "search_query": search or "",
                "error": "Сервис OCR временно недоступен",
            },
        )
    except Exception as e:
        logger.error(f"Attachments page error: {e}")
        raise HTTPException(500, "Ошибка загрузки страницы") from e


@app.get("/rnu", response_class=HTMLResponse)
async def rnu_dashboard(request: Request):
    """RNU validation dashboard with enhanced UI"""
    return templates.TemplateResponse("rnu_dashboard.html", {"request": request})


@app.get("/rnu/{supplier_bin}", response_class=HTMLResponse)
async def rnu_details(request: Request, supplier_bin: str):
    """RNU supplier details page with history and graphs"""
    try:
        # Validate BIN format
        if not supplier_bin.isdigit() or len(supplier_bin) != 12:
            raise HTTPException(400, "Invalid BIN format")

        # Get current RNU status from risk-engine
        async with httpx.AsyncClient() as client:
            rnu_response = await client.get(
                f"{GATEWAY_URL}/risk/validate_rnu/{supplier_bin}"
            )

            if rnu_response.status_code == 200:
                rnu_data = rnu_response.json()
            else:
                rnu_data = {
                    "supplier_bin": supplier_bin,
                    "status": "UNKNOWN",
                    "is_blocked": False,
                    "source": "error",
                    "validated_at": datetime.now().isoformat(),
                }

        # Get validation history
        validation_history = await get_rnu_validation_history(supplier_bin)

        # Get alert history
        alert_history = await get_rnu_alert_history(supplier_bin)

        return templates.TemplateResponse(
            "rnu_details.html",
            {
                "request": request,
                "supplier_bin": supplier_bin,
                "rnu_data": rnu_data,
                "validation_history": validation_history,
                "alert_history": alert_history,
            },
        )

    except Exception as e:
        logger.error(f"RNU details page error: {e}")
        raise HTTPException(500, "Error loading RNU details") from e


async def get_rnu_validation_history(supplier_bin: str, limit: int = 10) -> list:
    """Get RNU validation history for supplier"""
    try:
        with SessionLocal() as db:
            query = text(
                """
                SELECT supplier_bin, status, is_blocked, validated_at, expires_at
                FROM rnu_validation_cache
                WHERE supplier_bin = :supplier_bin
                ORDER BY validated_at DESC
                LIMIT :limit
            """
            )

            results = db.execute(
                query, {"supplier_bin": supplier_bin, "limit": limit}
            ).fetchall()

            history = []
            for row in results:
                history.append(
                    {
                        "supplier_bin": row.supplier_bin,
                        "status": row.status,
                        "is_blocked": row.is_blocked,
                        "validated_at": (
                            row.validated_at.isoformat() if row.validated_at else None
                        ),
                        "expires_at": (
                            row.expires_at.isoformat() if row.expires_at else None
                        ),
                    }
                )

            return history

    except Exception as e:
        logger.error(f"Error getting RNU validation history: {e}")
        return []


async def get_rnu_alert_history(supplier_bin: str, limit: int = 5) -> list:
    """Get RNU alert history for supplier"""
    try:
        with SessionLocal() as db:
            query = text(
                """
                SELECT supplier_bin, status, previous_status, notified_at, notification_type
                FROM rnu_alerts
                WHERE supplier_bin = :supplier_bin
                ORDER BY notified_at DESC
                LIMIT :limit
            """
            )

            results = db.execute(
                query, {"supplier_bin": supplier_bin, "limit": limit}
            ).fetchall()

            alerts = []
            for row in results:
                alerts.append(
                    {
                        "supplier_bin": row.supplier_bin,
                        "status": row.status,
                        "previous_status": row.previous_status,
                        "notified_at": (
                            row.notified_at.isoformat() if row.notified_at else None
                        ),
                        "notification_type": row.notification_type or "status_change",
                    }
                )

            return alerts

    except Exception as e:
        logger.error(f"Error getting RNU alert history: {e}")
        return []


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "web-ui", "goszakup_api_url": GOSZAKUP_API_URL}


@app.get("/lots")
async def get_lots(keyword: str = "лак", limit: int = 10):
    """Get lots from internal goszakup-api service"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{GOSZAKUP_API_URL}/search",
                params={"keyword": keyword, "limit": limit},
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"Goszakup-api service error: {response.status_code} - {response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Goszakup-api service error: {response.status_code}",
                )

    except httpx.TimeoutException as e:
        logger.error(f"Goszakup-api service timeout: {e}")
        raise HTTPException(408, "Goszakup-api service timeout") from e
    except Exception as e:
        logger.error(f"Goszakup-api service error: {e}")
        raise HTTPException(
            500, "Failed to fetch lots from goszakup-api service"
        ) from e


@app.post("/etl/upload")
async def etl_upload(file: UploadFile = File(...)):
    """Proxy ETL upload requests to etl-service"""
    try:
        # Forward the file to etl-service
        files = {"file": (file.filename, file.file, file.content_type)}

        async with httpx.AsyncClient(timeout=60.0) as etl_client:
            response = await etl_client.post(
                f"{ETL_SERVICE_URL}/etl/upload", files=files
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"ETL upload error: {response.status_code} - {response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"ETL upload error: {response.status_code}",
                )

    except httpx.TimeoutException as e:
        logger.error(f"ETL upload timeout: {e}")
        raise HTTPException(408, "ETL upload timeout") from e
    except Exception as e:
        logger.error(f"ETL upload error: {e}")
        raise HTTPException(500, "Failed to upload file to ETL service") from e


@app.get("/search")
async def search_lots(query: str, limit: int = 10):
    """Search lots through goszakup-api service"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{GOSZAKUP_API_URL}/search", params={"keyword": query, "limit": limit}
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"Lot search error: {response.status_code} - {response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Lot search error: {response.status_code}",
                )

    except httpx.TimeoutException as e:
        logger.error(f"Lot search timeout: {e}")
        raise HTTPException(408, "Lot search timeout") from e
    except Exception as e:
        logger.error(f"Lot search error: {e}")
        raise HTTPException(500, "Failed to search lots") from e


@app.post("/search/documents")
async def search_documents(request: dict):
    """Proxy document search requests to etl-service"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as etl_client:
            response = await etl_client.post(f"{ETL_SERVICE_URL}/search", json=request)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"Document search error: {response.status_code} - {response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Document search error: {response.status_code}",
                )

    except httpx.TimeoutException as e:
        logger.error(f"Document search timeout: {e}")
        raise HTTPException(408, "Document search timeout") from e
    except Exception as e:
        logger.error(f"Document search error: {e}")
        raise HTTPException(500, "Failed to search documents") from e


# ---------- Advanced Search Models ----------
class AdvancedSearchRequest(BaseModel):
    query: str = Field(
        ..., min_length=1, max_length=500, description="Search query text"
    )
    min_amount: float | None = Field(None, ge=0, description="Minimum lot amount")
    max_amount: float | None = Field(None, ge=0, description="Maximum lot amount")
    status: str | None = Field(None, description="Lot status filter")
    limit: int = Field(
        default=10, ge=1, le=100, description="Number of results to return"
    )
    offset: int = Field(default=0, ge=0, description="Offset for pagination")

    @validator("max_amount")
    def validate_amount_range(cls, v, values):
        if (
            v is not None
            and "min_amount" in values
            and values["min_amount"] is not None
        ):
            if v < values["min_amount"]:
                raise ValueError(
                    "max_amount must be greater than or equal to min_amount"
                )
        return v

    @validator("status")
    def validate_status(cls, v):
        if v is not None:
            # Map status names to refBuyStatusId values used in the database
            allowed_statuses = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}
            if str(v) not in allowed_statuses:
                raise ValueError(
                    f'Status must be one of: {", ".join(allowed_statuses)}'
                )
            return str(v)
        return v


class LotResult(BaseModel):
    id: int = Field(..., description="Lot ID")
    nameRu: str = Field(..., description="Lot name in Russian")
    amount: float = Field(..., description="Lot amount")
    status: int = Field(..., description="Lot status ID")
    trdBuyId: int = Field(..., description="Related tender/purchase ID")
    customerNameRu: str | None = Field(None, description="Customer name in Russian")


class AdvancedSearchResponse(BaseModel):
    results: list[LotResult] = Field(..., description="Search results")
    total_count: int = Field(..., description="Total number of matching lots")


class AutocompleteResponse(BaseModel):
    suggestions: list[str] = Field(..., description="Autocomplete suggestions")


# ---------- Advanced Search Endpoints ----------
@app.post("/api/search/advanced", response_model=AdvancedSearchResponse)
async def advanced_search(request: AdvancedSearchRequest):
    """
    Advanced search with filters for amounts and status

    - **query**: Search query text (full-text search)
    - **min_amount**: Minimum lot amount filter
    - **max_amount**: Maximum lot amount filter
    - **status**: Lot status filter (ACTIVE, COMPLETED, CANCELLED)
    - **limit**: Number of results to return (1-100)
    - **offset**: Offset for pagination
    """
    request_id = str(uuid.uuid4())

    logger.info(
        "Advanced search request",
        request_id=request_id,
        query=request.query,
        filters={
            "min_amount": request.min_amount,
            "max_amount": request.max_amount,
            "status": request.status,
        },
        limit=request.limit,
        offset=request.offset,
    )

    try:
        start_time = time.time()

        with SessionLocal() as db:
            # Use optimized query with covering indexes
            query_conditions = []
            query_params = {"query": request.query}

            # Full-text search condition using GIN indexes
            if request.query.strip():
                query_conditions.append(
                    """
                    (to_tsvector('russian', l.nameRu) @@ plainto_tsquery('russian', :query)
                     OR to_tsvector('russian', COALESCE(l.descriptionRu, '')) @@ plainto_tsquery('russian', :query)
                     OR to_tsvector('russian', t.nameRu) @@ plainto_tsquery('russian', :query))
                    """
                )

            # Amount filters using B-tree indexes
            if request.min_amount is not None:
                query_conditions.append("l.amount >= :min_amount")
                query_params["min_amount"] = request.min_amount

            if request.max_amount is not None:
                query_conditions.append("l.amount <= :max_amount")
                query_params["max_amount"] = request.max_amount

            # Status filter using indexed column
            if request.status is not None:
                query_conditions.append("t.refBuyStatusId = :status")
                query_params["status"] = int(request.status)

            # Add non-null filters for performance
            query_conditions.extend(
                [
                    "l.nameRu IS NOT NULL",
                    "l.amount IS NOT NULL",
                    "t.refBuyStatusId IS NOT NULL",
                ]
            )

            where_clause = " AND ".join(query_conditions)

            # Fast count query with covering index
            count_query = text(  # nosec B608
                f"""
                SELECT COUNT(*)
                FROM lots l
                INNER JOIN trdbuy t ON l.trdBuyId = t.id
                WHERE {where_clause}
            """
            )

            total_count = db.execute(count_query, query_params).scalar()

            # Optimized search query with sort by relevance and amount
            search_query = text(  # nosec B608
                f"""
                SELECT
                    l.id,
                    l.nameRu,
                    l.amount,
                    COALESCE(t.refBuyStatusId, 0) as status,
                    l.trdBuyId,
                    t.customerNameRu,
                    CASE WHEN :query != '' THEN
                        ts_rank_cd(
                            to_tsvector('russian', l.nameRu || ' ' || COALESCE(l.descriptionRu, '') || ' ' || COALESCE(t.nameRu, '')),
                            plainto_tsquery('russian', :query),
                            1
                        )
                    ELSE 1 END as relevance
                FROM lots l
                INNER JOIN trdbuy t ON l.trdBuyId = t.id
                WHERE {where_clause}
                ORDER BY
                    relevance DESC,
                    l.amount DESC,
                    l.lastUpdateDate DESC NULLS LAST
                LIMIT :limit OFFSET :offset
            """
            )

            query_params.update({"limit": request.limit, "offset": request.offset})

            results = db.execute(search_query, query_params).fetchall()

            # Convert results to response format
            lot_results = [
                LotResult(
                    id=row.id,
                    nameRu=row.nameRu or "",
                    amount=float(row.amount) if row.amount else 0.0,
                    status=row.status,
                    trdBuyId=row.trdBuyId,
                    customerNameRu=row.customerNameRu,
                )
                for row in results
            ]

            latency_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "Advanced search completed",
                request_id=request_id,
                results_count=len(lot_results),
                total_count=total_count,
                latency_ms=latency_ms,
                query=request.query,
                filters={
                    "min_amount": request.min_amount,
                    "max_amount": request.max_amount,
                    "status": request.status,
                },
            )

            return AdvancedSearchResponse(results=lot_results, total_count=total_count)

    except Exception as e:
        logger.error("Advanced search error", request_id=request_id, error=str(e))
        raise HTTPException(status_code=500, detail="Search failed") from e


@app.get("/api/search/autocomplete", response_model=AutocompleteResponse)
async def search_autocomplete(query: str):
    """
    Get autocomplete suggestions from ChromaDB with improved performance

    - **query**: Search query text (minimum 2 characters)

    Returns up to 5 autocomplete suggestions based on lot names
    Target latency: ≤500ms (95th percentile)
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())

    # Validate input length
    if len(query.strip()) < 2:
        return AutocompleteResponse(suggestions=[])

    if len(query.strip()) > 100:  # Prevent very long queries
        return AutocompleteResponse(suggestions=[])

    normalized_query = query.lower().strip()

    logger.info("Autocomplete request", request_id=request_id, query=normalized_query)

    try:
        # Try ChromaDB first for semantic similarity
        suggestions = await get_chromadb_suggestions(normalized_query)

        # If ChromaDB fails or returns few results, fallback to SQL prefix search
        if len(suggestions) < 3:
            sql_suggestions = await get_sql_autocomplete_fallback(normalized_query)
            # Merge and deduplicate
            all_suggestions = suggestions + sql_suggestions
            suggestions = list(dict.fromkeys(all_suggestions))[:5]

        latency_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "Autocomplete completed",
            request_id=request_id,
            suggestions_count=len(suggestions),
            latency_ms=latency_ms,
        )

        # Log performance warning if too slow
        if latency_ms > 500:
            logger.warning(
                "Autocomplete latency exceeded target",
                request_id=request_id,
                latency_ms=latency_ms,
                target_ms=500,
            )

        return AutocompleteResponse(suggestions=suggestions)

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Autocomplete error",
            request_id=request_id,
            error=str(e),
            latency_ms=latency_ms,
        )
        # Don't fail hard on autocomplete errors, return empty suggestions
        return AutocompleteResponse(suggestions=[])


async def get_chromadb_suggestions(query: str) -> list[str]:
    """Get suggestions from ChromaDB with timeout"""
    try:
        # Set timeout for ChromaDB operations
        import asyncio

        async def chromadb_query():
            # Get or create lot_names collection
            try:
                collection = chroma_client.get_collection("lot_names")
            except Exception:
                # If collection doesn't exist, try to create it or return empty
                try:
                    collection = chroma_client.create_collection("lot_names")
                    logger.warning("Created new lot_names collection")
                    return []  # Empty collection, no suggestions yet
                except Exception:
                    return []

            # Search in ChromaDB
            results = collection.query(
                query_texts=[query], n_results=5, include=["documents"]
            )

            suggestions = []
            if results and results["documents"] and results["documents"][0]:
                # Extract unique suggestions
                seen = set()
                for doc in results["documents"][0]:
                    if doc and len(doc.strip()) > 2 and doc.lower() not in seen:
                        suggestions.append(doc.strip())
                        seen.add(doc.lower())

            return suggestions

        # Execute with timeout
        return await asyncio.wait_for(chromadb_query(), timeout=0.3)  # 300ms timeout

    except TimeoutError:
        logger.warning("ChromaDB autocomplete timeout")
        return []
    except Exception as e:
        logger.warning(f"ChromaDB autocomplete error: {e}")
        return []


async def get_sql_autocomplete_fallback(query: str) -> list[str]:
    """Fallback autocomplete using SQL prefix search"""
    try:
        with SessionLocal() as db:
            # Use prefix index for fast autocomplete
            search_query = text(
                """
                SELECT DISTINCT l.nameRu
                FROM lots l
                WHERE l.nameRu ILIKE :prefix
                AND length(l.nameRu) > 3
                AND l.nameRu IS NOT NULL
                ORDER BY length(l.nameRu), l.nameRu
                LIMIT 5
            """
            )

            results = db.execute(search_query, {"prefix": f"{query}%"}).fetchall()

            return [row.nameRu for row in results if row.nameRu]

    except Exception as e:
        logger.warning(f"SQL autocomplete fallback error: {e}")
        return []


# ---------- Flowise MVP Models ----------
class ComplaintRequest(BaseModel):
    lot_id: int = Field(..., description="Lot ID for complaint")
    reason: str = Field(..., description="Complaint reason", max_length=500)
    date: str | None = Field(None, description="Complaint date (ISO format)")

    @validator("reason")
    def validate_reason(cls, v):
        if not v.strip():
            raise ValueError("Reason cannot be empty")
        return v.strip()


class ComplaintResponse(BaseModel):
    lot_id: int
    complaint_text: str
    reason: str
    date: str
    pdf_available: bool = True


class SupplierRequest(BaseModel):
    lot_name: str = Field(
        ..., description="Product/service name to search suppliers for"
    )

    @validator("lot_name")
    def validate_lot_name(cls, v):
        if len(v.strip()) < 3:
            raise ValueError("Lot name must be at least 3 characters")
        return v.strip()


class Supplier(BaseModel):
    name: str
    rating: float
    contacts: str
    link: str
    location: str | None = None


class SupplierResponse(BaseModel):
    lot_name: str
    suppliers: list[Supplier]
    total_found: int


# ---------- Flowise MVP Endpoints ----------
@app.post("/api/complaint/{lot_id}", response_model=ComplaintResponse)
async def generate_complaint(lot_id: int, request: ComplaintRequest):
    """
    Generate complaint document using Flowise agent

    Uses Flowise to generate complaint text and provides PDF export
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())

    logger.info(
        "Complaint generation request",
        request_id=request_id,
        lot_id=lot_id,
        reason=request.reason,
    )

    try:
        # Get lot information first
        lot_info = await get_lot_info(lot_id)

        # Prepare complaint date
        complaint_date = request.date or datetime.now().isoformat()

        # Generate complaint via Flowise (or mock)
        complaint_text = await generate_complaint_via_flowise(
            lot_id, lot_info, request.reason, complaint_date
        )

        latency_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "Complaint generated",
            request_id=request_id,
            lot_id=lot_id,
            latency_ms=latency_ms,
        )

        return ComplaintResponse(
            lot_id=lot_id,
            complaint_text=complaint_text,
            reason=request.reason,
            date=complaint_date,
        )

    except Exception as e:
        logger.error(
            "Complaint generation error",
            request_id=request_id,
            lot_id=lot_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail="Failed to generate complaint"
        ) from e


@app.get("/api/complaint/{lot_id}/pdf")
async def download_complaint_pdf(lot_id: int, reason: str, date: str):
    """Download complaint as PDF"""
    try:
        # Get complaint text
        lot_info = await get_lot_info(lot_id)
        complaint_text = await generate_complaint_via_flowise(
            lot_id, lot_info, reason, date
        )

        # Generate PDF
        pdf_buffer = generate_complaint_pdf(complaint_text, lot_id, reason, date)

        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=complaint_lot_{lot_id}.pdf"
            },
        )

    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate PDF") from e


@app.get("/api/supplier/{lot_name}", response_model=SupplierResponse)
async def find_suppliers(lot_name: str):
    """
    Find suppliers for a given product/service

    Searches suppliers from Satu.kz API and ChromaDB embeddings
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())

    logger.info("Supplier search request", request_id=request_id, lot_name=lot_name)

    try:
        # Search suppliers via API and embeddings
        suppliers = await search_suppliers_combined(lot_name)

        latency_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "Supplier search completed",
            request_id=request_id,
            lot_name=lot_name,
            suppliers_found=len(suppliers),
            latency_ms=latency_ms,
        )

        return SupplierResponse(
            lot_name=lot_name, suppliers=suppliers, total_found=len(suppliers)
        )

    except Exception as e:
        logger.error(
            "Supplier search error",
            request_id=request_id,
            lot_name=lot_name,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Failed to search suppliers") from e


# ---------- Flowise Helper Functions ----------
async def get_lot_info(lot_id: int) -> dict:
    """Get basic lot information"""
    try:
        with SessionLocal() as db:
            query = text(
                """
                SELECT l.nameRu, l.amount, t.customerNameRu, t.publishDate
                FROM lots l
                JOIN trdbuy t ON l.trdBuyId = t.id
                WHERE l.id = :lot_id
            """
            )

            result = db.execute(query, {"lot_id": lot_id}).fetchone()

            if result:
                return {
                    "name": result.nameRu or f"Лот {lot_id}",
                    "amount": result.amount or 0,
                    "customer": result.customerNameRu or "Неизвестный заказчик",
                    "publish_date": (
                        result.publishDate.isoformat() if result.publishDate else None
                    ),
                }
            else:
                return {
                    "name": f"Лот {lot_id}",
                    "amount": 0,
                    "customer": "Неизвестный заказчик",
                }

    except Exception:
        return {
            "name": f"Лот {lot_id}",
            "amount": 0,
            "customer": "Неизвестный заказчик",
        }


async def generate_complaint_via_flowise(
    lot_id: int, lot_info: dict, reason: str, date: str
) -> str:
    """Generate complaint text via Flowise or mock"""
    try:
        if FLOWISE_API_URL == "mock" or not FLOWISE_API_KEY:
            # Mock complaint generation
            complaint_template = f"""
ЖАЛОБА

Дата: {date}

По лоту: {lot_info['name']} (ID: {lot_id})
Заказчик: {lot_info['customer']}
Сумма: {lot_info.get('amount', 0):,.2f} тенге

Основание жалобы: {reason}

Подробное описание нарушений:
В ходе анализа указанного лота были выявлены существенные нарушения процедуры государственных закупок, а именно {reason.lower()}.

Данные нарушения противоречат требованиям Закона РК "О государственных закупках" и могут привести к необоснованному расходованию бюджетных средств.

Прошу рассмотреть данную жалобу и принять соответствующие меры.

---
Сгенерировано ZakupAI
            """
            return complaint_template.strip()

        # Real Flowise integration
        async with httpx.AsyncClient(timeout=30) as client:
            flowise_response = await client.post(
                f"{FLOWISE_API_URL}/api/v1/prediction/complaint-generator",
                json={
                    "question": f"Generate complaint for lot {lot_id}, reason={reason}, date={date}",
                    "overrideConfig": {
                        "lotInfo": lot_info,
                        "reason": reason,
                        "date": date,
                    },
                },
                headers={"Authorization": f"Bearer {FLOWISE_API_KEY}"},
            )

            if flowise_response.status_code == 200:
                result = flowise_response.json()
                return result.get("text", "Ошибка генерации жалобы")
            else:
                # Fallback to mock
                return await generate_complaint_via_flowise(
                    lot_id, lot_info, reason, date
                )

    except Exception as e:
        logger.warning(f"Flowise complaint generation failed: {e}, using mock")
        return await generate_complaint_via_flowise(lot_id, lot_info, reason, date)


async def search_suppliers_combined(lot_name: str) -> list[Supplier]:
    """Search suppliers using API + ChromaDB"""
    suppliers = []

    try:
        # Mock Satu.kz API search
        if SATU_API_URL == "mock":
            # Generate mock suppliers
            mock_suppliers = [
                Supplier(
                    name=f"ТОО «{lot_name.title()} Плюс»",
                    rating=4.2,
                    contacts="+7 727 123-45-67, info@supplier1.kz",
                    link="https://satu.kz/supplier1",
                    location="Алматы",
                ),
                Supplier(
                    name=f"ИП «{lot_name[:10]} Сервис»",
                    rating=3.8,
                    contacts="+7 717 987-65-43, sales@supplier2.kz",
                    link="https://satu.kz/supplier2",
                    location="Нур-Султан",
                ),
                Supplier(
                    name=f"АО «Казахский {lot_name[:8]}»",
                    rating=4.5,
                    contacts="+7 777 555-33-11, orders@supplier3.kz",
                    link="https://satu.kz/supplier3",
                    location="Шымкент",
                ),
            ]
            suppliers.extend(mock_suppliers)
        else:
            # Real Satu.kz API integration
            async with httpx.AsyncClient(timeout=10) as client:
                satu_response = await client.get(
                    f"{SATU_API_URL}/search", params={"q": lot_name, "limit": 10}
                )

                if satu_response.status_code == 200:
                    satu_data = satu_response.json()
                    for item in satu_data.get("suppliers", []):
                        suppliers.append(
                            Supplier(
                                name=item.get("name", "Неизвестный поставщик"),
                                rating=float(item.get("rating", 0)),
                                contacts=item.get("contacts", "Не указано"),
                                link=item.get("url", "#"),
                                location=item.get("city", "Не указано"),
                            )
                        )

        # Search in ChromaDB suppliers collection
        try:
            collection = chroma_client.get_collection("suppliers")
            results = collection.query(query_texts=[lot_name], n_results=5)

            if results and results["documents"]:
                for doc in results["documents"][0]:
                    # Parse supplier info from ChromaDB (mock format)
                    if doc:
                        suppliers.append(
                            Supplier(
                                name=f"Поставщик {doc[:20]}",
                                rating=4.0,
                                contacts="Из базы ChromaDB",
                                link="#",
                                location="ChromaDB",
                            )
                        )
        except Exception:
            logger.warning("ChromaDB suppliers collection not available")

        # Remove duplicates and limit to top suppliers by rating
        unique_suppliers = {s.name: s for s in suppliers}
        sorted_suppliers = sorted(
            unique_suppliers.values(), key=lambda x: x.rating, reverse=True
        )

        return sorted_suppliers[:10]

    except Exception as e:
        logger.error(f"Supplier search error: {e}")
        return suppliers[:3]  # Return at least mock data


def generate_complaint_pdf(
    complaint_text: str, lot_id: int, reason: str, date: str
) -> BytesIO:
    """Generate PDF document for complaint"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=16,
        spaceAfter=30,
        textColor=colors.darkblue,
    )

    story = []

    # Title with ZakupAI logo placeholder
    title = Paragraph("ЖАЛОБА", title_style)
    story.append(title)
    story.append(Spacer(1, 12))

    # Content
    content_style = ParagraphStyle(
        "Content", parent=styles["Normal"], fontSize=11, leading=16, spaceAfter=12
    )

    for line in complaint_text.split("\n"):
        if line.strip():
            para = Paragraph(line.strip(), content_style)
            story.append(para)
            story.append(Spacer(1, 6))

    # Footer
    footer_text = f"<i>Документ создан {datetime.now().strftime('%d.%m.%Y в %H:%M')}<br/>ZakupAI - система анализа государственных закупок</i>"
    footer = Paragraph(footer_text, styles["Normal"])
    story.append(Spacer(1, 30))
    story.append(footer)

    doc.build(story)
    buffer.seek(0)
    return buffer


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104
