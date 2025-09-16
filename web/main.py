import asyncio
import logging
import os
import time
from io import BytesIO
from pathlib import Path

import httpx
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

# Load environment variables from .env
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104
