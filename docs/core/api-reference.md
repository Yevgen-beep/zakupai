# API Reference

Полная документация API эндпоинтов ZakupAI платформы с примерами запросов и ответов.

## Аутентификация

Все API запросы требуют заголовок `X-API-Key` для аутентификации:

```bash
curl -H "X-API-Key: your-api-key-here" \
     -H "Content-Type: application/json" \
     http://localhost:8080/api/endpoint
```

## Base URLs

| Окружение   | Base URL                         |
| ----------- | -------------------------------- |
| Development | `http://localhost:8080`          |
| Staging     | `https://stage-api.zakupai.site` |
| Production  | `https://api.zakupai.site`       |

______________________________________________________________________

## Billing Service API

### POST /billing/create_key

Создает новый API ключ для пользователя.

**Request:**

```json
{
  "tg_id": 123456789,
  "email": "user@example.com"
}
```

**Response (200):**

```json
{
  "api_key": "550e8400-e29b-41d4-a716-446655440000",
  "plan": "free",
  "expires_at": null
}
```

**cURL Example:**

```bash
curl -X POST http://localhost:7004/billing/create_key \
  -H "Content-Type: application/json" \
  -d '{"tg_id": 123456789, "email": "user@example.com"}'
```

### POST /billing/validate_key

Проверяет валидность API ключа и лимиты.

**Request:**

```json
{
  "api_key": "550e8400-e29b-41d4-a716-446655440000",
  "endpoint": "lot"
}
```

**Response (200) - Valid:**

```json
{
  "valid": true,
  "plan": "free",
  "remaining_requests": 95,
  "message": null
}
```

**Response (200) - Limit Exceeded:**

```json
{
  "valid": false,
  "plan": "free",
  "remaining_requests": 0,
  "message": "Daily limit exceeded (100/100)"
}
```

### POST /billing/usage

Логирует использование API.

**Request:**

```json
{
  "api_key": "550e8400-e29b-41d4-a716-446655440000",
  "endpoint": "lot",
  "requests": 1
}
```

**Response (200):**

```json
{
  "logged": true
}
```

### GET /billing/stats/{tg_id}

Получает статистику пользователя.

**Response (200):**

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

______________________________________________________________________

## Calc Service API

### POST /calc/vat

Рассчитывает НДС для указанной суммы.

**Request:**

```json
{
  "amount": 1000000,
  "vat_rate": 0.12
}
```

**Response (200):**

```json
{
  "amount": 1000000,
  "vat_rate": 0.12,
  "amount_without_vat": 892857.14,
  "vat_amount": 107142.86,
  "total_with_vat": 1000000,
  "calculation_date": "2024-01-15T10:30:00Z"
}
```

**cURL Example:**

```bash
curl -X POST http://localhost:7001/calc/vat \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"amount": 1000000, "vat_rate": 0.12}'
```

### POST /calc/margin

Анализирует маржинальность и прибыль.

**Request:**

```json
{
  "cost_price": 800000,
  "selling_price": 1000000,
  "quantity": 1
}
```

**Response (200):**

```json
{
  "cost_price": 800000,
  "selling_price": 1000000,
  "quantity": 1,
  "gross_profit": 200000,
  "margin_percent": 20.0,
  "markup_percent": 25.0,
  "roi_percent": 25.0,
  "total_cost": 800000,
  "total_revenue": 1000000,
  "profit_per_unit": 200000
}
```

### POST /calc/penalty

Рассчитывает пени по контракту.

**Request:**

```json
{
  "contract_amount": 1000000,
  "days_overdue": 10,
  "penalty_rate": 0.1
}
```

**Response (200):**

```json
{
  "contract_amount": 1000000,
  "days_overdue": 10,
  "penalty_rate": 0.1,
  "daily_penalty": 100,
  "total_penalty": 1000,
  "amount_with_penalty": 1001000
}
```

______________________________________________________________________

## Risk Engine API

### POST /risk/score

Выполняет риск-скоринг лота.

**Request:**

```json
{
  "lot_id": "12345",
  "analysis_depth": "full"
}
```

**Response (200):**

```json
{
  "lot_id": "12345",
  "overall_risk_score": 0.45,
  "risk_level": "medium",
  "risk_factors": {
    "customer_risk": 0.2,
    "technical_risk": 0.6,
    "financial_risk": 0.3,
    "timeline_risk": 0.5
  },
  "recommendations": [
    "Запросить техническое уточнение по п.3.2",
    "Предусмотреть резерв времени на согласования"
  ],
  "confidence": 0.85,
  "analysis_date": "2024-01-15T10:30:00Z"
}
```

