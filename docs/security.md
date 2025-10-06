# Security Guide

## Обзор

ZakupAI реализует многоуровневую систему безопасности, включающую аутентификацию, авторизацию, валидацию данных, мониторинг безопасности и защиту от распространенных атак. Безопасность обеспечивается на уровне API, данных, инфраструктуры и DevOps процессов.

## Архитектура безопасности

```
┌─────────────────────────────────────────────────────────────────┐
│                    Security Layers                              │
├─────────────────────────────────────────────────────────────────┤
│ 1. Network Security (Firewall, SSL/TLS)                        │
├─────────────────────────────────────────────────────────────────┤
│ 2. API Security (X-API-Key, Rate Limiting)                     │
├─────────────────────────────────────────────────────────────────┤
│ 3. Application Security (Input Validation, CORS)               │
├─────────────────────────────────────────────────────────────────┤
│ 4. Data Security (Encryption, Audit Logs)                      │
├─────────────────────────────────────────────────────────────────┤
│ 5. Infrastructure Security (Container Security, Secrets)        │
└─────────────────────────────────────────────────────────────────┘
```

## Аутентификация и авторизация

### X-API-Key система

**Описание:** Единая система аутентификации для всех сервисов ZakupAI

**Реализация в FastAPI:**

```python
from fastapi import HTTPException, Header
from typing import Annotated
import os

# Dependency для проверки API ключа
async def verify_api_key(x_api_key: Annotated[str, Header()]) -> str:
    """
    Проверяет X-API-Key заголовок для аутентификации
    """
    expected_key = os.getenv("ZAKUPAI_API_KEY")

    if not expected_key:
        raise HTTPException(
            status_code=500,
            detail="API key not configured on server"
        )

    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="X-API-Key header is required"
        )

    if x_api_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return x_api_key

# Использование в защищенных эндпоинтах
@app.get("/info")
async def get_info(api_key: str = Depends(verify_api_key)):
    """Защищенный эндпоинт с информацией о сервисе"""
    return {
        "service": "calc-service",
        "version": "1.0.0",
        "authenticated": True
    }
```

### Billing Service интеграция

**Расширенная аутентификация через Billing Service:**

```python
import aiohttp
from fastapi import HTTPException

async def verify_billing_key(api_key: str, endpoint: str) -> dict:
    """
    Проверяет API ключ через Billing Service
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://billing-service:7004/billing/validate_key",
            json={"api_key": api_key, "endpoint": endpoint}
        ) as response:
            if response.status == 200:
                data = await response.json()
                if not data.get("valid"):
                    raise HTTPException(
                        status_code=429,
                        detail=f"API limit exceeded: {data.get('message')}"
                    )
                return data
            else:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid API key"
                )

# Middleware для автоматической проверки
class BillingAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Проверяем только защищенные пути
            protected_paths = ["/calc/", "/risk/", "/doc/", "/embed/"]
            path = scope["path"]

            if any(path.startswith(p) for p in protected_paths):
                headers = dict(scope["headers"])
                api_key = headers.get(b"x-api-key")

                if api_key:
                    try:
                        await verify_billing_key(
                            api_key.decode(),
                            path.split("/")[1]  # endpoint из пути
                        )
                    except HTTPException as e:
                        # Возвращаем ошибку аутентификации
                        response = Response(
                            content=json.dumps({"detail": e.detail}),
                            status_code=e.status_code,
                            media_type="application/json"
                        )
                        await response(scope, receive, send)
                        return

        await self.app(scope, receive, send)
```

## Rate Limiting

### Nginx Gateway уровень

**Конфигурация (`gateway/nginx.conf`):**

