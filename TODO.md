0. Базовая инфраструктура (Спринт 0)

\[x\] Docker Compose: db, calc-service, risk-engine, doc-service, embedding-api
\[x\] Health-check /health, защищённый /info (X-API-Key)
\[ \] CI: lint + build (GitHub Actions)
\[x\] Makefile: make up/down/logs/test (+ smoke-\*)
\[ \] Логи JSON + кореляция X-Request-Id во всех сервисах
\[x\] Скрипт запуска scripts/bootstrap.sh
\[x\] Удалить version: из docker-compose.yml (warning compose)
\[ \] Reverse-proxy (traefik/nginx) + rate limits
\[ \] Pre-commit хуки (ruff/black/isort, yamllint, markdownlint)

1. Данные и схема БД

\[x\] Таблица lots(id, title, price) (миграция V1)
\[x\] Миграция V2: lots(risk_score numeric, deadline date, customer_bin text, plan_id text)
\[x\] Таблицы: suppliers(bin, name), prices(source, sku, price), lot_prices(lot_id, price_id, qty)
\[ \] Индексы по customer_bin, deadline
\[ \] Индексы: prices(sku), prices(captured_at)
\[ \] Индексы: risk_evaluations(lot_id, created_at DESC)
\[ \] FK политика: CASCADE для lot_prices.(lot_id, price_id)
\[ \] Seeding: scripts/seed.sql + scripts/seed.sh
\[ \] Alembic миграции (инициализация, автогенерация)

2. Сервисы (FastAPI)

\[x\] calc-service: /calc/vat, /calc/margin, /calc/penalty + запись в finance_calcs
\[x\] risk-engine: /risk/score, /risk/explain/{lot_id} + запись в risk_evaluations
\[x\] doc-service: /tldr, /letters/generate, /render/html
\[x\] doc-service: экспорт HTML→PDF (/render/pdf)
\[x\] embedding-api: /embed, /index, /search
\[ \] doc-service: локализация ru-KZ
\[ \] Pytest + curl-примеры для всех сервисов

3. Интеграции (n8n / Flowise)

\[ \] n8n-nodes: goszakup-rk
\[ \] n8n-nodes: price-aggregator
\[ \] n8n-nodes: tender-finance-calc
\[ \] n8n-nodes: lot-risk-scoring
\[ \] n8n-nodes: doc-builder
\[ \] flowise-tools: lot-reader
\[ \] flowise-tools: risk-explain
\[ \] flowise-tools: finance-calc
\[ \] flowise-tools: template-gen

4. Клиентские потоки

\[ \] Telegram: /start + API Key
\[ \] Telegram: /lot \<id|url> → TL;DR → риск → финкальк → «Документы»
\[ \] Telegram: уведомления «горячие лоты» (cron)
\[ \] Веб-панель: страница лота + форма аплоада прайсов (CSV/XLSX)

5. Безопасность и доступ

\[x\] Единый X-API-Key (+ /info)
\[ \] Rate limits (traefik/nginx)
\[ \] Аудит-логи вызовов
\[ \] CORS/CSRF политика для веб-панели

6. DevOps / эксплуатация

\[x\] Smoke для calc/risk/doc/emb (скрипт + Makefile)
\[ \] Включить smoke-матрицу в CI по всем сервисам
\[ \] Envs: .env.dev, .env.stage, .env.prod
\[ \] Бэкапы БД (pg_dump + rclone в облако)
\[ \] Prometheus + Grafana, алерты
\[ \] Docker-теги релизов, compose pull && up -d

7. Документация

\[x\] OpenAPI: /docs, /openapi.json
\[x\] README.md: запуск, порты, curl (базово)
\[ \] CHANGELOG.md
\[ \] docs/architecture.md

8. Бизнес/юридическое

\[ \] Сверка «сервисы/боли» с бэклогом
\[ \] Виды деятельности/ОКЭД для ТОО (Astana Hub)
\[ \] Выжимка бизнес-плана → лендинг/презентация

9. Тест-кейсы (сквозняк)

\[ \] Импорт CSV/XLSX цен → prices
\[ \] Создать лот → сопоставить SKU → рассчитать маржу (calc-service)
\[ \] Риск-скоринг → сохранить в risk_evaluations (risk-engine)
\[ \] Сгенерировать письмо (doc-service)
