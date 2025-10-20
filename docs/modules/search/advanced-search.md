# Расширенный поиск лотов - API Документация

Система расширенного поиска ZakupAI предоставляет мощные возможности для поиска лотов с фильтрацией, автодополнением и поддержкой русского языка.

## Обзор функциональности

### Основные возможности

- **Полнотекстовый поиск** с поддержкой русского языка
- **Фильтрация по сумме** (мин/макс)
- **Фильтрация по статусу** лота
- **Автодополнение** на основе ChromaDB
- **Пагинация** результатов
- **Высокая производительность** с PostgreSQL GIN индексами

### Архитектура

- **Backend**: FastAPI с PostgreSQL и ChromaDB
- **Frontend**: React + Axios с автодополнением
- **Telegram Bot**: Интеграция через API
- **Caching**: Redis для оптимизации производительности

______________________________________________________________________

## API Endpoints

### 1. Расширенный поиск лотов

**Endpoint**: `POST /api/search/advanced`

Выполняет расширенный поиск лотов с возможностью фильтрации по различным параметрам.

#### Request Body

```json
{
  "query": "компьютеры",
  "min_amount": 10000.0,
  "max_amount": 1000000.0,
  "status": "1",
  "limit": 25,
  "offset": 0
}
```

#### Parameters

| Параметр     | Тип     | Обязательный | Описание                                        |
| ------------ | ------- | ------------ | ----------------------------------------------- |
| `query`      | string  | ✓            | Поисковый запрос (мин. 1 символ, макс. 500)     |
| `min_amount` | number  | -            | Минимальная сумма лота (≥ 0)                    |
| `max_amount` | number  | -            | Максимальная сумма лота (≥ 0)                   |
| `status`     | string  | -            | Статус лота (1-10)                              |
| `limit`      | integer | -            | Количество результатов (1-100, по умолчанию 10) |
| `offset`     | integer | -            | Смещение для пагинации (≥ 0, по умолчанию 0)    |

#### Response

**Успешный ответ (200)**:

```json
{
  "results": [
    {
      "id": 12345,
      "nameRu": "Поставка компьютерного оборудования",
      "amount": 250000.0,
      "status": 1,
      "trdBuyId": 67890,
      "customerNameRu": "ТОО Компания Пример"
    }
  ],
  "total_count": 1
}
```

**Ошибка валидации (422)**:

```json
{
  "detail": [
    {
      "loc": ["body", "max_amount"],
      "msg": "max_amount must be greater than or equal to min_amount",
      "type": "value_error"
    }
  ]
}
```

#### Примеры запросов

**Поиск по ключевым словам**:

```bash
curl -X POST "http://localhost:8000/api/search/advanced" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "медицинское оборудование",
       "limit": 10
     }'
```

**Поиск с фильтрацией по сумме**:

```bash
curl -X POST "http://localhost:8000/api/search/advanced" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "строительство",
       "min_amount": 100000,
       "max_amount": 5000000,
       "status": "1"
     }'
```

______________________________________________________________________

### 2. Автодополнение

**Endpoint**: `GET /api/search/autocomplete`

Возвращает предложения автодополнения на основе ChromaDB.

#### Query Parameters

| Параметр | Тип    | Обязательный | Описание                          |
| -------- | ------ | ------------ | --------------------------------- |
| `query`  | string | ✓            | Поисковый запрос (мин. 2 символа) |

#### Request

```bash
GET /api/search/autocomplete?query=компьют
```

#### Response

**Успешный ответ (200)**:

```json
{
  "suggestions": [
    "компьютеры",
    "компьютерное оборудование",
    "компьютерные программы",
    "компьютерная техника"
  ]
}
```

**Нет предложений (200)**:

```json
{
  "suggestions": []
}
```

#### Пример запроса

```bash
curl "http://localhost:8000/api/search/autocomplete?query=медицин"
```

______________________________________________________________________

## Telegram Bot Integration

### Команда `/search`

Расширенная команда поиска с поддержкой параметров.

#### Синтаксис

```
/search <запрос> [параметры]
```

#### Параметры

- `min_amount:X` - минимальная сумма
- `max_amount:X` - максимальная сумма
- `status:X` - статус лота (1-10)

#### Примеры

**Базовый поиск**:

```
/search компьютеры
```

**Поиск с фильтрами**:

```
/search строительство min_amount:100000 max_amount:5000000 status:1
```

**Поиск по диапазону сумм**:

```
/search медицинское оборудование min_amount:50000 max_amount:200000
```

______________________________________________________________________

## Web UI Integration

### HTML Structure