```nginx
# Rate limiting zones
limit_req_zone $binary_remote_addr zone=general:10m rate=60r/m;
limit_req_zone $binary_remote_addr zone=strict:10m rate=30r/m;
limit_req_zone $api_key zone=api_key_limit:10m rate=100r/m;

# Custom log format для security мониторинга
log_format security_log '$remote_addr - $remote_user [$time_local] '
                       '"$request" $status $body_bytes_sent '
                       '"$http_referer" "$http_user_agent" '
                       '"$http_x_api_key" $request_time';

server {
    listen 80;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";

    # Hide server information
    server_tokens off;

    # Rate limiting для внешних API
    location /api/ {
        limit_req zone=general burst=10 nodelay;
        limit_req_status 429;

        # API Key из заголовка для персонализированного лимита
        set $api_key $http_x_api_key;
        limit_req zone=api_key_limit burst=20 nodelay;

        proxy_pass http://backend_services;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # Security logging
        access_log /var/log/nginx/security.log security_log;
    }

    # Более строгие лимиты для административных эндпоинтов
    location /admin/ {
        limit_req zone=strict burst=5 nodelay;

        # Ограничение по IP для admin
        allow 192.168.1.0/24;
        allow 10.0.0.0/8;
        deny all;

        proxy_pass http://backend_services;
    }

    # Блокировка подозрительных запросов
    location ~* \.(env|git|svn|htaccess)$ {
        deny all;
        return 404;
    }
}
```

### Application-level Rate Limiting

**FastAPI middleware:**

```python
import time
import asyncio
from collections import defaultdict, deque
from fastapi import HTTPException

class RateLimitMiddleware:
    def __init__(self, app, calls: int = 100, period: int = 60):
        self.app = app
        self.calls = calls
        self.period = period
        self.clients = defaultdict(deque)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            client_ip = self.get_client_ip(scope)
            current_time = time.time()

            # Очищаем старые записи
            client_calls = self.clients[client_ip]
            while client_calls and client_calls[0] <= current_time - self.period:
                client_calls.popleft()

            # Проверяем лимит
            if len(client_calls) >= self.calls:
                response = Response(
                    content=json.dumps({
                        "error": "Rate limit exceeded",
                        "retry_after": self.period
                    }),
                    status_code=429,
                    media_type="application/json"
                )
                await response(scope, receive, send)
                return

            # Добавляем новый запрос
            client_calls.append(current_time)

        await self.app(scope, receive, send)

    def get_client_ip(self, scope):
        headers = dict(scope["headers"])
        # Проверяем X-Real-IP, затем X-Forwarded-For
        real_ip = headers.get(b"x-real-ip")
        if real_ip:
            return real_ip.decode()

        forwarded = headers.get(b"x-forwarded-for")
        if forwarded:
            return forwarded.decode().split(",")[0].strip()

        return scope.get("client", [""])[0]
```

## CORS и CSRF защита

### CORS конфигурация

**FastAPI CORS middleware:**

```python
from fastapi.middleware.cors import CORSMiddleware
import os

# CORS настройки по окружениям
def get_cors_origins():
    env = os.getenv("ENVIRONMENT", "dev")

    if env == "dev":
        return ["http://localhost:3000", "http://localhost:8082"]
    elif env == "stage":
        return ["https://stage.zakupai.site", "https://stage-admin.zakupai.site"]
    elif env == "prod":
        return ["https://zakupai.site", "https://admin.zakupai.site"]

    return []

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-RateLimit-Remaining"]
)
```

### CSRF защита

**CSRF токены для веб-интерфейса:**

```python
from fastapi import Cookie, Form, HTTPException
import secrets
import hmac
import hashlib

CSRF_SECRET = os.getenv("CSRF_SECRET", secrets.token_urlsafe(32))

def generate_csrf_token(session_id: str) -> str:
    """Генерирует CSRF токен для сессии"""
    timestamp = str(int(time.time()))
    payload = f"{session_id}:{timestamp}"
    signature = hmac.new(
        CSRF_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"{payload}:{signature}"

def verify_csrf_token(token: str, session_id: str) -> bool:
    """Проверяет CSRF токен"""
    try:
        payload, signature = token.rsplit(":", 1)
        expected_signature = hmac.new(
            CSRF_SECRET.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            return False

        token_session_id, timestamp = payload.split(":", 1)

        # Проверяем сессию и время жизни токена (1 час)
        if token_session_id != session_id:
            return False

        if int(time.time()) - int(timestamp) > 3600:
            return False

        return True

    except (ValueError, TypeError):
        return False

# Middleware для проверки CSRF
async def verify_csrf(
    csrf_token: str = Form(...),
    session_id: str = Cookie(...)
):
    if not verify_csrf_token(csrf_token, session_id):
        raise HTTPException(
            status_code=403,
            detail="Invalid CSRF token"
        )
```

