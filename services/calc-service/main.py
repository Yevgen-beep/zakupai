import os
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Annotated
from decimal import Decimal

from fastapi import FastAPI, Request, Header, HTTPException
from pydantic import BaseModel, Field
import psycopg2

# ---------- минимальное JSON-логирование + request-id ----------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("calc-service")

def get_request_id(x_request_id: Optional[str]) -> str:
    try:
        return str(uuid.UUID(x_request_id)) if x_request_id else str(uuid.uuid4())
    except Exception:
        return str(uuid.uuid4())

# ---------- DB helpers ----------
def _dsn_for(host: str) -> str:
    return "host={h} port={p} dbname={db} user={u} password={pw}".format(
        h=host,
        p=os.getenv("DB_PORT","5432"),
        db=os.getenv("DB_NAME","zakupai"),
        u=os.getenv("DB_USER","zakupai"),
        pw=os.getenv("DB_PASSWORD","zakupai"),
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

def save_finance_calc(lot_id: Optional[int], input_payload: dict, results: dict):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_calcs(lot_id, input, results, created_at)
                    VALUES (%s, %s::jsonb, %s::jsonb, now())
                    """,
                    (lot_id, json.dumps(input_payload, ensure_ascii=False, default=str), json.dumps(results, ensure_ascii=False, default=str)),
                )
    except Exception as e:
        log.warning(f"finance_calcs insert failed: {e}")

# ---------- FastAPI ----------
app = FastAPI(title="ZakupAI calc-service", version="0.1.1")

@app.middleware("http")
async def add_request_id_and_log(request: Request, call_next):
    rid = get_request_id(request.headers.get("X-Request-Id"))
    request.state.rid = rid
    response = await call_next(request)
    response.headers["X-Request-Id"] = rid
    return response

@app.get("/health")
def health():
    return {"status":"ok","service":"calc-service"}

@app.get("/info")
def info(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if x_api_key != os.getenv("API_KEY","dev-key"):
        raise HTTPException(status_code=401, detail="unauthorized")
    return {"service":"calc-service","version":"0.1.1"}

# ---------- схемы ----------
class VatRequest(BaseModel):
    amount: Annotated[Decimal, Field(ge=0)]
    vat_rate: Annotated[Decimal, Field(ge=0, le=100)] = Decimal('12')
    include_vat: bool = True
    lot_id: Optional[int] = None

class MarginRequest(BaseModel):
    lot_price: Annotated[Decimal, Field(ge=0)]
    cost: Annotated[Decimal, Field(ge=0)]
    logistics: Annotated[Decimal, Field(ge=0)] = Decimal('0')
    vat_rate: Annotated[Decimal, Field(ge=0, le=100)] = Decimal('12')
    price_includes_vat: bool = True
    lot_id: Optional[int] = None

class PenaltyRequest(BaseModel):
    contract_sum: Annotated[Decimal, Field(ge=0)]
    days_overdue: int = Field(ge=0, default=0)
    daily_rate_pct: Annotated[Decimal, Field(ge=0, le=100)] = Decimal('0.1')
    lot_id: Optional[int] = None

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
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    save_finance_calc(req.lot_id, req.model_dump(), result)
    return result

@app.post("/calc/margin")
def calc_margin(req: MarginRequest, request: Request):
    rid = request.state.rid
    rate = float(req.vat_rate) / 100.0
    revenue_gross = float(req.lot_price)
    revenue_net = revenue_gross / (1.0 + rate) if req.price_includes_vat else revenue_gross
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
        "assumptions": {"price_includes_vat": req.price_includes_vat, "vat_rate": float(req.vat_rate)},
        "request_id": rid,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    save_finance_calc(req.lot_id, req.model_dump(), result)
    return result

@app.post("/calc/penalty")
def calc_penalty(req: PenaltyRequest, request: Request):
    rid = request.state.rid
    penalty = float(req.contract_sum) * (float(req.daily_rate_pct)/100.0) * int(req.days_overdue)
    result = {
        "contract_sum": float(req.contract_sum),
        "days_overdue": int(req.days_overdue),
        "daily_rate_pct": float(req.daily_rate_pct),
        "penalty": round(penalty, 2),
        "request_id": rid,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    save_finance_calc(req.lot_id, req.model_dump(), result)
    return result
