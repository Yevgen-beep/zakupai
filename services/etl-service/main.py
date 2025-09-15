import io
import logging
import math
import os
import tempfile
import zipfile
from pathlib import Path

import aiohttp
import fitz  # PyMuPDF
import psycopg2
import psycopg2.extras
import pytesseract
from dotenv import load_dotenv
from etl import ETLService
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from PIL import Image
from pydantic import BaseModel, Field

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ETL Service",
    description="ETL service for ZakupAI platform - loads data from Kazakhstan Government Procurement GraphQL API to PostgreSQL",
    version="1.0.0",
)

# Constants
MAX_FILE_SIZE_MB = 50
ALLOWED_EXTENSIONS = {".pdf", ".zip"}
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


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


class ProcessedFile(BaseModel):
    file_name: str
    file_type: str
    content_preview: str


class UploadResponse(BaseModel):
    status: str
    files: list[ProcessedFile]


class OCRHealthResponse(BaseModel):
    status: str
    tesseract_available: bool = False
    message: str


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query text")
    collection: str = Field(
        default="etl_documents", description="ChromaDB collection name"
    )
    top_k: int = Field(
        default=5, ge=1, le=20, description="Number of results to return"
    )


class SearchResult(BaseModel):
    doc_id: str
    file_name: str
    score: float
    metadata: dict
    content_preview: str | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total_found: int


async def process_pdf_ocr(file_path: Path, file_name: str) -> str:
    """
    Process PDF file with OCR using PyMuPDF and Tesseract

    Args:
        file_path: Path to the PDF file
        file_name: Original file name

    Returns:
        Extracted text content
    """
    try:
        # Try to extract text directly from PDF first
        doc = fitz.open(file_path)
        text_content = []

        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)

            # Try to get text directly
            page_text = page.get_text("text").strip()

            if page_text and len(page_text) > 50:  # PDF has readable text
                text_content.append(page_text)
                logger.info(f"Extracted text from page {page_num + 1} of {file_name}")
            else:
                # PDF is likely a scan, use OCR
                logger.info(f"Running OCR on page {page_num + 1} of {file_name}")
                try:
                    # Get page as image
                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(2.0, 2.0)
                    )  # 2x scaling for better OCR
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))

                    # Run Tesseract OCR
                    ocr_text = pytesseract.image_to_string(
                        img, lang="rus+eng", config="--oem 3 --psm 6"
                    ).strip()

                    if ocr_text:
                        text_content.append(ocr_text)
                        logger.info(
                            f"OCR extracted {len(ocr_text)} characters from page {page_num + 1}"
                        )
                    else:
                        logger.warning(
                            f"No text extracted from page {page_num + 1} of {file_name}"
                        )

                except Exception as ocr_error:
                    logger.error(
                        f"OCR failed for page {page_num + 1} of {file_name}: {ocr_error}"
                    )
                    # Continue with other pages (fail-soft)
                    continue

        doc.close()

        # Combine all pages
        full_text = "\n\n".join(text_content)

        if not full_text.strip():
            logger.warning(f"No text extracted from {file_name}")
            return "[No text content extracted]"

        logger.info(
            f"Successfully extracted {len(full_text)} characters from {file_name}"
        )
        return full_text

    except Exception as e:
        logger.error(f"PDF processing failed for {file_name}: {e}")
        raise HTTPException(
            status_code=500, detail=f"PDF processing failed: {str(e)}"
        ) from e


async def save_to_postgres(
    file_name: str, file_type: str, content: str, lot_id: str | None = None
) -> int:
    """
    Save processed document to PostgreSQL

    Args:
        file_name: Original file name
        file_type: File type (pdf, etc.)
        content: Extracted text content
        lot_id: Optional lot identifier

    Returns:
        Document ID
    """
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise HTTPException(
                status_code=500, detail="DATABASE_URL environment variable not found"
            )

        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        # Insert with ON CONFLICT to handle duplicates
        cursor.execute(
            """
            INSERT INTO etl_documents (lot_id, file_name, file_type, content)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (lot_id, file_name)
            DO UPDATE SET
                file_type = EXCLUDED.file_type,
                content = EXCLUDED.content,
                created_at = now()
            RETURNING id
            """,
            (lot_id, file_name, file_type, content),
        )

        doc_id = cursor.fetchone()[0]
        conn.commit()

        cursor.close()
        conn.close()

        logger.info(f"Saved document {file_name} to PostgreSQL with ID {doc_id}")
        return doc_id

    except Exception as e:
        logger.error(f"PostgreSQL save failed for {file_name}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Database save failed: {str(e)}"
        ) from e


