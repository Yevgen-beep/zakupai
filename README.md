[![CI](https://github.com/Yevgen-beep/zakupai/actions/workflows/ci.yml/badge.svg)](https://github.com/Yevgen-beep/zakupai/actions/workflows/ci.yml)

# ZakupAI

MVP-платформа для автоматизации госзакупок РК.
ZakupAI анализирует тендеры, генерирует краткие TL;DR, оценивает риски и маржинальность, формирует документы и жалобы, а также интегрируется с n8n, Flowise и Telegram-ботом для бизнеса.

______________________________________________________________________

## 🚀 Возможности

- Автоматический разбор тендеров (TL;DR, риск-скоринг, маржа, НДС, штрафы)
- Генерация документов: письма, жалобы, отчёты (PDF/HTML)
- Telegram-бот @TenderFinderBot_bot как основной интерфейс для МСБ
- Интеграции: Flowise (визуальные AI-воркфлоу), n8n (автоматизация процессов)
- Мониторинг конкурентов и «горячие лоты» (уведомления по cron)
- Финансовый калькулятор для оценки выгодности участия

______________________________________________________________________

## 🏗 Архитектура

ZakupAI построен на микросервисной архитектуре (FastAPI + Docker).

### Основные сервисы

- **API Gateway** (`http://localhost:8080`) — маршрутизация, rate limits, X-API-Key
- **Billing Service** (`:7004`) — управление пользователями, API ключи, лимиты, подписки
- **Calc Service** (`:7001`) — расчёты (НДС, маржа, штрафы)
- **Risk Engine** (`:7002`) — риск-скоринг и объяснения
- **Doc Service** (`:7003`) — TL;DR, письма, PDF-экспорт, локализация (ru/kz/en)
- **Embedding API** (`:7010`) — векторизация, поиск, интеграция с Ollama

### Базы данных

- **PostgreSQL** (`:5432`) — лоты, цены, риски, финрезультаты + billing схема (users, api_keys, usage, payments)
- **ChromaDB** (`:8000`) — векторное хранилище для поиска

### Клиентские интерфейсы

- **Telegram Bot** (@TenderFinderBot_bot)
  - `/start` — приветствие + регистрация
  - `/key <API_KEY>` — привязка ключа
  - `/lot <id|url>` — полный анализ лота
  - `/help` — справка
- **Web UI** (`http://localhost:8082`) — просмотр лотов, загрузка прайсов (CSV/XLSX)
- **Flowise** (`http://localhost:3000`) — AI-воркфлоу (lot-reader, risk-explain, finance-calc, template-gen)
- **n8n** (`http://localhost:5678`) — автоматизация и пайплайны

### Мониторинг и DevOps

- **Prometheus** (`http://localhost:9090`) — метрики
- **Grafana** (`http://localhost:3001`) — дашборды
- **Alertmanager** (`http://localhost:9093`) — алерты
- **cAdvisor** (`http://localhost:8081`) — контейнеры
- **Node Exporter** (`:9100`) и **BlackBox Exporter** (`:9115`) — метрики хоста и HTTP
- Автобэкапы PostgreSQL (pg_dump + rclone → B2/S3)
- CI/CD (lint, build, smoke-тесты)

### 🛡️ Безопасность

**Конфигурация:**

- Все секреты загружаются из `.env` файлов (пароли, API ключи, токены)
- Обязательные переменные окружения валидируются при запуске
- Никогда не логируем API ключи или пароли (только маскированные версии)

**База данных:**

- Connection pooling с ограничениями (min/max соединения, таймауты)
- Параметризованные SQL запросы для защиты от инъекций
- Валидация входных данных с помощью Pydantic моделей
- Автоматическое закрытие соединений через контекстные менеджеры

**HTTP и API:**

- SSL verification включен по умолчанию для всех внешних запросов
- Request/Response логирование с уникальными X-Request-Id
- Таймауты для всех HTTP запросов (защита от зависания)
- Централизованная обработка ошибок без утечки технических деталей

**Telegram Bot:**

- Rate limiting: максимум 10 команд в минуту на пользователя
- Валидация и санитизация всех пользовательских вводов
- Безопасная обработка URL и ID лотов (защита от XSS)
- Логирование событий безопасности (превышения лимитов, подозрительные вводы)

**Валидация данных:**

- Строгая типизация с Pydantic для всех API моделей
- Ограничение размеров входных данных (защита от DoS)
- Email валидация по RFC стандартам
- UUID формат для API ключей с проверкой

**Monitoring безопасности:**

- Логирование всех security events с уровнем WARNING
- Отслеживание неудачных попыток авторизации
- Мониторинг превышений rate limits
- Централизованное логирование без секретов

### AI и Ollama

- **Ollama (host)** (`http://localhost:11434`)
- Модели: `qwen3`, `llama3`, `mistral`, `deepseek-r1`
- Используется для эмбеддингов и LLM-обработки

______________________________________________________________________

### 🔗 Потоки данных

````mermaid
flowchart LR
    TG[Telegram Bot] -->|/key /lot|
    B[Billing Service]
    W[Web UI] --> B
    F[⚡ Flowise] --> B
    N[n8n Workflows] --> B

    B --> G[API Gateway]

    G --> C[Calc Service]
    G --> R[Risk Engine]
    G --> D[Doc Service]
    G --> E[Embedding API]

    E --> O[Ollama (host)]
    G --> DB[(PostgreSQL)]
    E --> CH[(ChromaDB)]

🔑 Billing Service
MVP (Stage)
PostgreSQL (схема billing):
users — пользователи
api_keys — API-ключи и планы
usage — статистика использования
payments — оплаты и подписки

FastAPI endpoints:
POST /billing/create_key — создать API-ключ (автоматически при /start)
POST /billing/validate_key — валидация ключа + проверка лимитов
POST /billing/usage — логирование использования
GET /billing/stats/{tg_id} — статистика по пользователю

Система лимитов:
Free: 100 запросов/день, 20/час
Premium: 5000 запросов/день, 500/час
Docker: сервис работает на :7004, интегрирован в общий docker-compose

Тарифы
План	                Лимит в день	   Лимит в час	        Цена
Free	                    100	              20	            0 ₸
Premium	                  5000	            500	            10 000 ₸


Интеграция
Telegram Bot: выдаёт ключи и проверяет их перед анализом лота
Gateway: проверяет ключи перед доступом к API
Все сервисы ZakupAI: работают только через Billing валидацию

Сводка по портам
Gateway — http://localhost:8080
Web UI — http://localhost:8082
Telegram Bot — @TenderFinderBot_bot
Flowise — http://localhost:3000
n8n — http://localhost:5678
Postgres — :5432
ChromaDB — :8000
Calc Service — :7001
Risk Engine — :7002
Doc Service — :7003
Billing Service — :7004
Embedding API — :7010
Ollama (host) — http://localhost:11434
Prometheus — http://localhost:9090
Grafana — http://localhost:3001
Alertmanager — http://localhost:9093
cAdvisor — http://localhost:8081
Node Exporter — http://localhost:9100
BlackBox Exporter — http://localhost:9115

Security & DevOps
Rate limits: 60 req/min (Nginx Gateway)
X-API-Key для всех сервисов
CORS/CSRF политика: dev — открытая, stage — ограниченная, prod — строгая
Валидация входных данных (FastAPI deps)
Pre-commit хуки: ruff, black, isort, yamllint, mdformat
SAST (Bandit) в CI
Автобэкапы PostgreSQL (pg_dump + rclone → B2/S3)

Монетизация
Freemium → Premium подписка (10 000 ₸/мес)
Пакеты документов (3 000–10 000 ₸ за комплект)
AI-отчёты PDF для анализа тендеров
White Label для юристов и консалтинговых компаний

Виды деятельности (ОКЭД)
62.01.1 — Разработка ПО и SaaS (основной)
62.01.2 — ИТ-консалтинг, внедрение ИИ
63.11.1 — Обработка данных, API сервисы
62.03.0 — MLOps и инфраструктура
62.09.0 — Инновационные IT-решения

## 🚀 Быстрый запуск

### 1. Подготовка окружения
```bash
# Склонировать репозиторий
git clone <repo_url>
cd zakupai

# Скопировать конфигурационные файлы
cp .env.example .env
cp bot/.env.example bot/.env
````

### 2. Настройка Telegram Bot (обязательно)

**Важно:** Переменные окружения для бота прописываются в файле `./bot/.env` (не в корневом `.env`).

Отредактируйте файл `bot/.env`:

```bash
# Получите токен от @BotFather в Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Для разработки (по умолчанию)
ENVIRONMENT=development

# Для production добавьте webhook настройки
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook/telegram
TELEGRAM_WEBHOOK_SECRET=your_webhook_secret
```

### 3. Запуск сервисов

```bash
# Запустить все сервисы
docker-compose up -d

# Проверить статус
docker-compose ps

# Посмотреть логи бота
docker-compose logs -f zakupai-bot
```

### 4. Проверка конфигурации

```bash
# Проверить переменные окружения бота
docker exec zakupai-bot env | grep TELEGRAM

# Проверить webhook (если настроен)
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool

# Проверить API Gateway
curl http://localhost:8080/health
```

### 5. Тестирование бота

1. Найдите вашего бота в Telegram по токену
1. Отправьте `/start`
1. Попробуйте команды `/help`, `/search компьютеры`

**📋 Полный план тестирования:** [docs/test-plan.md](docs/test-plan.md)

______________________________________________________________________

## 📚 Документация по настройке

### Режимы работы бота

**Development (polling):**

- `ENVIRONMENT=development` в `bot/.env`
- Бот работает через polling (запрашивает обновления)
- Подходит для локальной разработки

**Production (webhook):**

- `ENVIRONMENT=production` или `staging` в `bot/.env`
- Настройте `TELEGRAM_WEBHOOK_URL` и `TELEGRAM_WEBHOOK_SECRET`
- Telegram отправляет обновления на ваш сервер
- Более эффективно для production

### Переменные окружения

Основные файлы конфигурации:

- `.env` — общие настройки (БД, API, мониторинг)
- `bot/.env` — настройки Telegram бота

**Критические переменные в bot/.env:**

```bash
TELEGRAM_BOT_TOKEN=       # Токен от @BotFather
TELEGRAM_WEBHOOK_URL=     # URL для webhook (production)
TELEGRAM_WEBHOOK_SECRET=  # Секрет для webhook (production)
ENVIRONMENT=              # development/staging/production
N8N_WEBHOOK_URL=         # URL n8n для поиска лотов
```

**Важно:** Production URL для n8n прописывается в файле `bot/.env` (переменная `N8N_WEBHOOK_URL`). Полный путь: `zakupai/bot/.env`.

### Устранение проблем

**Бот не отвечает:**

```bash
# Проверьте переменные
docker exec zakupai-bot env | grep TELEGRAM_BOT_TOKEN

# Проверьте логи
docker-compose logs zakupai-bot

# Перезапустите бота
docker-compose restart zakupai-bot
```

**Ошибка "Missing required environment variables: TELEGRAM_BOT_TOKEN":**

- Убедитесь, что файл `bot/.env` существует
- Проверьте, что в нем есть `TELEGRAM_BOT_TOKEN=ваш_токен`
- Перезапустите контейнер: `docker-compose restart zakupai-bot`

**База данных недоступна:**

```bash
# Запустите БД отдельно
docker-compose up -d db

# Дождитесь готовности (~30 секунд)
docker-compose logs db

# Запустите бота
docker-compose up -d zakupai-bot
```

______________________________________________________________________

## 🧪 Тестирование

Подробный сценарий проверки Telegram-бота доступен в **[docs/test-plan.md](docs/test-plan.md)**.

Включает тестирование:

- Базовых команд (`/start`, `/help`, `/key`)
- Основного функционала (`/lot`, `/search`)
- Интеграции с Billing Service
- Будущих возможностей (риск-анализ, документы)

______________________________________________________________________

## 🏗 Итоговая архитектура

ZakupAI — это готовая инфраструктура:

- Бэкенд сервисы для анализа тендеров
- Автоматизация через n8n и Flowise
- Клиентские интерфейсы (Telegram Bot, Web UI)
- Встроенный Billing Service (MVP)
- AI-интеграция через Ollama и Embedding API
- Мониторинг и бэкапы для продакшн-готовности