## Валидация входных данных

### Pydantic модели с валидацией

**Базовые модели безопасности:**

```python
from pydantic import BaseModel, validator, constr, conint, Field
from typing import Optional, List
import re

class SecureBaseModel(BaseModel):
    """Базовая модель с security валидаторами"""

    @validator('*', pre=True)
    def prevent_xss(cls, v):
        """Предотвращение XSS атак"""
        if isinstance(v, str):
            # Удаляем потенциально опасные символы
            dangerous_chars = ['<', '>', '"', "'", '&']
            for char in dangerous_chars:
                if char in v:
                    v = v.replace(char, '')

            # Ограничиваем длину строк
            if len(v) > 10000:
                raise ValueError("String too long")

        return v

class LotAnalysisRequest(SecureBaseModel):
    lot_id: constr(regex=r'^\d+$', min_length=1, max_length=20)
    include_risks: bool = True
    language: constr(regex=r'^(ru|kz|en)$') = 'ru'

    @validator('lot_id')
    def validate_lot_id(cls, v):
        """Дополнительная валидация lot_id"""
        try:
            lot_id_int = int(v)
            if lot_id_int <= 0 or lot_id_int > 999999999:
                raise ValueError("Invalid lot ID range")
        except ValueError:
            raise ValueError("Lot ID must be a positive integer")
        return v

class FinanceCalculationRequest(SecureBaseModel):
    amount: conint(gt=0, le=999999999)  # Положительное число до 1 млрд
    vat_rate: float = Field(ge=0.0, le=1.0, default=0.12)  # 0-100%
    currency: constr(regex=r'^(KZT|USD|EUR)$') = 'KZT'

    @validator('amount')
    def validate_amount(cls, v):
        """Проверка разумности суммы"""
        if v > 100000000:  # 100 млн
            raise ValueError("Amount too large for processing")
        return v

class UserRegistrationRequest(SecureBaseModel):
    tg_id: conint(gt=0, le=9999999999)  # Telegram ID
    email: Optional[constr(regex=r'^[^@]+@[^@]+\.[^@]+$')] = None

    @validator('email')
    def validate_email_domain(cls, v):
        """Проверка домена email"""
        if v:
            domain = v.split('@')[1].lower()
            # Блокируем подозрительные домены
            blocked_domains = ['tempmail.org', '10minutemail.com']
            if domain in blocked_domains:
                raise ValueError("Email domain not allowed")
        return v
```

### SQL Injection защита

**Параметризованные запросы:**

```python
import asyncpg
from typing import List, Dict, Any

class SecureDatabase:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    async def execute_query(
        self,
        query: str,
        params: List[Any] = None
    ) -> List[Dict]:
        """Безопасное выполнение SQL запросов"""

        # Проверяем, что запрос не содержит опасных конструкций
        dangerous_keywords = [
            'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE',
            'INSERT INTO users', 'UPDATE users SET'  # Защита критичных таблиц
        ]

        query_upper = query.upper()
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                raise ValueError(f"Query contains dangerous keyword: {keyword}")

        async with asyncpg.connect(self.connection_string) as conn:
            if params:
                result = await conn.fetch(query, *params)
            else:
                result = await conn.fetch(query)

            return [dict(row) for row in result]

    async def get_lot_data(self, lot_id: int) -> Dict:
        """Безопасное получение данных лота"""
        query = """
            SELECT id, title, price, customer_bin, deadline
            FROM lots
            WHERE id = $1 AND status = 'active'
            LIMIT 1
        """

        results = await self.execute_query(query, [lot_id])
        return results[0] if results else None

# Использование ORM для дополнительной защиты
from sqlalchemy import text

async def safe_query_with_sqlalchemy(session, lot_id: int):
    """Использование SQLAlchemy для защиты от SQL инъекций"""
    query = text("""
        SELECT * FROM lots
        WHERE id = :lot_id
        AND status = 'active'
    """)

    result = await session.execute(query, {"lot_id": lot_id})
    return result.fetchall()
```

