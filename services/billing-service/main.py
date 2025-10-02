import logging
import os
import time
import uuid
from datetime import UTC, datetime

import psycopg2
from fastapi import FastAPI, HTTPException, Request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from zakupai_common.fastapi.metrics import add_prometheus_middleware

# ---------- минимальное JSON-логирование + request-id ----------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("billing-service")

SERVICE_NAME = "billing"


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
            log.info(f"Connected to DB at {host}")
            return conn
        except Exception as e:
            last_err = e
            log.debug(f"Cannot connect to DB at {host}: {e}")
    raise Exception(f"No DB connection possible. Last error: {last_err}")


# ---------- Models ----------
class CreateKeyRequest(BaseModel):
    tg_id: int
    email: str | None = None


class CreateKeyResponse(BaseModel):
    api_key: str
    plan: str
    expires_at: str | None = None


class ValidateKeyRequest(BaseModel):
    api_key: str
    endpoint: str


class ValidateKeyResponse(BaseModel):
    valid: bool
    plan: str = "free"
    remaining_requests: int = 0
    message: str | None = None


class UsageRequest(BaseModel):
    api_key: str
    endpoint: str
    requests: int = 1


class UsageResponse(BaseModel):
    logged: bool


# ---------- Plans Configuration ----------
PLANS = {
    "free": {
        "requests_per_day": 100,
        "requests_per_hour": 20,
        "features": ["basic_analysis"],
    },
    "premium": {
        "requests_per_day": 5000,
        "requests_per_hour": 500,
        "features": ["basic_analysis", "pdf_export", "risk_scoring", "doc_generation"],
    },
}


# ---------- Database Operations ----------
def init_billing_schema():
    """Initialize billing schema and tables"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Create billing schema
            cur.execute("CREATE SCHEMA IF NOT EXISTS billing;")

            # Users table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS billing.users (
                    id SERIAL PRIMARY KEY,
                    tg_id BIGINT UNIQUE,
                    email TEXT,
                    plan TEXT DEFAULT 'free',
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT now(),
                    updated_at TIMESTAMP DEFAULT now()
                );
            """
            )

            # API Keys table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS billing.api_keys (
                    id SERIAL PRIMARY KEY,
                    user_id INT REFERENCES billing.users(id) ON DELETE CASCADE,
                    key TEXT UNIQUE NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT now(),
                    expires_at TIMESTAMP,
                    last_used_at TIMESTAMP
                );
            """
            )

            # Usage table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS billing.usage (
                    id BIGSERIAL PRIMARY KEY,
                    api_key_id INT REFERENCES billing.api_keys(id) ON DELETE CASCADE,
                    endpoint TEXT NOT NULL,
                    requests INT DEFAULT 1,
                    created_at TIMESTAMP DEFAULT now()
                );
            """
            )

            # Payments table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS billing.payments (
                    id SERIAL PRIMARY KEY,
                    user_id INT REFERENCES billing.users(id) ON DELETE CASCADE,
                    amount NUMERIC(10,2) NOT NULL,
                    currency TEXT DEFAULT 'KZT',
                    method TEXT,
                    status TEXT DEFAULT 'pending',
                    external_id TEXT,
                    created_at TIMESTAMP DEFAULT now()
                );
            """
            )

            # Indexes
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_billing_users_tg_id ON billing.users(tg_id);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_billing_api_keys_key ON billing.api_keys(key);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_billing_api_keys_user_id ON billing.api_keys(user_id);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_billing_usage_api_key_id ON billing.usage(api_key_id);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_billing_usage_created_at ON billing.usage(created_at);"
            )

        conn.commit()
        log.info("Billing schema initialized successfully")
    finally:
        conn.close()


def create_or_get_user(tg_id: int, email: str | None = None):
    """Create user or return existing"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Check if user exists
            cur.execute(
                "SELECT id, plan, status FROM billing.users WHERE tg_id = %s", (tg_id,)
            )
            user = cur.fetchone()

            if user:
                return {"id": user[0], "plan": user[1], "status": user[2]}

            # Create new user
            cur.execute(
                """
                INSERT INTO billing.users (tg_id, email, plan, status)
                VALUES (%s, %s, 'free', 'active')
                RETURNING id, plan, status
            """,
                (tg_id, email),
            )

            user = cur.fetchone()
            conn.commit()
            return {"id": user[0], "plan": user[1], "status": user[2]}
    finally:
        conn.close()


