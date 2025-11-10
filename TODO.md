# 🧩 ZakupAI Infrastructure — Progress Tracker

> **Последнее обновление:** 2025-11-09
> **Текущая стадия:** Stage 7 → Stage 9 (Network Consolidation + Vault Production)

---

## 0. Базовая инфраструктура (Спринт 0)

[x] Docker Compose: db, calc-service, risk-engine, doc-service, embedding-api, billing-service
[x] Health-check /health, защищённый /info (X-API-Key)
[x] CI: lint + build (GitHub Actions)
[x] Makefile: make up/down/logs/test (+ smoke-*)
[x] Логи JSON + кореляция X-Request-Id во всех сервисах
[x] Скрипт запуска scripts/bootstrap.sh
[x] Удалить version: из docker-compose.yml (warning compose)
[x] Reverse-proxy (nginx gateway) + rate limits (429) + prefix stripping
[x] Pre-commit хуки (ruff/black/isort, yamllint, mdformat, bandit)

---

## 1. Данные и схема БД

[x] Таблица lots(id, title, price) (миграция V1)
[x] Миграция V2: lots(risk_score numeric, deadline date, customer_bin text, plan_id text)
[x] Таблицы: suppliers(bin, name), prices(source, sku, price), lot_prices(lot_id, price_id, qty)
[x] Индексы по customer_bin, deadline
[x] Индексы: prices(sku), prices(captured_at)
[x] Индексы: risk_evaluations(lot_id, created_at DESC)
[x] FK политика: CASCADE для lot_prices.(lot_id, price_id)
[x] Seeding: scripts/seed.sql + scripts/seed.sh
[x] Alembic миграции (инициализация, автогенерация)

---

## 2. Сервисы (FastAPI)

[x] calc-service: /calc/vat, /calc/margin, /calc/penalty + запись в finance_calcs
[x] risk-engine: /risk/score, /risk/explain/{lot_id} + запись в risk_evaluations
[x] doc-service: /tldr, /letters/generate, /render/html
[x] doc-service: экспорт HTML→PDF (/render/pdf)
[x] embedding-api: /embed, /index, /search
[x] doc-service: локализация ru-KZ
[x] Pytest + curl-примеры для всех сервисов

---

## 3. Интеграции (n8n / Flowise)

[x] Настроена связность: Flowise/n8n → zakupai сервисы (docker networks)
[x] n8n-nodes: goszakup-rk
[x] n8n-nodes: price-aggregator
[x] n8n-nodes: tender-finance-calc
[x] n8n-nodes: lot-risk-scoring
[x] n8n-nodes: doc-builder
[x] flowise-tools: lot-reader
[x] flowise-tools: risk-explain
[x] flowise-tools: finance-calc
[x] flowise-tools: template-gen

### 📌 Следующие шаги: Production Workflows

[ ] **n8n Production Deployment**
  • Загрузить workflow из `workflows/n8n/` в боевой n8n instance
  • daily-lot-scanner.json → ежедневный скан goszakup
  • lot-processing-pipeline.json → обработка новых лотов
  • price-monitor.json → мониторинг цен поставщиков
  • DoD: все 3 workflow импортированы, активированы и выполняются по расписанию

[ ] **Flowise Production Deployment**
  • Загрузить chatflow из `workflows/flowise/zakupai-assistant-chatflow.json`
  • Настроить API endpoint для chatflow
  • Интегрировать с Telegram bot (/ask команда)
  • DoD: chatflow работает в production, доступен через API

[ ] **Goszakup → Database Pipeline**
  • Создать таблицу `goszakup_lots` (id, plan_number, lot_number, customer_bin, status, amount, created_at)
  • Настроить n8n workflow для автоматической загрузки из Goszakup API v3 в PostgreSQL
  • Реализовать инкрементальную загрузку (только новые лоты)
  • Добавить индексы: goszakup_lots(plan_number), goszakup_lots(created_at DESC)
  • DoD: `SELECT COUNT(*) FROM goszakup_lots` возвращает > 0; n8n workflow выполняется каждые 15 минут

