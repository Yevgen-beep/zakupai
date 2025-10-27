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
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field, validator

# Import RNU client
from rnu_client import RNUClient, RNUValidationError, get_rnu_client
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from zakupai_common.vault_client import VaultClientError, load_kv_to_env
from zakupai_common.audit_logger import get_audit_logger
from zakupai_common.compliance import ComplianceSettings
from zakupai_common.fastapi.error_middleware import ErrorHandlerMiddleware
from zakupai_common.fastapi.health import health_router
from zakupai_common.fastapi.metrics import add_prometheus_middleware
from zakupai_common.logging import setup_logging
from zakupai_common.metrics import set_anti_dumping
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse
from exceptions import validation_exception_handler, payload_too_large_handler, rate_limit_handler

try:
    from typing import Annotated  # py>=3.9
except ImportError:
    from typing import Annotated

# ---------- структурированное логирование ----------
import structlog

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    context_class=dict,
    cache_logger_on_first_use=True,
)

# Fallback logging for stdlib
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)

log = structlog.get_logger("risk-engine")


def bootstrap_vault():
    try:
        db_secret = load_kv_to_env("db")
        os.environ.setdefault("DB_USER", db_secret.get("POSTGRES_USER", ""))
        os.environ.setdefault("DB_PASSWORD", db_secret.get("POSTGRES_PASSWORD", ""))
        os.environ.setdefault("DB_NAME", db_secret.get("POSTGRES_DB", ""))
        os.environ.setdefault("DATABASE_URL", db_secret.get("DATABASE_URL", ""))
        os.environ.setdefault("POSTGRES_USER", db_secret.get("POSTGRES_USER", ""))
        os.environ.setdefault(
            "POSTGRES_PASSWORD", db_secret.get("POSTGRES_PASSWORD", "")
        )
        os.environ.setdefault("POSTGRES_DB", db_secret.get("POSTGRES_DB", ""))
        load_kv_to_env("api", mapping={"API_KEY": "API_KEY", "X_API_KEY": "X_API_KEY"})
        log.info("vault_bootstrap_success", loaded_keys=sorted(db_secret.keys()))
    except VaultClientError as exc:
        log.warning("Vault bootstrap skipped: %s", exc)
    except Exception:  # pragma: no cover - defensive fallback
        log.exception("Vault bootstrap failed")


bootstrap_vault()

SERVICE_NAME = "risk"


audit_logger = get_audit_logger(SERVICE_NAME)


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

    # Compliance checks using ComplianceSettings
    if ComplianceSettings.REESTR_NEDOBRO_ENABLED:
        # Check недобросовестный реестр (placeholder - in real implementation would check customer_bin)
        customer_bin = lot.get("customer_bin")
        flags["reestr_check"] = bool(customer_bin)  # placeholder logic

    if ComplianceSettings.SINGLE_SOURCE_LIST_ENABLED:
        # Check if lot type matches single source criteria
        flags["single_source_eligible"] = lot.get("plan_id") in (None, "", "null")

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


# ---------- RNU Notification System ----------
async def check_rnu_status_changes():
    """Check for new RNU status changes and send notifications"""
    try:
        conn, _ = _get_conn_and_host()
        with conn, conn.cursor() as cur:
            # Find new blocked suppliers without notifications
            cur.execute(
                """
                SELECT rvc.supplier_bin, rvc.status, rvc.validated_at
                FROM rnu_validation_cache rvc
                WHERE rvc.status != 'ACTIVE'
                AND NOT EXISTS (
                    SELECT 1 FROM rnu_alerts ra
                    WHERE ra.supplier_bin = rvc.supplier_bin
                    AND ra.status = rvc.status
                    AND ra.notified_at > rvc.validated_at - INTERVAL '10 minutes'
                )
                ORDER BY rvc.validated_at DESC
                LIMIT 100
                """
            )

            status_changes = cur.fetchall()

            for supplier_bin, status, validated_at in status_changes:
                await send_rnu_notifications(supplier_bin, status, validated_at)

        if status_changes:
            log.info(f"Processed {len(status_changes)} RNU status change notifications")

    except Exception as e:
        log.error(f"Error checking RNU status changes: {e}")