## Логирование и аудит

### Структурированные audit логи

**Audit logging middleware:**

```python
import json
import logging
from datetime import datetime
from fastapi import Request
import hashlib

# Настройка audit logger
audit_logger = logging.getLogger("audit")
audit_handler = logging.FileHandler("/var/log/zakupai/audit.log")
audit_handler.setFormatter(
    logging.Formatter('%(message)s')
)
audit_logger.addHandler(audit_handler)
audit_logger.setLevel(logging.INFO)

class AuditLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request_start = datetime.utcnow()

            # Получаем информацию о запросе
            client_ip = self.get_client_ip(scope)
            user_agent = self.get_header(scope, "user-agent")
            api_key = self.get_header(scope, "x-api-key")

            # Хэшируем API ключ для логирования
            api_key_hash = hashlib.sha256(
                api_key.encode() if api_key else b""
            ).hexdigest()[:16] if api_key else None

            # Перехватываем response
            response_data = {}

            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    response_data["status_code"] = message["status"]
                elif message["type"] == "http.response.body":
                    response_data["body_size"] = len(message.get("body", b""))

                await send(message)

            await self.app(scope, receive, send_wrapper)

            # Логируем audit событие
            audit_event = {
                "timestamp": request_start.isoformat(),
                "event_type": "api_request",
                "client_ip": client_ip,
                "user_agent": user_agent,
                "api_key_hash": api_key_hash,
                "method": scope["method"],
                "path": scope["path"],
                "query_string": scope["query_string"].decode(),
                "status_code": response_data.get("status_code"),
                "response_size": response_data.get("body_size"),
                "duration_ms": int(
                    (datetime.utcnow() - request_start).total_seconds() * 1000
                ),
            }

            audit_logger.info(json.dumps(audit_event))

        else:
            await self.app(scope, receive, send)

    def get_client_ip(self, scope):
        # Аналогично RateLimitMiddleware
        pass

    def get_header(self, scope, header_name):
        headers = dict(scope["headers"])
        header_value = headers.get(header_name.encode())
        return header_value.decode() if header_value else None
```

### Security событий мониторинг

**Детекция подозрительных событий:**

```python
import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta

class SecurityMonitor:
    def __init__(self):
        self.failed_attempts = defaultdict(deque)
        self.blocked_ips = set()

    async def track_failed_auth(self, client_ip: str, api_key: str = None):
        """Отслеживание неудачных попыток аутентификации"""
        current_time = datetime.utcnow()

        # Очищаем старые записи (за последний час)
        cutoff_time = current_time - timedelta(hours=1)
        attempts = self.failed_attempts[client_ip]

        while attempts and attempts[0] < cutoff_time:
            attempts.popleft()

        # Добавляем новую попытку
        attempts.append(current_time)

        # Проверяем количество неудачных попыток
        if len(attempts) >= 10:  # 10 неудачных попыток за час
            self.blocked_ips.add(client_ip)

            # Отправляем алерт
            await self.send_security_alert({
                "type": "brute_force_attempt",
                "client_ip": client_ip,
                "attempts": len(attempts),
                "api_key_hash": hashlib.sha256(
                    api_key.encode() if api_key else b""
                ).hexdigest()[:16],
                "blocked": True
            })

    async def check_suspicious_patterns(self, request_data: dict):
        """Поиск подозрительных паттернов в запросах"""
        suspicious_indicators = []

        # SQL injection паттерны
        sql_patterns = [
            "' OR '1'='1", "UNION SELECT", "DROP TABLE",
            "INSERT INTO", "DELETE FROM", "--", "/*"
        ]

        query_string = request_data.get("query_string", "")
        for pattern in sql_patterns:
            if pattern.lower() in query_string.lower():
                suspicious_indicators.append(f"SQL injection pattern: {pattern}")

        # XSS паттерны
        xss_patterns = ["<script>", "javascript:", "onload=", "onerror="]
        for pattern in xss_patterns:
            if pattern.lower() in query_string.lower():
                suspicious_indicators.append(f"XSS pattern: {pattern}")

        # Необычно большие запросы
        if len(query_string) > 1000:
            suspicious_indicators.append("Unusually large query string")

        if suspicious_indicators:
            await self.send_security_alert({
                "type": "suspicious_request_pattern",
                "client_ip": request_data.get("client_ip"),
                "indicators": suspicious_indicators,
                "request_path": request_data.get("path")
            })

    async def send_security_alert(self, alert_data: dict):
        """Отправка security алертов"""
        alert = {
            "timestamp": datetime.utcnow().isoformat(),
            "severity": "high",
            **alert_data
        }

        # Логируем в security лог
        security_logger = logging.getLogger("security")
        security_logger.warning(json.dumps(alert))

        # Отправляем в monitoring систему
        # await send_to_prometheus_alertmanager(alert)

        # Отправляем в Telegram для критичных событий
        if alert_data.get("type") in ["brute_force_attempt", "sql_injection"]:
            await self.send_telegram_alert(alert)

    async def send_telegram_alert(self, alert: dict):
        """Отправка критичных алертов в Telegram"""
        # Реализация отправки в Telegram
        pass
```

