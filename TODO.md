## 0) Базовая инфраструктура (Спринт 0)
- [x] Docker Compose: db, calc-service, risk-engine, doc-service, embedding-api
- [x] Health-check `/health`, защищённый `/info` (X-API-Key)
- [x] [CI](https://github.com/Yevgen-beep/zakupai/actions/workflows/ci.yml/badge.svg)](https://github.com/Yevgen-beep/zakupai/actions/workflows/ci.yml)

- [  ] Makefile: `make up/down/logs/test`
- [  ] Логи JSON + кореляция `X-Request-Id` во всех сервисах
- [  ] Pre-commit хуки (ruff/black/isort, yamllint, markdownlint)
- [x] Скрипт запуска `scripts/bootstrap.sh`
- [  ] Удалить `version:` из `docker-compose.yml` (warning compose)
- [  ] Reverse-proxy (traefik/nginx) + rate limits

## 1) Данные и схема БД
- [x] Таблица `lots(id, title, price)` (миграция V1)
- [x] Миграция V2: `lots(risk_score numeric, deadline date, customer_bin text, plan_id text)`
- [x] Таблицы: `suppliers`, `prices`, `lot_prices`
- [x] Таблицы: `risk_evaluations`, `finance_calcs`
- [x] Индексы: `lots(customer_bin, deadline)`, `prices(sku)`, `lot_prices(lot_id)`
- [  ] Индексы: `prices(captured_at)`, `risk_evaluations(lot_id, created_at desc)`
- [  ] FK политика: CASCADE вместо SET NULL
- [  ] Сидинг: `scripts/seed.sql` + `seed.sh`
- [  ] Alembic миграции (инициализация, автогенерация)

## 2) Сервисы (FastAPI)

### calc-service (8001)
- [x] `/health`
- [  ] `POST /calc/vat`
- [  ] `POST /calc/margin`
- [  ] `POST /calc/penalty`
- [  ] Сохранение расчётов в `finance_calcs`
- [  ] Pytest + curl-примеры

### risk-engine (8002)
- [x] `/health`
- [  ] `POST /score/lot`
- [  ] `GET /risk/explain/{lot_id}`
- [  ] YAML-правила + версия в ответе
- [  ] Сохранение в `risk_evaluations`
- [  ] Юнит-тесты

### doc-service (8003)
- [x] `/health`
- [  ] `POST /tldr`
- [  ] `POST /letters/generate`
- [  ] Экспорт в PDF (WeasyPrint/wkhtmltopdf)

### embedding-api (8004)
- [x] `/health`
- [x] `POST /embed` (заглушка)
- [  ] `POST /search` (mock top-k)
- [  ] Реальная модель эмбеддингов

## 3) Интеграции (n8n / Flowise)

### n8n-nodes
- [  ] `goszakup-rk`
- [  ] `price-aggregator`
- [  ] `tender-finance-calc`
- [  ] `lot-risk-scoring`
- [  ] `doc-builder`

### flowise-tools
- [  ] `lot-reader`
- [  ] `risk-explain`
- [  ] `finance-calc`
- [  ] `template-gen`

## 4) Клиентские потоки
- [  ] Telegram: `/start` + API Key
- [  ] Telegram: `/lot <id|url>` → TL;DR → риск → финкальк → «Документы»
- [  ] Telegram: уведомления «горячие лоты» (cron)
- [  ] Веб-панель: страница лота
- [  ] Веб-панель: форма аплоада прайсов

## 5) Безопасность и доступ
- [x] Единый `X-API-Key` (middleware `/info`)
- [  ] Rate limits
- [  ] Аудит-логи
- [  ] CORS/CSRF политика

## 6) DevOps / эксплуатация
- [  ] Envs: `.env.dev`, `.env.stage`, `.env.prod`
- [  ] Бэкапы БД (pg_dump + rclone)
- [  ] Prometheus + Grafana
- [  ] Алерты по health
- [  ] Docker-теги релизов

## 7) Документация
- [  ] OpenAPI: `/docs`, `/openapi.json`
- [  ] README: запуск, миграции, curl
- [  ] CHANGELOG.md
- [  ] docs/architecture.md

## 8) Бизнес/юридическое
- [  ] Сверка «сервисы/боли» с бэклогом
- [  ] Виды деятельности/ОКЭД для ТОО (Astana Hub)
- [  ] Выжимка бизнес-плана → лендинг/презентация

## 9) Тест-кейсы (сквозняк)
- [  ] Импорт CSV цен → `prices`
- [  ] Создать лот → сопоставить SKU → рассчитать маржу
- [  ] Риск-скоринг → сохранить в `risk_evaluations`
- [  ] Сгенерировать письмо (doc-service)

