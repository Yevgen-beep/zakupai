# Billing Service Documentation

## Обзор

Billing Service обеспечивает управление пользователями, API ключами, лимитами и подписками в экосистеме ZakupAI. Работает как центральный компонент для валидации доступа и контроля использования всех сервисов.

## Архитектура

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Telegram Bot  │    │    Web UI       │    │   n8n/Flowise   │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────────┐
                    │ Billing Service │
                    │    :7004        │
                    └─────────┬───────┘
                              │
                    ┌─────────────────┐
                    │   PostgreSQL    │
                    │ billing schema  │
                    └─────────────────┘
```

## Схема базы данных

### Таблица `billing.users`

```sql
CREATE TABLE billing.users (
    id SERIAL PRIMARY KEY,
    tg_id BIGINT UNIQUE,                     -- Telegram ID
    email TEXT,                              -- Email (опционально)
    plan TEXT DEFAULT 'free',                -- 'free', 'premium'
    status TEXT DEFAULT 'active',            -- 'active', 'suspended', 'inactive'
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
```

### Таблица `billing.api_keys`

```sql
CREATE TABLE billing.api_keys (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES billing.users(id) ON DELETE CASCADE,
    key TEXT UNIQUE NOT NULL,                -- UUID формат
    status TEXT DEFAULT 'active',            -- 'active', 'revoked', 'expired'
    created_at TIMESTAMP DEFAULT now(),
    expires_at TIMESTAMP,                    -- NULL = не истекает
    last_used_at TIMESTAMP
);
```

### Таблица `billing.usage`

```sql
CREATE TABLE billing.usage (
    id BIGSERIAL PRIMARY KEY,
    api_key_id INT REFERENCES billing.api_keys(id) ON DELETE CASCADE,
    endpoint TEXT NOT NULL,                  -- '/calc/margin', '/risk/analyze', 'lot', 'start'
    requests INT DEFAULT 1,                  -- количество запросов
    created_at TIMESTAMP DEFAULT now()
);
```

### Таблица `billing.payments`

```sql
CREATE TABLE billing.payments (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES billing.users(id) ON DELETE CASCADE,
    amount NUMERIC(10,2) NOT NULL,           -- сумма
    currency TEXT DEFAULT 'KZT',
    method TEXT,                             -- 'test', 'kaspi', 'stripe'
    status TEXT DEFAULT 'pending',           -- 'pending', 'success', 'failed'
    external_id TEXT,                        -- ID от платежной системы
    created_at TIMESTAMP DEFAULT now()
);
```

### Индексы для оптимизации

```sql
CREATE INDEX idx_billing_users_tg_id ON billing.users(tg_id);
CREATE INDEX idx_billing_api_keys_key ON billing.api_keys(key);
CREATE INDEX idx_billing_api_keys_user_id ON billing.api_keys(user_id);
CREATE INDEX idx_billing_usage_api_key_id ON billing.usage(api_key_id);
CREATE INDEX idx_billing_usage_created_at ON billing.usage(created_at);
```

## API Endpoints

### POST /billing/create_key

**Описание:** Создает новый API ключ для пользователя

**Request:**

```json
{
    "tg_id": 123456789,
    "email": "user@example.com"
}
```

**Response:**

```json
{
    "api_key": "550e8400-e29b-41d4-a716-446655440000",
    "plan": "free",
    "expires_at": null
}
```

### POST /billing/validate_key

**Описание:** Валидирует API ключ и проверяет лимиты

**Request:**

```json
{
    "api_key": "550e8400-e29b-41d4-a716-446655440000",
    "endpoint": "lot"
}
```

**Response (успех):**

```json
{
    "valid": true,
    "plan": "free",
    "remaining_requests": 95,
    "message": null
}
```

**Response (лимит превышен):**

```json
{
    "valid": false,
    "plan": "free",
    "remaining_requests": 0,
    "message": "Daily limit exceeded (100/100)"
}
```

### POST /billing/usage

**Описание:** Логирует использование API

**Request:**

```json
{
    "api_key": "550e8400-e29b-41d4-a716-446655440000",
    "endpoint": "lot",
    "requests": 1
}
```

**Response:**

```json
{
    "logged": true
}
```

### GET /billing/stats/{tg_id}

**Описание:** Получает статистику пользователя

**Response:**

```json
{
    "tg_id": 123456789,
    "plan": "free",
    "status": "active",
    "created_at": "2024-01-15T10:30:00",
    "keys": {
        "total": 2,
        "active": 1
    },
    "usage": {
        "total_requests": 247,
        "today_requests": 15,
        "hour_requests": 3,
        "daily_limit": 100,
        "hourly_limit": 20
    },
    "limits": {
        "daily_remaining": 85,
        "hourly_remaining": 17
    }
}
```

## Система лимитов

### Планы подписки

| План        | Запросов/день | Запросов/час | Цена         | Особенности                                     |
| ----------- | ------------- | ------------ | ------------ | ----------------------------------------------- |
| **Free**    | 100           | 20           | 0 ₸          | Базовый анализ                                  |
| **Premium** | 5,000         | 500          | 10,000 ₸/мес | PDF экспорт, риск-скоринг, генерация документов |

### Алгоритм проверки лимитов

```python
def check_limits(api_key_id: int, plan: str) -> bool:
    plan_config = PLANS.get(plan, PLANS["free"])

    # Дневной лимит
    daily_usage = get_daily_usage(api_key_id)
    if daily_usage >= plan_config["requests_per_day"]:
        return False

    # Часовой лимит
    hourly_usage = get_hourly_usage(api_key_id)
    if hourly_usage >= plan_config["requests_per_hour"]:
        return False

    return True
```

### SQL запросы лимитов

**Дневной лимит:**

```sql
SELECT COALESCE(SUM(requests), 0)
FROM billing.usage
WHERE api_key_id = $1
AND created_at >= CURRENT_DATE
```

**Часовой лимит:**

```sql
SELECT COALESCE(SUM(requests), 0)
FROM billing.usage
WHERE api_key_id = $1
AND created_at >= NOW() - INTERVAL '1 hour'
```

## Docker конфигурация

### docker-compose.yml

```yaml
billing-service:
  build: ./services/billing-service
  container_name: zakupai-billing-service
  ports:
    - "7004:8000"
  env_file:
    - .env
  depends_on:
    db:
      condition: service_healthy
  networks:
    - zakupai-network
  restart: unless-stopped
```

### Health check

```bash
curl http://localhost:7004/health
# Response: {"status": "healthy", "service": "billing"}
```

## Production архитектура (Future)

### Изоляция сервиса

```
┌─────────────────────────────────────────────────────────────────┐
│                    Production Infrastructure                     │
├─────────────────────────────────────────────────────────────────┤
│  ZakupAI Services (zakupai.site)                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │ Calc        │ │ Risk        │ │ Doc         │               │
│  │ Service     │ │ Engine      │ │ Service     │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│            │             │             │                        │
│            └─────────────┼─────────────┘                        │
│                          │ X-API-Key requests                   │
│                          ▼                                      │
├─────────────────────────────────────────────────────────────────┤
│  Isolated Billing Service (billing.zakupai.site)              │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ • Отдельная БД (billing-only PostgreSQL)                   │ │
│  │ • Оффсайт бэкапы (Backblaze B2, AWS S3)                   │ │
│  │ • Kaspi API + Stripe интеграция                            │ │
│  │ • Webhook обработка платежей                               │ │
│  │ • Отдельный CI/CD и мониторинг                             │ │
│  │ • Доступ только через X-API-Key                            │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Платежные системы

#### Kaspi API (Казахстан)

```json
{
    "merchant_id": "KASPI_MERCHANT_ID",
    "amount": 10000.00,
    "currency": "KZT",
    "order_id": "premium_subscription_123",
    "callback_url": "https://billing.zakupai.site/webhook/kaspi"
}
```

#### Stripe (Международные)

```json
{
    "amount": 2500,
    "currency": "usd",
    "payment_method_types": ["card"],
    "metadata": {
        "user_id": "123",
        "plan": "premium"
    }
}
```

### Webhook обработка

```python
@app.post("/webhook/payment_callback")
async def payment_webhook(payload: dict):
    """
    Обработка webhook от платежных систем
    """
    # 1. Проверяем подпись webhook
    # 2. Находим платеж по external_id
    # 3. Обновляем статус: pending → success
    # 4. Активируем Premium подписку
    # 5. Уведомляем пользователя в Telegram
```

### Безопасность Production

**Изоляция доступа:**

- Разработчики имеют доступ только к ZakupAI сервисам
- Billing Service изолирован на отдельном сервере
- Общение только через X-API-Key валидацию

**Бэкапы:**

```bash
# Автоматические бэкапы billing БД
pg_dump billing_db > billing_backup_$(date +%Y%m%d).sql
rclone copy billing_backup_$(date +%Y%m%d).sql backblaze:zakupai-billing-backups/
```

**Мониторинг:**

- Отдельный Prometheus/Grafana для billing
- Алерты на превышение лимитов
- Мониторинг платежных транзакций

## Использование

### Интеграция в коде

```python
# Проверка API ключа перед выполнением операции
async def validate_request(api_key: str, endpoint: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://billing-service:7004/billing/validate_key",
            json={"api_key": api_key, "endpoint": endpoint}
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("valid", False)
    return False

# Логирование после успешного выполнения
async def log_api_usage(api_key: str, endpoint: str):
    async with aiohttp.ClientSession() as session:
        await session.post(
            "http://billing-service:7004/billing/usage",
            json={"api_key": api_key, "endpoint": endpoint, "requests": 1}
        )
```

### Мониторинг метрик

```bash
# Активные пользователи
curl "http://localhost:7004/billing/metrics" | grep billing_active_users

# Использование по планам
curl "http://localhost:7004/billing/metrics" | grep billing_requests_by_plan

# Превышение лимитов
curl "http://localhost:7004/billing/metrics" | grep billing_limit_exceeded
```

## Заключение

Billing Service обеспечивает:

- ✅ Централизованное управление пользователями и ключами
- ✅ Контроль лимитов Free/Premium планов
- ✅ Детальное логирование использования
- ✅ Готовность к Production с платежными системами
- ✅ Изоляция и безопасность в продакшене