### GET /risk/explain/{lot_id}

Получает детальное объяснение рисков.

**Response (200):**

```json
{
  "lot_id": "12345",
  "detailed_explanation": {
    "customer_analysis": {
      "score": 0.2,
      "factors": ["Надежный заказчик", "Своевременные платежи"],
      "history": "15 успешных контрактов за 2 года"
    },
    "technical_analysis": {
      "score": 0.6,
      "factors": ["Сложные технические требования", "Короткий срок реализации"],
      "complexity_indicators": ["API интеграция", "Высокие нагрузки"]
    },
    "financial_analysis": {
      "score": 0.3,
      "factors": ["Адекватный бюджет", "Стандартные условия оплаты"],
      "budget_adequacy": "sufficient"
    }
  },
  "mitigation_strategies": [
    "Создать детальный технический план",
    "Заложить буферное время на тестирование"
  ]
}
```

______________________________________________________________________

## Doc Service API

### POST /tldr

Генерирует краткое описание лота.

**Request:**

```json
{
  "lot_id": "12345",
  "language": "ru",
  "include_risks": true
}
```

**Response (200):**

```json
{
  "lot_id": "12345",
  "title": "Разработка веб-приложения для управления документооборотом",
  "summary": "Создание системы электронного документооборота с интеграцией ЭЦП",
  "key_requirements": [
    "Web-приложение на React/Node.js",
    "Интеграция с КазТокен",
    "Поддержка 1000+ пользователей",
    "Срок: 90 дней"
  ],
  "estimated_complexity": "high",
  "price": 5000000,
  "deadline": "2024-04-15",
  "customer": "АО \"Казпочта\"",
  "quick_analysis": {
    "pros": ["Техническое ТЗ детально проработано", "Адекватный бюджет"],
    "cons": ["Сжатые сроки", "Сложная интеграция"],
    "recommendation": "Участие возможно при наличии опытной команды"
  }
}
```

### POST /letters/generate

Генерирует документы по шаблонам.

**Request:**

```json
{
  "template": "commercial_offer",
  "context": {
    "lot_id": "12345",
    "company_name": "ТОО \"Инновации\"",
    "contact_person": "Иван Иванов",
    "proposed_price": 4500000,
    "delivery_time": 75
  },
  "language": "ru"
}
```

**Response (200):**

```json
{
  "document_type": "commercial_offer",
  "generated_content": "Уважаемые коллеги!\n\nТОО \"Инновации\" предлагает...",
  "document_id": "doc_abc123",
  "format": "html",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### POST /render/pdf

Конвертирует HTML в PDF.

**Request:**

```json
{
  "html_content": "<html><body><h1>Коммерческое предложение</h1>...</body></html>",
  "options": {
    "format": "A4",
    "orientation": "portrait",
    "margin": "2cm"
  }
}
```

**Response (200):**

```json
{
  "pdf_url": "https://storage.zakupai.site/documents/doc_abc123.pdf",
  "file_size": 156789,
  "pages_count": 3,
  "generated_at": "2024-01-15T10:30:00Z"
}
```

______________________________________________________________________

## Embedding API

### POST /embed

Создает векторные представления текста.

**Request:**

```json
{
  "text": "Разработка веб-приложения для управления документооборотом",
  "model": "all-MiniLM-L6-v2"
}
```

**Response (200):**

```json
{
  "embedding": [0.123, -0.456, 0.789, ...],
  "dimensions": 384,
  "model": "all-MiniLM-L6-v2",
  "text_length": 58
}
```

### POST /index

Индексирует документ в векторной базе.

**Request:**

```json
{
  "doc_id": "lot_12345",
  "content": "Полный текст технического задания...",
  "metadata": {
    "type": "tender_specification",
    "lot_id": "12345",
    "category": "IT",
    "indexed_at": "2024-01-15T10:30:00Z"
  }
}
```

**Response (200):**

```json
{
  "doc_id": "lot_12345",
  "indexed": true,
  "vector_id": "vec_abc123",
  "chunks_created": 5,
  "processing_time_ms": 234
}
```

### POST /search

Поиск похожих документов.

**Request:**

```json
{
  "query": "веб-приложение React Node.js",
  "limit": 10,
  "threshold": 0.7,
  "filters": {
    "category": "IT",
    "price_min": 1000000
  }
}
```

**Response (200):**

```json
{
  "query": "веб-приложение React Node.js",
  "results": [
    {
      "doc_id": "lot_12345",
      "similarity": 0.89,
      "content_excerpt": "Разработка веб-приложения на React/Node.js...",
      "metadata": {
        "lot_id": "12345",
        "price": 5000000,
        "category": "IT"
      }
    }
  ],
  "total_found": 1,
  "search_time_ms": 45
}
```

______________________________________________________________________

## Gateway Health Checks

### GET /health

Проверка работоспособности системы.

**Response (200):**

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "services": {
    "calc-service": "healthy",
    "risk-engine": "healthy",
    "doc-service": "healthy",
    "billing-service": "healthy",
    "embedding-api": "healthy"
  },
  "database": {
    "postgresql": "connected",
    "chromadb": "connected"
  }
}
```

