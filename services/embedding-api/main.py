import hashlib
import json
import logging
import math
import os
import time
import uuid
from datetime import UTC, datetime
from typing import Annotated

import chromadb
import psycopg2
from chromadb import Settings
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse

from zakupai_common.vault_client import VaultClientError, load_kv_to_env
from zakupai_common.fastapi.metrics import add_prometheus_middleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from exceptions import validation_exception_handler, rate_limit_handler

# ---------- минимальное JSON-логирование + request-id ----------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("embedding-api")


def bootstrap_vault():
    """Load secrets from Vault, fallback to .env if not available."""
    try:
        db_secret = load_kv_to_env("db")
        os.environ.setdefault("DB_USER", db_secret.get("POSTGRES_USER", ""))
        os.environ.setdefault("DB_PASSWORD", db_secret.get("POSTGRES_PASSWORD", ""))
        os.environ.setdefault("DB_NAME", db_secret.get("POSTGRES_DB", ""))
        os.environ.setdefault("DATABASE_URL", db_secret.get("DATABASE_URL", ""))

        load_kv_to_env("api", mapping={"API_KEY": "API_KEY"})
        log.info("Vault bootstrap success: secrets loaded")
    except VaultClientError as exc:
        log.warning(f"Vault load failed: {exc}. Using .env fallback.")
    except Exception as exc:
        log.warning(f"Unexpected Vault error: {exc}. Using .env fallback.")


bootstrap_vault()

SERVICE_NAME = "embedding"


def get_request_id(x_request_id: str | None) -> str:
    try:
        return str(uuid.UUID(x_request_id)) if x_request_id else str(uuid.uuid4())
    except Exception:
        return str(uuid.uuid4())


# ---------- DB helpers ----------
def _dsn_for(host: str) -> str:
    return "host={h} port={p} dbname={db} user={u} password={pw}".format(
        h=host,
        p=os.getenv("DB_PORT", "5432"),
        db=os.getenv("DB_NAME", "zakupai"),
        u=os.getenv("DB_USER", "zakupai"),
        pw=os.getenv("DB_PASSWORD", "zakupai"),
    )


def get_conn():
    candidates = []
    if os.getenv("DB_HOST"):
        candidates.append(os.getenv("DB_HOST"))
    candidates += ["zakupai-db", "db", "localhost"]
    last_err = None
    for host in candidates:
        try:
            conn = psycopg2.connect(_dsn_for(host))
            return conn
        except Exception as e:
            last_err = e
            log.warning(f"DB connect failed for host '{host}': {e}")
    raise last_err or RuntimeError("DB connection failed")


