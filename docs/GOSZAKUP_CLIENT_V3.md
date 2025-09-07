# Универсальный клиент API госзакупок Казахстана v3

Полнофункциональный асинхронный клиент для работы с GraphQL API портала государственных закупок Казахстана с расширенными возможностями кеширования, мониторинга и экспорта.

## 🚀 Основные возможности

- **Полная поддержка GraphQL API v3** - работа со всеми типами сущностей
- **Расширенная система фильтров** - поддержка всех доступных фильтров из схемы API
- **Динамическая генерация запросов** - автоматическое построение GraphQL запросов
- **Кеширование с TTL** - повышение производительности и снижение нагрузки на API
- **Retry логика с exponential backoff** - надежная обработка временных сбоев
- **Пагинация и field selection** - эффективная работа с большими объемами данных
- **Экспорт в разные форматы** - JSON, CSV, Excel, TXT
- **Мониторинг и webhook поддержка** - отслеживание новых лотов и контрактов
- **Батчинг запросов** - оптимизация множественных операций
- **Интеграция с Telegram** - готовые методы форматирования
- **Статистическая агрегация** - анализ и группировка данных
- **Полная типизация** - использование Python typing для всех компонентов

## 📦 Установка и зависимости

### Основные зависимости

```bash
pip install aiohttp asyncio
```

### Дополнительные зависимости (опционально)

```bash
# Для экспорта в Excel
pip install openpyxl

# Для тестирования
pip install pytest pytest-asyncio
```

### Файлы клиента

- `bot/goszakup_client_v3.py` - основной клиент
- `bot/goszakup_client_extensions.py` - расширения (экспорт, мониторинг, батчинг)
- `tests/test_goszakup_client_v3.py` - тесты
- `examples/goszakup_client_usage.py` - примеры использования

## 🎯 Быстрый старт

### Базовое использование

```python
import asyncio
from bot.goszakup_client_v3 import GoszakupClient, TradeMethod, LotStatus

async def main():
    TOKEN = "your_api_token_here"

    async with GoszakupClient(token=TOKEN) as client:
        # Простой поиск лотов
        lots = await client.search_lots(
            keyword="компьютер",
            limit=10
        )

        for lot in lots:
            print(f"{lot.lotNumber}: {lot.nameRu} - {lot.amount:,.0f} тг")

asyncio.run(main())
```

### Расширенный поиск с фильтрами

```python
from bot.goszakup_client_extensions import GoszakupClientFull

async def advanced_search():
    async with GoszakupClientFull(token=TOKEN) as client:
        # Поиск с множественными фильтрами
        lots = await client.search_lots(
            keyword="строительство",
            customer_bin=["050140008196", "050140008197"],
            trade_methods=[TradeMethod.OPEN_TENDER, TradeMethod.REQUEST_QUOTATIONS],
            status=[LotStatus.PUBLISHED, LotStatus.ACCEPTING_APPLICATIONS],
            amount_range=(1000000, 50000000),
            publish_date_from="2024-01-01",
            end_date_to="2024-12-31",
            regions=["Алматы", "Астана"],
            return_fields=["id", "lotNumber", "nameRu", "amount", "Customer", "TrdBuy.refTradeMethodsNameRu"]
        )

        return lots
```

## 📚 Подробная документация

### Основные классы

#### GoszakupClient

Базовый клиент с основной функциональностью.

**Инициализация:**

```python
client = GoszakupClient(
    token="your_token",
    graphql_url="https://ows.goszakup.gov.kz/v3/graphql",  # опционально
    timeout=30,  # таймаут запросов в секундах
    enable_cache=True,  # включить кеширование
    cache_ttl=300,  # время жизни кеша в секундах
    retry_config=RetryConfig(max_retries=3, base_delay=1.0, max_delay=60.0)
)
```

#### GoszakupClientFull

Полный клиент со всеми расширениями (наследует от GoszakupClient).

```python
from bot.goszakup_client_extensions import GoszakupClientFull

client = GoszakupClientFull(token="your_token")
```

### Методы поиска

#### search_lots()

Поиск лотов с расширенными фильтрами.

**Параметры:**