## DevOps Security

### Pre-commit hooks

**Файл `.pre-commit-config.yaml`:**

```yaml
repos:
  # Code quality
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3.12

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.0.270
    hooks:
      - id: ruff

  # Security scanning
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: [-r, services/, bot/, -f, json, -o, bandit-report.json]
        exclude: tests/

  # Secrets detection
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        exclude: package.lock.json

  # Infrastructure security
  - repo: https://github.com/aquasecurity/tfsec
    rev: v1.28.1
    hooks:
      - id: tfsec
        files: \.tf$

  # Docker security
  - repo: https://github.com/hadolint/hadolint
    rev: v2.12.0
    hooks:
      - id: hadolint-docker
        args: [--config, .hadolint.yaml]
```

### SAST - Static Analysis Security Testing

**Bandit конфигурация (`.bandit`):**

```yaml
skips:
  - B101  # assert_used - безопасно в тестах

exclude:
  - .venv
  - venv
  - build
  - dist
  - migrations
  - __pycache__
  - node_modules
  - .git
```

**Современный подход:** Bandit интегрирован в CI/CD с SARIF-отчётами для GitHub Security.

#### GitHub Security Integration (SARIF)

ZakupAI использует **SARIF (Static Analysis Results Interchange Format)** для автоматической публикации результатов безопасности в GitHub Security → Code Scanning.

**Преимущества SARIF:**

- 🔍 Визуализация уязвимостей прямо в Pull Requests
- 📊 Централизованный Security Dashboard в GitHub
- 🚨 Автоматические алерты для критичных находок
- 📝 Исторический трекинг уязвимостей
- ✅ Не блокирует CI pipeline при обнаружении проблем

**Конфигурация в `.github/workflows/ci.yml`:**

```yaml
bandit-scan:
  runs-on: ubuntu-latest
  permissions:
    security-events: write  # Необходимо для загрузки SARIF
    contents: read
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: "3.11"

    - name: Install bandit
      run: pip install bandit[sarif]

    - name: Run bandit (SARIF)
      continue-on-error: true  # Не блокируем pipeline
      run: |
        bandit -c .bandit \
          -r services/ libs/ bot/ web/ scripts/ tests/ *.py \
          --severity-level medium \
          -f sarif -o bandit.sarif

    - name: Upload SARIF to GitHub Security
      uses: github/codeql-action/upload-sarif@v3
      if: always()
      with:
        sarif_file: bandit.sarif
        category: bandit-security-scan

    - name: Upload SARIF artifact
      uses: actions/upload-artifact@v4
      if: always()
      with:
        name: bandit-sarif-report
        path: bandit.sarif
        retention-days: 30
```

**Ключевые параметры:**

| Параметр                         | Значение               | Назначение                           |
| -------------------------------- | ---------------------- | ------------------------------------ |
| `--severity-level medium`        | MEDIUM/HIGH/CRITICAL   | Фильтрует LOW-severity находки       |
| `continue-on-error: true`        | Продолжить при ошибках | Не блокирует deploy при находках     |
| `if: always()`                   | Всегда выполнять       | Загружает SARIF даже при ошибках     |
| `category: bandit-security-scan` | Категория в Security   | Отличает от других сканеров (CodeQL) |
| `retention-days: 30`             | 30 дней                | Хранение артефактов для аудита       |

