# ETL Service для ZakupAI

Сервис извлечения, трансформации и загрузки данных из GraphQL API госзакупок Казахстана в PostgreSQL.

## 🏗️ Архитектура

```
GraphQL API (ows.goszakup.gov.kz) → ETL Service → PostgreSQL
```

## 📋 Требования

- Python 3.11+
- PostgreSQL 13+
- Docker (опционально)
- Активный API токен госзакупок Казахстана

## 🚀 Быстрый старт

### 1. Переменные окружения

Создайте файл `.env`:

```bash
GOSZAKUP_TOKEN=your_goszakup_api_token_here
DATABASE_URL=postgresql://zakupai:zakupai@localhost:5432/zakupai
```

### 2. Запуск с Docker

```bash
cd services/etl-service
docker build -t etl-service .
docker run -p 8000:8000 --env-file .env etl-service
```

### 3. Запуск локально

```bash
cd services/etl-service
pip install -r requirements.txt
uvicorn main:app --reload
```

## 📊 API Эндпоинты

### POST /run

Запуск ETL процесса для загрузки данных за последние 7 дней.

**Параметры:**

- `days` (int): Количество дней для загрузки (фиксировано 7 для тестирования)

**Пример запроса:**

```bash
curl -X POST "http://localhost:8000/run" \
  -H "Content-Type: application/json" \
  -d '{"days": 7}'
```

**Ответ:**

```json
{
  "status": "success",
  "records": {
    "lots": 1250,
    "trdbuy": 875,
    "contracts": 340,
    "subjects": 15432,
    "rnu": 234,
    "plans": 567,
    "acts": 890,
    "subject_address": 12340,
    "subject_users": 8901,
    "ref_kato": 2456,
    "ref_countries": 195,
    "ref_buy_status": 15,
    "ref_trade_methods": 8,
    "ref_contract_status": 12,
    "contract_act": 445
  },
  "errors": []
}
```

### GET /health

Проверка состояния сервиса.

**Ответ:**

```json
{"status": "ok"}
```

## 🗃️ Структура данных

### Основные сущности (с фильтром по датам)

#### Lots (Лоты)

```sql
CREATE TABLE lots (
    id BIGINT PRIMARY KEY,
    trdBuyId BIGINT,
    nameRu TEXT,
    amount NUMERIC,
    descriptionRu TEXT,
    lastUpdateDate TIMESTAMP
);
```

#### TrdBuy (Закупки)

```sql
CREATE TABLE trdbuy (
    id BIGINT PRIMARY KEY,
    publishDate TIMESTAMP,
    endDate TIMESTAMP,
    customerBin VARCHAR(12),
    customerNameRu TEXT,
    refBuyStatusId INTEGER,
    nameRu TEXT,
    totalSum NUMERIC,
    numberAnno VARCHAR(50)
);
```

#### Contracts (Договоры)

```sql
CREATE TABLE contracts (
    id BIGINT PRIMARY KEY,
    trdBuyId BIGINT,
    contractSum NUMERIC,
    signDate TIMESTAMP,
    supplierBin VARCHAR(12),
    supplierNameRu TEXT,
    executionStatus TEXT,
    contractNumber VARCHAR(100)
);
```

### Справочные данные

#### Subjects (Участники)

```sql
CREATE TABLE subjects (
    id BIGINT PRIMARY KEY,
    bin VARCHAR(12) UNIQUE,
    iin VARCHAR(12),
    nameRu TEXT,
    okedCode VARCHAR(10),
    regionCode VARCHAR(10),
    markSmallEmployer BOOLEAN DEFAULT FALSE,
    markPatronymicSupplier BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## ⚙️ Конфигурация ETL

### GraphQL API параметры

- **URL:** `https://ows.goszakup.gov.kz/v3/graphql`
- **Авторизация:** `Bearer <GOSZAKUP_TOKEN>`
- **Лимит записей:** 200 на запрос
- **Пагинация:** через параметр `after` (ID последней записи)

### Защита от лимитов

- Задержка между запросами: `1 + random(0, 0.5)` секунд
- Retry при 403/429 ошибках: 3 попытки с экспоненциальной задержкой
- Максимальное время ожидания: 10 секунд

### Логирование

- **Файл:** `etl.log`
- **Ротация:** каждые 10MB, хранится 5 файлов
- **Уровни:** DEBUG (запросы), INFO (статистика), ERROR (ошибки)
- **Формат:** `%(asctime)s - %(levelname)s - %(message)s`

## 🔗 Интеграция с БД

### Подключение

Использует `psycopg2` для подключения к PostgreSQL через `DATABASE_URL`.

### Стратегия загрузки

- **Массовая вставка** через `psycopg2.extras.execute_values()`
- **Обработка конфликтов:** `ON CONFLICT DO NOTHING` (upsert)
- **Автоматическое создание таблиц** с базовой схемой
- **Индексы:** автоматически для `trdBuyId`, `bin`, `id`

### Схема конфликтов

- `lots`: по `id`
- `trdbuy`: по `id`
- `contracts`: по `id`
- `subjects`: по `id`
- `ref_kato`: по `katoCode`
- `ref_countries`: по `code`

## 🐳 Docker

### Dockerfile особенности

- Базовый образ: `python:3.11-slim`
- Установка `curl` для health check
- Создание директории для логов
- Health check каждые 30 секунд

### Health Check

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

## 📈 Мониторинг

### Метрики в ответе ETL

- Количество загруженных записей по каждой сущности
- Список ошибок (если есть)
- Статус выполнения (`success`/`error`)

### Логи

```bash
# Просмотр логов в реальном времени
tail -f etl.log

# Поиск ошибок
grep ERROR etl.log

# Статистика загрузки
grep "Fetched" etl.log
```

## 🔒 Безопасность

- API токен передается через переменные окружения
- Подключение к БД через защищенный URL
- Логирование не содержит конфиденциальных данных
- Health check без авторизации

## 🚨 Troubleshooting

### Частые ошибки

**403 Forbidden**

```
Error: API token invalid or expired
Solution: Check GOSZAKUP_TOKEN environment variable
```

**Connection refused**

```
Error: Could not connect to PostgreSQL
Solution: Check DATABASE_URL and database availability
```

**Rate limiting (429)**

```
Info: Automatic retry with exponential backoff
Action: No action required, service handles automatically
```

### Debug режим

```bash
# Запуск с детальным логированием
LOG_LEVEL=DEBUG uvicorn main:app --reload
```

## 📚 Зависимости

```
fastapi==0.104.1      # Web framework
uvicorn==0.24.0       # ASGI server
aiohttp==3.9.1        # HTTP client для GraphQL
psycopg2-binary==2.9.9 # PostgreSQL adapter
pydantic==2.5.0       # Data validation
python-dotenv==1.0.0  # Environment variables
tenacity==8.2.3       # Retry functionality
```

## 🔄 Процесс ETL

1. **Extract:** Загрузка данных из GraphQL API с пагинацией
1. **Transform:** Минимальная трансформация (типы данных)
1. **Load:** Массовая вставка в PostgreSQL с обработкой конфликтов

### Порядок загрузки

1. Lots (последние 7 дней)
1. TrdBuy (последние 7 дней)
1. Contracts (последние 7 дней)
1. Все справочные данные (Subjects, RNU, Plans, Acts, etc.)

## 📞 Поддержка

Для вопросов и предложений создавайте issues в репозитории проекта ZakupAI.
