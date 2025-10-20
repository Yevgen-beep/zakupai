# ZakupAI Search v2 - Полноценная система поиска лотов

## 🎯 Обзор

Система поиска лотов ZakupAI v2 представляет собой полноценное решение для работы с API Госзакупок Казахстана. Поддерживает **GraphQL v2**, **GraphQL v3** и **REST v3** с интеллектуальным выбором оптимального API и автоматическим fallback.

## 🚀 Ключевые особенности

### ✨ Интеллектуальный выбор API

- **Простые запросы** → REST v3 (быстрее)
- **Средние запросы** → GraphQL v2 (больше возможностей)
- **Сложные запросы** → GraphQL v2 (максимальная гибкость)
- **Автоматический fallback** при недоступности API

### 📊 Полная поддержка фильтров

- Поиск по ключевым словам (`лак`, `уголь`, `мебель`)
- Фильтрация по БИН заказчика
- Диапазоны сумм (от-до)
- Способы закупки (тендер, из одного источника, и др.)
- Статусы лотов (опубликован, прием заявок, и др.)
- Временные периоды (даты публикации, окончания)

### 🔗 Готовая интеграция

- **Telegram бот** с новыми командами
- **N8N workflows** для автоматизации
- **RESTful API** для внешних интеграций
- **Статистика и мониторинг** использования

## 📂 Структура проекта

```
bot/
├── search/                     # Основной модуль поиска
│   ├── __init__.py            # Экспорты модуля
│   ├── graphql_v2_client.py   # GraphQL v2 клиент
│   ├── rest_v3_client.py      # REST/GraphQL v3 клиент
│   ├── search_service.py      # Главный поисковый сервис
│   └── mappings.py            # Справочники ID → Название
├── services_v2.py             # Обновленные сервисы
├── handlers_v2.py             # Новые обработчики Telegram
tests/
├── test_graphql_search.py     # Тесты GraphQL v2
├── test_rest_search.py        # Тесты REST v3
├── test_fallback.py          # Тесты fallback логики
└── run_all_tests.py          # Запуск всех тестов
```

## ⚙️ Установка и настройка

### 1. Установка зависимостей

```bash
pip install aiohttp asyncio
```

### 2. Переменные окружения

```bash
# GraphQL v2 токен (приоритетный)
export GOSZAKUP_V2_TOKEN="ваш_graphql_v2_токен"

# REST v3 токен (fallback)
export GOSZAKUP_V3_TOKEN="ваш_rest_v3_токен"

# Для Telegram бота
export BOT_TOKEN="ваш_telegram_bot_токен"
```

### 3. Конфигурация

```python
# config.py
class GoszakupConfig:
    v2_token = "ваш_graphql_v2_токен"
    v3_token = "ваш_rest_v3_токен"
```

## 🔍 Примеры использования

### Базовое использование в Python

```python
from bot.search import GoszakupSearchService, search_lots_for_telegram

# Инициализация с обоими токенами
service = GoszakupSearchService(
    graphql_v2_token="your_v2_token",
    rest_v3_token="your_v3_token"
)

# Простой поиск
results = await service.search_by_keyword("лак", limit=10)

# Сложный поиск с фильтрами
results = await service.search_complex(
    keyword="мебель",
    customer_bin="123456789012",
    trade_methods=["тендер", "конкурс"],
    min_amount=100000,
    max_amount=500000
)

# Готовый текст для Telegram
text = await search_lots_for_telegram("уголь", limit=5)
```

### Telegram бот команды

```bash
# Простой поиск
/search лак
/search компьютеры офисные
/search мебель БИН:123456789012
/search уголь сумма:100000-500000

# Расширенный поиск
/search_advanced keyword=компьютеры min=50000 max=200000
/search_advanced bin=123456789012 method=тендер status=прием

# Анализ конкретного лота
/lot LOT-123456789
/lot ANNO-987654321

# Статистика
/stats
```

### N8N Workflow

```json
{
  "webhook": "POST /goszakup-search",
  "graphql_request": {
    "url": "https://ows.goszakup.gov.kz/v2/graphql",
    "query": "query SearchLots($filter: LotsFiltersInput) { ... }",
    "variables": { "filter": { "nameRu": "{{$json.query}}" } }
  },
  "fallback_rest": {
    "url": "https://ows.goszakup.gov.kz/v3/lots",
    "params": { "nameRu": "{{$json.query}}", "limit": 10 }
  }
}
```

