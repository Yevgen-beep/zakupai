# Telegram Bot Billing Integration

Документация по интеграции Telegram-бота ZakupAI с Billing Service.

## Обзор

Все команды Telegram-бота интегрированы с Billing Service для:

- **Валидации API ключей** перед выполнением команд
- **Логирования использования** каждой команды
- **Контроля лимитов** (rate limiting и тарифные планы)
- **Безопасности** (защита от спама и злоупотреблений)

## Архитектура

```mermaid
flowchart TD
    User[👤 Пользователь] --> TgBot[🤖 Telegram Bot]
    TgBot --> Decorator[🔒 @validate_and_log_bot]
    Decorator --> BillingAPI[💳 Billing Service API]

    Decorator --> RateLimit[⏱️ Rate Limiter]
    Decorator --> SearchLimit[🔍 Search Rate Limiter]

    BillingAPI --> Validate[✅ validate_key]
    BillingAPI --> LogUsage[📝 log_usage]

    Validate --> Execute[⚡ Выполнение команды]
    Execute --> LogUsage

    subgraph "Команды бота"
        Start[/start]
        Key[/key]
        Search[/search]
        Lot[/lot]
        Help[/help]
    end

    Execute --> Start
    Execute --> Key
    Execute --> Search
    Execute --> Lot
    Execute --> Help
```

## Endpoints для команд

Каждая команда бота передает свой endpoint в Billing Service:

| Команда   | Endpoint   | Требует ключ | Rate Limit     | Стоимость |
| --------- | ---------- | ------------ | -------------- | --------- |
| `/start`  | `"start"`  | Нет          | 10/мин         | 0         |
| `/key`    | `"key"`    | Нет\*        | 10/мин         | 0         |
| `/search` | `"search"` | Да           | 1/сек + 10/мин | 2         |
| `/lot`    | `"lot"`    | Да           | 10/мин         | 5         |
| `/help`   | `"help"`   | Нет          | 10/мин         | 0         |

\*Команда `/key` валидирует переданный ключ через Billing Service.

## Ключевые компоненты

### 1. Универсальная функция endpoint

```python
def get_command_endpoint(message_text: str) -> str:
    """Извлекает команду для использования как endpoint"""
    if message_text.startswith('/'):
        command = message_text.split()[0][1:]  # /lot 123 → "lot"
        return command
    return "unknown"
```

### 2. Декоратор валидации и логирования

```python
@validate_and_log(require_key=True)  # Требует ключ
@validate_and_log(require_key=False) # Не требует ключ
```

**Что делает декоратор:**

1. Извлекает endpoint из команды (`/lot` → `"lot"`)
1. Проверяет API ключ через `POST /billing/validate_key`
1. Выполняет основную функцию команды
1. Логирует использование через `POST /billing/usage`

### 3. Команды и их endpoints

| Команда      | Endpoint  | Требует ключ | Описание                       |
| ------------ | --------- | ------------ | ------------------------------ |
| `/start`     | `"start"` | ❌           | Создает ключ или приветствие   |
| `/key <key>` | `"key"`   | ❌           | Проверяет и сохраняет ключ     |
| `/lot <id>`  | `"lot"`   | ✅           | Анализ лота (основная функция) |
| `/help`      | `"help"`  | ❌           | Справка                        |
| `/stats`     | `"stats"` | ✅           | Статистика пользователя        |

## Методы ZakupaiAPIClient

### validate_key(api_key, endpoint="unknown")

```python
# Отправляет POST /billing/validate_key
await client.validate_key("uuid-key", "lot")
# → {"valid": true, "plan": "free", "remaining_requests": 99}
```

### create_billing_key(tg_id, email=None)

```python
# Отправляет POST /billing/create_key
new_key = await client.create_billing_key(tg_id=12345)
# → "abc-123-def-456" или ""
```

### log_usage(api_key, endpoint, requests=1)

```python
# Отправляет POST /billing/usage
logged = await client.log_usage("uuid-key", "lot", 1)
# → True/False
```

## Лимиты и планы

```python
PLANS = {
    "free": {
        "requests_per_day": 100,
        "requests_per_hour": 20,
    },
    "premium": {
        "requests_per_day": 5000,
        "requests_per_hour": 500,
    }
}
```

**Проверка лимитов происходит в Billing Service:**

- Дневной лимит: `SELECT SUM(requests) FROM billing.usage WHERE created_at >= CURRENT_DATE`
- Часовой лимит: `SELECT SUM(requests) FROM billing.usage WHERE created_at >= NOW() - INTERVAL '1 hour'`

## Добавление новых команд

```python
@dp.message(Command("premium"))  # Регистрируем команду
@validate_and_log(require_key=True)  # Автоматическая валидация и логирование
async def command_premium_handler(message: Message) -> None:
    """
    Новая команда - автоматически получит endpoint="premium"
    """
    await message.answer("💎 Информация о Premium подписке...")
    # Декоратор автоматически:
    # 1. Проверит ключ через validate_key(key, "premium")
    # 2. Выполнит эту функцию
    # 3. Залогирует через log_usage(key, "premium")
```

## Тестирование

Запустите тест интеграции:

```bash
python test_bot_billing.py
```

**Что тестируется:**

- ✅ Создание API ключей
- ✅ Валидация для всех endpoints
- ✅ Логирование использования
- ✅ Извлечение endpoint из команд

## Dev Mode

В dev режиме (`DEV_MODE = True`):

- Валидация ключей отключена
- Логирование отключено
- Показываются тестовые данные

## Production готовность

**Система готова для Production:**

- ✅ Все команды передают корректные endpoints
- ✅ Валидация ключей работает универсально
- ✅ Логирование всех действий
- ✅ Контроль лимитов Free/Premium
- ✅ Декоратор обрабатывает ошибки
- ✅ Легко добавлять новые команды

**Результат:** Каждое действие пользователя в боте проходит через Billing Service с правильной идентификацией endpoint'а.