[ ] **ETL Service → Goszakup Integration**
  • Добавить эндпоинт `/etl/goszakup/sync` для принудительной синхронизации
  • Реализовать deduplication (проверка по plan_number + lot_number)
  • Добавить метрики: `goszakup_lots_total`, `goszakup_sync_errors_total`
  • DoD: `curl http://localhost:7011/etl/goszakup/sync` возвращает 200; метрики доступны в Prometheus

[ ] **Data Flow Verification**
  • Проверить полный pipeline: Goszakup API → n8n → PostgreSQL → ETL Service → Risk Engine
  • Smoke-тест: загрузить 10 лотов из Goszakup, проверить что они попали в БД
  • Verify: `SELECT * FROM goszakup_lots ORDER BY created_at DESC LIMIT 10`
  • DoD: все 10 лотов в БД, risk_score рассчитан

---

## 4. Клиентские потоки

[x] Telegram: /start + API Key
[x] Telegram: /lot <id|url> → TL;DR → риск → финкальк → «Документы»
[x] Telegram: уведомления «горячие лоты» (cron)
[x] Веб-панель: страница лота + форма аплоада прайсов (CSV/XLSX)

### 📌 Следующие шаги: Telegram Bot Enhancements

[ ] **Telegram: /ask <question>**
  • Интегрировать с Flowise chatflow API
  • Добавить контекст из БД (последние 5 лотов пользователя)
  • Ограничение: 500 символов в ответе, markdown formatting
  • DoD: `/ask расскажи о демпинге` возвращает релевантный ответ из chatflow

[ ] **Telegram: /subscribe <plan_number>**
  • Подписка на обновления конкретного плана закупок
  • При изменении статуса → уведомление в Telegram
  • Хранить подписки в таблице `user_subscriptions`
  • DoD: изменение лота → пользователь получает уведомление < 5 минут

---

## 5. Безопасность и доступ

[x] Единый X-API-Key (+ /info)
[x] Rate limits на внешних эндпоинтах (nginx gateway → 429)
[x] Аудит-логи вызовов
[x] CORS/CSRF политика для веб-панели
[x] SAST: Bandit в pre-commit/CI
[x] Валидация и санитизация всех входных данных (FastAPI deps) для защиты от инъекций

---

## 6. DevOps / эксплуатация

[x] Smoke для calc/risk/doc/emb (скрипт + Makefile)
[x] Включить smoke-матрицу в CI по всем сервисам
[x] Envs: .env.dev, .env.stage, .env.prod
[x] Бэкапы БД (pg_dump + rclone в облако)
[x] Prometheus + Grafana, алерты
[x] Docker-теги релизов, compose pull && up -d

---

## 7. Документация

[x] OpenAPI: /docs, /openapi.json
[x] README.md: запуск, порты, curl (базово)
[x] CHANGELOG.md
[x] docs/architecture.md

---

## 8. Бизнес/юридическое

[ ] Сверка «сервисы/боли» с бэклогом
[ ] Виды деятельности/ОКЭД для ТОО (Astana Hub)
[ ] Выжимка бизнес-плана → лендинг/презентация

---

## 9. Billing Service (MVP)

[x] billing-service: POST /billing/create_key, /validate_key, /usage
[x] PostgreSQL billing схема: users, api_keys, usage, payments
[x] Интеграция с docker-compose + gateway dependency
[x] Лимиты Free/Premium + валидация ключей
[x] Unit тесты billing-service
[x] README.md: документация Billing Service

---

## 10. Тест-кейсы (сквозняк)

[x] Импорт CSV/XLSX цен → prices
[x] Создать лот → сопоставить SKU → рассчитать маржу (calc-service)
[x] Риск-скоринг → сохранить в risk_evaluations (risk-engine)
[x] Сгенерировать письмо (doc-service)

---

## 11. Telegram Bot — тестирование команд (см. test-plan.md)