- `keyword` - ключевое слово для поиска
- `customer_bin` - список БИН заказчиков
- `trade_methods` - список способов закупок (TradeMethod enum)
- `status` - список статусов лотов (LotStatus enum)
- `amount_range` - диапазон сумм (tuple)
- `publish_date_from/to` - период публикации
- `end_date_from/to` - период завершения
- `regions` - список регионов для поиска
- `limit` - максимальное количество результатов (по умолчанию 50)
- `after` - курсор для пагинации
- `return_fields` - список полей для возврата
- `**additional_filters` - дополнительные фильтры

**Пример:**

```python
lots = await client.search_lots(
    keyword="медицинское оборудование",
    customer_bin=["123456789012"],
    trade_methods=[TradeMethod.OPEN_TENDER],
    status=[LotStatus.PUBLISHED],
    amount_range=(100000, 5000000),
    publish_date_from="2024-01-01",
    limit=20
)
```

#### search_contracts()

Поиск контрактов.

**Основные параметры:**

- `supplier_bin` - БИН поставщиков
- `customer_bin` - БИН заказчиков
- `contract_sum_range` - диапазон сумм контрактов
- `sign_date_from/to` - период подписания
- `status` - статусы контрактов
- `include_acts` - включить акты выполненных работ
- `include_payments` - включить информацию о платежах

**Пример:**

```python
contracts = await client.search_contracts(
    supplier_bin=["987654321098"],
    sign_date_from="2024-01-01",
    status=[ContractStatus.ACTIVE],
    include_acts=True,
    limit=10
)
```

#### search_subjects()

Поиск участников закупок.

**Параметры:**

- `bin_list` - список БИН
- `name_keyword` - ключевое слово в названии
- `subject_type` - тип участника (SubjectType enum)
- `is_active` - статус активности

#### search_trd_buy()

Поиск объявлений о закупках.

### Фильтры и типы данных

#### Enums

```python
# Способы закупок
class TradeMethod(Enum):
    OPEN_TENDER = 1  # Открытый конкурс
    REQUEST_QUOTATIONS = 2  # Запрос ценовых предложений
    FROM_ONE_SOURCE = 3  # Из одного источника
    ELECTRONIC_STORE = 5  # Электронный магазин

# Статусы лотов
class LotStatus(Enum):
    PUBLISHED = 2  # Опубликован
    ACCEPTING_APPLICATIONS = 3  # Прием заявок
    COMPLETED = 6  # Завершен

# Статусы контрактов
class ContractStatus(Enum):
    ACTIVE = 2  # Действующий
    COMPLETED = 3  # Исполнен
    TERMINATED = 4  # Расторгнут
```

#### Dataclasses фильтров

```python
@dataclass
class LotsFiltersInput:
    lotNumber: Optional[str] = None
    nameRu: Optional[str] = None
    nameDescriptionRu: Optional[str] = None  # Морфологический поиск
    customerBin: Optional[List[str]] = None
    amountFrom: Optional[float] = None
    amountTo: Optional[float] = None
    publishDateFrom: Optional[str] = None
    publishDateTo: Optional[str] = None
    # ... множество других полей
```

### Результаты поиска

#### LotResult

```python
@dataclass
class LotResult:
    id: str
    lotNumber: str
    nameRu: str
    amount: float
    customerNameRu: str
    customerBin: str
    status: str
    tradeMethod: str
    publishDate: Optional[str] = None
    endDate: Optional[str] = None
    # ... другие поля
```

## 🔧 Расширенные возможности

### Экспорт данных

Клиент поддерживает экспорт в различные форматы:

```python
from bot.goszakup_client_extensions import ExportFormat

# Получаем данные
lots = await client.search_lots(keyword="тест", limit=10)

# Экспорт в JSON
json_data = await client.export_search_results(lots, ExportFormat.JSON)
with open("lots.json", "w", encoding="utf-8") as f:
    f.write(json_data)

# Экспорт в CSV
csv_data = await client.export_search_results(lots, ExportFormat.CSV)
with open("lots.csv", "w", encoding="utf-8") as f:
    f.write(csv_data)

# Экспорт в Excel (требует openpyxl)
excel_data = await client.export_search_results(lots, ExportFormat.EXCEL)
with open("lots.xlsx", "wb") as f:
    f.write(excel_data)
```

