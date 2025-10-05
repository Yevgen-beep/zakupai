import asyncio
import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

import httpx
import pandas as pd
import redis
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field, validator
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy import (
    and_,
    bindparam,
    case,
    column,
    create_engine,
    func,
    literal,
    literal_column,
    or_,
    select,
    table,
    text,
    true,
)
from sqlalchemy.orm import sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware

from .flowise_endpoints import create_flowise_endpoints

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


lots_table = table(
    "lots",
    column("id"),
    column("nameRu"),
    column("amount"),
    column("descriptionRu"),
    column("trdBuyId"),
    column("lastUpdateDate"),
)

trdbuy_table = table(
    "trdbuy",
    column("id"),
    column("refBuyStatusId"),
    column("customerNameRu"),
    column("nameRu"),
)

# Legacy handle for tests that patch chroma client directly
chroma_client = None


# Redis setup for caching
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

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

# Week 4.2 Configuration
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "5"))
SUPPLIER_CACHE_TTL = int(os.getenv("SUPPLIER_CACHE_TTL", "48"))  # hours
COMPLAINT_CACHE_TTL = int(os.getenv("COMPLAINT_CACHE_TTL", "24"))  # hours

# Scheduler for cleanup tasks
scheduler = AsyncIOScheduler()

# FastAPI app
app = FastAPI(
    title="ZakupAI Web Panel",
    description="Web interface for ZakupAI tender analysis",
    version="1.0.0",
)

# Prometheus instrumentation setup
instrumentator = Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=["/metrics", "/health"],
)
instrumentator.instrument(app).expose(app)

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
                    f"Status must be one of: {', '.join(allowed_statuses)}"
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
            lots_alias = lots_table.alias("l")
            trdbuy_alias = trdbuy_table.alias("t")
            join_clause = lots_alias.join(
                trdbuy_alias, lots_alias.c.trdBuyId == trdbuy_alias.c.id
            )

            query_params = {"query": request.query}
            query_bind = bindparam("query")
            ts_query = func.plainto_tsquery("russian", query_bind)

            query_conditions = [
                lots_alias.c.nameRu.isnot(None),
                lots_alias.c.amount.isnot(None),
                trdbuy_alias.c.refBuyStatusId.isnot(None),
            ]

            if request.query.strip():
                query_conditions.append(
                    or_(
                        func.to_tsvector("russian", lots_alias.c.nameRu).op("@@")(
                            ts_query
                        ),
                        func.to_tsvector(
                            "russian",
                            func.coalesce(lots_alias.c.descriptionRu, literal("")),
                        ).op("@@")(ts_query),
                        func.to_tsvector("russian", trdbuy_alias.c.nameRu).op("@@")(
                            ts_query
                        ),
                    )
                )

            if request.min_amount is not None:
                query_conditions.append(lots_alias.c.amount >= bindparam("min_amount"))
                query_params["min_amount"] = request.min_amount

            if request.max_amount is not None:
                query_conditions.append(lots_alias.c.amount <= bindparam("max_amount"))
                query_params["max_amount"] = request.max_amount

            if request.status is not None:
                query_conditions.append(
                    trdbuy_alias.c.refBuyStatusId == bindparam("status")
                )
                query_params["status"] = int(request.status)

            where_clause = and_(*query_conditions) if query_conditions else true()

            count_stmt = (
                select(func.count()).select_from(join_clause).where(where_clause)
            )

            total_count = db.execute(count_stmt, query_params).scalar()

            search_vector = literal_column(
                "l.nameRu || ' ' || COALESCE(l.descriptionRu, '') || ' ' || COALESCE(t.nameRu, '')"
            )

            relevance_expr = func.ts_rank_cd(
                func.to_tsvector("russian", search_vector),
                ts_query,
                literal(1),
            )

            relevance = case(
                (query_bind != "", relevance_expr),
                else_=literal(1),
            ).label("relevance")

            search_stmt = (
                select(
                    lots_alias.c.id,
                    lots_alias.c.nameRu,
                    lots_alias.c.amount,
                    func.coalesce(trdbuy_alias.c.refBuyStatusId, literal(0)).label(
                        "status"
                    ),
                    lots_alias.c.trdBuyId,
                    trdbuy_alias.c.customerNameRu,
                    relevance,
                )
                .select_from(join_clause)
                .where(where_clause)
                .order_by(
                    relevance.desc(),
                    lots_alias.c.amount.desc(),
                    lots_alias.c.lastUpdateDate.desc().nullslast(),
                )
                .limit(request.limit)
                .offset(request.offset)
            )

            results = db.execute(search_stmt, query_params).fetchall()

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