def ensure_schema():
    """Создаёт таблицу embeddings если её нет"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS embeddings (
                        id SERIAL PRIMARY KEY,
                        ref_id TEXT,
                        text TEXT,
                        vector JSONB,
                        created_at TIMESTAMPTZ DEFAULT now()
                    )
                """
                )
                # Also ensure audit_logs table
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id bigserial PRIMARY KEY,
                        service text NOT NULL,
                        route text NOT NULL,
                        method text NOT NULL,
                        status int NOT NULL,
                        req_id text,
                        ip text,
                        duration_ms int,
                        payload_hash text,
                        error text,
                        created_at timestamp DEFAULT now()
                    );
                """
                )
    except Exception as e:
        log.error(f"Schema creation failed: {e}")
        raise


def save_audit_log(
    service: str,
    route: str,
    method: str,
    status: int,
    req_id: str | None,
    ip: str | None,
    duration_ms: int,
    payload_hash: str | None,
    error: str | None = None,
) -> None:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_logs(service, route, method, status, req_id, ip, duration_ms, payload_hash, error)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        service,
                        route,
                        method,
                        status,
                        req_id,
                        ip,
                        duration_ms,
                        payload_hash,
                        error,
                    ),
                )
    except Exception as e:
        log.warning(f"audit_logs insert failed: {e}")


# ---------- ChromaDB helpers ----------
def get_chroma_client():
    """Получение клиента ChromaDB"""
    chroma_host = os.getenv("CHROMADB_HOST", "chromadb")
    chroma_port = int(os.getenv("CHROMADB_PORT", "8000"))

    return chromadb.HttpClient(
        host=chroma_host,
        port=chroma_port,
        settings=Settings(anonymized_telemetry=False, allow_reset=True),
    )


# ---------- Vector helpers ----------
def text_to_vector(text: str, dim: int = 128) -> list[float]:
    """Детерминированный вектор из текста через SHA256"""
    hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()
    vector = []
    for i in range(dim):
        byte_idx = i % len(hash_bytes)
        vector.append(hash_bytes[byte_idx] / 255.0)
    return vector


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Косинусная близость двух векторов"""
    if len(vec1) != len(vec2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        start_time = time.perf_counter()

        # Get request info
        req_id = request.headers.get("x-request-id") or None
        xff = request.headers.get("x-forwarded-for")
        ip = (
            xff.split(",")[0].strip()
            if xff
            else (request.client.host if request.client else None)
        )

        # Read body for hash
        body = await request.body()
        payload_hash = hashlib.sha256(body[:8192]).hexdigest()[:16] if body else None

        # Process request
        error = None
        try:
            response = await call_next(request)
            status = response.status_code
        except HTTPException as e:
            status = e.status_code
            error = str(e.detail)
            response = Response(
                content=json.dumps({"detail": e.detail}),
                status_code=status,
                media_type="application/json",
            )
        except Exception as e:
            status = 500
            error = str(e)
            response = Response(
                content=json.dumps({"detail": "Internal server error"}),
                status_code=status,
                media_type="application/json",
            )

        # Calculate duration
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Save audit log
        try:
            save_audit_log(
                service="embedding-api",
                route=request.url.path,
                method=request.method,
                status=status,
                req_id=req_id,
                ip=ip,
                duration_ms=duration_ms,
                payload_hash=payload_hash,
                error=error,
            )
        except Exception as e:
            log.warning(f"audit log save failed: {e}")

        response.headers["X-Request-Id"] = req_id or str(uuid.uuid4())
        return response


# ---------- FastAPI ----------
app = FastAPI(
    title="ZakupAI embedding-api",
    version="0.1.0",
    root_path="/emb",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Stage 7 Phase 1 — Rate Limiter Initialization
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Register centralized exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# Stage 7 Phase 1 — Payload size limiter
class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    MAX_SIZE = 2 * 1024 * 1024  # 2 MB
    async def dispatch(self, request, call_next):
        if request.url.path in ["/health", "/metrics", "/docs", "/openapi.json", "/emb/health", "/emb/metrics", "/emb/docs", "/emb/openapi.json"]:
          return await call_next(request)
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_SIZE:
          return JSONResponse(status_code=413, content={"detail": "Payload Too Large"})
        return await call_next(request)

app.add_middleware(PayloadSizeLimitMiddleware)

# Add audit middleware
app.add_middleware(AuditMiddleware)
add_prometheus_middleware(app, SERVICE_NAME)


@app.on_event("startup")
async def startup_event():
    ensure_schema()


@app.middleware("http")
async def add_request_id_and_log(request: Request, call_next):
    rid = get_request_id(request.headers.get("X-Request-Id"))
    request.state.rid = rid
    response = await call_next(request)
    response.headers["X-Request-Id"] = rid
    return response


@app.get("/health")
def health():
    return {"status": "ok", "service": "embedding-api"}


@app.get("/info")
def info(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    if x_api_key != os.getenv("API_KEY", "dev-key"):
        raise HTTPException(status_code=401, detail="unauthorized")
    return {"service": "embedding-api", "version": "0.1.0"}


# ---------- схемы ----------
class EmbedRequest(BaseModel):
    text: Annotated[str, Field(min_length=1)]
    dim: Annotated[int, Field(ge=1, le=1024)] = 128


class IndexRequest(BaseModel):
    ref_id: Annotated[str, Field(min_length=1, max_length=128)]
    text: Annotated[str, Field(min_length=1, max_length=8000)]


class SearchRequest(BaseModel):
    query: Annotated[str, Field(min_length=1, max_length=2000)]
    top_k: Annotated[int, Field(ge=1, le=20)] = 10


class ChromaIndexRequest(BaseModel):
    collection_name: str = "lots"
    document_id: str
    text: str
    metadata: dict | None = None


class ChromaSearchRequest(BaseModel):
    collection_name: str = "lots"
    query: str
    top_k: int = 10
    where: dict | None = None


# ---------- эндпоинты ----------
@app.post("/embed")
@limiter.limit("30/minute")
def embed(req: EmbedRequest, request: Request):
    rid = request.state.rid

    vector = text_to_vector(req.text, req.dim)

    return {
        "vector": vector,
        "dim": req.dim,
        "text_length": len(req.text),
        "request_id": rid,
        "ts": datetime.now(UTC).isoformat(),
    }


@app.post("/index")
@limiter.limit("30/minute")
def index(req: IndexRequest, request: Request):
    if len(req.text) > 8000:
        raise HTTPException(status_code=413, detail="Text too large")
    rid = request.state.rid

    try:
        vector = text_to_vector(req.text)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO embeddings(ref_id, text, vector)
                    VALUES (%s, %s, %s::jsonb)
                    RETURNING id
                """,
                    (req.ref_id, req.text, json.dumps(vector)),
                )

                inserted_id = cur.fetchone()[0]

        return {
            "id": inserted_id,
            "ref_id": req.ref_id,
            "vector_dim": len(vector),
            "request_id": rid,
            "ts": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        log.error(f"Index operation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Index failed: {e}") from e


@app.post("/search")
@limiter.limit("30/minute")
def search(req: SearchRequest, request: Request):
    rid = request.state.rid

    try:
        query_vector = text_to_vector(req.query)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ref_id, text, vector FROM embeddings")
                rows = cur.fetchall()

        results = []
        for ref_id, text, vector_json in rows:
            try:
                # vector_json уже десериализован из JSONB
                stored_vector = (
                    vector_json
                    if isinstance(vector_json, list)
                    else json.loads(vector_json)
                )
                score = cosine_similarity(query_vector, stored_vector)
                results.append(
                    {
                        "ref_id": ref_id,
                        "score": round(score, 4),
                        "text_preview": text[:100] + "..." if len(text) > 100 else text,
                    }
                )
            except Exception as e:
                log.warning(f"Failed to process embedding {ref_id}: {e}")

        # Сортировка по убыванию score и ограничение top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[: req.top_k]

        return {
            "results": results,
            "query": req.query,
            "top_k": req.top_k,
            "total_found": len(results),
            "request_id": rid,
            "ts": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        log.error(f"Search operation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {e}") from e


# ---------- ChromaDB эндпоинты ----------
@app.post("/chroma/index")
@limiter.limit("30/minute")
async def chroma_index(req: ChromaIndexRequest, request: Request):
    """Индексация документа в ChromaDB"""
    rid = request.state.rid

    try:
        client = get_chroma_client()

        # Создать или получить коллекцию
        try:
            collection = client.get_collection(req.collection_name)
        except Exception as e:
            log.info(
                f"Collection {req.collection_name} not found, creating new one: {e}"
            )
            collection = client.create_collection(
                name=req.collection_name,
                metadata={"description": f"Collection for {req.collection_name}"},
            )

        # Добавить документ
        collection.add(
            documents=[req.text], ids=[req.document_id], metadatas=[req.metadata or {}]
        )

        return {
            "success": True,
            "collection_name": req.collection_name,
            "document_id": req.document_id,
            "text_length": len(req.text),
            "request_id": rid,
            "ts": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        log.error(f"ChromaDB index failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"ChromaDB index failed: {e}"
        ) from e


@app.post("/chroma/search")
@limiter.limit("30/minute")
async def chroma_search(req: ChromaSearchRequest, request: Request):
    """Семантический поиск в ChromaDB"""
    rid = request.state.rid

    try:
        client = get_chroma_client()

        # Получить коллекцию
        try:
            collection = client.get_collection(req.collection_name)
        except Exception as e:
            log.error(f"Failed to get collection '{req.collection_name}': {e}")
            raise HTTPException(
                status_code=404, detail=f"Collection '{req.collection_name}' not found"
            ) from e

        # Выполнить поиск
        results = collection.query(
            query_texts=[req.query], n_results=req.top_k, where=req.where
        )

        # Форматировать результаты
        formatted_results = []
        if results["documents"] and len(results["documents"]) > 0:
            for i, doc in enumerate(results["documents"][0]):
                formatted_results.append(
                    {
                        "id": results["ids"][0][i] if results["ids"] else None,
                        "text": doc,
                        "score": (
                            1 - results["distances"][0][i]
                            if results["distances"]
                            else None
                        ),
                        "metadata": (
                            results["metadatas"][0][i] if results["metadatas"] else {}
                        ),
                    }
                )

        return {
            "results": formatted_results,
            "collection_name": req.collection_name,
            "query": req.query,
            "total_found": len(formatted_results),
            "request_id": rid,
            "ts": datetime.now(UTC).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"ChromaDB search failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"ChromaDB search failed: {e}"
        ) from e


@app.get("/chroma/collections")
async def list_collections(request: Request):
    """Список всех коллекций в ChromaDB"""
    rid = request.state.rid

    try:
        client = get_chroma_client()
        collections = client.list_collections()

        return {
            "collections": [
                {"name": col.name, "metadata": col.metadata} for col in collections
            ],
            "count": len(collections),
            "request_id": rid,
            "ts": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        log.error(f"ChromaDB list collections failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"ChromaDB operation failed: {e}"
        ) from e


@app.delete("/chroma/collections/{collection_name}")
async def delete_collection(collection_name: str, request: Request):
    """Удаление коллекции из ChromaDB"""
    rid = request.state.rid

    try:
        client = get_chroma_client()
        client.delete_collection(collection_name)

        return {
            "success": True,
            "collection_name": collection_name,
            "request_id": rid,
            "ts": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        log.error(f"ChromaDB delete collection failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"ChromaDB operation failed: {e}"
        ) from e


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