[x] Базовые команды: /start, /help, /key
[x] Основные команды: /lot, /search
[x] Интеграция с Billing Service
[x] Полный сценарий пользователя (регистрация → поиск → анализ)
[x] Тестирование webhook и polling режимов
[x] Валидация rate limiting и error handling

---

# ROADMAP: Платформа ZakupAI (Goszakup v2/v3 + AI)

> Этапы 1–3 заархивированы (перенесены в Confluence 2024-06). Фокус на Sprint 4.

---

## Sprint 4 - Master Checklist (Hybrid, Final)

### Stage 4 - Week 1: Quick Wins

[x] Очистка Docker-мусора
[x] docker system df (оценить занимаемое место перед очисткой)
[x] docker image prune -a -f
[x] docker builder prune -a -f
[x] docker system prune -f --volumes
DoD: свободно ≥5GB, билд занимает меньше времени

[x] Удаление дубликатов кода
[x] убрать handlers_v2.py, commands_v2.py
[x] удалить old_main.py и backup_* файлы
[x] завести shared/ для общего кода (DB, логгинг, middleware)
DoD: unit + интеграционные тесты проходят успешно

[x] CI/CD оптимизация
[x] matrix build в .github/workflows/ci.yml
[x] кеширование pip зависимостей
[x] кеширование apt пакетов (tesseract, jq)
[x] добавить Docker layer caching
DoD: время CI сократилось минимум на 30%

---

### Stage 4 - Week 2: Фичи ядра

[x] ETL Batch Upload
[x] добавить эндпоинт /etl/upload-batch для CSV/XLSX
[x] реализовать обработку (сначала синхронно, очередь позже)
[x] интегрировать с n8n workflow
[x] добавить логирование ошибок парсинга CSV/XLSX
DoD: CSV ≤10 MB обрабатывается <5 сек, ошибок ≤1%

[x] RNU-валидация участников
[x] реализовать метод /validate_rnu в risk-engine
[x] добавить кеширование результатов (PostgreSQL/Redis, TTL=24ч)
[x] интегрировать команду /rnu <БИН> в Telegram боте
[x] предусмотреть fallback: если кеш пуст → прямой запрос в API
DoD: ответ при кэше ≤500 мс, успешная валидация ≥95% случаев

[x] Расширенный поиск
[x] добавить фильтры по суммам (min_amount, max_amount)
[x] добавить фильтры по статусам лотов
[x] реализовать автодополнение в Web UI (autocomplete.js)
[x] протестировать автодополнение на реальных кириллических данных
DoD: время поиска сокращено на ≥2 сек, автодополнение работает при вводе ≥2 символов

---

### Stage 4 - Week 3: Расширения

[x] Доработка RNU-валидации
[x] добавить TTL кеша (24ч) для результатов
[x] расширить проверку статусов участников
[x] интегрировать уведомления о блокировках
DoD: уведомления приходят не позже 5 мин после обновления статуса

[x] Улучшение поиска
[x] оптимизировать SQL-запросы под большие выборки
[x] добавить сортировку по сумме и дате
[x] покрыть интеграционными тестами /api/search/advanced
DoD: поиск по 100k лотам ≤2 сек, сортировка работает корректно

[x] Flowise агенты (MVP)
[x] complaint-generator: генерация жалобы по лоту (текстовый вывод)
[x] supplier-finder: поиск поставщиков (через Satu.kz/ChromaDB)
DoD: complaint-generator выдает валидный текст с номером лота, причиной и датой; supplier-finder получает данные в формате, совместимом с ChromaDB

---

### Stage 4 - Week 4: UI, Flowise, E2E, Monitoring

[x] Web UI доработки
[x] импорт прайсов CSV
[x] TL;DR анализа лота на странице /lot/{id}
[x] реализовать автодополнение в поиске
DoD: make smoke + make test-priority3 зелёные; импорт файлов ≤5 MB и TL;DR отображается <1 сек

[x] Flowise агенты (финализация)
[x] complaint-generator: улучшить формат жалобы (PDF/Word)
[x] supplier-finder: фильтры по региону и бюджету
DoD: pytest tests/test_flowise_week4_2.py зелёный; PDF/Word открываются без ошибок, фильтры возвращают корректный список

