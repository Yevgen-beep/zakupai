# ZakupAI Telegram Bot

Telegram бот для анализа тендеров через ZakupAI API. Предоставляет функции TL;DR, риск-анализа, финансовых расчётов и генерации документов.

## Возможности

- 🔑 Управление API ключами пользователей
- 📊 Полный анализ лотов: описание, риск-скор, финансовые расчёты
- 🤖 Интеграция с ZakupAI сервисами (calc, risk, doc, embedding)
- 💾 PostgreSQL для хранения пользовательских данных
- 🧪 Comprehensive test coverage
- 🐳 Docker контейнеризация

## Команды бота

| Команда          | Описание              | Пример                                                                  |
| ---------------- | --------------------- | ----------------------------------------------------------------------- |
| `/start`         | Начать работу с ботом | `/start`                                                                |
| `/key <api_key>` | Установить API ключ   | `/key your-api-key-here`                                                |
| `/lot <id\|url>` | Анализ лота           | `/lot 12345` или `/lot https://goszakup.gov.kz/ru/announce/index/12345` |
| `/help`          | Справка по командам   | `/help`                                                                 |

## Быстрый старт

### 1. Клонирование и настройка

```bash
git clone <repository>
cd zakupai/bot

# Копирование конфигурации
cp .env.example .env
```

### 2. Настройка переменных окружения

Отредактируйте `.env`:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
ZAKUPAI_API_URL=http://localhost:8080
ZAKUPAI_API_KEY=your_zakupai_api_key
DATABASE_URL=postgresql://zakupai:password123@localhost:5432/zakupai
```

### 3. Установка зависимостей

```bash
# Python 3.11+ требуется
pip install -r requirements.txt
```

### 4. Инициализация базы данных

```bash
# Подключение к PostgreSQL и выполнение init.sql
psql -U zakupai -d zakupai -f init.sql
```

### 5. Запуск бота

```bash
python main.py
```

## Docker развёртывание

### Сборка образа

```bash
docker build -t zakupai-bot .
```

### Запуск с docker-compose

```yaml
version: '3.8'

services:
  zakupai-bot:
    build: .
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - ZAKUPAI_API_URL=http://gateway:8080
      - ZAKUPAI_API_KEY=${ZAKUPAI_API_KEY}
      - DATABASE_URL=postgresql://zakupai:password123@db:5432/zakupai
    depends_on:
      - db
      - gateway
    networks:
      - zakupai-net
    restart: unless-stopped

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: zakupai
      POSTGRES_USER: zakupai
      POSTGRES_PASSWORD: password123
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - zakupai-net

networks:
  zakupai-net:

volumes:
  postgres_data:
```

```bash
docker-compose up -d
```

## Архитектура

```
bot/
├── main.py           # Основной модуль бота (aiogram 3)
├── client.py         # HTTP клиент для ZakupAI API
├── db.py            # PostgreSQL операции (asyncpg)
├── models.py        # Pydantic модели данных
├── smoke.py         # Smoke тесты
├── init.sql         # Инициализация БД
├── requirements.txt # Python зависимости
├── Dockerfile       # Docker образ
├── .env.example     # Пример конфигурации
└── tests/
    ├── test_main.py     # Тесты команд бота
    ├── test_client.py   # Тесты API клиента
    ├── test_db.py       # Тесты БД операций
    └── test_models.py   # Тесты моделей данных