### Мониторинг новых лотов

Автоматическое отслеживание новых лотов по заданным критериям:

```python
def process_new_lot(lot):
    print(f"Новый лот: {lot.nameRu}")
    # Отправка уведомления, сохранение в БД и т.д.

# Создание callback
callback = create_monitoring_callback(process_new_lot)

# Запуск мониторинга
subscription_id = await client.monitor_lots(
    filters={'keyword': 'строительство', 'regions': ['Алматы']},
    callback=callback,
    interval=300  # проверка каждые 5 минут
)

# Остановка мониторинга
await client.stop_monitoring(subscription_id)
```

### Батчевые операции

Эффективная обработка множественных запросов:

```python
# Батчевый поиск по списку БИН
bins = ["123456789012", "987654321098", "555666777888"]
results = await client.batch_search_by_bins(
    bins=bins,
    entity_type='lots',
    batch_size=10,
    keyword="оборудование"
)

# Результаты сгруппированы по БИН
for bin_code, lots in results.items():
    print(f"БИН {bin_code}: {len(lots)} лотов")
```

### Предустановленные фильтры

Использование готовых наборов фильтров:

```python
# Встроенные предустановки
lots = await client.search_with_preset('construction_almaty')

# Добавление дополнительных фильтров
lots = await client.search_with_preset(
    'it_equipment',
    additional_filters={'amount_range': (100000, 1000000)}
)
```

### Статистическая агрегация

Анализ результатов поиска:

```python
lots = await client.search_lots(keyword="компьютер", limit=50)

# Получение статистики
stats = await client.get_lots_stats(lots, group_by='tradeMethod')

print(f"Всего лотов: {stats['total']}")
print(f"Общая сумма: {stats['total_amount']:,.0f} тг")
print(f"Средняя сумма: {stats['avg_amount']:,.0f} тг")

# Группировка
for method, data in stats['groups'].items():
    print(f"{method}: {data['count']} лотов на {data['amount']:,.0f} тг")
```

### Интеграция с Telegram

Готовые методы для форматирования данных для Telegram бота:

```python
# Поиск с автоматическим форматированием
telegram_text = await client.search_lots_for_telegram(
    keyword="компьютер",
    limit=5
)

# Отправка в Telegram
await bot.send_message(chat_id=user_id, text=telegram_text)

# Индивидуальное форматирование
lots = await client.search_lots(keyword="оборудование", limit=1)
if lots:
    formatted = client.format_lot_for_telegram(lots[0])
    print(formatted)
```

## ⚙️ Конфигурация и настройки

### Кеширование

```python
# Настройка кеша при инициализации
client = GoszakupClient(
    token=TOKEN,
    enable_cache=True,
    cache_ttl=600  # 10 минут
)

# Управление кешем
await client.clear_cache()  # Очистка
client.disable_cache()     # Отключение
client.enable_cache()      # Включение

# Получение статистики кеша
stats = await client.get_stats()
print(f"Попаданий в кеш: {stats['stats']['cache_hits']}")
print(f"Промахов: {stats['stats']['cache_misses']}")
```

### Retry логика

```python
from bot.goszakup_client_v3 import RetryConfig

# Настройка retry
retry_config = RetryConfig(
    max_retries=5,      # Максимум 5 попыток
    base_delay=2.0,     # Базовая задержка 2 сек
    max_delay=120.0     # Максимальная задержка 2 мин
)

client = GoszakupClient(token=TOKEN, retry_config=retry_config)
```

### Пагинация

```python
# Первая страница
lots_page1 = await client.search_lots(keyword="тест", limit=50)

# Следующая страница (если есть курсор в ответе)
if lots_page1:
    last_lot_id = lots_page1[-1].id
    lots_page2 = await client.search_lots(
        keyword="тест",
        limit=50,
        after=last_lot_id
    )
```

## 🧪 Тестирование

### Запуск тестов

```bash
# Все тесты
python -m pytest tests/test_goszakup_client_v3.py -v

# Только unit тесты
python -m pytest tests/test_goszakup_client_v3.py -v -k "not integration"

# Интеграционные тесты (требуют токен)
export GOSZAKUP_TOKEN=your_real_token
python -m pytest tests/test_goszakup_client_v3.py -v -m integration
```

