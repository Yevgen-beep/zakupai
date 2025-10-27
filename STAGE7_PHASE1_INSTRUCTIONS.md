# Stage 7 Phase 1: Security Quick Wins - Инструкция по запуску

## 📋 Что было реализовано

В `calc-service` добавлены следующие security-фичи:

### 1️⃣ Pydantic валидация входных данных
- **Файл**: `services/calc-service/schemas.py`
- **Схемы**:
  - `ProfitRequest`: валидация `lot_id`, `supplier_id`, `region`
  - `RiskScoreRequest`: валидация `supplier_bin` (12 цифр), `year` (2015-2030)

### 2️⃣ Ограничение размера payload (HTTP 413)
- **Файл**: `services/calc-service/main.py` → `PayloadSizeLimitMiddleware`
- **Лимит**: 2 MB
- Возвращает `{"detail": "Payload Too Large"}` если тело запроса > 2MB

### 3️⃣ Rate Limiter (slowapi)
- **Библиотека**: `slowapi>=0.1.9` добавлена в `requirements.txt`
- **Настройка**: `30 requests/minute` на эндпоинты `/calc/profit` и `/calc/risk-score`
- **Обработчик**: возвращает HTTP 429 с сообщением "Too Many Requests"

### 4️⃣ Централизованная обработка ошибок
- **Файл**: `services/calc-service/exceptions.py`
- **Обработчики**:
  - `validation_exception_handler` (422)
  - `payload_too_large_handler` (413)
  - `rate_limit_handler` (429)
  - `unauthorized_handler` (401)

### 5️⃣ Unit-тесты
- **Файл**: `services/calc-service/tests/test_validation.py`
- **Тесты**:
  - Валидация 422 (invalid lot_id, negative values, invalid BIN, invalid year, region length)
  - Payload limit 413
  - Rate limiting 429
  - Успешные запросы 200

### 6️⃣ OpenAPI документация
- **Скрипт**: `services/calc-service/generate_openapi.py`
- **Вывод**: `docs/openapi-calc.json`

---

## 🚀 Инструкция по запуску

### Шаг 1: Пересборка контейнера

```bash
docker compose build calc-service
```

### Шаг 2: Перезапуск сервиса

```bash
docker compose up -d calc-service
```

### Шаг 3: Проверка логов

```bash
docker compose logs -f calc-service
```

Убедитесь, что сервис запустился без ошибок.

---

## 🧪 Тестирование

### Вариант 1: Smoke-тесты (bash)

```bash
chmod +x stage7-smoke.sh
./stage7-smoke.sh
```

Этот скрипт проверит:
- ✅ Валидацию (422 для невалидных данных)
- ✅ Payload limit (413)
- ✅ Успешные запросы (200)

### Вариант 2: Pytest (внутри контейнера)

```bash
docker compose exec calc-service pytest tests/test_validation.py -v
```

### Вариант 3: Ручное тестирование с curl

#### Тест 1: Невалидный `lot_id` (ожидается 422)

```bash
curl -X POST http://localhost:7001/calc/profit \
  -H "Content-Type: application/json" \
  -d '{"lot_id":"abc","supplier_id":1,"region":"Almaty"}'
```

**Ожидаемый результат:**
```json
{
  "detail": "Validation error",
  "errors": [
    {
      "field": "body.lot_id",
      "message": "Input should be a valid integer",
      "type": "int_parsing"
    }
  ]
}
```

#### Тест 2: Отрицательный `lot_id` (ожидается 422)

```bash
curl -X POST http://localhost:7001/calc/profit \
  -H "Content-Type: application/json" \
  -d '{"lot_id":-1,"supplier_id":1,"region":"Almaty"}'
```

#### Тест 3: Невалидный BIN (ожидается 422)

```bash
curl -X POST http://localhost:7001/calc/risk-score \
  -H "Content-Type: application/json" \
  -d '{"supplier_bin":"123","year":2024}'
```

#### Тест 4: Успешный запрос (ожидается 200)

```bash
curl -X POST http://localhost:7001/calc/profit \
  -H "Content-Type: application/json" \
  -d '{"lot_id":123,"supplier_id":456,"region":"Almaty"}'
```

**Ожидаемый результат:**
```json
{
  "lot_id": 123,
  "supplier_id": 456,
  "region": "Almaty",
  "profit": 12756,
  "request_id": "...",
  "ts": "2025-10-26T..."
}
```

---

## 📊 Генерация OpenAPI документации

```bash
docker compose exec calc-service python generate_openapi.py
```

Проверить результат:
```bash
cat docs/openapi-calc.json | jq .
```

Или открыть Swagger UI в браузере:
```
http://localhost:7001/calc/docs
```

---

## ✅ Критерии приемки (DoD)

- [x] Файлы созданы: `schemas.py`, `exceptions.py`, `generate_openapi.py`
- [x] `main.py` обновлен: middleware, rate limiter, обработчики ошибок
- [x] `test_validation.py` содержит тесты для 422/413/429
- [x] `requirements.txt` содержит `slowapi>=0.1.9`
- [ ] Контейнер `calc-service` пересобран и запущен
- [ ] Все smoke-тесты проходят
- [ ] Pytest тесты проходят
- [ ] OpenAPI документация сгенерирована
- [ ] Swagger UI доступен по `/calc/docs`

---

## 🔄 Следующие шаги

После успешной проверки:

1. **Тиражирование** на остальные сервисы:
   - `risk-engine`
   - `doc-service`
   - `embedding-api`
   - `etl-service`

2. **Stage 7 Phase 2**: Vault integration
3. **Stage 7 Phase 3**: mTLS между сервисами
4. **Stage 7 Phase 4**: Audit logging + Loki retention

---

## 📝 Заметки

- Rate limiter использует IP-адрес клиента (`get_remote_address`)
- Для production можно настроить rate limiting по API-ключу или user_id
- Payload limit проверяется по заголовку `Content-Length`
- Все ошибки валидации логируются в JSON-формате