async def index_in_chromadb(
    doc_id: int, file_name: str, content: str, lot_id: str | None = None
) -> bool:
    """
    Index document content in ChromaDB via embedding-api

    Args:
        doc_id: Document ID from PostgreSQL
        file_name: Original file name
        content: Document content to index
        lot_id: Optional lot identifier

    Returns:
        Success status
    """
    try:
        embedding_api_url = os.getenv("EMBEDDING_API_URL", "http://localhost:8004")

        # Prepare metadata
        metadata = {"doc_id": doc_id, "file_name": file_name, "source": "etl_documents"}
        if lot_id:
            metadata["lot_id"] = lot_id

        # Index in ChromaDB
        index_payload = {
            "ref_id": f"etl_doc:{doc_id}",
            "text": content[:5000],  # Limit text size for embedding
            "metadata": metadata,
            "collection": "etl_documents",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{embedding_api_url}/index",
                json=index_payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    logger.info(f"Successfully indexed {file_name} in ChromaDB")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(
                        f"ChromaDB indexing failed for {file_name}: {error_text}"
                    )
                    return False

    except Exception as e:
        logger.error(f"ChromaDB indexing failed for {file_name}: {e}")
        # Don't raise exception - indexing failure shouldn't break the upload
        return False


def check_env_variables():
    """Check if required environment variables are present"""
    api_token = os.getenv("GOSZAKUP_TOKEN")
    database_url = os.getenv("DATABASE_URL")

    if not api_token:
        raise HTTPException(
            status_code=500, detail="GOSZAKUP_TOKEN environment variable not found"
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


@app.get("/etl/ocr", response_model=OCRHealthResponse)
async def ocr_health():
    """OCR service health check and Tesseract availability"""
    try:
        import subprocess  # nosec B404 - subprocess needed for tesseract check

        # Try to call tesseract
        result = subprocess.run(  # nosec B603 B607 - tesseract command is safe
            ["tesseract", "--version"], capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            logger.info("Tesseract OCR is available")
            return OCRHealthResponse(
                status="ready",
                tesseract_available=True,
                message="Tesseract OCR ready for processing",
            )
        else:
            logger.warning("Tesseract command failed")
            return OCRHealthResponse(
                status="not_ready",
                tesseract_available=False,
                message="Tesseract command failed",
            )

    except ImportError:
        logger.warning("pytesseract not installed")
        return OCRHealthResponse(
            status="not_implemented",
            tesseract_available=False,
            message="pytesseract not installed",
        )
    except subprocess.TimeoutExpired:
        logger.warning("Tesseract timeout")
        return OCRHealthResponse(
            status="timeout",
            tesseract_available=False,
            message="Tesseract command timeout",
        )
    except FileNotFoundError:
        logger.warning("Tesseract not found in system")
        return OCRHealthResponse(
            status="not_implemented",
            tesseract_available=False,
            message="Tesseract not found in system - install tesseract-ocr package",
        )
    except Exception as e:
        logger.error(f"OCR health check failed: {e}")
        return OCRHealthResponse(
            status="error",
            tesseract_available=False,
            message=f"Error checking Tesseract: {str(e)}",
        )


@app.post("/etl/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...), lot_id: str | None = None):
    """
    Upload and process PDF or ZIP files with OCR

    - **file**: PDF or ZIP file (max 50MB)
    - **lot_id**: Optional lot identifier for document association
    - **Returns**: JSON with processed files and content previews

    Supported formats: .pdf, .zip
    Processing: PyMuPDF text extraction + Tesseract OCR for scans
    Storage: PostgreSQL + ChromaDB indexing
    """

    try:
        # Validate file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning

        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE_MB}MB, got: {file_size / 1024 / 1024:.1f}MB",
            )

        # Validate file extension
        file_path = Path(file.filename) if file.filename else Path("unknown")
        file_extension = file_path.suffix.lower()

        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_extension}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            )

        logger.info(
            f"Processing upload: {file.filename} ({file_size / 1024 / 1024:.1f}MB)"
        )

        processed_files = []

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            if file_extension == ".zip":
                # Handle ZIP files
                zip_path = temp_dir_path / file.filename
                with zip_path.open("wb") as buffer:
                    content = await file.read()
                    buffer.write(content)

                try:
                    with zipfile.ZipFile(zip_path, "r") as zip_ref:
                        # Extract all PDF files
                        for zip_file in zip_ref.namelist():
                            if zip_file.endswith("/") or zip_file.startswith("."):
                                continue

                            zip_file_path = Path(zip_file)
                            if zip_file_path.suffix.lower() == ".pdf":
                                # Extract file
                                extracted_path = temp_dir_path / zip_file_path.name
                                with (
                                    zip_ref.open(zip_file) as source,
                                    extracted_path.open("wb") as target,
                                ):
                                    target.write(source.read())

                                # Process PDF with OCR
                                try:
                                    content = await process_pdf_ocr(
                                        extracted_path, zip_file_path.name
                                    )

                                    # Save to PostgreSQL
                                    doc_id = await save_to_postgres(
                                        zip_file_path.name, "pdf", content, lot_id
                                    )

                                    # Index in ChromaDB
                                    await index_in_chromadb(
                                        doc_id, zip_file_path.name, content, lot_id
                                    )

                                    # Add to results
                                    processed_files.append(
                                        ProcessedFile(
                                            file_name=zip_file_path.name,
                                            file_type="pdf",
                                            content_preview=(
                                                content[:200] + "..."
                                                if len(content) > 200
                                                else content
                                            ),
                                        )
                                    )

                                except Exception as process_error:
                                    logger.error(
                                        f"Failed to process {zip_file_path.name}: {process_error}"
                                    )
                                    # Add failed file to results
                                    processed_files.append(
                                        ProcessedFile(
                                            file_name=zip_file_path.name,
                                            file_type="pdf",
                                            content_preview="[Processing failed]",
                                        )
                                    )

                        if not processed_files:
                            logger.warning(
                                f"No PDF files found in ZIP: {file.filename}"
                            )
                            return UploadResponse(status="error", files=[])

                except zipfile.BadZipFile as e:
                    logger.error(f"Invalid ZIP file: {file.filename}")
                    raise HTTPException(
                        status_code=400, detail="Invalid or corrupted ZIP file"
                    ) from e

            elif file_extension == ".pdf":
                # Handle single PDF file
                pdf_path = temp_dir_path / file.filename
                with pdf_path.open("wb") as buffer:
                    content = await file.read()
                    buffer.write(content)

                # Process PDF with OCR
                content = await process_pdf_ocr(pdf_path, file.filename)

                # Save to PostgreSQL
                doc_id = await save_to_postgres(file.filename, "pdf", content, lot_id)

                # Index in ChromaDB
                await index_in_chromadb(doc_id, file.filename, content, lot_id)

                # Add to results
                processed_files.append(
                    ProcessedFile(
                        file_name=file.filename,
                        file_type="pdf",
                        content_preview=(
                            content[:200] + "..." if len(content) > 200 else content
                        ),
                    )
                )

            else:
                raise HTTPException(
                    status_code=400, detail=f"Unexpected file type: {file_extension}"
                )

        logger.info(f"Successfully processed {len(processed_files)} files")
        return UploadResponse(status="ok", files=processed_files)

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Upload processing failed for {file.filename}: {e}")
        raise HTTPException(
            status_code=500, detail=f"File processing failed: {str(e)}"
        ) from e