#### Как интерпретировать SARIF-отчёты

**1. Просмотр в GitHub UI**

После запуска CI, результаты появляются в:

```
Repository → Security → Code scanning alerts
```

**Пример алерта:**

```
🔴 HIGH: Possible SQL injection vector through string-based query construction
📍 File: services/calc-service/main.py:142
📝 Description: User input is used directly in SQL query without parameterization
🔧 Fix: Use parameterized queries with asyncpg or SQLAlchemy
```

**2. Уровни Severity**

| Уровень         | Описание                                      | Действие                      |
| --------------- | --------------------------------------------- | ----------------------------- |
| 🔴 **CRITICAL** | Критичная уязвимость (RCE, SQLi)              | Немедленно исправить          |
| 🟠 **HIGH**     | Высокий риск (XSS, Path Traversal)            | Исправить в течение недели    |
| 🟡 **MEDIUM**   | Средний риск (weak crypto, hardcoded secrets) | Исправить в следующем спринте |
| 🟢 **LOW**      | Низкий риск (информационные предупреждения)   | Опционально                   |

**3. Частые находки Bandit и решения**

**B201 - Flask app with debug=True**

```python
# ❌ Небезопасно
app.run(debug=True)

# ✅ Безопасно
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
app.run(debug=DEBUG)
```

**B608 - Hardcoded SQL strings**

```python
# ❌ Небезопасно
query = f"SELECT * FROM users WHERE id = {user_id}"

# ✅ Безопасно (параметризованный запрос)
query = "SELECT * FROM users WHERE id = $1"
result = await conn.fetch(query, user_id)
```

**B105 - Hardcoded password**

```python
# ❌ Небезопасно
PASSWORD = "admin123"

# ✅ Безопасно
PASSWORD = os.getenv("ADMIN_PASSWORD")
if not PASSWORD:
    raise ValueError("ADMIN_PASSWORD not set")
```

**B301 - Pickle usage**

```python
# ❌ Небезопасно (deserialization attack)
import pickle
data = pickle.loads(user_input)

# ✅ Безопасно
import json
data = json.loads(user_input)
```

**B603 - subprocess without shell=False**

```python
# ❌ Небезопасно (command injection)
subprocess.call(f"ls {user_path}", shell=True)

# ✅ Безопасно
subprocess.call(["ls", user_path], shell=False)
```

**4. Скачивание SARIF-отчётов**

Для детального анализа скачайте артефакт:

```
GitHub Actions → Workflow Run → Artifacts → bandit-sarif-report
```

**Просмотр локально:**

```bash
# Установка SARIF Viewer
npm install -g @microsoft/sarif-multitool

# Конвертация в HTML
sarif-multitool convert bandit.sarif -o bandit-report.html

# Открытие в браузере
open bandit-report.html
```

**5. Подавление False Positives**

Если Bandit ошибочно сообщает об уязвимости, используйте аннотацию:

```python
import subprocess

def safe_execute_command(command: list[str]):
    """Выполняет команду безопасно (whitelist проверен выше)"""
    # nosec B603 - command is validated against whitelist
    return subprocess.call(command, shell=False)
```

**В `.bandit` можно глобально исключить правила:**

```yaml
skips:
  - B101  # assert_used
  - B601  # paramiko_calls (если используете paramiko)
```

**6. Автоматизация исправлений**

Для массовых исправлений используйте semgrep autofix:

```bash
# Установка
pip install semgrep

# Автоисправление SQL injection
semgrep --config "p/sql-injection" --autofix services/
```

#### GitHub Actions Security Workflow (полный пример)

