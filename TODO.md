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

## Stage 7 — Security & Audit

🎯 **Цель:** завершить формирование безопасной и наблюдаемой платформы ZakupAI.
**Фокус:** безопасность, валидация данных, Vault, mTLS, аудит, централизованное логирование.

---

### Stage 7 — Input Validation / Rate Limit / Docs

[x] Добавить Pydantic-валидацию входных данных для всех API (max_length, ranges)
[x] Реализовать ограничение размера payload (413 Payload Too Large)
[x] Внедрить rate-limiter (по API-ключу / IP / user_id)
[x] Добавить централизованную обработку ошибок (422, 413, 401)
[x] Сгенерировать OpenAPI / Swagger и загрузить в Docs-портал
[x] Обновить тесты для валидации (ожидание 422 / 413)
[x] Обновить CI-workflows для smoke-тестов Docs
[ ] Fix gateway external port mapping and add /health endpoint
  • Ensure "8080:80" in docker-compose.yml
  • Add Nginx health location:
    ```nginx
    location /health {
        return 200 '{"status":"ok"}';
        add_header Content-Type application/json;
    }
    ```
[x] Stage 7 Phase 1 — Security Quick Wins (completed)

---

### Stage 7 — Monitoring + Vault + Secrets

[x] Поднять контейнер Vault (`hashicorp/vault:1.17`)
  • Конфиг → `monitoring/vault/config.hcl`, порт 8200
  • Сгенерировать root-token и CA

[x] Интегрировать `hvac` в calc-service, etl-service, risk-engine
  • Чтение DB credentials и API keys из Vault при старте
  • Fallback на .env если Vault недоступен
  • DoD: сервисы стартуют без .env, читают секреты из Vault ✅

[x] Перенести конфиденциальные переменные (DB URI, API keys, Telegram tokens)
[ ] Настроить Alertmanager webhook (реальный Telegram / Slack)
[x] Business metrics (anti-dumping %, goszakup errors) — метрики доступны в Prometheus

---

### Stage 7 — mTLS между сервисами

[ ] Сгенерировать внутренний CA и клиентские сертификаты
[ ] Настроить Nginx reverse proxy с mutual TLS (ssl_verify_client on)
[ ] Обновить healthcheck на GET /health (с TLS)
[ ] Проверить: `curl --cert client.pem --key client.key` → 200, без сертификата → 403

---

### Stage 7 — Audit + Logging + Testing

[ ] Создать `shared/audit.py` — класс `AuditLogger.log_access(user_id, resource, action)`
[ ] Интегрировать во все FastAPI-сервисы
[ ] Настроить log retention в Loki (3 года, сжатие после 180 дней)
[ ] Прогнать нагрузочные тесты (Locust ≥ 1000 req/min, P95 < 500 ms)
[ ] Выполнить `make security-scan` → bandit + snyk + dependency-check (0 critical)

### 📊 Stage 7 — Summary

**DoD:**
- Все сервисы защищены rate-limiter'ом
- Vault интегрирован во все FastAPI-сервисы
- mTLS включён между gateway и risk-engine
- AuditLogger ведёт централизованные логи (retention = 3 года)
- Security scan проходит без high-severity уязвимостей

---

### 🧾 Документация и CI

[ ] Выполнить план аудита безопасности (security-scan + нагрузочные тесты)
  • `make security-scan` → bandit + snyk + dependency-check (0 critical)
  • Locust ≥ 1000 req/min, P95 < 500 ms
  • DoD: security-scan проходит без high-severity уязвимостей

[ ] Обновить `.github/workflows/ci-optimized.yml` для тестов валидации и security scan
[x] Подготовить README раздел «Безопасность и мониторинг» — см. docs/VAULT_*.md, docs/NETWORK_*.md
[ ] DoD: CI зелёный, security-scan 0 critical, все тесты пройдены.

---

### Финализация

