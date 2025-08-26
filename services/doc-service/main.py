import os
import uuid
import json
import logging
import io
from datetime import datetime, timezone
from typing import Optional, Annotated, Union, List, Any

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from jinja2 import Environment, FileSystemLoader
import psycopg2
import weasyprint

# ---------- минимальное JSON-логирование + request-id ----------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("doc-service")

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

# ---------- Jinja2 setup ----------
jinja_env = Environment(loader=FileSystemLoader("templates"))

# ---------- FastAPI ----------
app = FastAPI(title="ZakupAI doc-service", version="0.1.0")

@app.middleware("http")
async def add_request_id_and_log(request: Request, call_next):
    rid = get_request_id(request.headers.get("X-Request-Id"))
    request.state.rid = rid
    response = await call_next(request)
    response.headers["X-Request-Id"] = rid
    return response

@app.get("/health")
def health():
    return {"status":"ok","service":"doc-service"}

@app.get("/info")
def info(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    if x_api_key != os.getenv("API_KEY","dev-key"):
        raise HTTPException(status_code=401, detail="unauthorized")
    return {"service":"doc-service","version":"0.1.0"}

# ---------- схемы ----------
class TldrRequest(BaseModel):
    lot_id: Optional[int] = None
    text: Optional[str] = None

class LetterGenerateRequest(BaseModel):
    template: str
    context: dict

class RenderHtmlRequest(BaseModel):
    template: str
    context: dict

class RenderPDFRequest(BaseModel):
    html: Optional[str] = None
    template: Optional[str] = None
    context: dict[str, Any] = Field(default_factory=dict)

# ---------- helpers ----------
def generate_tldr_from_lot(lot_id: int) -> dict:
    """Генерирует 3-5 строк TL;DR по lot_id из БД"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Получаем информацию о лоте
                cur.execute("""
                    SELECT id, title, price, deadline, customer_bin, plan_id
                    FROM lots WHERE id = %s
                """, (lot_id,))
                lot_row = cur.fetchone()
                
                if not lot_row:
                    return {"lines": ["Лот не найден"], "lot_id": lot_id, "market_sum": 0}
                
                lot_data = {
                    "id": lot_row[0],
                    "title": lot_row[1],
                    "price": float(lot_row[2]) if lot_row[2] else 0,
                    "deadline": lot_row[3],
                    "customer_bin": lot_row[4],
                    "plan_id": lot_row[5]
                }
                
                # Получаем рыночную сумму
                cur.execute("""
                    SELECT COALESCE(SUM(p.price * lp.qty), 0) as market_sum
                    FROM lot_prices lp
                    JOIN prices p ON lp.price_id = p.id
                    WHERE lp.lot_id = %s
                """, (lot_id,))
                market_sum_row = cur.fetchone()
                market_sum = float(market_sum_row[0]) if market_sum_row else 0
                
                # Генерируем простые строки
                lines = [
                    f"Лот: {lot_data['title']}",
                    f"Цена лота: {lot_data['price']:,.0f} тенге",
                    f"Рыночная стоимость: {market_sum:,.0f} тенге",
                ]
                
                if lot_data['deadline']:
                    lines.append(f"Срок поставки: {lot_data['deadline']}")
                
                if lot_data['customer_bin']:
                    lines.append(f"БИН заказчика: {lot_data['customer_bin']}")
                
                return {
                    "lines": lines,
                    "lot_id": lot_id,
                    "market_sum": market_sum
                }
                
    except Exception as e:
        log.error(f"Error generating TLDR for lot {lot_id}: {e}")
        return {"lines": [f"Ошибка получения данных: {e}"], "lot_id": lot_id, "market_sum": 0}

def generate_tldr_from_text(text: str) -> dict:
    """Генерирует 3-5 строк TL;DR из произвольного текста"""
    words = text.split()
    lines = [
        f"Текст содержит {len(words)} слов",
        f"Первые слова: {' '.join(words[:5])}...",
        f"Длина текста: {len(text)} символов"
    ]
    
    # Простой поиск ключевых слов
    if "БИН" in text or "bin" in text.lower():
        lines.append("Содержит информацию о БИН")
    if any(word in text.lower() for word in ["поставка", "товар", "услуг"]):
        lines.append("Связано с поставками/услугами")
        
    return {"lines": lines, "lot_id": None, "market_sum": 0}

# ---------- эндпоинты ----------
@app.post("/tldr")
def tldr(req: TldrRequest, request: Request):
    rid = request.state.rid
    
    if req.lot_id:
        result = generate_tldr_from_lot(req.lot_id)
    elif req.text:
        result = generate_tldr_from_text(req.text)
    else:
        raise HTTPException(status_code=400, detail="Either lot_id or text required")
    
    result.update({
        "request_id": rid,
        "ts": datetime.now(timezone.utc).isoformat()
    })
    
    return result

@app.post("/letters/generate")
def generate_letter(req: LetterGenerateRequest, request: Request):
    rid = request.state.rid
    
    try:
        template = jinja_env.get_template(f"letters/{req.template}.html")
        context = req.context.copy()
        context["today"] = datetime.now().strftime("%Y-%m-%d")
        
        html = template.render(**context)
        
        return {
            "html": html,
            "template": req.template,
            "request_id": rid,
            "ts": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        log.error(f"Template rendering error: {e}")
        raise HTTPException(status_code=400, detail=f"Template error: {e}")

@app.post("/render/html")
def render_html(req: RenderHtmlRequest, request: Request):
    rid = request.state.rid
    
    try:
        template = jinja_env.get_template(f"{req.template}.html")
        html = template.render(**req.context)
        
        return {
            "html": html,
            "template": req.template,
            "request_id": rid,
            "ts": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        log.error(f"Template rendering error: {e}")
        raise HTTPException(status_code=400, detail=f"Template error: {e}")

@app.post("/render/pdf")
def render_pdf(req: RenderPDFRequest, request: Request):
    rid = request.state.rid
    
    try:
        if req.template:
            template = jinja_env.get_template(f"{req.template}.html")
            html = template.render(**req.context)
        elif req.html:
            html = req.html
        else:
            raise HTTPException(status_code=400, detail="Either html or template required")
        
        pdf_bytes = weasyprint.HTML(string=html).write_pdf()
        
        log.info(f'PDF generated successfully (request_id={rid})')
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": "inline; filename=document.pdf"}
        )
    except Exception as e:
        log.error(f"PDF render error (request_id={rid}): {e}")
        raise HTTPException(status_code=500, detail=f"PDF error: {e}")