def create_api_key(user_id: int):
    """Create new API key for user"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Generate secure API key
            api_key = str(uuid.uuid4())

            cur.execute(
                """
                INSERT INTO billing.api_keys (user_id, key, status)
                VALUES (%s, %s, 'active')
                RETURNING key
            """,
                (user_id, api_key),
            )

            result = cur.fetchone()
            conn.commit()
            return result[0]
    finally:
        conn.close()


def validate_api_key(api_key: str, endpoint: str):
    """Validate API key and check limits"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Get key info with user plan
            cur.execute(
                """
                SELECT ak.id, ak.user_id, ak.status, ak.expires_at, u.plan, u.status as user_status
                FROM billing.api_keys ak
                JOIN billing.users u ON ak.user_id = u.id
                WHERE ak.key = %s
            """,
                (api_key,),
            )

            key_info = cur.fetchone()
            if not key_info:
                return {"valid": False, "message": "Invalid API key"}

            key_id, user_id, key_status, expires_at, plan, user_status = key_info

            # Check key status
            if key_status != "active":
                return {"valid": False, "message": "API key is not active"}

            # Check user status
            if user_status != "active":
                return {"valid": False, "message": "User account is not active"}

            # Check expiration
            if expires_at and expires_at < datetime.now(UTC):
                return {"valid": False, "message": "API key has expired"}

            # Check usage limits
            plan_config = PLANS.get(plan, PLANS["free"])

            # Daily limit
            cur.execute(
                """
                SELECT COALESCE(SUM(requests), 0)
                FROM billing.usage
                WHERE api_key_id = %s
                AND created_at >= CURRENT_DATE
            """,
                (key_id,),
            )

            daily_usage = cur.fetchone()[0]
            daily_limit = plan_config["requests_per_day"]

            if daily_usage >= daily_limit:
                return {
                    "valid": False,
                    "plan": plan,
                    "message": f"Daily limit exceeded ({daily_usage}/{daily_limit})",
                }

            # Hourly limit
            cur.execute(
                """
                SELECT COALESCE(SUM(requests), 0)
                FROM billing.usage
                WHERE api_key_id = %s
                AND created_at >= NOW() - INTERVAL '1 hour'
            """,
                (key_id,),
            )

            hourly_usage = cur.fetchone()[0]
            hourly_limit = plan_config["requests_per_hour"]

            if hourly_usage >= hourly_limit:
                return {
                    "valid": False,
                    "plan": plan,
                    "message": f"Hourly limit exceeded ({hourly_usage}/{hourly_limit})",
                }

            # Update last_used_at
            cur.execute(
                """
                UPDATE billing.api_keys
                SET last_used_at = NOW()
                WHERE id = %s
            """,
                (key_id,),
            )

            conn.commit()

            return {
                "valid": True,
                "plan": plan,
                "remaining_requests": daily_limit - daily_usage - 1,
                "key_id": key_id,
            }
    finally:
        conn.close()