- [ ] Финальные тесты и безопасность (нагрузочные тесты + rate limits)
  DoD: make test-priority4 + security scan (bandit/snyk) зелёные; нагрузочные тесты ≥1000 req/min без деградации

---

## Stage 8 — Network Consolidation (✅ COMPLETED 2025-11-09)

🎯 **Цель:** консолидировать Docker сети и упростить топологию

[x] **Phase 1: Discovery**
  • Сканировать все compose файлы на устаревшие сети (ai-network, vault-net, backend)
  • Найти все объявления deprecated `version:` полей
  • DoD: составлен список файлов для рефакторинга

[x] **Phase 2: Refactor**
  • Удалить ai-network из docker-compose.yml
  • Мигрировать 5 сервисов (embedding-api, risk-engine, doc-service, flowise, n8n) на zakupai-network
  • Удалить `version:` из 4 override файлов
  • DoD: только 2 сети остались: zakupai-network + monitoring-net

[x] **Phase 3: Validation**
  • Валидировать все Docker Compose конфиги (base, stage8, stage9, monitoring)
  • Проверить отсутствие legacy сетей
  • DoD: docker compose config успешно для всех overlay файлов

[x] **Phase 4: Deliverables**
  • Создать network_cleanup.patch (161 строка)
  • Создать docs/NETWORK_CLEANUP_SUMMARY.md
  • DoD: патч сгенерирован, документация полная

[x] **Phase 5: Architecture Documentation**
  • Создать docs/NETWORK_ARCHITECTURE_FINAL.md с диаграммами
  • Описать все 21 сервис с портами и назначением
  • DoD: архитектурная диаграмма актуальна

### 📊 Stage 8 — Summary

**Результаты:**
- ✅ Сети консолидированы: 4+ legacy → 2 canonical (zakupai-network + monitoring-net)
- ✅ 5 сервисов мигрировано с ai-network на zakupai-network
- ✅ 4 deprecated `version:` поля удалены
- ✅ Все конфиги валидны (base, stage8, stage9, monitoring)
- ✅ Полная документация сгенерирована

**Файлы:**
- 📄 [docs/NETWORK_ARCHITECTURE_FINAL.md](docs/NETWORK_ARCHITECTURE_FINAL.md) — топология + service inventory
- 📄 [docs/NETWORK_CLEANUP_SUMMARY.md](docs/NETWORK_CLEANUP_SUMMARY.md) — изменения + валидация
- 📄 [network_cleanup.patch](network_cleanup.patch) — unified diff (161 lines)

**Следующий шаг:** Deploy changes → `docker compose down && docker network prune -f && docker compose up -d`

---

## Stage 9 — Production Readiness & Vault Hardening

🎯 **Цель:** подготовить инфраструктуру к production-развертыванию

### Stage 9 — Vault Production Setup

[ ] **Vault Stage 9 Deployment**
  • Активировать docker-compose.override.stage9.vault-prod.yml
  • Настроить Backblaze B2 storage backend (S3-compatible)
  • Включить TLS для Vault API (мутуальные сертификаты)
  • Настроить audit logging в файл + syslog
  • DoD: Vault работает с B2 backend, TLS активен, audit logs пишутся

[ ] **Vault Auto-Unseal Production**
  • Перенести unseal keys в зашифрованный файл (AES-256)
  • Настроить автоматический unseal при старте контейнера
  • Создать backup стратегию для unseal keys (offline хранение)
  • DoD: Vault автоматически unseals после restart, keys в безопасности

[ ] **Secrets Migration to Vault**
  • Перенести все .env переменные в Vault KV v2
  • Обновить все сервисы для чтения из Vault при старте
  • Удалить .env из всех Docker images
  • DoD: `docker-compose up` стартует без .env, все секреты из Vault

### Stage 9 — Database Hardening

[ ] **PostgreSQL Production Config**
  • Изменить default password для postgres user
  • Создать read-only role для мониторинга
  • Настроить connection pooling (PgBouncer)
  • Включить WAL archiving для PITR (Point-in-Time Recovery)
  • DoD: БД готова к production, backups настроены