async def get_chromadb_suggestions(query: str) -> list[str]:
    """
    Legacy alias после удаления ChromaDB.
    Теперь всегда используем SQL fallback.
    """
    return await get_sql_autocomplete_fallback(query)


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


# ---------- Flowise Enhanced Endpoints ----------
create_flowise_endpoints(app, SessionLocal, redis_client)


# ---------- Flowise Helper Functions ----------


class Supplier(BaseModel):
    """Legacy supplier model used by existing helper functions."""

    name: str
    rating: float
    contacts: str
    link: str
    location: str | None = None


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

По лоту: {lot_info["name"]} (ID: {lot_id})
Заказчик: {lot_info["customer"]}
Сумма: {lot_info.get("amount", 0):,.2f} тенге

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
    """Search suppliers using API"""
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

        # ChromaDB suppliers collection removed - using only Satu.kz API results

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


# =============================================================================
# Week 4.1: Web UI Enhancements
# =============================================================================


class CSVImportProgress(BaseModel):
    """WebSocket progress update for CSV import"""

    progress: float = Field(..., ge=0, le=100, description="Progress percentage")
    rows_ok: int = Field(..., ge=0, description="Successfully processed rows")
    rows_error: int = Field(..., ge=0, description="Failed rows")
    current_row: int = Field(default=0, ge=0, description="Current processing row")
    message: str | None = Field(default="", description="Status message")


class ImportLogResponse(BaseModel):
    """Response model for import log"""

    id: int
    file_name: str
    status: str
    total_rows: int
    success_rows: int
    error_rows: int
    error_details: list[dict] | None = None
    processing_time_ms: int | None = None
    imported_at: datetime


class LotSummaryResponse(BaseModel):
    """Response model for lot TL;DR summary"""

    lot_id: int
    summary: str
    source: str  # 'cache', 'flowise', 'fallback'
    cached: bool
    generated_at: datetime


# WebSocket connection manager for CSV import progress
class WSConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info("WebSocket connected", client_id=client_id)

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info("WebSocket disconnected", client_id=client_id)

    async def send_progress(self, client_id: str, progress: CSVImportProgress):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(progress.json())
            except Exception as e:
                logger.error(
                    "Failed to send WebSocket message",
                    client_id=client_id,
                    error=str(e),
                )
                self.disconnect(client_id)


ws_manager = WSConnectionManager()