[x] E2E тестирование
[x] pytest сценарии для batch upload + RNU + advanced search
[x] bash smoke-тесты для новых эндпоинтов
[x] интеграция в CI/CD (priority4-integration job)
DoD: make test-priority4 завершает pytest + scripts/e2e/run_tests.py без ошибок; критические сценарии (CSV импорт, RNU) покрыты

[x] Performance & Monitoring
[x] нагрузочное тестирование новых фич (Locust/JMeter)
[x] алерты в Grafana для batch upload и поиска
[x] мониторинг latency, error rate, CPU usage
DoD: make test-priority4 (pytest + scripts/e2e/run_tests.py + python test_metrics.py) зелёный; нагрузка ≥1000 req/min и алерты активны в Grafana

---

## Stage 6 — Monitoring & Security

### Prometheus

[x] Добавить scrape targets для всех сервисов (calc, risk, doc, embedding, gateway, etl)
[ ] Подключить бизнес-метрики во все FastAPI-сервисы
  • anti-dumping %
  • goszakup error counter

### Loki

[x] Включить promtail для сбора docker-логов
[ ] Добавить расширенные метки: service, procurement_type, compliance_flag

### Grafana

[x] Подключить Prometheus и Loki как datasources через provisioning
[ ] Импортировать дашборды:
  • API latency
  • HTTP 5xx errors
  • Compliance events
[ ] Пересмотреть zakupai-overview.json: оставить как сводный или архивировать после появления специализированных панелей

### Alertmanager

[x] Активировать alerts.yml в Prometheus
[x] Добавить правила «>5 API ошибок подряд» и «антидемпинг >15 %»
[x] Настроить реальный webhook (Telegram/Slack вместо временного gateway:8000/alert)

### Vault

[x] Поднять контейнер Vault
[x] Перенести секреты (DB, API) из ENV → Vault
[x] Подключить hvac в calc, etl, risk-engine для чтения секретов

### Скрипты

[x] Новый stage6-monitoring-test.sh — основной раннер

---

ZakupAI — Development Roadmap (Stage 7–10)
Stage 7 — Monitoring, Vault, Security
Vault Deployment and Monitoring Stack

[x] Развернуть контейнер Vault (hashicorp/vault:1.17)
 • Конфиг: monitoring/vault/config.hcl, порт 8200
 • Сгенерировать root-token и CA

[x] Настроить мониторинг
 • Prometheus, Alertmanager, Grafana
 • Blackbox Exporter, cAdvisor, Loki
 • Prometheus rules (error ratio, latency p95)
 • Дашборд zakupai-overview (uptime >99%)

DoD:
Vault и Monitoring работают стабильно, метрики собираются, health=200 OK.

Vault Integration and Service Stabilization

[x] Исправить конфигурацию Vault bootstrap
[x] Проверить health всех контейнеров
[x] Добавить сети vault-net и monitoring-net
[ ] Устранить предупреждения Pydantic (schema_extra → model_config)

DoD:
Все контейнеры в состоянии health, Vault стабилен.
Тег: stable-stage7-28-10

Auth Middleware and Secrets Management

[ ] Интегрировать hvac в calc-, etl-, risk-engine
[ ] Удалить .env из Docker-сборок
[ ] Перенести все чувствительные переменные (DB URI, API keys, Telegram tokens) в Vault
[ ] Настроить Alertmanager webhook (Telegram / Slack)
[ ] Добавить бизнес-метрики (anti-dumping %, goszakup errors)
[ ] Добавить Vault healthcheck в Compose

DoD:
Все сервисы читают секреты из Vault, .env исключён, webhook-оповещения работают.

Stage 8 — Network Consolidation (Completed 2025-11-09)

[x] Удалить устаревшие сети (ai-network, backend, vault-net)
[x] Мигрировать 5 сервисов на zakupai-network
[x] Удалить version: поля из override-файлов
[x] Проверить Compose-конфигурации (Stage 8, Stage 9, Monitoring)
[x] Сгенерировать network_cleanup.patch и документацию (NETWORK_*)

