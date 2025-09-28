import hashlib
import json
import logging
import os
import time
import uuid
from datetime import UTC, datetime

import psycopg2
from fastapi import FastAPI, Header, HTTPException, Query, Request
from jinja2 import Environment, FileSystemLoader, select_autoescape
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field, validator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# ---------- logging ----------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("doc-service")

API_KEY = os.getenv("API_KEY", "changeme")

# Template whitelist
ALLOWED_TEMPLATES = {"tldr", "letters/guarantee"}

# Localization support
SUPPORTED_LANGUAGES = {"ru", "kz", "en"}
DEFAULT_LANGUAGE = "ru"


def load_locales():
    """Load all localization files"""
    locales = {}
    locales_dir = os.path.join(os.path.dirname(__file__), "locales")

    for lang in SUPPORTED_LANGUAGES:
        lang_file = os.path.join(locales_dir, lang, "messages.json")
        try:
            if os.path.exists(lang_file):
                with open(lang_file, encoding="utf-8") as f:
                    locales[lang] = json.load(f)
            else:
                log.warning(f"Locale file not found: {lang_file}")
                locales[lang] = {}
        except Exception as e:
            log.error(f"Failed to load locale {lang}: {e}")
            locales[lang] = {}

    return locales


def get_translation(key: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """Get translation for a key in specified language"""
    if lang not in LOCALES:
        lang = DEFAULT_LANGUAGE

    return LOCALES[lang].get(key, key)


def get_localized_context(context: dict, lang: str = DEFAULT_LANGUAGE) -> dict:
    """Add translations to template context"""
    localized = context.copy()

    # Add all translations with 't_' prefix
    if lang in LOCALES:
        for key, value in LOCALES[lang].items():
            localized[f"t_{key}"] = value

    # Add language info
    localized["_lang"] = lang
    localized["_supported_langs"] = list(SUPPORTED_LANGUAGES)

    return localized


# Load locales at startup
LOCALES = load_locales()


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


def get_lot(lot_id: int) -> dict:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, title, price FROM lots WHERE id = %s", (lot_id,)
                )
                row = cur.fetchone()
                if row:
                    return {"id": row[0], "title": row[1], "price": row[2]}
                return {}
    except Exception as e:
        log.warning(f"get_lot failed: {e}")
        return {}


# ---------- Audit Middleware ----------
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
                service="doc-service",
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


# ---------- Validation Models ----------
class TldrRequest(BaseModel):
    lot_id: int = Field(ge=1)


class RenderRequest(BaseModel):
    template: str
    context: dict[str, str | int | float | list[str]]

    @validator("template")
    def template_must_be_allowed(cls, v):
        if v not in ALLOWED_TEMPLATES:
            raise ValueError(f"Template must be one of: {', '.join(ALLOWED_TEMPLATES)}")
        return v

    @validator("context")
    def validate_context(cls, v):
        for key, val in v.items():
            if isinstance(val, str) and len(val) > 500:
                raise ValueError(
                    f'String values must be <= 500 chars, got {len(val)} for key "{key}"'
                )
            if isinstance(val, list) and len(val) > 50:
                raise ValueError(
                    f'List values must be <= 50 items, got {len(val)} for key "{key}"'
                )
        return v


# ---------- FastAPI ----------
app = FastAPI(
    title="ZakupAI doc-service",
    version="0.1.1",
    root_path="/doc",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Add audit middleware
app.add_middleware(AuditMiddleware)

# Setup Jinja2 with autoescape
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(templates_dir, exist_ok=True)
env = Environment(
    loader=FileSystemLoader(templates_dir),
    autoescape=select_autoescape(["html", "xml"]),
)


@app.on_event("startup")
def startup_event():
    ensure_audit_schema()


def check_api_key(x_api_key: str | None):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/health")
def health():
    return {"status": "ok", "service": "doc-service"}


@app.get("/info")
def info(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    check_api_key(x_api_key)
    return {"service": "doc-service", "version": "0.1.1"}


@app.post("/tldr")
def tldr_endpoint(
    req: TldrRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    lang: str = Query(
        default=DEFAULT_LANGUAGE, description="Language code (ru, kz, en)"
    ),
):
    check_api_key(x_api_key)

    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    lot = get_lot(req.lot_id)
    if not lot:
        raise HTTPException(404, f"Lot {req.lot_id} not found")

    # Generate localized TL;DR
    title = lot.get("title", "Unknown lot")
    price = lot.get("price", 0)

    # Create lines with translations
    lines = [
        f"{get_translation('lot_summary', lang)}: {title}",
        f"{get_translation('price', lang)}: {price:,.2f} {get_translation('currency', lang) if 'currency' in LOCALES.get(lang, {}) else 'тенге'}",
        f"{get_translation('status', lang)}: {get_translation('active', lang)}",
    ]

    return {
        "lot_id": req.lot_id,
        "lines": lines,
        "language": lang,
        "ts": datetime.now(UTC).isoformat(),
    }


@app.post("/letters/generate")
def generate_letter(
    req: RenderRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    lang: str = Query(
        default=DEFAULT_LANGUAGE, description="Language code (ru, kz, en)"
    ),
):
    check_api_key(x_api_key)

    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    # Simple template rendering with localization
    if req.template == "letters/guarantee":
        supplier = req.context.get("supplier_name", "N/A")
        lot_title = req.context.get("lot_title", "N/A")
        contact = req.context.get("contact", "N/A")

        # Get localized strings
        guarantee_letter_title = get_translation("guarantee_letter", lang)
        supplier_label = get_translation("company_name", lang)
        date_label = get_translation("date", lang)

        html = f"""
        <html>
        <head>
            <meta charset="utf-8">
        </head>
        <body>
        <h1>{guarantee_letter_title}</h1>
        <p>{supplier_label}: {supplier}</p>
        <p>{get_translation("lot_summary", lang)}: {lot_title}</p>
        <p>{get_translation("customer", lang)}: {contact}</p>
        <p>{date_label}: {datetime.now().strftime("%d.%m.%Y")}</p>
        <br>
        <p>{get_translation("with_respect", lang)},</p>
        <p>{get_translation("director", lang)}</p>
        </body>
        </html>
        """
    else:
        html = "<html><body><h1>Template not implemented</h1></body></html>"

    return {
        "template": req.template,
        "html": html,
        "language": lang,
        "length": len(html),
        "ts": datetime.now(UTC).isoformat(),
    }


@app.post("/render/html")
def render_html(
    req: RenderRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    lang: str = Query(
        default=DEFAULT_LANGUAGE, description="Language code (ru, kz, en)"
    ),
):
    check_api_key(x_api_key)
    return generate_letter(req, x_api_key, lang)


@app.get("/languages")
def get_languages(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Get available languages and their translations"""
    check_api_key(x_api_key)

    return {
        "default_language": DEFAULT_LANGUAGE,
        "supported_languages": list(SUPPORTED_LANGUAGES),
        "locales": LOCALES,
        "ts": datetime.now(UTC).isoformat(),
    }


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