async def send_rnu_notifications(supplier_bin: str, status: str, validated_at):
    """Send notifications for RNU status change"""
    try:
        conn, _ = _get_conn_and_host()
        with conn, conn.cursor() as cur:
            # Get all subscribers for this BIN
            cur.execute(
                """
                SELECT user_id, telegram_user_id, email
                FROM rnu_subscriptions
                WHERE supplier_bin = %s AND is_active = true
                """,
                (supplier_bin,),
            )

            subscribers = cur.fetchall()
            notifications_sent = 0

            for user_id, telegram_user_id, _email in subscribers:
                # Send Telegram notification if telegram_user_id exists
                if telegram_user_id:
                    success = await send_telegram_notification(
                        telegram_user_id, supplier_bin, status
                    )
                    if success:
                        notifications_sent += 1

                # Record alert in database
                cur.execute(
                    """
                    INSERT INTO rnu_alerts (supplier_bin, status, user_id, notified_at)
                    VALUES (%s, %s, %s, now())
                    """,
                    (supplier_bin, status, user_id),
                )

            log.info(
                f"Sent {notifications_sent} notifications for BIN {supplier_bin} status {status}"
            )

    except Exception as e:
        log.error(f"Error sending RNU notifications for {supplier_bin}: {e}")


async def send_telegram_notification(
    telegram_user_id: int, supplier_bin: str, status: str
) -> bool:
    """Send Telegram notification about RNU status change"""
    try:
        import httpx

        # Get Telegram bot token from environment
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            log.warning("TELEGRAM_BOT_TOKEN not set, skipping Telegram notification")
            return False

        # Status emoji mapping
        status_emoji = {
            "BLOCKED": "🔴",
            "SUSPENDED": "🟡",
            "LIQUIDATED": "⚫",
            "BLACKLISTED": "🚫",
            "ACTIVE": "🟢",
            "UNKNOWN": "❓",
        }

        emoji = status_emoji.get(status, "⚠️")

        # Web UI link
        web_url = os.getenv("WEB_UI_URL", "http://localhost:8000")

        message = f"Alert: BIN {supplier_bin} {emoji} {status}.\nℹ️ Подробнее в Web UI: {web_url}/rnu/{supplier_bin}"

        # Send via Telegram Bot API
        telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                telegram_url,
                json={
                    "chat_id": telegram_user_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )

            if response.status_code == 200:
                log.info(
                    f"Telegram notification sent to {telegram_user_id} for BIN {supplier_bin}"
                )
                return True
            else:
                log.warning(
                    f"Telegram API error {response.status_code}: {response.text}"
                )
                return False

    except Exception as e:
        log.error(f"Error sending Telegram notification: {e}")
        return False


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to limit request payload size to 2MB.
    Returns HTTP 413 if payload exceeds the limit.
    Stage 7 Phase 1: Security Quick Wins
    """
    MAX_SIZE = 2 * 1024 * 1024  # 2 MB

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ["/health", "/metrics", "/docs", "/openapi.json"]:
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_SIZE:
            return JSONResponse(
                status_code=413,
                content={"detail": "Payload Too Large"}
            )

        return await call_next(request)


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
app = FastAPI(
    title="ZakupAI risk-engine",
    version="1.0.0",
    root_path="/risk",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Setup logging
setup_logging("risk-engine")

# Initialize rate limiter (Stage 7 Phase 1)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Register exception handlers (Stage 7 Phase 1)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# Add middlewares (order matters: payload check -> error handler -> audit -> prometheus)
app.add_middleware(PayloadSizeLimitMiddleware)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(AuditMiddleware)
add_prometheus_middleware(app, SERVICE_NAME)

# Initialize scheduler
scheduler = AsyncIOScheduler()

# Include routers
app.include_router(health_router)


@app.on_event("startup")
async def _startup():
    _ensure_schema()

    # Start RNU notification scheduler (every 5 minutes)
    scheduler.add_job(
        check_rnu_status_changes,
        trigger="interval",
        minutes=5,
        id="rnu_status_checker",
        replace_existing=True,
    )
    scheduler.start()
    log.info("RNU notification scheduler started")


@app.on_event("shutdown")
async def _shutdown():
    scheduler.shutdown()


@app.middleware("http")
async def mid(request: Request, call_next):
    rid = _rid(request.headers.get("X-Request-Id"))
    request.state.rid = rid
    resp = await call_next(request)
    resp.headers["X-Request-Id"] = rid
    return resp


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
@limiter.limit("30/minute")
def risk_score(req: ScoreRequest, request: Request):
    import time

    start_time = time.time()
    request_id = getattr(request.state, "rid", str(uuid.uuid4()))
    lot: dict[str, Any] | None = None
    anti_dumping_percent = 0.0

    log.info(
        "Risk score calculation started",
        action="risk_score_start",
        lot_id=req.lot_id,
        request_id=request_id,
    )

    try:
        lot = _get_lot(req.lot_id)
        if not lot:
            log.warning(
                "Lot not found",
                action="risk_score_not_found",
                lot_id=req.lot_id,
                request_id=request_id,
            )
            raise HTTPException(404, f"lot {req.lot_id} not found")

        market_sum = _get_market_sum(req.lot_id)
        flags = _compute_flags(lot, market_sum)
        score = _score(flags)

        lot_price = float(lot.get("price") or 0)
        if market_sum and market_sum > 0:
            anti_dumping_percent = max(0.0, (market_sum - lot_price) / market_sum * 100)
        else:
            anti_dumping_percent = 0.0

        set_anti_dumping(SERVICE_NAME, str(req.lot_id), anti_dumping_percent)
        flags["anti_dumping_percent"] = round(anti_dumping_percent, 2)

        explain = {
            "weights": WEIGHTS,
            "thresholds": TH,
            "lot": lot,
            "calc": {"market_sum": flags.get("market_sum")},
        }

        saved = _save_eval(req.lot_id, score, flags, explain)
        latency_ms = int((time.time() - start_time) * 1000)

        log.info(
            "Risk score calculation completed",
            action="risk_score_completed",
            lot_id=req.lot_id,
            score=score,
            market_sum=market_sum,
            saved=saved,
            latency_ms=latency_ms,
            request_id=request_id,
        )

        result = {
            "lot_id": req.lot_id,
            "score": score,
            "flags": flags,
            "saved": saved,
            "ts": datetime.now(UTC).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        log.error(
            "Risk score calculation failed",
            action="risk_score_error",
            lot_id=req.lot_id,
            error=str(e),
            latency_ms=latency_ms,
            request_id=request_id,
        )
        raise HTTPException(500, "Internal server error") from e
    else:
        compliance_flag = "anti_dumping" if anti_dumping_percent > 15 else None
        audit_logger.info(
            "risk_score",
            extra={
                "lot_id": str(req.lot_id),
                "anti_dumping_percent": round(anti_dumping_percent, 2),
                "procurement_type": lot.get("procurement_type") if lot else None,
                "compliance_flag": compliance_flag,
            },
        )
        return result


# ---------- RNU Validation Models ----------
class RNUValidationResponse(BaseModel):
    supplier_bin: str = Field(..., description="Business Identification Number")
    status: str = Field(
        ...,
        description="RNU supplier status: ACTIVE, BLOCKED, SUSPENDED, LIQUIDATED, BLACKLISTED, UNKNOWN",
    )
    is_blocked: bool = Field(
        ..., description="Whether the supplier is blocked in RNU registry"
    )
    source: str = Field(..., description="Data source: 'cache' or 'api'")
    validated_at: str = Field(..., description="ISO timestamp of validation")

    @validator("supplier_bin")
    def validate_supplier_bin(cls, v):
        if not v or not v.isdigit() or len(v) != 12:
            raise ValueError("Supplier BIN must be exactly 12 digits")
        return v

    @validator("status")
    def validate_status(cls, v):
        allowed_statuses = {
            "ACTIVE",
            "BLOCKED",
            "SUSPENDED",
            "LIQUIDATED",
            "BLACKLISTED",
            "UNKNOWN",
        }
        if v not in allowed_statuses:
            raise ValueError(f"Status must be one of: {allowed_statuses}")
        return v


# ---------- RNU Validation Endpoint ----------
@app.get("/validate_rnu/{supplier_bin}", response_model=RNUValidationResponse)
async def validate_rnu_supplier(
    supplier_bin: str, request: Request, rnu_client: RNUClient = Depends(get_rnu_client)
):
    """
    Validate supplier BIN through RNU registry with caching

    - **supplier_bin**: Business Identification Number (12 digits)

    Returns validation result with caching:
    - Checks Redis cache first (TTL=24h)
    - Falls back to PostgreSQL cache
    - Calls external RNU API if not cached
    - Updates both caches with result

    Performance targets:
    - Cache response: <500ms (95%)
    - API response: <2sec (95%)
    - Availability: ≥95%
    """
    import time

    start_time = time.time()
    request_id = getattr(request.state, "rid", str(uuid.uuid4()))

    log.info(
        "RNU validation started",
        action="rnu_validation_start",
        bin=supplier_bin,
        request_id=request_id,
    )

    try:
        # Validate BIN format early
        if not supplier_bin.isdigit() or len(supplier_bin) != 12:
            log.warning(
                "Invalid BIN format",
                action="rnu_validation_invalid_format",
                bin=supplier_bin,
                request_id=request_id,
            )
            raise HTTPException(
                status_code=400, detail="Invalid BIN format: must be exactly 12 digits"
            )

        result = await rnu_client.validate_supplier(supplier_bin)
        latency_ms = int((time.time() - start_time) * 1000)

        log.info(
            "RNU validation completed",
            action="rnu_validation_completed",
            bin=supplier_bin,
            status=result.get("status"),
            is_blocked=result.get("is_blocked"),
            source=result.get("source"),
            latency_ms=latency_ms,
            request_id=request_id,
        )

        # Log performance warning if too slow
        if latency_ms > 2000:
            log.warning(
                "RNU validation latency exceeded target",
                action="rnu_validation_slow",
                bin=supplier_bin,
                latency_ms=latency_ms,
                target_ms=2000,
                request_id=request_id,
            )

        return RNUValidationResponse(**result)

    except RNUValidationError as e:
        latency_ms = int((time.time() - start_time) * 1000)

        log.error(
            "RNU validation error",
            action="rnu_validation_error",
            bin=supplier_bin,
            error=str(e),
            error_type=type(e).__name__,
            latency_ms=latency_ms,
            request_id=request_id,
        )

        if "Invalid BIN format" in str(e):
            raise HTTPException(status_code=400, detail=str(e)) from e
        elif "Rate limit exceeded" in str(e):
            raise HTTPException(
                status_code=429, detail="Rate limit exceeded, please try again later"
            ) from e
        else:
            raise HTTPException(
                status_code=503, detail="RNU service temporarily unavailable"
            ) from e

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)

        log.error(
            "Unexpected error in RNU validation",
            action="rnu_validation_unexpected_error",
            bin=supplier_bin,
            error=str(e),
            error_type=type(e).__name__,
            latency_ms=latency_ms,
            request_id=request_id,
        )
        raise HTTPException(status_code=500, detail="Internal server error") from e


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


# ---------- RNU Subscription Management ----------
class RNUSubscriptionRequest(BaseModel):
    supplier_bin: str = Field(..., description="Business Identification Number")
    telegram_user_id: int = Field(..., description="Telegram user ID for notifications")

    @validator("supplier_bin")
    def validate_supplier_bin(cls, v):
        if not v or not v.isdigit() or len(v) != 12:
            raise ValueError("Supplier BIN must be exactly 12 digits")
        return v


@app.post("/rnu/subscribe")
async def subscribe_rnu_notifications(req: RNUSubscriptionRequest):
    """Subscribe to RNU status change notifications for a supplier"""
    try:
        conn, _ = _get_conn_and_host()
        with conn, conn.cursor() as cur:
            # Check subscription limit
            cur.execute(
                "SELECT COUNT(*) FROM rnu_subscriptions WHERE user_id = %s AND is_active = true",
                (req.telegram_user_id,),
            )
            count = cur.fetchone()[0]

            if count >= 100:
                raise HTTPException(400, "Maximum 100 subscriptions per user")

            # Insert or update subscription
            cur.execute(
                """
                INSERT INTO rnu_subscriptions (user_id, supplier_bin, telegram_user_id, is_active)
                VALUES (%s, %s, %s, true)
                ON CONFLICT (user_id, supplier_bin)
                DO UPDATE SET is_active = true, updated_at = now()
                """,
                (req.telegram_user_id, req.supplier_bin, req.telegram_user_id),
            )

            log.info(
                f"User {req.telegram_user_id} subscribed to RNU alerts for BIN {req.supplier_bin}"
            )

            return {
                "status": "success",
                "message": f"Subscribed to RNU notifications for BIN {req.supplier_bin}",
                "supplier_bin": req.supplier_bin,
                "user_id": req.telegram_user_id,
            }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error creating RNU subscription: {e}")
        raise HTTPException(500, "Internal server error") from e


@app.delete("/rnu/subscribe/{supplier_bin}/{user_id}")
async def unsubscribe_rnu_notifications(supplier_bin: str, user_id: int):
    """Unsubscribe from RNU status change notifications"""
    try:
        if not supplier_bin.isdigit() or len(supplier_bin) != 12:
            raise HTTPException(400, "Invalid BIN format")

        conn, _ = _get_conn_and_host()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE rnu_subscriptions SET is_active = false, updated_at = now()
                WHERE user_id = %s AND supplier_bin = %s
                """,
                (user_id, supplier_bin),
            )

            if cur.rowcount == 0:
                raise HTTPException(404, "Subscription not found")

            log.info(
                f"User {user_id} unsubscribed from RNU alerts for BIN {supplier_bin}"
            )

            return {
                "status": "success",
                "message": f"Unsubscribed from RNU notifications for BIN {supplier_bin}",
            }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error removing RNU subscription: {e}")
        raise HTTPException(500, "Internal server error") from e


@app.get("/rnu/subscriptions/{user_id}")
async def get_user_rnu_subscriptions(user_id: int):
    """Get user's active RNU subscriptions"""
    try:
        conn, _ = _get_conn_and_host()
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT rs.supplier_bin, rs.subscribed_at, rvc.status, rvc.validated_at
                FROM rnu_subscriptions rs
                LEFT JOIN rnu_validation_cache rvc ON rs.supplier_bin = rvc.supplier_bin
                WHERE rs.user_id = %s AND rs.is_active = true
                ORDER BY rs.subscribed_at DESC
                """,
                (user_id,),
            )

            subscriptions = []
            for row in cur.fetchall():
                subscriptions.append(
                    {
                        "supplier_bin": row[0],
                        "subscribed_at": row[1].isoformat() if row[1] else None,
                        "current_status": row[2] or "UNKNOWN",
                        "last_validated": row[3].isoformat() if row[3] else None,
                    }
                )

            return {
                "user_id": user_id,
                "subscriptions": subscriptions,
                "total": len(subscriptions),
            }

    except Exception as e:
        log.error(f"Error getting RNU subscriptions: {e}")
        raise HTTPException(500, "Internal server error") from e


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