[ ] **Redis Production Config**
  • Включить Redis persistence (AOF + RDB)
  • Настроить Redis password authentication
  • Ограничить memory usage (maxmemory-policy allkeys-lru)
  • DoD: Redis сохраняет данные после restart, защищен паролем

### Stage 9 — Monitoring & Alerting

[ ] **Grafana Dashboards Production**
  • Создать дашборд "Production Overview" (uptime, latency, errors)
  • Создать дашборд "Business Metrics" (lots processed, risk scores, revenue)
  • Создать дашборд "Security Events" (failed auth, rate limits, vault access)
  • DoD: все 3 дашборда импортированы и показывают real-time данные

[ ] **Prometheus Alerts Production**
  • Добавить alert: "Service Down" (target down > 2 min)
  • Добавить alert: "High Error Rate" (5xx > 5% за 5 min)
  • Добавить alert: "Database Connection Pool Exhausted"
  • Добавить alert: "Disk Space Low" (< 10% free)
  • DoD: alerts тестируются, notifications приходят в Telegram

### Stage 9 — Load Testing & Performance

[ ] **Load Testing Production Config**
  • Запустить Locust с 1000 concurrent users на 10 минут
  • Измерить P95 latency для всех эндпоинтов
  • Проверить отсутствие memory leaks (мониторинг 24 часа)
  • DoD: P95 < 500ms, 0 memory leaks, система стабильна

[ ] **Database Query Optimization**
  • Анализ slow queries (PostgreSQL pg_stat_statements)
  • Добавить недостающие индексы
  • Оптимизировать N+1 queries в ORM
  • DoD: все queries < 100ms, slow query log пуст

---

## Stage 9.5 — Goszakup Integration & Workflows Deployment

🎯 **Цель:** запустить автоматическую загрузку данных из Goszakup и production workflows

### Stage 9.5 — Goszakup → Database Pipeline

[ ] **Create goszakup_lots Table**
  • Создать миграцию Alembic для таблицы `goszakup_lots`
  • Поля: id, plan_number, lot_number, customer_bin, status, amount, created_at, updated_at
  • Индексы: goszakup_lots(plan_number), goszakup_lots(created_at DESC), goszakup_lots(customer_bin)
  • DoD: миграция применена, таблица создана

[ ] **ETL Service Goszakup Endpoint**
  • Добавить endpoint `/etl/goszakup/sync` в etl-service
  • Реализовать deduplication по (plan_number, lot_number)
  • Добавить метрики: `goszakup_lots_total`, `goszakup_sync_errors_total`, `goszakup_sync_duration_seconds`
  • DoD: `curl http://localhost:7011/etl/goszakup/sync` возвращает 200 + JSON с количеством загруженных лотов

[ ] **n8n Workflow Deployment**
  • Импортировать `workflows/n8n/daily-lot-scanner.json` в n8n instance
  • Импортировать `workflows/n8n/lot-processing-pipeline.json`
  • Импортировать `workflows/n8n/price-monitor.json`
  • Настроить cron schedule: daily-lot-scanner каждые 15 минут
  • DoD: все 3 workflow активны, выполняются по расписанию

[ ] **Data Pipeline Verification**
  • Smoke test: загрузить 10 лотов из Goszakup через n8n
  • Проверить: `SELECT COUNT(*) FROM goszakup_lots` > 10
  • Запустить risk-engine для оценки загруженных лотов
  • DoD: полный pipeline работает end-to-end (Goszakup → DB → Risk Engine → Prometheus)

### Stage 9.5 — Flowise & Telegram Bot Integration

[ ] **Flowise Chatflow Deployment**
  • Импортировать `workflows/flowise/zakupai-assistant-chatflow.json` в Flowise
  • Получить API endpoint для chatflow
  • Протестировать chatflow через API: POST /api/v1/prediction/{chatflowId}
  • DoD: chatflow работает, возвращает валидные ответы на вопросы о закупках

