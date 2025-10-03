import hashlib
import json
import logging
import os
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

import psycopg2
from fastapi import FastAPI, Header, HTTPException, Request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from services.common.vault_client import VaultClientError, load_kv_to_env
from zakupai_common.fastapi.metrics import add_prometheus_middleware

# ---------- минимальное JSON-логирование + request-id ----------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("calc-service")


def bootstrap_vault():
    try:
        db_secret = load_kv_to_env("db")
        # Ensure compatibility variables for legacy code
        os.environ.setdefault("DB_USER", db_secret.get("POSTGRES_USER", ""))
        os.environ.setdefault("DB_PASSWORD", db_secret.get("POSTGRES_PASSWORD", ""))
        os.environ.setdefault("DB_NAME", db_secret.get("POSTGRES_DB", ""))
        os.environ.setdefault("DATABASE_URL", db_secret.get("DATABASE_URL", ""))
        os.environ.setdefault("POSTGRES_USER", db_secret.get("POSTGRES_USER", ""))
        os.environ.setdefault(
            "POSTGRES_PASSWORD", db_secret.get("POSTGRES_PASSWORD", "")
        )
        os.environ.setdefault("POSTGRES_DB", db_secret.get("POSTGRES_DB", ""))
        load_kv_to_env("api", mapping={"API_KEY": "API_KEY"})
    except VaultClientError as exc:
        log.warning("Vault bootstrap skipped: %s", exc)
    except Exception as exc:  # pragma: no cover - defensive fallback
        log.error("Vault bootstrap failed", exc_info=exc)


bootstrap_vault()

SERVICE_NAME = "calc"


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
    # Порядок попыток: из ENV, затем наиболее вероятные имена в сети compose
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


def ensure_audit_schema():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
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
        log.warning(f"audit schema setup failed: {e}")


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


def save_finance_calc(lot_id: int | None, input_payload: dict, results: dict):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_calcs(lot_id, input, results, created_at)
                    VALUES (%s, %s::jsonb, %s::jsonb, now())
                    """,
                    (
                        lot_id,
                        json.dumps(input_payload, ensure_ascii=False, default=str),
                        json.dumps(results, ensure_ascii=False, default=str),
                    ),
                )
    except Exception as e:
        log.warning(f"finance_calcs insert failed: {e}")


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

        # Save audit log in background
        try:
            save_audit_log(
                service="calc-service",
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
    title="ZakupAI calc-service",
    version="0.1.1",
    root_path="/calc",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Add audit middleware
app.add_middleware(AuditMiddleware)
add_prometheus_middleware(app, SERVICE_NAME)


# Ensure audit schema on startup
@app.on_event("startup")
def startup_event():
    ensure_audit_schema()


@app.middleware("http")
async def add_request_id_and_log(request: Request, call_next):
    rid = get_request_id(request.headers.get("X-Request-Id"))
    request.state.rid = rid
    response = await call_next(request)
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/info")
def info(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    if x_api_key != os.getenv("API_KEY", "dev-key"):
        raise HTTPException(status_code=401, detail="unauthorized")
    return {"service": "calc-service", "version": "0.1.1"}


# ---------- схемы ----------
class VatRequest(BaseModel):
    amount: Annotated[Decimal, Field(gt=0)]
    vat_rate: Annotated[Decimal, Field(ge=0, le=20)] = Decimal("12")
    include_vat: bool = True
    lot_id: Annotated[int, Field(ge=1)] | None = None


class MarginRequest(BaseModel):
    lot_price: Annotated[Decimal, Field(ge=0)]
    cost: Annotated[Decimal, Field(ge=0)]
    logistics: Annotated[Decimal, Field(ge=0)] = Decimal("0")
    vat_rate: Annotated[Decimal, Field(ge=0, le=20)] = Decimal("12")
    price_includes_vat: bool = True
    lot_id: Annotated[int, Field(ge=1)] | None = None


class PenaltyRequest(BaseModel):
    contract_sum: Annotated[Decimal, Field(ge=0)]
    days_overdue: Annotated[int, Field(ge=0)] = 0
    daily_rate_pct: Annotated[Decimal, Field(ge=0, le=5)] = Decimal("0.1")
    lot_id: Annotated[int, Field(ge=1)] | None = None


# ---------- эндпоинты ----------
@app.post("/calc/vat")
def calc_vat(req: VatRequest, request: Request):
    rid = request.state.rid
    rate = float(req.vat_rate) / 100.0
    if req.include_vat:
        base = float(req.amount) / (1.0 + rate)
        vat = float(req.amount) - base
        total = float(req.amount)
    else:
        base = float(req.amount)
        vat = base * rate
        total = base + vat
    result = {
        "base": round(base, 2),
        "vat": round(vat, 2),
        "total": round(total, 2),
        "vat_rate": float(req.vat_rate),
        "include_vat": req.include_vat,
        "request_id": rid,
        "ts": datetime.now(UTC).isoformat(),
    }
    save_finance_calc(req.lot_id, req.model_dump(), result)
    return result


@app.post("/calc/margin")
def calc_margin(req: MarginRequest, request: Request):
    rid = request.state.rid
    rate = float(req.vat_rate) / 100.0
    revenue_gross = float(req.lot_price)
    revenue_net = (
        revenue_gross / (1.0 + rate) if req.price_includes_vat else revenue_gross
    )
    cost_total = float(req.cost) + float(req.logistics)
    profit = revenue_net - cost_total
    margin_pct = (profit / revenue_net * 100.0) if revenue_net > 0 else 0.0
    roi_pct = (profit / cost_total * 100.0) if cost_total > 0 else 0.0
    result = {
        "revenue_gross": round(revenue_gross, 2),
        "revenue_net": round(revenue_net, 2),
        "cost_total": round(cost_total, 2),
        "profit": round(profit, 2),
        "margin_pct": round(margin_pct, 2),
        "roi_pct": round(roi_pct, 2),
        "assumptions": {
            "price_includes_vat": req.price_includes_vat,
            "vat_rate": float(req.vat_rate),
        },
        "request_id": rid,
        "ts": datetime.now(UTC).isoformat(),
    }
    save_finance_calc(req.lot_id, req.model_dump(), result)
    return result


@app.post("/calc/penalty")
def calc_penalty(req: PenaltyRequest, request: Request):
    rid = request.state.rid
    penalty = (
        float(req.contract_sum)
        * (float(req.daily_rate_pct) / 100.0)
        * int(req.days_overdue)
    )
    result = {
        "contract_sum": float(req.contract_sum),
        "days_overdue": int(req.days_overdue),
        "daily_rate_pct": float(req.daily_rate_pct),
        "penalty": round(penalty, 2),
        "request_id": rid,
        "ts": datetime.now(UTC).isoformat(),
    }
    save_finance_calc(req.lot_id, req.model_dump(), result)
    return result


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
