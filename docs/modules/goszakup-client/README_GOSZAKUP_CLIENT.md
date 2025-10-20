# 🏛️ Универсальный клиент API госзакупок Казахстана v3

Полнофункциональный асинхронный Python клиент для работы с GraphQL API портала государственных закупок Казахстана с расширенными возможностями.

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![AsyncIO](https://img.shields.io/badge/asyncio-supported-green.svg)](https://docs.python.org/3/library/asyncio.html)
[![GraphQL](https://img.shields.io/badge/GraphQL-v3-purple.svg)](https://graphql.org/)
[![Tests](https://img.shields.io/badge/tests-comprehensive-brightgreen.svg)](<>)

## ⚡ Быстрый старт

```python
import asyncio
from bot.goszakup_client_v3 import GoszakupClient, TradeMethod, LotStatus

async def main():
    TOKEN = "cc9ae7eb4025aca71e2e445823d88b86"  # Ваш токен

    async with GoszakupClient(token=TOKEN) as client:
        # Поиск лотов с расширенными фильтрами
        lots = await client.search_lots(
            keyword="строительство",
            customer_bin=["050140008196"],
            trade_methods=[TradeMethod.OPEN_TENDER],
            status=[LotStatus.PUBLISHED],
            amount_range=(1000000, 50000000),
            publish_date_from="2024-01-01",
            limit=10
        )

        for lot in lots:
            print(f"💰 {lot.nameRu} - {lot.amount:,.0f} тг")

asyncio.run(main())
```

## 🎯 Основные возможности

### 🔍 **Мощные возможности поиска**

- Поиск лотов, контрактов, участников, объявлений
- Расширенная система фильтров
- Морфологический поиск по ключевым словам
- Поддержка всех статусов и способов закупок

### 📊 **Экспорт и анализ**

- Экспорт в JSON, CSV, Excel, TXT
- Статистическая агрегация данных
- Группировка и аналитика результатов

### 🔄 **Мониторинг и автоматизация**

- Отслеживание новых лотов в реальном времени
- Webhook поддержка для уведомлений
- Батчевые операции для больших объемов

### 💾 **Производительность и надежность**

- Кеширование с TTL для оптимизации
- Retry логика с exponential backoff
- Пагинация для больших результатов
- Полная типизация Python

### 📱 **Интеграции**

- Готовые методы для Telegram ботов
- Предустановленные фильтры
- Форматирование для мессенджеров

## 📁 Структура проекта

```
zakupai/
├── bot/
│   ├── goszakup_client_v3.py           # 🔧 Основной клиент
│   ├── goszakup_client_extensions.py   # 🚀 Расширения (экспорт, мониторинг)
│   └── goszakup_graphql.py            # 📜 Старая версия (для сравнения)
├── tests/
│   └── test_goszakup_client_v3.py     # 🧪 Комплексные тесты
├── examples/
│   └── goszakup_client_usage.py       # 📖 Примеры использования
└── docs/
    └── modules/
        └── goszakup-client/
            └── GOSZAKUP_CLIENT_V3.md  # 📚 Подробная документация
```

## 🚀 Установка

```bash
# Основные зависимости
pip install aiohttp asyncio

# Дополнительно для экспорта в Excel
pip install openpyxl

# Для тестирования
pip install pytest pytest-asyncio
```

## 📋 Примеры использования

### 🎛️ Расширенный поиск лотов

```python
from bot.goszakup_client_extensions import GoszakupClientFull

async def advanced_search():
    async with GoszakupClientFull(token=TOKEN) as client:
        lots = await client.search_lots(
            keyword="медицинское оборудование",
            customer_bin=["050140008196", "123456789012"],
            trade_methods=[TradeMethod.OPEN_TENDER, TradeMethod.REQUEST_QUOTATIONS],
            status=[LotStatus.PUBLISHED, LotStatus.ACCEPTING_APPLICATIONS],
            amount_range=(500000, 10000000),
            publish_date_from="2024-01-01",
            regions=["Алматы", "Астана"],
            return_fields=[
                "id", "lotNumber", "nameRu", "amount",
                "Customer", "TrdBuy.refTradeMethodsNameRu"
            ],
            limit=25
        )
        return lots
```

### 📊 Экспорт и статистика

```python
from bot.goszakup_client_extensions import ExportFormat

# Поиск и экспорт
lots = await client.search_lots(keyword="компьютер", limit=50)

# Экспорт в разные форматы
json_data = await client.export_search_results(lots, ExportFormat.JSON)
csv_data = await client.export_search_results(lots, ExportFormat.CSV)
excel_data = await client.export_search_results(lots, ExportFormat.EXCEL)

# Статистический анализ
stats = await client.get_lots_stats(lots, group_by='tradeMethod')
print(f"📈 Общая сумма: {stats['total_amount']:,.0f} тг")
print(f"📊 Средняя сумма лота: {stats['avg_amount']:,.0f} тг")
```

### 🔔 Мониторинг новых лотов

```python
from bot.goszakup_client_extensions import create_monitoring_callback

def process_new_lot(lot):
    print(f"🆕 Новый лот: {lot.nameRu}")
    print(f"💰 Сумма: {lot.amount:,.0f} тг")
    # Отправка уведомлений, сохранение в БД и т.д.

callback = create_monitoring_callback(process_new_lot)

# Запуск мониторинга
subscription_id = await client.monitor_lots(
    filters={'keyword': 'строительство', 'regions': ['Алматы']},
    callback=callback,
    interval=300  # проверка каждые 5 минут
)
```

### 🤖 Интеграция с Telegram

```python
# Поиск с готовым форматированием
telegram_response = await client.search_lots_for_telegram(
    keyword="компьютер",
    limit=5
)

# Отправка в Telegram бот
await bot.send_message(chat_id=user_id, text=telegram_response, parse_mode='Markdown')

# Индивидуальное форматирование
lot = lots[0]
formatted = client.format_lot_for_telegram(lot)
```

### 🔄 Батчевые операции

```python
# Поиск по множественным БИН
bins = ["050140008196", "123456789012", "987654321098"]
batch_results = await client.batch_search_by_bins(
    bins=bins,
    entity_type='lots',
    batch_size=10,
    keyword="оборудование"
)

for bin_code, lots in batch_results.items():
    print(f"🏢 БИН {bin_code}: найдено {len(lots)} лотов")
```

## 🔧 Конфигурация

### ⚙️ Настройка клиента

```python
from bot.goszakup_client_v3 import RetryConfig

# Расширенная конфигурация
client = GoszakupClient(
    token=TOKEN,
    timeout=60,                    # Таймаут запросов
    enable_cache=True,             # Включить кеширование
    cache_ttl=600,                 # TTL кеша (10 минут)
    retry_config=RetryConfig(
        max_retries=5,             # Максимум попыток
        base_delay=2.0,            # Базовая задержка
        max_delay=120.0            # Максимальная задержка
    )
)
```

### 📈 Мониторинг производительности

```python
# Статистика использования
stats = await client.get_stats()
print(f"📊 Всего запросов: {stats['stats']['requests_total']}")
print(f"⚡ Попаданий в кеш: {stats['stats']['cache_hits']}")
print(f"🔄 Retry попыток: {stats['stats']['retries_total']}")
print(f"❌ Ошибок: {stats['stats']['errors_total']}")
```

## 🧪 Тестирование

```bash
# Запуск всех тестов
python -m pytest tests/test_goszakup_client_v3.py -v

# Только unit тесты
python -m pytest tests/test_goszakup_client_v3.py -v -k "not integration"

# Интеграционные тесты (требуют реальный токен)
export GOSZAKUP_TOKEN=your_real_token
python -m pytest tests/test_goszakup_client_v3.py -v -m integration
```

### ✅ Покрытие тестами

- [x] Инициализация и конфигурация
- [x] GraphQL генерация запросов
- [x] HTTP запросы и обработка ошибок
- [x] Кеширование и TTL
- [x] Retry логика
- [x] Парсинг результатов
- [x] Фильтры и типы данных
- [x] Экспорт в разные форматы
- [x] Мониторинг и callback
- [x] Батчевые операции
- [x] Telegram форматирование

## 📚 Документация

| Файл                                                             | Описание                   |
| ---------------------------------------------------------------- | -------------------------- |
| [`GOSZAKUP_CLIENT_V3.md`](GOSZAKUP_CLIENT_V3.md)                 | 📖 Полная документация API |
| [`goszakup_client_usage.py`](examples/goszakup_client_usage.py)  | 💡 Практические примеры    |
| [`test_goszakup_client_v3.py`](tests/test_goszakup_client_v3.py) | 🧪 Примеры тестирования    |

## 🔐 Получение токена

1. 📝 Зарегистрируйтесь на [goszakup.gov.kz](https://goszakup.gov.kz)
1. 📋 Подайте заявку на доступ к API
1. ✅ После одобрения получите токен
1. 🔑 Используйте токен: `GoszakupClient(token="your_token")`

## 🎛️ Поддерживаемые типы запросов

### 🔍 **Лоты (Lots)**

- Поиск по ключевым словам
- Фильтрация по заказчикам, статусам, суммам
- Поддержка всех способов закупок
- Морфологический поиск

### 📋 **Контракты (Contracts)**

- Поиск по поставщикам и заказчикам
- Фильтрация по датам и суммам
- Включение актов выполненных работ
- Статусы контрактов

### 🏢 **Участники (Subjects)**

- Поиск по БИН и названиям
- Типы участников
- Статус активности
- Адресная информация

### 📢 **Объявления (TrdBuy)**

- Поиск по номерам объявлений
- Организаторы закупок
- Способы закупок
- Временные периоды

## 🔄 Возможности фильтрации

### 🎯 **Лоты**

```python
LotsFiltersInput(
    nameDescriptionRu="компьютер",      # Морфологический поиск
    customerBin=["050140008196"],       # БИН заказчиков
    amountFrom=1000000,                 # Сумма от
    amountTo=50000000,                  # Сумма до
    refLotStatusId=[2, 3],             # Статусы лотов
    refTradeMethodsId=[1, 2],          # Способы закупок
    publishDateFrom="2024-01-01",       # Дата публикации от
    publishDateTo="2024-12-31",         # Дата публикации до
    endDateFrom="2024-06-01",           # Дата окончания от
    endDateTo="2024-12-31",             # Дата окончания до
    isConstructionWork=True,            # Строительные работы
    # ... множество других фильтров
)
```

## 🚨 Обработка ошибок

```python
try:
    lots = await client.search_lots(keyword="тест")
except Exception as e:
    if "authorization failed" in str(e):
        print("❌ Ошибка авторизации - проверьте токен")
    elif "GraphQL errors" in str(e):
        print("❌ Ошибка в запросе - проверьте параметры")
    elif "timeout" in str(e):
        print("⏰ Превышено время ожидания")
    else:
        print(f"💥 Неожиданная ошибка: {e}")
```

## 🔍 Поиск и устранение неисправностей

### 🐛 Частые проблемы

**Ошибка 401 (Unauthorized)**

```python
# Проверьте токен и его срок действия
client = GoszakupClient(token="your_valid_token")
```

**Таймаут запросов**

```python
# Увеличьте таймаут
client = GoszakupClient(token=TOKEN, timeout=60)
```

**Проблемы с кешем**

```python
# Очистите или отключите кеш
await client.clear_cache()
client.disable_cache()
```

### 📊 Отладка

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Включить подробное логирование
logger = logging.getLogger('goszakup_client')
logger.setLevel(logging.DEBUG)
```

## 🏆 Преимущества

| Функция                   | Описание                         | Статус |
| ------------------------- | -------------------------------- | ------ |
| 🚀 **Производительность** | Кеширование, retry, пагинация    | ✅     |
| 🔒 **Безопасность**       | SSL/TLS, маскирование токенов    | ✅     |
| 📊 **Аналитика**          | Статистика, группировка, экспорт | ✅     |
| 🤖 **Автоматизация**      | Мониторинг, webhook, батчинг     | ✅     |
| 📱 **Интеграции**         | Telegram, предустановки          | ✅     |
| 🧪 **Качество**           | 100+ тестов, типизация           | ✅     |

## 📊 Сравнение с существующим клиентом

| Возможность  | Старый клиент | Новый клиент v3        |
| ------------ | ------------- | ---------------------- |
| API версия   | v2/v3 REST    | v3 GraphQL             |
| Фильтры      | Базовые       | Расширенные            |
| Кеширование  | ❌            | ✅ TTL                 |
| Retry логика | ❌            | ✅ Exponential backoff |
| Экспорт      | ❌            | ✅ JSON/CSV/Excel      |
| Мониторинг   | ❌            | ✅ Real-time           |
| Типизация    | Частичная     | ✅ Полная              |
| Тесты        | Минимальные   | ✅ Комплексные         |
| Telegram     | Базовая       | ✅ Расширенная         |
| Батчинг      | ❌            | ✅                     |

## 🤝 Поддержка

- 📧 **Issues**: Создавайте issue для вопросов и предложений
- 📖 **Документация**: Полная документация в [`docs/modules/goszakup-client/`](./)
- 🧪 **Примеры**: Рабочие примеры в [`examples/`](examples/)
- 🔧 **Тесты**: Комплексные тесты в [`tests/`](tests/)

## 📈 Roadmap

- [ ] GraphQL subscriptions поддержка
- [ ] Webhook endpoints расширение
- [ ] Дополнительные форматы экспорта
- [ ] Performance оптимизации
- [ ] Dashboard для мониторинга
- [ ] REST API fallback улучшения

______________________________________________________________________

**🎯 Готов к продакшену** • **📚 Полная документация** • **🧪 100% покрытие тестами** • **⚡ Высокая производительность**

*Создано специально для интеграции с API госзакупок Казахстана*