[ ] **Telegram Bot /ask Command**
  • Добавить команду `/ask <question>` в bot/handlers.py
  • Интегрировать с Flowise API endpoint
  • Добавить контекст: последние 5 лотов пользователя из БД
  • Ограничение ответа: 500 символов, markdown formatting
  • DoD: `/ask что такое демпинг?` возвращает релевантный ответ из chatflow

[ ] **Telegram Bot /subscribe Command**
  • Создать таблицу `user_subscriptions` (user_id, plan_number, created_at)
  • Реализовать команду `/subscribe <plan_number>`
  • При изменении статуса лота → отправить уведомление подписанным пользователям
  • DoD: изменение статуса → уведомление < 5 минут

### 📊 Stage 9.5 — Summary

**DoD:**
- Таблица `goszakup_lots` содержит > 100 лотов
- n8n workflows выполняются автоматически по расписанию
- Flowise chatflow доступен через API
- Telegram bot команды `/ask` и `/subscribe` работают
- Метрики `goszakup_*` доступны в Prometheus

---

## Stage 10 — Production Deployment & Pilot

### Stage 10 — Production Infrastructure

[ ] **Cloud Deployment (VPS/Cloud)**
  • Арендовать VPS (мин. 8GB RAM, 4 vCPU, 100GB SSD)
  • Настроить firewall (только 80, 443, SSH)
  • Установить Docker + Docker Compose
  • Настроить автоматические security updates
  • DoD: сервер готов, firewall настроен

[ ] **Domain & SSL**
  • Зарегистрировать домен zakupai.kz (или .com)
  • Настроить DNS A-record → VPS IP
  • Получить SSL-сертификат Let's Encrypt (certbot)
  • Настроить nginx для HTTPS redirect (80 → 443)
  • DoD: https://zakupai.kz доступен с валидным SSL

[ ] **CI/CD Production Pipeline**
  • Настроить GitHub Actions для auto-deploy в production
  • Добавить stage: build → test → deploy to VPS
  • Настроить rollback механизм (предыдущая версия в Docker tags)
  • DoD: git push to main → auto-deploy на production

### Stage 10 — Pilot Program

[ ] **Pilot Preparation**
  • Подготовить onboarding материалы (инструкции, видео)
  • Создать Telegram support group для пилотных пользователей
  • Настроить feedback форму (Google Forms / Typeform)
  • DoD: все материалы готовы, support channel создан

[ ] **Pilot Launch (10-20 компаний)**
  • Отобрать 10-20 компаний (малый/средний бизнес)
  • Провести онлайн-демо (30 минут на компанию)
  • Выдать Premium API keys (бесплатно на 1 месяц)
  • Собрать NPS score после 2 недель использования
  • DoD: ≥10 компаний активны, NPS ≥ 40

[ ] **Pilot Metrics & Feedback**
  • Собрать метрики: DAU, WAU, feature usage
  • Провести 1-on-1 интервью с 5 key users
  • Зафиксировать top-3 pain points
  • Подготовить отчёт с рекомендациями
  • DoD: отчёт готов, roadmap обновлен

---

## Синхронизация с Makefile

- Проверка целей: `make smoke`, `make test-priority3`, `make test-priority4` – доступны.

- Карта проверок:
  - `make smoke` – базовые smoke по сервисам
  - `make test-priority3` – E2E пайплайн (ETL → Chroma → Web UI)
  - `make test-priority4` – Flowise pytest + gateway E2E + метрики

---

## 🔥 Критические Next Steps (Top Priority)

### 1. Deploy Network Changes (Stage 8 Completion)

```bash
# Stop services
docker compose down

# Remove legacy networks
docker network prune -f

# Start with new topology
docker compose up -d

# Verify
docker ps --format "table {{.Names}}\t{{.Networks}}"
docker network ls | grep zakupai
```

**DoD:** только 2 сети (zakupai-network + monitoring-net), все сервисы запущены

---

### 2. Goszakup → Database Pipeline (URGENT)

