import hashlib
import json
import logging
import math
import os
import uuid
from datetime import UTC, datetime
from typing import Annotated

import psycopg2
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

# ---------- минимальное JSON-логирование + request-id ----------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("embedding-api")


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
    except Exception as e:
        log.error(f"Schema creation failed: {e}")
        raise


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


# ---------- FastAPI ----------
app = FastAPI(title="ZakupAI embedding-api", version="0.1.0")


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
    ref_id: Annotated[str, Field(min_length=1)]
    text: Annotated[str, Field(min_length=1)]


class SearchRequest(BaseModel):
    query: Annotated[str, Field(min_length=1)]
    top_k: Annotated[int, Field(ge=1, le=100)] = 10


# ---------- эндпоинты ----------
@app.post("/embed")
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
def index(req: IndexRequest, request: Request):
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