```html
<form id="advancedSearchForm">
  <div class="search-input-container">
    <input type="text" id="advancedSearchInput" />
    <div id="searchSuggestions" class="autocomplete-container"></div>
  </div>

  <input type="number" id="minAmount" />
  <input type="number" id="maxAmount" />
  <select id="statusFilter">...</select>
</form>
```

### JavaScript Integration

```javascript
// Initialize autocomplete
const autocomplete = new SearchAutocomplete('advancedSearchInput', 'searchSuggestions');

// Handle form submission
document.getElementById('advancedSearchForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const response = await fetch('/api/search/advanced', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(formData)
  });
  const results = await response.json();
  // Process results...
});
```

______________________________________________________________________

## Database Schema

### Основные таблицы

#### `lots` (лоты)

```sql
CREATE TABLE lots (
    id BIGINT PRIMARY KEY,
    trdBuyId BIGINT NOT NULL,
    nameRu TEXT,
    amount NUMERIC(20,2),
    descriptionRu TEXT,
    lastUpdateDate TIMESTAMP,
    FOREIGN KEY (trdBuyId) REFERENCES trdbuy(id)
);
```

#### `trdbuy` (тендеры/закупки)

```sql
CREATE TABLE trdbuy (
    id BIGINT PRIMARY KEY,
    publishDate TIMESTAMP,
    endDate TIMESTAMP,
    customerBin VARCHAR(12),
    customerNameRu TEXT,
    refBuyStatusId INT,
    nameRu TEXT,
    totalSum NUMERIC(20,2)
);
```

### Индексы для производительности

```sql
-- GIN индексы для полнотекстового поиска
CREATE INDEX idx_lots_nameRu_gin ON lots USING GIN (to_tsvector('russian', nameRu));
CREATE INDEX idx_lots_descriptionRu_gin ON lots USING GIN (to_tsvector('russian', descriptionRu));
CREATE INDEX idx_trdbuy_nameRu_gin ON trdbuy USING GIN (to_tsvector('russian', nameRu));

-- B-tree индексы для фильтрации
CREATE INDEX idx_lots_amount ON lots(amount) WHERE amount IS NOT NULL;
CREATE INDEX idx_trdbuy_status ON trdbuy(refBuyStatusId) WHERE refBuyStatusId IS NOT NULL;

-- Композитные индексы для оптимизации JOIN
CREATE INDEX idx_lots_trdbuy_composite ON lots(trdBuyId, amount DESC, lastUpdateDate DESC);
```

______________________________________________________________________

## Performance Metrics

### Целевые показатели производительности

| Метрика                    | Целевое значение | Описание                                |
| -------------------------- | ---------------- | --------------------------------------- |
| **Время ответа поиска**    | < 2 секунды      | Время выполнения `/api/search/advanced` |
| **Время автодополнения**   | < 500ms          | Время ответа `/api/search/autocomplete` |
| **Пропускная способность** | 100+ RPS         | Запросов в секунду при пиковой нагрузке |
| **Точность поиска**        | > 85%            | Релевантность результатов поиска        |

### Мониторинг производительности

#### SQL запросы для мониторинга индексов

```sql
-- Статистика использования индексов
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
WHERE indexname LIKE 'idx_lots_%' OR indexname LIKE 'idx_trdbuy_%'
ORDER BY idx_scan DESC;

-- Размеры таблиц и индексов
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size
FROM pg_tables
WHERE tablename IN ('lots', 'trdbuy')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

#### Логирование производительности

```python
# Пример кода с логированием производительности
import time
import structlog

logger = structlog.get_logger(__name__)

@app.post("/api/search/advanced")
async def advanced_search(request: AdvancedSearchRequest):
    start_time = time.time()
    request_id = str(uuid.uuid4())

    try:
        # ... выполнение поиска

        execution_time = time.time() - start_time
        logger.info(
            "Advanced search completed",
            request_id=request_id,
            execution_time=execution_time,
            results_count=len(results),
            total_count=total_count
        )

    except Exception as e:
        logger.error(
            "Advanced search failed",
            request_id=request_id,
            error=str(e),
            execution_time=time.time() - start_time
        )