### Покрытие тестами

- ✅ Инициализация и конфигурация клиента
- ✅ Генерация GraphQL запросов
- ✅ Обработка HTTP запросов и ошибок
- ✅ Парсинг результатов
- ✅ Кеширование и TTL
- ✅ Retry логика
- ✅ Фильтры и типы данных
- ✅ Экспорт в разные форматы
- ✅ Мониторинг и callback
- ✅ Батчевые операции
- ✅ Telegram форматирование
- ✅ Статистические функции

## 🚨 Обработка ошибок

Клиент предоставляет подробную обработку различных типов ошибок:

```python
try:
    lots = await client.search_lots(keyword="тест")
except Exception as e:
    if "authorization failed" in str(e):
        print("Ошибка авторизации - проверьте токен")
    elif "GraphQL errors" in str(e):
        print("Ошибка в запросе - проверьте параметры")
    elif "timeout" in str(e):
        print("Превышено время ожидания")
    else:
        print(f"Неожиданная ошибка: {e}")
```

## 📊 Мониторинг и логирование

Клиент ведет подробную статистику и логи:

```python
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('goszakup_client')

# Получение статистики
stats = await client.get_stats()
print(f"Всего запросов: {stats['stats']['requests_total']}")
print(f"Ошибок: {stats['stats']['errors_total']}")
print(f"Retry попыток: {stats['stats']['retries_total']}")
```

## 🔐 Безопасность

- **Токен авторизации** передается только в защищенных заголовках
- **Маскирование** чувствительных данных в логах
- **SSL/TLS** шифрование всех запросов
- **Rate limiting** обработка ограничений API
- **Валидация входных данных** предотвращение инъекций

## 📋 Примеры использования

Полные рабочие примеры доступны в файле `examples/goszakup_client_usage.py`:

1. **Базовые поисковые запросы**
1. **Расширенные фильтры и комбинации**
1. **Экспорт данных в разные форматы**
1. **Кеширование и оптимизация**
1. **Мониторинг новых лотов**
1. **Батчевые операции**
1. **Интеграция с Telegram**
1. **Статистический анализ**
1. **Обработка ошибок**
1. **Комплексные сценарии**

## 🤝 Поддержка и развитие

### Известные ограничения

- GraphQL API может иметь лимиты на количество запросов
- Некоторые поля могут быть недоступны в зависимости от уровня доступа
- Размер ответа ограничен возможностями API

### Планы развития

- Поддержка GraphQL subscriptions
- Расширение webhook функциональности
- Добавление новых форматов экспорта
- Оптимизация производительности
- Расширение интеграций

### Вклад в развитие

Мы приветствуем вклад сообщества! Пожалуйста:

1. Создайте issue для обсуждения новых функций
1. Следуйте существующему стилю кода
1. Добавляйте тесты для новой функциональности
1. Обновляйте документацию

## 📞 Получение токена

Для получения токена доступа к API госзакупок:

1. Зарегистрируйтесь на портале [goszakup.gov.kz](https://goszakup.gov.kz)
1. Подайте заявку на получение доступа к API
1. После одобрения получите токен авторизации
1. Используйте токен в параметре `token` при инициализации клиента

## 🆘 Поиск и устранение неисправностей

### Частые проблемы

**Ошибка авторизации (401)**

- Проверьте корректность токена
- Убедитесь что токен не истек
- Проверьте доступность API

**Таймаут запроса**

```python
client = GoszakupClient(token=TOKEN, timeout=60)  # Увеличить таймаут
```

**Проблемы с кешем**

```python
await client.clear_cache()  # Очистить кеш
client.disable_cache()     # Отключить временно
```

**Большие объемы данных**

```python
# Используйте пагинацию и ограничения
lots = await client.search_lots(keyword="тест", limit=10)
```

### Отладка

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Включить подробные логи
logger = logging.getLogger('goszakup_client')
logger.setLevel(logging.DEBUG)
```

______________________________________________________________________

*Документация обновлена: Сентябрь 2024*
*Версия клиента: 3.0*
*Совместимость: API госзакупок v3, Python 3.9+*
