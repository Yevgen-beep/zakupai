0. Базовая инфраструктура (Спринт 0)

\[x\] Docker Compose: db, calc-service, risk-engine, doc-service, embedding-api, billing-service
\[x\] Health-check /health, защищённый /info (X-API-Key)
\[x\] CI: lint + build (GitHub Actions)
\[x\] Makefile: make up/down/logs/test (+ smoke-\*)
\[x\] Логи JSON + кореляция X-Request-Id во всех сервисах
\[x\] Скрипт запуска scripts/bootstrap.sh
\[x\] Удалить version: из docker-compose.yml (warning compose)
\[x\] Reverse-proxy (nginx gateway) + rate limits (429) + prefix stripping
\[x\] Pre-commit хуки (ruff/black/isort, yamllint, mdformat, bandit)

1. Данные и схема БД

\[x\] Таблица lots(id, title, price) (миграция V1)
\[x\] Миграция V2: lots(risk_score numeric, deadline date, customer_bin text, plan_id text)
\[x\] Таблицы: suppliers(bin, name), prices(source, sku, price), lot_prices(lot_id, price_id, qty)
\[x\] Индексы по customer_bin, deadline
\[x\] Индексы: prices(sku), prices(captured_at)
\[x\] Индексы: risk_evaluations(lot_id, created_at DESC)
\[x\] FK политика: CASCADE для lot_prices.(lot_id, price_id)
\[x\] Seeding: scripts/seed.sql + scripts/seed.sh
\[x\] Alembic миграции (инициализация, автогенерация)

2. Сервисы (FastAPI)

\[x\] calc-service: /calc/vat, /calc/margin, /calc/penalty + запись в finance_calcs
\[x\] risk-engine: /risk/score, /risk/explain/{lot_id} + запись в risk_evaluations
\[x\] doc-service: /tldr, /letters/generate, /render/html
\[x\] doc-service: экспорт HTML→PDF (/render/pdf)
\[x\] embedding-api: /embed, /index, /search
\[x\] doc-service: локализация ru-KZ
\[x\] Pytest + curl-примеры для всех сервисов

3. Интеграции (n8n / Flowise)

\[x\] Настроена связность: Flowise/n8n → zakupai сервисы (docker networks)
\[x\] n8n-nodes: goszakup-rk
\[x\] n8n-nodes: price-aggregator
\[x\] n8n-nodes: tender-finance-calc
\[x\] n8n-nodes: lot-risk-scoring
\[x\] n8n-nodes: doc-builder
\[x\] flowise-tools: lot-reader
\[x\] flowise-tools: risk-explain
\[x\] flowise-tools: finance-calc
\[x\] flowise-tools: template-gen

4. Клиентские потоки

\[x\] Telegram: /start + API Key
\[x\] Telegram: /lot \<id|url> → TL;DR → риск → финкальк → «Документы»
\[ \] Telegram: уведомления «горячие лоты» (cron)
\[x\] Веб-панель: страница лота + форма аплоада прайсов (CSV/XLSX)

5. Безопасность и доступ

\[x\] Единый X-API-Key (+ /info)
\[x\] Rate limits на внешних эндпоинтах (nginx gateway → 429)
\[x\] Аудит-логи вызовов
\[ \] CORS/CSRF политика для веб-панели
\[x\] SAST: Bandit в pre-commit/CI
\[x\] Валидация и санитизация всех входных данных (FastAPI deps) для защиты от инъекций

6. DevOps / эксплуатация1

\[x\] Smoke для calc/risk/doc/emb (скрипт + Makefile)
\[x\] Включить smoke-матрицу в CI по всем сервисам
\[x\] Envs: .env.dev, .env.stage, .env.prod
\[x\] Бэкапы БД (pg_dump + rclone в облако)
\[x\] Prometheus + Grafana, алерты
\[ \] Docker-теги релизов, compose pull && up -d

7. Документация

\[x\] OpenAPI: /docs, /openapi.json
\[x\] README.md: запуск, порты, curl (базово)
\[x\] CHANGELOG.md
\[x\] docs/architecture.md

8. Бизнес/юридическое

\[ \] Сверка «сервисы/боли» с бэклогом
\[ \] Виды деятельности/ОКЭД для ТОО (Astana Hub)
\[ \] Выжимка бизнес-плана → лендинг/презентация

9. Billing Service (MVP)

\[x\] billing-service: POST /billing/create_key, /validate_key, /usage
\[x\] PostgreSQL billing схема: users, api_keys, usage, payments
\[x\] Интеграция с docker-compose + gateway dependency
\[x\] Лимиты Free/Premium + валидация ключей
\[x\] Unit тесты billing-service
\[x\] README.md: документация Billing Service

10. Тест-кейсы (сквозняк)

\[x\] Импорт CSV/XLSX цен → prices
\[x\] Создать лот → сопоставить SKU → рассчитать маржу (calc-service)
\[x\] Риск-скоринг → сохранить в risk_evaluations (risk-engine)
\[x\] Сгенерировать письмо (doc-service)