def log_usage(api_key: str, endpoint: str, requests: int = 1):
    """Log API usage"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Get api_key_id
            cur.execute("SELECT id FROM billing.api_keys WHERE key = %s", (api_key,))
            result = cur.fetchone()

            if not result:
                return False

            api_key_id = result[0]

            cur.execute(
                """
                INSERT INTO billing.usage (api_key_id, endpoint, requests)
                VALUES (%s, %s, %s)
            """,
                (api_key_id, endpoint, requests),
            )

            conn.commit()
            return True
    finally:
        conn.close()


# ---------- Middleware ----------
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        x_request_id = request.headers.get("x-request-id")
        request_id = get_request_id(x_request_id)

        # Log request
        log.info(f"Request {request_id}: {request.method} {request.url}")

        response = await call_next(request)

        # Log response
        duration = time.time() - start_time
        log.info(f"Response {request_id}: {response.status_code} in {duration:.3f}s")

        response.headers["X-Request-ID"] = request_id
        return response


# ---------- FastAPI App ----------
app = FastAPI(
    title="ZakupAI Billing Service",
    description="User management, API keys, usage tracking",
    version="1.0.0",
)

app.add_middleware(RequestLoggingMiddleware)
add_prometheus_middleware(app, SERVICE_NAME)


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.on_event("startup")
async def startup_event():
    """Initialize database schema on startup"""
    try:
        init_billing_schema()
        log.info("Billing service started successfully")
    except Exception as e:
        log.error(f"Failed to initialize billing service: {e}")
        raise


# ---------- API Routes ----------


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/billing/create_key", response_model=CreateKeyResponse)
async def create_key(request: CreateKeyRequest):
    """Create API key for user"""
    try:
        # Create or get user
        user = create_or_get_user(request.tg_id, request.email)

        # Create API key
        api_key = create_api_key(user["id"])

        log.info(f"Created API key for tg_id={request.tg_id}, plan={user['plan']}")

        return CreateKeyResponse(api_key=api_key, plan=user["plan"], expires_at=None)

    except Exception as e:
        log.error(f"Error creating API key: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.post("/billing/validate_key", response_model=ValidateKeyResponse)
async def validate_key(request: ValidateKeyRequest):
    """Validate API key and check limits"""
    try:
        result = validate_api_key(request.api_key, request.endpoint)

        if result["valid"]:
            log.info(f"Valid API key for {request.endpoint}, plan={result['plan']}")
        else:
            log.warning(
                f"Invalid/limited API key for {request.endpoint}: {result.get('message')}"
            )

        return ValidateKeyResponse(**result)

    except Exception as e:
        log.error(f"Error validating API key: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.post("/billing/usage", response_model=UsageResponse)
async def usage(request: UsageRequest):
    """Log API usage"""
    try:
        logged = log_usage(request.api_key, request.endpoint, request.requests)

        if logged:
            log.info(f"Logged {request.requests} requests for {request.endpoint}")
        else:
            log.warning("Failed to log usage for API key")

        return UsageResponse(logged=logged)

    except Exception as e:
        log.error(f"Error logging usage: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.get("/billing/stats/{tg_id}")
async def get_user_stats(tg_id: int):
    """Get user statistics"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Get user info
            cur.execute(
                """
                SELECT u.id, u.plan, u.status, u.created_at,
                       COUNT(ak.id) as total_keys,
                       COUNT(CASE WHEN ak.status = 'active' THEN 1 END) as active_keys
                FROM billing.users u
                LEFT JOIN billing.api_keys ak ON u.id = ak.user_id
                WHERE u.tg_id = %s
                GROUP BY u.id, u.plan, u.status, u.created_at
            """,
                (tg_id,),
            )

            user_stats = cur.fetchone()
            if not user_stats:
                raise HTTPException(status_code=404, detail="User not found")

            user_id, plan, status, created_at, total_keys, active_keys = user_stats

            # Get usage stats
            cur.execute(
                """
                SELECT
                    COUNT(*) as total_requests,
                    COUNT(CASE WHEN created_at >= CURRENT_DATE THEN 1 END) as today_requests,
                    COUNT(CASE WHEN created_at >= NOW() - INTERVAL '1 hour' THEN 1 END) as hour_requests
                FROM billing.usage us
                JOIN billing.api_keys ak ON us.api_key_id = ak.id
                WHERE ak.user_id = %s
            """,
                (user_id,),
            )

            usage_stats = cur.fetchone()
            total_requests, today_requests, hour_requests = usage_stats

            plan_config = PLANS.get(plan, PLANS["free"])

            return {
                "tg_id": tg_id,
                "plan": plan,
                "status": status,
                "created_at": created_at.isoformat(),
                "keys": {"total": total_keys, "active": active_keys},
                "usage": {
                    "total_requests": total_requests,
                    "today_requests": today_requests,
                    "hour_requests": hour_requests,
                    "daily_limit": plan_config["requests_per_day"],
                    "hourly_limit": plan_config["requests_per_hour"],
                },
                "limits": {
                    "daily_remaining": max(
                        0, plan_config["requests_per_day"] - today_requests
                    ),
                    "hourly_remaining": max(
                        0, plan_config["requests_per_hour"] - hour_requests
                    ),
                },
            }

    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104