@app.websocket("/ws/import/{client_id}")
async def websocket_import_progress(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for CSV import progress updates"""
    await ws_manager.connect(websocket, client_id)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)


@app.post("/web-ui/import-prices")
async def import_prices_csv(file: UploadFile = File(...), client_id: str = Form(...)):
    """
    Import prices from CSV file with WebSocket progress updates
    Week 4.1: CSV import ≤5 MB, WebSocket progress, validation
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info(
        "CSV import started",
        request_id=request_id,
        filename=file.filename,
        client_id=client_id,
    )

    # Validate file
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV files are supported")

    # Check file size (5MB limit)
    file_content = await file.read()
    file_size_mb = len(file_content) / (1024 * 1024)
    if file_size_mb > 5:
        raise HTTPException(400, f"File too large: {file_size_mb:.1f}MB (max 5MB)")

    # Create import log
    with SessionLocal() as db:
        log_result = db.execute(
            text(
                """
                INSERT INTO import_logs (file_name, status, file_size_mb)
                VALUES (:filename, 'PROCESSING', :size_mb)
                RETURNING id
            """
            ),
            {"filename": file.filename, "size_mb": file_size_mb},
        )
        log_id = log_result.scalar()
        db.commit()

    # Process CSV in chunks
    try:
        # Reset file pointer
        csv_data = BytesIO(file_content)

        # Validate headers
        df_sample = pd.read_csv(csv_data, nrows=0)
        required_columns = {"product_name", "amount", "supplier_bin"}
        if not required_columns.issubset(df_sample.columns):
            missing = required_columns - set(df_sample.columns)
            raise HTTPException(400, f"Missing required columns: {missing}")

        # Process in chunks
        csv_data.seek(0)
        chunk_size = 1000
        total_rows = 0
        success_rows = 0
        error_rows = 0
        errors = []

        # Count total rows first for progress
        total_df = pd.read_csv(csv_data)
        total_rows = len(total_df)
        csv_data.seek(0)

        row_count = 0
        for chunk_num, chunk in enumerate(pd.read_csv(csv_data, chunksize=chunk_size)):
            chunk_errors = []
            chunk_success = 0

            for _idx, row in chunk.iterrows():
                row_count += 1
                try:
                    # Validate row data
                    product_name = str(row["product_name"]).strip()
                    amount = float(row["amount"])
                    supplier_bin = str(row["supplier_bin"]).strip()

                    # Validation checks
                    if not product_name or product_name == "nan":
                        raise ValueError("product_name cannot be empty")
                    if amount < 0:
                        raise ValueError("amount must be >= 0")
                    if not re.match(r"^[0-9]{12}$", supplier_bin):
                        raise ValueError("supplier_bin must be 12 digits")

                    # Insert to database
                    with SessionLocal() as db:
                        db.execute(
                            text(
                                """
                                INSERT INTO prices (product_name, amount, supplier_bin)
                                VALUES (:name, :amount, :bin)
                            """
                            ),
                            {
                                "name": product_name,
                                "amount": amount,
                                "bin": supplier_bin,
                            },
                        )
                        db.commit()

                    chunk_success += 1

                except Exception as e:
                    error_rows += 1
                    chunk_errors.append(
                        {
                            "row": row_count,
                            "error": str(e),
                            "data": (
                                row.to_dict() if hasattr(row, "to_dict") else str(row)
                            ),
                        }
                    )

            success_rows += chunk_success
            errors.extend(chunk_errors)

            # Send progress update via WebSocket
            progress = (row_count / total_rows) * 100
            progress_update = CSVImportProgress(
                progress=progress,
                rows_ok=success_rows,
                rows_error=error_rows,
                current_row=row_count,
                message=f"Processing chunk {chunk_num + 1}...",
            )
            await ws_manager.send_progress(client_id, progress_update)

            # Small delay to prevent overwhelming
            if chunk_num % 10 == 0:  # Every 10 chunks (10k rows)
                await asyncio.sleep(0.1)

        # Determine final status
        if error_rows == 0:
            final_status = "SUCCESS"
        elif success_rows == 0:
            final_status = "FAILED"
        else:
            final_status = "PARTIAL"

        processing_time_ms = int((time.time() - start_time) * 1000)

        # Update import log
        with SessionLocal() as db:
            db.execute(
                text(
                    """
                    SELECT update_import_status(
                        :log_id, :status, :success, :errors, :error_details, :time_ms
                    )
                """
                ),
                {
                    "log_id": log_id,
                    "status": final_status,
                    "success": success_rows,
                    "errors": error_rows,
                    "error_details": (
                        json.dumps(errors[:100]) if errors else None
                    ),  # Limit errors
                    "time_ms": processing_time_ms,
                },
            )
            db.execute(
                text("UPDATE import_logs SET total_rows = :total WHERE id = :log_id"),
                {"total": total_rows, "log_id": log_id},
            )
            db.commit()

        # Send final progress
        final_progress = CSVImportProgress(
            progress=100.0,
            rows_ok=success_rows,
            rows_error=error_rows,
            current_row=total_rows,
            message=f"Complete! Status: {final_status}",
        )
        await ws_manager.send_progress(client_id, final_progress)

        logger.info(
            "CSV import completed",
            request_id=request_id,
            status=final_status,
            success_rows=success_rows,
            error_rows=error_rows,
            processing_time_ms=processing_time_ms,
        )

        return {
            "import_log_id": log_id,
            "status": final_status,
            "total_rows": total_rows,
            "success_rows": success_rows,
            "error_rows": error_rows,
            "processing_time_ms": processing_time_ms,
            "errors": errors[:10],  # Return first 10 errors only
        }

    except Exception as e:
        # Update log with failure
        with SessionLocal() as db:
            db.execute(
                text(
                    """
                    SELECT update_import_status(
                        :log_id, 'FAILED', 0, 0, :error_details, :time_ms
                    )
                """
                ),
                {
                    "log_id": log_id,
                    "error_details": json.dumps([{"error": str(e)}]),
                    "time_ms": int((time.time() - start_time) * 1000),
                },
            )
            db.commit()

        logger.error(
            "CSV import failed",
            request_id=request_id,
            error=str(e),
            filename=file.filename,
        )

        raise HTTPException(500, f"Import failed: {str(e)}") from e


@app.get("/web-ui/import-status/{log_id}")
async def get_import_status(log_id: int):
    """Get import log status by ID"""
    with SessionLocal() as db:
        result = db.execute(
            text(
                """
                SELECT id, file_name, status, total_rows, success_rows, error_rows,
                       error_details, processing_time_ms, imported_at
                FROM import_logs WHERE id = :log_id
            """
            ),
            {"log_id": log_id},
        ).fetchone()

        if not result:
            raise HTTPException(404, "Import log not found")

        return {
            "id": result[0],
            "file_name": result[1],
            "status": result[2],
            "total_rows": result[3],
            "success_rows": result[4],
            "error_rows": result[5],
            "error_details": json.loads(result[6]) if result[6] else [],
            "processing_time_ms": result[7],
            "imported_at": result[8],
        }


@app.get("/web-ui/lot/{lot_id}")
async def get_lot_tldr(lot_id: int):
    """
    Get lot TL;DR summary with Redis cache and Flowise integration
    Week 4.1: <1 sec, Redis TTL 24h, Flowise fallback
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()

    logger.info("Lot TL;DR request", request_id=request_id, lot_id=lot_id)

    # Check Redis cache first
    cache_key = f"lot_summary:{lot_id}"
    try:
        cached_summary = redis_client.get(cache_key)
        if cached_summary:
            summary_data = json.loads(cached_summary)
            logger.info(
                "TL;DR cache hit",
                request_id=request_id,
                lot_id=lot_id,
                latency_ms=int((time.time() - start_time) * 1000),
            )

            return LotSummaryResponse(
                lot_id=lot_id,
                summary=summary_data["summary"],
                source="cache",
                cached=True,
                generated_at=datetime.fromisoformat(summary_data["generated_at"]),
            )
    except Exception as e:
        logger.warning("Redis cache error", error=str(e))

    # Get lot data from database
    with SessionLocal() as db:
        lot_result = db.execute(
            text(
                """
                SELECT l.id, l.nameRu, l.amount, COALESCE(t.refBuyStatusId, 0) as status,
                       t.customerNameRu
                FROM lots l
                LEFT JOIN trdbuy t ON l.trdBuyId = t.id
                WHERE l.id = :lot_id
            """
            ),
            {"lot_id": lot_id},
        ).fetchone()

        if not lot_result:
            raise HTTPException(404, "Lot not found")

    lot_name = lot_result[1] or "Без названия"
    lot_amount = lot_result[2] or 0
    lot_status = lot_result[3]
    customer_name = lot_result[4] or "Неизвестно"

    # Status mapping
    status_names = {
        1: "ACTIVE",
        2: "COMPLETED",
        3: "CANCELLED",
        4: "DRAFT",
        5: "PUBLISHED",
        0: "UNKNOWN",
    }
    status_name = status_names.get(lot_status, "UNKNOWN")

    # Try Flowise summarizer
    summary = None
    source = "fallback"

    try:
        flowise_prompt = f"""Summarize lot {lot_id}: {lot_name}, {lot_amount} тенге, status: {status_name}, customer: {customer_name}.
        Create concise summary ≤500 characters in Russian focusing on key details for procurement analysis."""

        async with httpx.AsyncClient(timeout=3.0) as client:
            flowise_response = await client.post(
                f"{FLOWISE_API_URL}/api/v1/prediction/lot-summarizer",
                json={
                    "question": flowise_prompt,
                    "overrideConfig": {"temperature": 0.3, "maxTokens": 150},
                },
                headers={"Content-Type": "application/json"},
            )

            if flowise_response.status_code == 200:
                flowise_data = flowise_response.json()
                summary = flowise_data.get("text", "").strip()
                if summary and len(summary) <= 500:
                    source = "flowise"
                    logger.info(
                        "Flowise TL;DR success", request_id=request_id, lot_id=lot_id
                    )
    except Exception as e:
        logger.warning("Flowise TL;DR failed", request_id=request_id, error=str(e))

    # Fallback summary if Flowise failed
    if not summary or source == "fallback":
        summary = f"Лот {lot_id}: {lot_name[:100]}{'...' if len(lot_name) > 100 else ''}, {lot_amount:,.0f} ₸, {status_name}, Заказчик: {customer_name[:50]}"
        source = "fallback"

    # Cache successful result
    try:
        cache_data = {
            "summary": summary,
            "source": source,
            "generated_at": datetime.now().isoformat(),
        }
        redis_client.setex(cache_key, 86400, json.dumps(cache_data))  # 24h TTL
    except Exception as e:
        logger.warning("Redis cache set error", error=str(e))

    processing_time_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "TL;DR generated",
        request_id=request_id,
        lot_id=lot_id,
        source=source,
        latency_ms=processing_time_ms,
    )

    return LotSummaryResponse(
        lot_id=lot_id,
        summary=summary,
        source=source,
        cached=False,
        generated_at=datetime.now(),
    )


@app.get("/api/search/autocomplete")
async def search_autocomplete(query: str):
    """
    Search autocomplete with SQL fallback
    Week 4.1: ≥2 chars, ≤500ms, Cyrillic support, Redis cache
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()

    # Validate query
    if len(query) < 2:
        return {"suggestions": []}

    # Normalize query: trim, lowercase, filter non-letters/spaces
    normalized_query = re.sub(r"[^\w\sа-яё]", "", query.lower().strip())
    if not normalized_query:
        return {"suggestions": []}

    logger.info(
        "Autocomplete request",
        request_id=request_id,
        query=query,
        normalized=normalized_query,
    )

    # Check Redis cache
    cache_key = f"autocomplete:{hashlib.md5(normalized_query.encode(), usedforsecurity=False).hexdigest()}"
    try:
        cached_suggestions = redis_client.get(cache_key)
        if cached_suggestions:
            suggestions = json.loads(cached_suggestions)
            logger.info(
                "Autocomplete cache hit",
                request_id=request_id,
                query=normalized_query,
                suggestions_count=len(suggestions),
                latency_ms=int((time.time() - start_time) * 1000),
            )
            return {"suggestions": suggestions}
    except Exception as e:
        logger.warning("Redis autocomplete cache error", error=str(e))

    # Use get_chromadb_suggestions which now internally calls SQL fallback
    suggestions = await get_chromadb_suggestions(normalized_query)

    logger.info(
        "Autocomplete suggestions retrieved",
        request_id=request_id,
        suggestions_count=len(suggestions),
    )

    # Cache results
    try:
        if suggestions:
            redis_client.setex(cache_key, 86400, json.dumps(suggestions))  # 24h TTL
    except Exception as e:
        logger.warning("Autocomplete cache set error", error=str(e))

    processing_time_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "Autocomplete completed",
        request_id=request_id,
        query=normalized_query,
        suggestions_count=len(suggestions),
        latency_ms=processing_time_ms,
    )

    return {"suggestions": suggestions}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104
