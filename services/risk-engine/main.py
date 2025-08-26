import hashlib
import json
import logging
import os
import time
import uuid
from datetime import UTC, date, datetime
from typing import Any

import psycopg2
import yaml
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

try:
    from typing import Annotated  # py>=3.9
except ImportError:
    from typing import Annotated

# ---------- логирование JSON ----------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("risk-engine")


def _rid(x: str | None) -> str:
    try:
        return str(uuid.UUID(x)) if x else str(uuid.uuid4())
    except Exception:
        return str(uuid.uuid4())


# ---------- DB ----------
def _dsn(host: str) -> str:
    return (
        f"host={host} port={os.getenv('DB_PORT', '5432')}"
        f" dbname={os.getenv('DB_NAME', 'zakupai')}"
        f" user={os.getenv('DB_USER', 'zakupai')}"
        f" password={os.getenv('DB_PASSWORD', 'zakupai')}"
    )


def _get_conn_and_host():
    cands = [os.getenv("DB_HOST")] if os.getenv("DB_HOST") else []
    cands += ["zakupai-db", "db", "localhost"]
    last = None
    for h in cands:
        try:
            conn = psycopg2.connect(_dsn(h))
            return conn, h
        except Exception as e:
            last = e
            log.warning(f"DB connect failed for '{h}': {e}")
    raise last or RuntimeError("DB connection failed")


