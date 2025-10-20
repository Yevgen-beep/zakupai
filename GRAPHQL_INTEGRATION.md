# GraphQL Integration для ZakupAI

## 📋 Обзор

Реализована интеграция с GraphQL v2 API Госзакупок для корректного поиска по ключевым словам («лак», «уголь», «мебель» и т.д.) с автоматическим fallback на REST v3 API.

## 🚀 Основные компоненты

### 1. **GraphQL модуль** (`bot/goszakup_graphql.py`)

- ✅ Полная поддержка GraphQL v2 API
- ✅ Основан на реальной introspection схеме
- ✅ Автоматический fallback на REST v3
- ✅ Типизированные результаты поиска
- ✅ Обработка ошибок и таймаутов

### 2. **Обновленный сервис** (`bot/services.py`)

- ✅ Интеграция GraphQL в существующий GoszakupService
- ✅ Обратная совместимость с существующим кодом
- ✅ Логирование и мониторинг
- ✅ Конфигурация через переменные окружения

### 3. **N8N Workflows**

- ✅ `zakupai_workflow_fixed.json` - исправленный workflow
- ✅ `zakupai_workflow_enhanced.json` - расширенный с fallback
- ✅ Корректные GraphQL запросы из реальной схемы
- ✅ Улучшенное форматирование результатов

### 4. **Тестовый скрипт** (`test_graphql_search.py`)

- ✅ Демонстрация всех возможностей API
- ✅ Сравнение GraphQL vs REST
- ✅ Руководство по интеграции

## 🔍 Как работает поиск

### GraphQL v2 (приоритет):

```graphql
query SearchLots($filter: LotsFiltersInput) {
  Lots(filter: $filter) {
    lotNumber
    nameRu
    descriptionRu
    amount
    count
    customerNameRu
    TrdBuy {
      nameRu
      numberAnno
      RefTradeMethods { nameRu }
    }
    RefLotsStatus { nameRu }
  }
}
```

### Переменные:

```json
{
  "filter": {
    "nameRu": "лак",
    "nameDescriptionRu": "лак"
  }
}
```

### REST v3 (fallback):

```
GET https://ows.goszakup.gov.kz/v3/lots?nameRu=лак&descriptionRu=лак&limit=10
```

## ⚙️ Установка и настройка

### 1. Переменные окружения:

```bash
export GOSZAKUP_TOKEN="ваш_токен_api"
```

### 2. Для N8N workflow:

```json
{
  "name": "Authorization",
  "value": "Bearer {{$env.GOSZAKUP_TOKEN}}"
}
```

### 3. Для Python кода:

```python
from bot.goszakup_graphql import GoszakupGraphQLClient, format_search_results

# Инициализация
client = GoszakupGraphQLClient(token='your_token')

# Поиск с GraphQL + fallback
results = await client.search_lots('лак', limit=10)
formatted = format_search_results(results)
```

## 🔧 API Reference

### `GoszakupGraphQLClient`

#### `__init__(token: str, timeout: int = 30)`

- `token`: Bearer токен для авторизации
- `timeout`: Таймаут запросов в секундах

#### `async search_lots(keyword: str, limit: int = 10, use_graphql: bool = True, filters: Optional[Dict] = None) -> List[SearchResult]`

- `keyword`: Ключевое слово для поиска
- `limit`: Максимальное количество результатов
- `use_graphql`: Использовать GraphQL (True) или сразу REST (False)
- `filters`: Дополнительные фильтры для GraphQL

#### `format_search_results(results: List[SearchResult]) -> str`

Форматирует результаты для пользователя в читаемом виде.

## 🎯 Примеры использования

### Поиск по слову "лак":

```python
results = await client.search_lots("лак", limit=5)
```

### Расширенный поиск с фильтрами:

```python
filters = {
    "nameRu": "лак",
    "nameDescriptionRu": "краска",
    "customerId": 12345
}
results = await client.search_lots("лак", filters=filters)
```

### Только REST (без GraphQL):

```python
results = await client.search_lots("лак", use_graphql=False)
```

## 📊 Результат поиска

Каждый результат содержит:

- 📝 Номер лота
- 📋 Номер объявления
- 📦 Наименование и описание
- 🔢 Количество и сумма
- 🏢 Заказчик (название и БИН)
- 🛒 Способ закупки
- 📌 Статус лота

## 🚀 Преимущества GraphQL v2

✅ **Гибкая фильтрация** - точный поиск через `LotsFiltersInput`
✅ **Минимальный трафик** - только нужные поля
✅ **Связанные данные** - TrdBuy, статусы, методы в одном запросе
✅ **Типизация** - строгие типы данных
✅ **Надежность** - fallback на REST при проблемах

## 🔄 Fallback стратегия

1. **Основной**: GraphQL v2 API
1. **При ошибке GraphQL**: автоматический переход на REST v3
1. **При блокировке токена**: использование публичного REST
1. **При таймауте**: повтор с REST API

## 📝 Логирование

Все операции логируются:

- Успешные GraphQL запросы
- Fallback на REST API
- Ошибки авторизации
- Таймауты и сетевые проблемы

## 🧪 Тестирование

```bash
# Запуск тестов без токена (показывает структуру запросов)
python3 test_graphql_search.py

# Запуск с токеном (живое тестирование)
export GOSZAKUP_TOKEN="your_token"
python3 test_graphql_search.py
```

## 🔐 Безопасность

- ✅ Валидация входных данных
- ✅ Обфускация токенов в логах
- ✅ SSL/TLS для всех запросов
- ✅ Таймауты для предотвращения зависания
- ✅ Обработка ошибок авторизации

## 📈 Мониторинг

Рекомендуется отслеживать:

- Соотношение GraphQL vs REST запросов
- Время ответа API
- Количество ошибок авторизации
- Эффективность поиска (найденные лоты / запрос)

______________________________________________________________________

**Готово к использованию!** 🎉

Все компоненты интегрированы и протестированы. Telegram бот автоматически будет использовать GraphQL v2 для более точного и быстрого поиска.