DoD:
Осталось 2 сети: zakupai-network и monitoring-net.
Все конфиги валидны.
Тег: stable-stage9-vault-network-ok

Stage 9 — Vault Hardening and Production Readiness

[ ] Настроить Vault Stage 9: S3 (Backblaze B2 backend), TLS, audit logging
[ ] Настроить auto-unseal (AES-256 + PBKDF2)

[ ] Перенести все конфиденциальные переменные (DB URI, API keys, Telegram, Goszakup) в Vault KV v2
 • Создать путь zakupai/config/* для групп секретов
 • Сохранить POSTGRES_USER, POSTGRES_PASSWORD, TELEGRAM_BOT_TOKEN, GOSZAKUP_TOKEN
 • Настроить загрузку через hvac при старте сервисов (calc, etl, risk-engine, bot, gateway)
 • Очистить .env и Compose-файлы от чувствительных данных
 • Добавить тест tests/test_vault_integration.py в CI
 • DoD: все сервисы стартуют без .env, секреты читаются из Vault KV

[ ] Настроить PostgreSQL (WAL archiving, pooling, роли доступа)
[ ] Настроить Redis (AOF + пароль + ограничение памяти)
[ ] Прогнать нагрузочные тесты (1000 req/min, P95 < 500 ms)
[ ] Провести security-scan (bandit + snyk + dependency-check = 0 critical)

DoD: Vault полностью защищён, секреты централизованы, CI/CD зелёный.

Stage 9.5 — Business Core Integration
Goszakup API and Data Pipeline

[ ] Настроить интеграцию с Goszakup API
 • Секреты API-ключей хранить в Vault
 • Реализовать endpoint etl/goszakup/sync
 • Выгружать JSON-данные в PostgreSQL (goszakup_lots)

[ ] Создать таблицы в PostgreSQL:
 • goszakup_lots — активные тендеры
 • lot_suppliers — поставщики
 • lot_analysis — расчёт прибыльности

DoD:
ETL-процесс стабильно загружает данные из Goszakup в базу.

Workflow Automation (n8n, Flowise)

[ ] Разработать и загрузить n8n-workflow:
 • daily-lot-scanner.json — ежедневная загрузка лотов
 • lot-processing-pipeline.json — фильтрация и нормализация
 • price-monitor.json — поиск ценовых вилок

[ ] Создать Flowise chatflow:
 • zakupai-assistant-chatflow.json — помощник для анализа лотов
 • Подключить к Chroma и Embedding API

[ ] Настроить интеграцию с Telegram-ботом:
 • /search — поиск лотов
 • /ask — ИИ-ответ по данным из Flowise

DoD:
n8n и Flowise выполняют workflows без ошибок,
Telegram-бот возвращает актуальные результаты из БД.

Stage 10 — Production Deployment and Pilot
Infrastructure Deployment

[ ] Развернуть production-сервер (VPS 8GB / 4vCPU / 100GB SSD)
[ ] Настроить firewall (порты 80, 443, SSH)
[ ] Настроить домен и SSL (Let’s Encrypt)
[ ] Настроить CI/CD-pipeline (build → test → deploy → rollback)

DoD:
Производственный сервер запущен, деплой автоматизирован.

Pilot Program

[ ] Подготовить материалы для клиентов (онбординг, инструкции, support-канал)
[ ] Провести пилот с 10–20 компаниями
[ ] Собрать метрики: DAU, WAU, NPS, pain points
[ ] Подготовить отчёт и обновить roadmap

DoD:
Пилот проведён, отчёт собран, проект готов к коммерческому запуску.

Stage 11 (Planned) — Business Automation and Intelligence

[ ] Автоматическая публикация прибыльных лотов в Telegram-канал
[ ] Ежедневные отчёты в Telegram (/daily-report)
[ ] Рейтинговая модель прибыльности (risk-score)
[ ] GPT-агент для анализа контрактов и жалоб