def _ensure_schema():
    try:
        conn, _ = _get_conn_and_host()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
            CREATE TABLE IF NOT EXISTS risk_evaluations (
              id SERIAL PRIMARY KEY,
              lot_id INTEGER,
              score NUMERIC,
              flags JSONB,
              explain JSONB,
              created_at TIMESTAMPTZ DEFAULT now()
            );"""
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
        log.warning(f"_ensure_schema failed: {e}")


def _save_audit_log(
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
        conn, _ = _get_conn_and_host()
        with conn, conn.cursor() as cur:
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


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _fetch_one_dict(cur) -> dict[str, Any] | None:
    row = cur.fetchone()
    if not row:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row, strict=False))


def _get_lot(lot_id: int) -> dict[str, Any] | None:
    conn, _ = _get_conn_and_host()
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, price, deadline, customer_bin, plan_id FROM lots WHERE id=%s",
            (lot_id,),
        )
        return _fetch_one_dict(cur)


def _get_market_sum(lot_id: int) -> float | None:
    """Сумма ориентир по лоту = Σ(price * qty) из связок lot_prices → prices"""
    conn, _ = _get_conn_and_host()
    with conn, conn.cursor() as cur:
        cur.execute(
            """
        SELECT COALESCE(SUM(p.price * lp.qty),0) AS total_market, COALESCE(SUM(lp.qty),0) AS total_qty
        FROM lot_prices lp
        JOIN prices p ON p.id = lp.price_id
        WHERE lp.lot_id = %s
        """,
            (lot_id,),
        )
        total_market, total_qty = cur.fetchone()
        if total_qty and float(total_qty) > 0:
            return float(total_market)
        return None


# ---------- правила ----------
def _load_rules():
    path = os.path.join(os.path.dirname(__file__), "rules.yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


RULES = _load_rules()
WEIGHTS = RULES.get("weights", {})
TH = RULES.get("thresholds", {})


def _compute_flags(lot: dict[str, Any], market_sum: float | None) -> dict[str, Any]:
    flags: dict[str, Any] = {}
    # дедлайн
    try:
        dl: date | None = lot.get("deadline")
        if dl:
            days_left = (dl - date.today()).days
            flags["days_left"] = days_left
            flags["short_deadline"] = days_left <= int(TH.get("deadline_days_hot", 3))
        else:
            flags["days_left"] = None
            flags["short_deadline"] = False
    except Exception:
        flags["days_left"] = None
        flags["short_deadline"] = False
    # выше рынка
    try:
        lot_price = float(lot.get("price") or 0.0)
        factor = float(TH.get("over_market_factor", 1.2))
        if market_sum and market_sum > 0:
            flags["market_sum"] = round(market_sum, 2)
            flags["over_market"] = lot_price > market_sum * factor
        else:
            flags["market_sum"] = None
            flags["over_market"] = False
    except Exception:
        flags["market_sum"] = None
        flags["over_market"] = False
    # нет плановой закупки
    flags["no_plan_id"] = lot.get("plan_id") in (None, "", "null")
    return flags


def _score(flags: dict[str, Any]) -> float:
    s = 0.0
    if flags.get("short_deadline"):
        s += float(WEIGHTS.get("short_deadline", 0))
    if flags.get("over_market"):
        s += float(WEIGHTS.get("over_market", 0))
    if flags.get("no_plan_id"):
        s += float(WEIGHTS.get("no_plan_id", 0))
    return max(0.0, min(100.0, s))


def _save_eval(
    lot_id: int, score: float, flags: dict[str, Any], explain: dict[str, Any]
) -> bool:
    try:
        conn, host = _get_conn_and_host()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
              INSERT INTO risk_evaluations(lot_id, score, flags, explain, created_at)
              VALUES (%s, %s, %s::jsonb, %s::jsonb, now())
            """,
                (lot_id, score, _dump(flags), _dump(explain)),
            )
        # попытка обновить lots.risk_score, если колонка есть
        try:
            with conn, conn.cursor() as cur2:
                cur2.execute(
                    "UPDATE lots SET risk_score=%s WHERE id=%s", (score, lot_id)
                )
        except Exception as e2:
            log.warning(f"lots.risk_score update skipped: {e2}")
        log.info(f'saved risk_evaluations for lot {lot_id} (host="{host}")')
        return True
    except Exception as e:
        log.warning(f"risk_evaluations insert failed: {e}")
        return False


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
            _save_audit_log(
                service="risk-engine",
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


# ---------- API ----------
app = FastAPI(title="ZakupAI risk-engine", version="1.0.0")

# Add audit middleware
app.add_middleware(AuditMiddleware)


@app.on_event("startup")
def _startup():
    _ensure_schema()


@app.middleware("http")
async def mid(request: Request, call_next):
    rid = _rid(request.headers.get("X-Request-Id"))
    request.state.rid = rid
    resp = await call_next(request)
    resp.headers["X-Request-Id"] = rid
    return resp


@app.get("/health")
def health():
    return {"status": "ok", "service": "risk-engine"}


@app.get("/info")
def info(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    if x_api_key != os.getenv("API_KEY", "dev-key"):
        raise HTTPException(status_code=401, detail="unauthorized")
    return {
        "service": "risk-engine",
        "version": "1.0.0",
        "rules_version": RULES.get("version"),
    }


class ScoreRequest(BaseModel):
    lot_id: Annotated[int, Field(ge=1)]


@app.post("/risk/score")
def risk_score(req: ScoreRequest):
    lot = _get_lot(req.lot_id)
    if not lot:
        raise HTTPException(404, f"lot {req.lot_id} not found")
    market_sum = _get_market_sum(req.lot_id)
    flags = _compute_flags(lot, market_sum)
    score = _score(flags)
    explain = {
        "weights": WEIGHTS,
        "thresholds": TH,
        "lot": lot,
        "calc": {"market_sum": flags.get("market_sum")},
    }
    saved = _save_eval(req.lot_id, score, flags, explain)
    return {
        "lot_id": req.lot_id,
        "score": score,
        "flags": flags,
        "saved": saved,
        "ts": datetime.now(UTC).isoformat(),
    }


@app.get("/risk/explain/{lot_id}")
def risk_explain(lot_id: int):
    lot = _get_lot(lot_id)
    if not lot:
        raise HTTPException(404, f"lot {lot_id} not found")
    market_sum = _get_market_sum(lot_id)
    flags = _compute_flags(lot, market_sum)
    score = _score(flags)
    return {
        "lot_id": lot_id,
        "score": score,
        "flags": flags,
        "weights": WEIGHTS,
        "thresholds": TH,
        "lot": lot,
        "ts": datetime.now(UTC).isoformat(),
    }