```yaml
name: Security Scan

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  security-scan:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
      contents: read
    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'

    - name: Install security tools
      run: |
        pip install bandit[sarif] safety semgrep

    - name: Run Bandit SAST (SARIF)
      continue-on-error: true
      run: |
        bandit -c .bandit \
          -r services/ libs/ bot/ web/ scripts/ tests/ *.py \
          --severity-level medium \
          -f sarif -o bandit.sarif

    - name: Upload Bandit SARIF
      uses: github/codeql-action/upload-sarif@v3
      if: always()
      with:
        sarif_file: bandit.sarif
        category: bandit-sast

    - name: Check dependencies vulnerabilities
      run: |
        safety check --json --output safety-report.json || true

    - name: Run Semgrep
      run: |
        semgrep --config=auto --sarif --output=semgrep.sarif services/ bot/

    - name: Upload Semgrep SARIF
      uses: github/codeql-action/upload-sarif@v3
      if: always()
      with:
        sarif_file: semgrep.sarif
        category: semgrep-sast

    - name: Upload security reports
      uses: actions/upload-artifact@v4
      if: always()
      with:
        name: security-reports
        path: |
          bandit.sarif
          semgrep.sarif
          safety-report.json
        retention-days: 30
```

### Secrets Management

**Docker secrets в production:**

```yaml
# docker-compose.prod.yml
version: '3.8'

secrets:
  zakupai_api_key:
    external: true
  postgres_password:
    external: true
  telegram_token:
    external: true

services:
  billing-service:
    secrets:
      - zakupai_api_key
      - postgres_password
    environment:
      - ZAKUPAI_API_KEY_FILE=/run/secrets/zakupai_api_key
      - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
```

**Чтение secrets в приложении:**

```python
import os

def get_secret(secret_name: str, default: str = None) -> str:
    """Читает секрет из файла или переменной среды"""

    # Проверяем файл секрета (Docker secrets)
    secret_file = os.getenv(f"{secret_name.upper()}_FILE")
    if secret_file and os.path.exists(secret_file):
        with open(secret_file, 'r') as f:
            return f.read().strip()

    # Проверяем переменную среды
    env_value = os.getenv(secret_name.upper())
    if env_value:
        return env_value

    if default is not None:
        return default

    raise ValueError(f"Secret {secret_name} not found")

# Использование
ZAKUPAI_API_KEY = get_secret("zakupai_api_key")
POSTGRES_PASSWORD = get_secret("postgres_password")
TELEGRAM_TOKEN = get_secret("telegram_token")
```

## Container Security

### Dockerfile security

**Безопасный Dockerfile:**

```dockerfile
# Используем официальный образ с фиксированной версией
FROM python:3.12.1-slim

# Создаем non-root пользователя
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Устанавливаем security обновления
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    security-updates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем файлы с правильными правами
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .

# Убираем лишние права
RUN chmod -R 755 /app && \
    chmod -R 644 /app/*.py

# Переключаемся на non-root пользователя
USER appuser

# Используем non-root порт
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Container scanning

**Trivy security scanning:**

```bash
# Scan образа на уязвимости
trivy image zakupai/calc-service:latest

# Scan файловой системы
trivy fs /path/to/zakupai

# Интеграция в CI/CD
trivy image --exit-code 1 --severity HIGH,CRITICAL zakupai/calc-service:latest
```

## Network Security

### Firewall правила

**UFW конфигурация для production:**

```bash
#!/bin/bash

# Reset firewall
ufw --force reset
ufw default deny incoming
ufw default allow outgoing

# SSH (ограничиваем до admin сети)
ufw allow from 192.168.1.0/24 to any port 22
ufw allow from 10.0.0.0/8 to any port 22

# HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Monitoring (только admin IP)
ufw allow from 192.168.1.100 to any port 9090  # Prometheus
ufw allow from 192.168.1.100 to any port 3001  # Grafana

# Database (только internal)
ufw deny 5432/tcp

# API services (только через gateway)
ufw deny 7001/tcp  # calc-service
ufw deny 7002/tcp  # risk-engine
ufw deny 7003/tcp  # doc-service
ufw deny 7004/tcp  # billing-service

# Rate limiting with fail2ban
apt-get install fail2ban
systemctl enable fail2ban
systemctl start fail2ban

ufw --force enable
```

### SSL/TLS конфигурация

**Nginx SSL config:**

```nginx
# SSL configuration
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;