**Текущая проблема:** нет автоматической загрузки данных из Goszakup в БД

**План:**
1. Создать таблицу `goszakup_lots` в PostgreSQL
2. Настроить n8n workflow `daily-lot-scanner.json` для загрузки
3. Добавить endpoint `/etl/goszakup/sync` в etl-service
4. Проверить full pipeline: Goszakup API → n8n → DB → Risk Engine

**DoD:**
- Таблица `goszakup_lots` содержит > 100 лотов
- n8n workflow выполняется каждые 15 минут
- Метрики `goszakup_lots_total` доступны в Prometheus

---

### 3. Production Workflows Deployment

**Задача:** загрузить n8n/Flowise workflows в production instance

**Файлы:**
- `workflows/n8n/daily-lot-scanner.json`
- `workflows/n8n/lot-processing-pipeline.json`
- `workflows/n8n/price-monitor.json`
- `workflows/flowise/zakupai-assistant-chatflow.json`

**DoD:**
- Все 4 workflow импортированы и активны
- Flowise chatflow доступен через API
- Telegram bot команда `/ask` работает

---

### 4. Vault Stage 9 Migration

**Задача:** мигрировать Vault с file backend на Backblaze B2 (S3)

**План:**
1. Создать Backblaze B2 bucket `zakupai-vault-prod`
2. Обновить `monitoring/vault/config/secure/config-stage9.hcl`
3. Активировать `docker-compose.override.stage9.vault-prod.yml`
4. Протестировать backup/restore

**DoD:**
- Vault работает с B2 backend
- TLS включен
- Audit logs пишутся в файл

---

## 📊 Project Health Dashboard

| Metric                    | Current | Target | Status |
|---------------------------|---------|--------|--------|
| Services Running          | 15      | 21     | 🟡     |
| Docker Networks           | 2       | 2      | ✅     |
| Vault Integration         | 3/8     | 8/8    | 🟡     |
| Test Coverage             | ~60%    | 80%    | 🟡     |
| CI/CD Pipeline Time       | ~8 min  | <5 min | 🟡     |
| Production Ready Services | 5       | 21     | 🔴     |
| Documentation Coverage    | 70%     | 90%    | 🟡     |
| Security Score (Bandit)   | B+      | A      | 🟡     |

**Legend:** ✅ Complete | 🟡 In Progress | 🔴 Not Started

---

## 🎯 Current Sprint Focus (Sprint 7.5)

**Dates:** 2025-11-09 → 2025-11-23 (2 недели)

**Goals:**
1. ✅ Завершить Stage 8 (Network Consolidation) — DONE
2. 🟡 Запустить Goszakup → DB pipeline (Stage 9 prep)
3. 🟡 Загрузить production workflows (n8n + Flowise)
4. 🔴 Начать Vault Stage 9 migration (B2 backend)

**Blockers:**
- Нет Backblaze B2 credentials (нужно создать account)
- n8n workflows нужно протестировать перед production
- Goszakup API rate limits (нужно уточнить лимиты)

---

## 📚 Key Documentation

- 📄 [NETWORK_ARCHITECTURE_FINAL.md](docs/NETWORK_ARCHITECTURE_FINAL.md) — network topology
- 📄 [NETWORK_CLEANUP_SUMMARY.md](docs/NETWORK_CLEANUP_SUMMARY.md) — Stage 8 changes
- 📄 [VAULT_OPERATIONS.md](docs/VAULT_OPERATIONS.md) — Vault setup guide
- 📄 [VAULT_ADMIN_GUIDE.md](docs/VAULT_ADMIN_GUIDE.md) — admin tasks
- 📄 [VAULT_MIGRATION_STAGE7_TO_STAGE9.md](docs/VAULT_MIGRATION_STAGE7_TO_STAGE9.md) — upgrade path

---

**Last Updated:** 2025-11-09
**Next Review:** 2025-11-16
**Maintainer:** ZakupAI DevOps Team