```

______________________________________________________________________

## Error Handling

### HTTP Status Codes

| Код     | Описание                  | Пример                        |
| ------- | ------------------------- | ----------------------------- |
| **200** | Успешный запрос           | Поиск выполнен                |
| **400** | Некорректный запрос       | Недопустимый формат данных    |
| **422** | Ошибка валидации          | Неверные параметры фильтрации |
| **500** | Внутренняя ошибка сервера | Ошибка базы данных            |

### Примеры ошибок

**Ошибка валидации параметров**:

```json
{
  "detail": [
    {
      "loc": ["body", "query"],
      "msg": "ensure this value has at least 1 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

**Ошибка диапазона сумм**:

```json
{
  "detail": [
    {
      "loc": ["body", "max_amount"],
      "msg": "max_amount must be greater than or equal to min_amount",
      "type": "value_error"
    }
  ]
}
```

**Внутренняя ошибка сервера**:

```json
{
  "detail": "Search failed"
}
```

______________________________________________________________________

## Security Considerations

### Валидация входных данных

- Все строковые параметры экранируются для предотвращения SQL injection
- Ограничения на длину строк и размер результатов
- Валидация числовых диапазонов

### Rate Limiting

- Ограничение на количество запросов в секунду
- Защита от злоупотреблений API

### Логирование безопасности

- Логирование всех запросов с IP-адресами
- Мониторинг подозрительной активности

______________________________________________________________________

## Testing

### Unit Tests

```python
import pytest
from fastapi.testclient import TestClient

def test_advanced_search_basic():
    response = client.post("/api/search/advanced", json={
        "query": "компьютеры",
        "limit": 10
    })
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "total_count" in data

def test_advanced_search_with_filters():
    response = client.post("/api/search/advanced", json={
        "query": "строительство",
        "min_amount": 10000,
        "max_amount": 100000,
        "status": "1"
    })
    assert response.status_code == 200
    # Проверка фильтрации...

def test_autocomplete():
    response = client.get("/api/search/autocomplete?query=компьют")
    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data
    assert len(data["suggestions"]) >= 0
```

### Integration Tests

```python
def test_end_to_end_search():
    # Тестирование полного цикла: запрос -> поиск -> результат
    search_request = {
        "query": "медицинское оборудование",
        "min_amount": 50000,
        "limit": 20
    }

    response = client.post("/api/search/advanced", json=search_request)
    assert response.status_code == 200

    results = response.json()["results"]
    for result in results:
        assert result["amount"] >= 50000
        assert "медицин" in result["nameRu"].lower()
```

### Performance Tests

```python
import asyncio
import time

async def test_search_performance():
    start = time.time()

    # Параллельные запросы
    tasks = [
        client.post("/api/search/advanced", json={"query": f"тест{i}"})
        for i in range(100)
    ]

    responses = await asyncio.gather(*tasks)
    execution_time = time.time() - start

    assert execution_time < 10  # Все 100 запросов за 10 секунд
    assert all(r.status_code == 200 for r in responses)
```

______________________________________________________________________

## Deployment

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://zakupai:password@localhost:5432/zakupai

# ChromaDB
CHROMADB_HOST=localhost
CHROMADB_PORT=8000

# Redis Cache
REDIS_URL=redis://localhost:6379/0

# Performance
MAX_SEARCH_RESULTS=100
SEARCH_TIMEOUT=30
AUTOCOMPLETE_CACHE_TTL=3600
```

### Docker Compose

```yaml
version: '3.8'
services:
  web:
    build: .
    environment:
      - DATABASE_URL=postgresql://zakupai:password@postgres:5432/zakupai
      - CHROMADB_HOST=chromadb
    depends_on:
      - postgres
      - chromadb
      - redis

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: zakupai
      POSTGRES_USER: zakupai
      POSTGRES_PASSWORD: password
    volumes:
      - ./db/init:/docker-entrypoint-initdb.d

  chromadb:
    image: ghcr.io/chroma-core/chroma:latest
    environment:
      - CHROMA_SERVER_HOST=0.0.0.0

  redis:
    image: redis:7-alpine
```

### Production Considerations

1. **Database Optimization**

   - Настройка PostgreSQL для высокой нагрузки
   - Регулярное обновление статистики таблиц
   - Мониторинг производительности запросов

1. **Caching Strategy**

   - Redis для кеширования частых запросов
   - ChromaDB оптимизация для автодополнения
   - CDN для статических ресурсов

1. **Monitoring & Logging**

   - Структурированное логирование с request ID
   - Метрики производительности в Prometheus
   - Алерты на высокое время ответа

______________________________________________________________________

## Changelog

### Version 1.0.0 (2024-09-17)

- ✅ Базовая функциональность расширенного поиска
- ✅ Автодополнение с ChromaDB
- ✅ Интеграция с Telegram ботом
- ✅ Web UI с автодополнением
- ✅ PostgreSQL GIN индексы для производительности
- ✅ Полная документация API

### Planned Features (v1.1.0)

- 🔄 Кеширование поисковых результатов
- 🔄 Расширенные фильтры (даты, регионы)
- 🔄 Экспорт результатов в Excel/CSV
- 🔄 Сохраненные поисковые запросы
- 🔄 API rate limiting и авторизация

______________________________________________________________________

## Support & Contact

Для вопросов и поддержки:

- **Документация**: `/docs/`
- **Issues**: GitHub Issues
- **API Reference**: Swagger UI в `/docs/`