```

## Интеграции

### ZakupAI API Endpoints

| Сервис        | Endpoint            | Описание              |
| ------------- | ------------------- | --------------------- |
| doc-service   | `POST /doc/tldr`    | Краткое описание лота |
| risk-engine   | `POST /risk/score`  | Риск-скор лота        |
| calc-service  | `POST /calc/vat`    | Расчёт НДС            |
| calc-service  | `POST /calc/margin` | Расчёт маржи          |
| embedding-api | `POST /embed`       | Генерация эмбеддингов |

### Схема БД

```sql
-- Пользователи и API ключи
CREATE TABLE tg_keys (
    user_id BIGINT PRIMARY KEY,
    api_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Активность пользователей (опционально)
CREATE TABLE tg_user_activity (
    id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES tg_keys(user_id),
    command TEXT NOT NULL,
    lot_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Кэш результатов анализа
CREATE TABLE tg_lot_cache (
    lot_id TEXT PRIMARY KEY,
    tldr_data JSONB,
    risk_data JSONB,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 hour')
);
```

## Тестирование

### Запуск тестов

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=bot --cov-report=html

# Только unit тесты
pytest tests/test_models.py tests/test_client.py

# Только интеграционные тесты
pytest tests/test_main.py tests/test_db.py
```

### Smoke тесты

```bash
# Переменные окружения
export ZAKUPAI_API_URL=http://localhost:8080
export ZAKUPAI_API_KEY=your-api-key

# Запуск smoke тестов
python smoke.py
```

Smoke тесты проверяют:

- ✅ Подключение к БД
- ✅ Health check API
- ✅ Авторизацию (/info endpoint)
- ✅ Calc service (VAT, margin)
- ✅ Doc service (TL;DR)
- ✅ Risk engine (scoring)
- ✅ Embedding API
- ✅ Rate limiting

## Мониторинг и логирование

### Health Check

```bash
# Проверка состояния БД
python -c "import asyncio; from db import health_check; print(asyncio.run(health_check()))"

# HTTP health check (если включен)
curl http://localhost:8000/health
```

### Логи

Бот использует структурированное логирование JSON:

```json
{
  "timestamp": "2024-01-15T10:30:45Z",
  "level": "INFO",
  "message": "User 123456789 analyzed lot 12345",
  "user_id": 123456789,
  "lot_id": "12345",
  "command": "lot"
}
```

## Производительность

### Рекомендации

- **Пул соединений БД**: 1-10 соединений
- **API таймауты**: 30 секунд
- **Кэширование**: 1 час для результатов анализа
- **Rate limiting**: Обрабатывается на уровне nginx gateway

### Масштабирование

```bash
# Несколько инстансов бота
docker-compose up -d --scale zakupai-bot=3

# Horizontal Pod Autoscaler (Kubernetes)
kubectl autoscale deployment zakupai-bot --cpu-percent=70 --min=1 --max=10
```

## Безопасность

- ✅ API ключи хранятся в зашифрованном виде в БД
- ✅ Rate limiting на уровне gateway
- ✅ Валидация всех входных данных (Pydantic)
- ✅ Аудит логи пользовательских действий
- ✅ No secrets in logs или code

## Разработка

### Локальная разработка

```bash
# Виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\\Scripts\\activate  # Windows

# Зависимости для разработки
pip install -r requirements.txt

# Pre-commit хуки
pip install pre-commit
pre-commit install

# Форматирование и линтинг
black bot/
isort bot/
ruff check bot/
mypy bot/
```

### Структура коммитов

```bash
# Примеры коммитов
git commit -m "feat: add /lot command with risk analysis"
git commit -m "fix: handle API timeout errors in client"
git commit -m "docs: update README with deployment instructions"
git commit -m "test: add integration tests for lot analysis"
```

## Troubleshooting

### Частые проблемы

**1. Bot не отвечает**

```bash
# Проверка логов
docker logs zakupai-bot

# Проверка подключения к API
curl -H "X-API-Key: your-key" http://localhost:8080/health
```

**2. Ошибки БД**

```bash
# Проверка соединения
psql postgresql://zakupai:password123@localhost:5432/zakupai -c "SELECT 1;"

# Пересоздание таблиц
psql -U zakupai -d zakupai -f init.sql
```

**3. API таймауты**

```bash
# Увеличение таймаутов в .env
API_TIMEOUT=60
```

## Поддержка

- 📧 Email: support@zakupai.kz
- 💬 Telegram: @zakupai_support
- 🐛 Issues: [GitHub Issues](https://github.com/zakupai/bot/issues)
- 📖 Docs: [ZakupAI Documentation](https://docs.zakupai.kz)

## Лицензия

MIT License - см. [LICENSE](LICENSE) файл.