@app.post("/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    """
    Search documents in ChromaDB collection

    - **query**: Text to search for
    - **collection**: ChromaDB collection name (default: etl_documents)
    - **top_k**: Number of results to return (1-20, default: 5)

    Returns documents with similarity scores and metadata
    """
    try:
        embedding_api_url = os.getenv("EMBEDDING_API_URL", "http://localhost:7010")

        search_payload = {
            "query": request.query,
            "top_k": request.top_k,
            "collection": request.collection,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{embedding_api_url}/search",
                json=search_payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    search_data = await response.json()

                    results = []
                    for item in search_data.get("results", []):
                        # Extract document info from ChromaDB results
                        metadata = item.get("metadata", {})
                        doc_id = metadata.get("doc_id", "unknown")
                        file_name = metadata.get("file_name", "unknown")

                        # Get content preview from PostgreSQL if doc_id available
                        content_preview = None
                        if doc_id != "unknown" and doc_id.startswith("etl_doc:"):
                            try:
                                db_doc_id = int(doc_id.split(":")[-1])
                                content_preview = await get_document_preview(db_doc_id)
                            except (ValueError, IndexError):
                                pass

                        results.append(
                            SearchResult(
                                doc_id=item.get("id", doc_id),
                                file_name=file_name,
                                score=item.get("score", 0.0),
                                metadata=metadata,
                                content_preview=content_preview,
                            )
                        )

                    return SearchResponse(
                        query=request.query, results=results, total_found=len(results)
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"ChromaDB search failed: {error_text}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Search service unavailable: {error_text}",
                    )

    except aiohttp.ClientError as e:
        logger.error(f"ChromaDB connection failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Search service unavailable - ChromaDB connection failed",
        ) from e
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}") from e


async def get_document_preview(doc_id: int, max_length: int = 200) -> str | None:
    """
    Get document content preview from PostgreSQL

    Args:
        doc_id: Document ID
        max_length: Maximum length of preview text

    Returns:
        Content preview or None if not found
    """
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            return None

        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        cursor.execute("SELECT content FROM etl_documents WHERE id = %s", (doc_id,))

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result and result[0]:
            content = result[0]
            if len(content) > max_length:
                return content[:max_length] + "..."
            return content

        return None

    except Exception as e:
        logger.error(f"Failed to get document preview for ID {doc_id}: {e}")
        return None


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