## 📋 API Reference

### GoszakupSearchService

#### Инициализация

```python
service = GoszakupSearchService(
    graphql_v2_token: Optional[str] = None,
    rest_v3_token: Optional[str] = None,
    default_strategy: SearchStrategy = SearchStrategy.AUTO
)
```

#### Основные методы

**search_lots(query, strategy=None, limit=10)**

- Универсальный поиск с автовыбором API

**search_by_keyword(keyword, limit=10)**

- Простой поиск по ключевому слову

**search_complex(keyword=None, customer_bin=None, ...)**

- Сложный поиск с множественными фильтрами

**get_lot_by_number(lot_number)**

- Поиск конкретного лота по номеру

**format_results_for_telegram(results, show_source=False)**

- Форматирование для Telegram бота

### Стратегии поиска

```python
SearchStrategy.AUTO        # Автовыбор (рекомендуется)
SearchStrategy.GRAPHQL_V2  # Принудительно GraphQL v2
SearchStrategy.REST_V3     # Принудительно REST v3
SearchStrategy.GRAPHQL_V3  # Принудительно GraphQL v3
```

### Фильтры поиска

#### GraphQL v2 (LotsFiltersInput)

```python
{
    "nameRu": "лак",                    # Название на русском
    "nameDescriptionRu": "краска",      # Поиск в названии и описании
    "customerBin": "123456789012",      # БИН заказчика
    "customerNameRu": "ТОО Компания",   # Название заказчика
    "refTradeMethodsId": [1, 3, 7],     # Способы закупки
    "refLotStatusId": [1, 2, 10],       # Статусы лотов
    "trdBuyNumberAnno": "ANNO-001",     # Номер объявления
    "amount": [100000],                 # Суммы (список)
    "lastUpdateDate": ["2024-01-01"]    # Дата обновления
}
```

#### REST v3

```python
{
    "nameRu": "лак",                    # Название
    "descriptionRu": "краска",          # Описание
    "customerBin": "123456789012",      # БИН заказчика
    "amountFrom": 100000,               # Сумма от
    "amountTo": 500000,                 # Сумма до
    "publishDateFrom": "2024-01-01",    # Дата публикации от
    "publishDateTo": "2024-12-31",      # Дата публикации до
    "refTradeMethodsId": "1,3,7"        # Способы закупки (строка)
}
```

## 🗂️ Справочники

### Способы закупки (ref_trade_methods)

```python
1  -> "Открытый тендер"
2  -> "Конкурс по заявкам"
3  -> "Из одного источника"
4  -> "Запрос ценовых предложений"
7  -> "Открытый конкурс"
10 -> "Электронный магазин"
```

### Статусы лотов (ref_lot_status)

```python
1  -> "Опубликован"
2  -> "Прием заявок"
3  -> "Рассмотрение заявок"
4  -> "Определение победителя"
5  -> "Завершен"
6  -> "Отменен"
10 -> "Подача заявок"
11 -> "Подписание договора"
```

## 🧪 Тестирование

### Запуск всех тестов

```bash
cd tests
python run_all_tests.py
```

### Отдельные тесты

```bash
# GraphQL v2 тесты (требуют токен)
export GOSZAKUP_V2_TOKEN="your_token"
python test_graphql_search.py

# REST v3 тесты (работают без токена)
python test_rest_search.py

# Fallback логика
python test_fallback.py
```

### Интеграционные тесты

```bash
# С реальными токенами
export GOSZAKUP_V2_TOKEN="real_v2_token"
export GOSZAKUP_V3_TOKEN="real_v3_token"
python run_all_tests.py
```

## 📊 Мониторинг и статистика

### Получение статистики

```python
service = GoszakupSearchService(...)
stats = service.get_search_statistics()

print(f"GraphQL v2 запросов: {stats['v2_requests']}")
print(f"REST v3 запросов: {stats['v3_rest_requests']}")
print(f"Fallback случаев: {stats['fallback_requests']}")
print(f"Успешность: {stats['success_rate']*100:.1f}%")
```

### Telegram статистика

```bash
/stats  # Показывает детальную статистику пользователя
```

## 🔄 Fallback стратегия

### Логика выбора API

1. **Простой запрос** (только ключевое слово):

   - REST v3 → Быстро и эффективно

1. **Умеренный запрос** (2-3 фильтра):

   - GraphQL v2 (если доступен) → Больше возможностей
   - REST v3 (fallback) → Надежный запасной вариант