# HSTS
add_header Strict-Transport-Security "max-age=63072000" always;

# OCSP Stapling
ssl_stapling on;
ssl_stapling_verify on;
ssl_trusted_certificate /etc/ssl/certs/chain.pem;

# Security headers
add_header X-Frame-Options DENY always;
add_header X-Content-Type-Options nosniff always;
add_header Referrer-Policy no-referrer-when-downgrade always;
add_header Permissions-Policy "geolocation=(),midi=(),sync-xhr=(),microphone=(),camera=(),magnetometer=(),gyroscope=(),fullscreen=(self),payment=()";
```

## Мониторинг безопасности

### Security метрики

**Prometheus security metrics:**

```python
from prometheus_client import Counter, Histogram, Gauge

# Security метрики
security_events = Counter(
    'security_events_total',
    'Total security events',
    ['event_type', 'severity', 'client_ip']
)

auth_failures = Counter(
    'auth_failures_total',
    'Authentication failures',
    ['reason', 'client_ip']
)

blocked_requests = Counter(
    'blocked_requests_total',
    'Blocked suspicious requests',
    ['reason', 'client_ip']
)

# Использование
security_events.labels(
    event_type="brute_force",
    severity="high",
    client_ip="192.168.1.100"
).inc()
```

### Alerting правила

**Prometheus security alerts:**

```yaml
# security-alerts.yml
groups:
- name: security.rules
  rules:

  - alert: HighAuthFailureRate
    expr: rate(auth_failures_total[5m]) > 0.5
    for: 1m
    labels:
      severity: warning
    annotations:
      summary: "High authentication failure rate detected"
      description: "More than 30 auth failures per minute from {{ $labels.client_ip }}"

  - alert: SuspiciousRequestPattern
    expr: rate(blocked_requests_total[5m]) > 0.1
    for: 30s
    labels:
      severity: critical
    annotations:
      summary: "Suspicious request patterns detected"
      description: "Blocking {{ $value }} suspicious requests per second"

  - alert: SecurityEventSpike
    expr: rate(security_events_total[1m]) > 1.0
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "Security events spike detected"
      description: "Unusual security activity: {{ $value }} events per second"
```

## Incident Response

### Автоматическое блокирование

**IP blocking система:**

```python
class AutoBlockingSystem:
    def __init__(self):
        self.blocked_ips = set()
        self.temp_blocks = {}  # IP -> expiry time

    async def handle_security_event(self, event: dict):
        """Обработка security событий с автоблокировкой"""

        client_ip = event.get("client_ip")
        event_type = event.get("type")

        # Немедленная блокировка для критичных событий
        if event_type in ["sql_injection", "rce_attempt", "directory_traversal"]:
            await self.permanent_block_ip(client_ip)

        # Временная блокировка для подозрительной активности
        elif event_type in ["brute_force", "rate_limit_exceeded"]:
            await self.temporary_block_ip(client_ip, duration=3600)  # 1 час

    async def permanent_block_ip(self, ip: str):
        """Постоянная блокировка IP"""
        self.blocked_ips.add(ip)

        # Добавляем в iptables
        await asyncio.subprocess.run([
            "iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"
        ])

        # Уведомляем админов
        await self.notify_admins(f"🚨 Permanent block: {ip}")

    async def temporary_block_ip(self, ip: str, duration: int):
        """Временная блокировка IP"""
        expiry_time = time.time() + duration
        self.temp_blocks[ip] = expiry_time

        # Планируем разблокировку
        asyncio.create_task(self.unblock_ip_after(ip, duration))
```

## Заключение

Система безопасности ZakupAI обеспечивает:

- ✅ **Многоуровневую защиту** - от сети до приложения
- ✅ **Аутентификацию и авторизацию** - X-API-Key + Billing Service
- ✅ **Защиту от атак** - XSS, SQL injection, CSRF, brute force
- ✅ **Мониторинг безопасности** - логирование, алерты, метрики
- ✅ **DevSecOps процессы** - SAST, dependency scanning, security gates
- ✅ **Incident response** - автоматическое блокирование, уведомления
- ✅ **Compliance** - аудит логи, шифрование, secrets management