### GET /info

Информация о системе (требует X-API-Key).

**Response (200):**

```json
{
  "name": "ZakupAI API Gateway",
  "version": "1.0.0",
  "environment": "production",
  "uptime_seconds": 86400,
  "requests_processed": 15420,
  "rate_limits": {
    "default": "60/minute",
    "authenticated": "100/minute"
  }
}
```

______________________________________________________________________

## Коды ошибок

| Code    | Description           | Example                           |
| ------- | --------------------- | --------------------------------- |
| **400** | Bad Request           | Неверный формат запроса           |
| **401** | Unauthorized          | Отсутствует или неверный API ключ |
| **403** | Forbidden             | Доступ запрещен                   |
| **429** | Too Many Requests     | Превышен rate limit               |
| **500** | Internal Server Error | Внутренняя ошибка сервера         |

### Примеры ошибок

**401 Unauthorized:**

```json
{
  "detail": "X-API-Key header is required",
  "error_code": "MISSING_API_KEY"
}
```

**429 Too Many Requests:**

```json
{
  "detail": "Daily limit exceeded (100/100)",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 3600,
  "plan": "free",
  "upgrade_url": "https://zakupai.site/premium"
}
```

**422 Validation Error:**

```json
{
  "detail": [
    {
      "loc": ["body", "lot_id"],
      "msg": "Lot ID must be a positive integer",
      "type": "value_error"
    }
  ],
  "error_code": "VALIDATION_ERROR"
}
```

______________________________________________________________________

## Rate Limits

| Plan        | Requests/Day | Requests/Hour | Burst |
| ----------- | ------------ | ------------- | ----- |
| **Free**    | 100          | 20            | 5     |
| **Premium** | 5,000        | 500           | 50    |

### Headers в ответе

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642248000
```

______________________________________________________________________

## SDK и Libraries

### Python SDK

```python
from zakupai import ZakupaiClient

client = ZakupaiClient(api_key="your-api-key")

# Анализ лота
result = client.analyze_lot("12345")
print(result.risk_score)

# Расчет НДС
vat = client.calculate_vat(1000000, vat_rate=0.12)
print(f"НДС: {vat.vat_amount} тг")
```

### JavaScript SDK

```javascript
import { ZakupaiAPI } from 'zakupai-js';

const api = new ZakupaiAPI({ apiKey: 'your-api-key' });

// Анализ лота
const analysis = await api.analyzeLot('12345');
console.log(`Риск: ${analysis.riskScore}`);

// TL;DR генерация
const tldr = await api.generateTldr('12345', { language: 'ru' });
console.log(tldr.summary);
```

______________________________________________________________________

## Webhook Events

### Payment Success

Отправляется при успешной оплате Premium подписки.

**POST /webhooks/payment**

```json
{
  "event": "payment.success",
  "user_id": 123456789,
  "plan": "premium",
  "amount": 10000,
  "currency": "KZT",
  "payment_method": "kaspi",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### API Limit Warning

Отправляется при достижении 80% лимита.

**POST /webhooks/limit_warning**

```json
{
  "event": "limit.warning",
  "user_id": 123456789,
  "plan": "free",
  "usage_percent": 80,
  "remaining_requests": 20,
  "reset_time": "2024-01-16T00:00:00Z"
}
```

______________________________________________________________________

## Postman Collection

Импортируйте коллекцию для тестирования API:

```json
{
  "info": {
    "name": "ZakupAI API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:8080"
    },
    {
      "key": "api_key",
      "value": "your-api-key-here"
    }
  ]
}
```

[Скачать Postman Collection](https://api.zakupai.site/postman/zakupai-api.json)

______________________________________________________________________

## Поддержка

- **API Issues**: [GitHub Issues](https://github.com/zakupai/zakupai/issues)
- **Documentation**: [docs.zakupai.site](https://docs.zakupai.site)
- **Status Page**: [status.zakupai.site](https://status.zakupai.site)
- **Discord**: [discord.gg/zakupai](https://discord.gg/zakupai)