1. **Сложный запрос** (4+ фильтров):

   - GraphQL v2 (приоритет) → Максимальная гибкость
   - GraphQL v3 (fallback) → Альтернатива
   - REST v3 (последний шанс) → Базовые возможности

### Обработка ошибок

```python
try:
    results = await service.search_lots("лак")
except Exception as e:
    if "authorization" in str(e).lower():
        # Проблема с токеном - проверить актуальность
    elif "timeout" in str(e).lower():
        # Таймаут - повторить позже
    else:
        # Другая ошибка - логировать и показать fallback
```

## 🎯 Примеры реальных запросов

### 1. Поиск лакокрасочных материалов

```python
# Простой поиск
results = await service.search_by_keyword("лак")

# С БИН заказчика
results = await service.search_complex(
    keyword="лак краска",
    customer_bin="123456789012"
)

# В определенном ценовом диапазоне
results = await service.search_complex(
    keyword="лакокрасочные материалы",
    min_amount=50000,
    max_amount=200000
)
```

### 2. Поиск офисной мебели

```python
results = await service.search_complex(
    keyword="мебель офисная",
    trade_methods=["Открытый тендер", "Конкурс"],
    statuses=["Прием заявок", "Опубликован"],
    min_amount=100000
)
```

### 3. Поиск угля для отопления

```python
results = await service.search_complex(
    keyword="уголь каменный",
    min_amount=500000,
    max_amount=2000000,
    trade_methods=["Открытый тендер"]
)
```

## 🔧 Интеграция с существующим кодом

### Быстрая миграция

```python
# Старый код
from bot.services import goszakup_service
lots = await goszakup_service.search_lots("лак")

# Новый код (обратная совместимость)
from bot.services_v2 import goszakup_service
lots = await goszakup_service.search_lots("лак")  # Работает так же!
```

### Новые возможности

```python
# Расширенный поиск (новое)
lots = await goszakup_service.search_lots_advanced(
    keyword="мебель",
    customer_bin="123456789012",
    min_amount=100000
)

# Статистика (новое)
stats = goszakup_service.get_search_statistics()

# Проверка доступности API (новое)
if goszakup_service.is_v2_available():
    print("GraphQL v2 доступен!")
```

## 🚦 Рекомендации по использованию

### 🟢 Рекомендуется

- Использовать `SearchStrategy.AUTO` для оптимального выбора
- Устанавливать оба токена (v2 и v3) для максимальной надежности
- Использовать `limit=10-20` для оптимальной производительности
- Мониторить статистику для анализа использования

### 🟡 Осторожно

- Не устанавливать `limit > 100` без необходимости
- При частых запросах следить за лимитами токенов
- GraphQL v2 может быть медленнее для простых запросов

### 🔴 Избегать

- Принудительное использование только одного API без fallback
- Жестко зашитые стратегии без учета сложности запроса
- Игнорирование ошибок без логирования

## 📞 Поддержка и помощь

### 💬 Часто задаваемые вопросы

**Q: Какой токен лучше использовать?**
A: Оба! GraphQL v2 для сложных запросов, REST v3 как fallback.

**Q: Что если один из API недоступен?**
A: Система автоматически переключится на доступный API.

**Q: Как получить токены?**
A: Обратитесь в техподдержку goszakup.gov.kz

**Q: Можно ли использовать без токенов?**
A: Частично - только публичные endpoints REST v3.

### 🐛 Отчеты об ошибках

1. Запустите тесты: `python tests/run_all_tests.py`
1. Соберите логи с уровнем DEBUG
1. Укажите версию токенов и условия воспроизведения
1. Отправьте на zakupai.kz/support

### 📈 Roadmap

- [ ] WebSocket подписки на изменения лотов
- [ ] ML-рекомендации релевантных лотов
- [ ] Интеграция с Elasticsearch для полнотекстового поиска
- [ ] API rate limiting и кэширование
- [ ] Поддержка GraphQL subscriptions

______________________________________________________________________

## ✅ Готово к использованию!

Система ZakupAI Search v2 полностью готова к использованию в продакшене.

### Быстрый старт:

1. Установите токены: `export GOSZAKUP_V2_TOKEN=...`
1. Запустите тесты: `python tests/run_all_tests.py`
1. Используйте в коде: `from bot.search import GoszakupSearchService`
1. Для Telegram бота: импортируйте `handlers_v2.py`

**Удачи в работе с госзакупками! 🚀**
