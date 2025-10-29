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
\[x\] Telegram: уведомления «горячие лоты» (cron)
\[x\] Веб-панель: страница лота + форма аплоада прайсов (CSV/XLSX)

5. Безопасность и доступ

\[x\] Единый X-API-Key (+ /info)
\[x\] Rate limits на внешних эндпоинтах (nginx gateway → 429)
\[x\] Аудит-логи вызовов
\[x\] CORS/CSRF политика для веб-панели
\[x\] SAST: Bandit в pre-commit/CI
\[x\] Валидация и санитизация всех входных данных (FastAPI deps) для защиты от инъекций

6. DevOps / эксплуатация1

\[x\] Smoke для calc/risk/doc/emb (скрипт + Makefile)
\[x\] Включить smoke-матрицу в CI по всем сервисам
\[x\] Envs: .env.dev, .env.stage, .env.prod
\[x\] Бэкапы БД (pg_dump + rclone в облако)
\[x\] Prometheus + Grafana, алерты
\[x\] Docker-теги релизов, compose pull && up -d

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

11. Telegram Bot — тестирование команд (см. test-plan.md)

\[x\] Базовые команды: /start, /help, /key
\[x\] Основные команды: /lot, /search
\[x\] Интеграция с Billing Service
\[x\] Полный сценарий пользователя (регистрация → поиск → анализ)
\[x\] Тестирование webhook и polling режимов
\[x\] Валидация rate limiting и error handling

______________________________________________________________________

# ROADMAP: Платформа ZakupAI (Goszakup v2/v3 + AI)

> Этапы 1–3 заархивированы (перенесены в Confluence 2024-06). Фокус на Sprint 4.

Sprint 4 - Master Checklist (Hybrid, Final)

# ========================= Stage 4 - Week 1: Quick Wins

\[x\] Очистка Docker-мусора
\[x\] docker system df (оценить занимаемое место перед очисткой)
\[x\] docker image prune -a -f
\[x\] docker builder prune -a -f
\[x\] docker system prune -f --volumes
DoD: свободно ≥5GB, билд занимает меньше времени

\[x\] Удаление дубликатов кода
\[x\] убрать handlers_v2.py, commands_v2.py
\[x\] удалить old_main.py и backup\_\* файлы
\[x\] завести shared/ для общего кода (DB, логгинг, middleware)
DoD: unit + интеграционные тесты проходят успешно

\[x\] CI/CD оптимизация
\[x\] matrix build в .github/workflows/ci.yml
\[x\] кеширование pip зависимостей
\[x\] кеширование apt пакетов (tesseract, jq)
\[x\] добавить Docker layer caching
DoD: время CI сократилось минимум на 30%

# ========================= Stage 4 - Week 2: Фичи ядра

\[x\] ETL Batch Upload
\[x\] добавить эндпоинт /etl/upload-batch для CSV/XLSX
\[x\] реализовать обработку (сначала синхронно, очередь позже)
\[x\] интегрировать с n8n workflow
\[x\] добавить логирование ошибок парсинга CSV/XLSX
DoD: CSV ≤10 MB обрабатывается \<5 сек, ошибок ≤1%

\[x\] RNU-валидация участников
\[x\] реализовать метод /validate_rnu в risk-engine
\[x\] добавить кеширование результатов (PostgreSQL/Redis, TTL=24ч)
\[x\] интегрировать команду /rnu \<БИН> в Telegram боте
\[x\] предусмотреть fallback: если кеш пуст → прямой запрос в API
DoD: ответ при кэше ≤500 мс, успешная валидация ≥95% случаев

\[x\] Расширенный поиск
\[x\] добавить фильтры по суммам (min_amount, max_amount)
\[x\] добавить фильтры по статусам лотов
\[x\] реализовать автодополнение в Web UI (autocomplete.js)
\[x\] протестировать автодополнение на реальных кириллических данных
DoD: время поиска сокращено на ≥2 сек, автодополнение работает при вводе ≥2 символов

# ========================= Stage 4 - Week 3: Расширения

\[x\] Доработка RNU-валидации
\[x\] добавить TTL кеша (24ч) для результатов
\[x\] расширить проверку статусов участников
\[x\] интегрировать уведомления о блокировках
DoD: уведомления приходят не позже 5 мин после обновления статуса

\[x\] Улучшение поиска
\[x\] оптимизировать SQL-запросы под большие выборки
\[x\] добавить сортировку по сумме и дате
\[x\] покрыть интеграционными тестами /api/search/advanced
DoD: поиск по 100k лотам ≤2 сек, сортировка работает корректно

\[x\] Flowise агенты (MVP)
\[x\] complaint-generator: генерация жалобы по лоту (текстовый вывод)
\[x\] supplier-finder: поиск поставщиков (через Satu.kz/ChromaDB)
DoD: complaint-generator выдает валидный текст с номером лота, причиной и датой; supplier-finder получает данные в формате, совместимом с ChromaDB

# ========================= Stage 4 - Week 4: UI, Flowise, E2E, Monitoring

\[x\] Web UI доработки
\[x\] импорт прайсов CSV
\[x\] TL;DR анализа лота на странице /lot/{id}
\[x\] реализовать автодополнение в поиске
DoD: make smoke + make test-priority3 зелёные; импорт файлов ≤5 MB и TL;DR отображается \<1 сек

\[x\] Flowise агенты (финализация)
\[x\] complaint-generator: улучшить формат жалобы (PDF/Word)
\[x\] supplier-finder: фильтры по региону и бюджету
DoD: pytest tests/test_flowise_week4_2.py зелёный; PDF/Word открываются без ошибок, фильтры возвращают корректный список

\[x\] E2E тестирование
\[x\] pytest сценарии для batch upload + RNU + advanced search
\[x\] bash smoke-тесты для новых эндпоинтов
\[x\] интеграция в CI/CD (priority4-integration job)
DoD: make test-priority4 завершает pytest + scripts/e2e/run_tests.py без ошибок; критические сценарии (CSV импорт, RNU) покрыты

\[x\] Performance & Monitoring
\[x\] нагрузочное тестирование новых фич (Locust/JMeter)
\[x\] алерты в Grafana для batch upload и поиска
\[x\] мониторинг latency, error rate, CPU usage
DoD: make test-priority4 (pytest + scripts/e2e/run_tests.py + python test_metrics.py) зелёный; нагрузка ≥1000 req/min и алерты активны в Grafana

Финализированный план Stage6
Stage6 Monitoring & Security:
Prometheus
\[x\] Добавить scrape targets для всех сервисов (calc, risk, doc, embedding, gateway, etl)
\[ \] Подключить бизнес-метрики во все FastAPI-сервисы
— anti-dumping %
— goszakup error counter

Loki

\[x\] Включить promtail для сбора docker-логов
\[ \] Добавить расширенные метки: service, procurement_type, compliance_flag

Grafana

\[x\] Подключить Prometheus и Loki как datasources через provisioning
\[ \] Импортировать дашборды:
— API latency
— HTTP 5xx errors
— Compliance events
\[ \] Пересмотреть zakupai-overview.json: оставить как сводный или архивировать после появления специализированных панелей

Alertmanager

\[x\] Активировать alerts.yml в Prometheus
\[x\] Добавить правила «>5 API ошибок подряд» и «антидемпинг >15 %»
\[x\] Настроить реальный webhook (Telegram/Slack вместо временного gateway:8000/alert)

Vault

\[x\] Поднять контейнер Vault
\[x\] Перенести секреты (DB, API) из ENV → Vault
\[x\] Подключить hvac в calc, etl, risk-engine для чтения секретов


Скрипты

\[x\] Новый stage6-monitoring-test.sh — основной раннер


# ========================= Stage 7 — Security & Audit

🎯 Цель: завершить формирование безопасной и наблюдаемой платформы ZakupAI.  
Фокус: безопасность, валидация данных, Vault, mTLS, аудит, централизованное логирование.

---

## Stage 7 — Input Validation / Rate Limit / Docs

[x] Добавить Pydantic-валидацию входных данных для всех API (max_length, ranges)  
[x] Реализовать ограничение размера payload (413 Payload Too Large)  
[x] Внедрить rate-limiter (по API-ключу / IP / user_id)  
[x] Добавить централизованную обработку ошибок (422, 413, 401)  
[x] Сгенерировать OpenAPI / Swagger и загрузить в Docs-портал  
[x] Обновить тесты для валидации (ожидание 422 / 413)  
[x] Обновить CI-workflows для smoke-тестов Docs  
[ ] Fix gateway external port mapping and add /health endpoint
    - Ensure "8080:80" in docker-compose.yml
    - Add Nginx health location:
        location /health {
            return 200 '{"status":"ok"}';
            add_header Content-Type application/json;
        }
[x]Stage 7 Phase 1 — Security Quick Wins (completed)
---

## Stage 7 — Monitoring + Vault + Secrets

[x] Поднять контейнер Vault (`hashicorp/vault:1.17`)  
 • Конфиг → `monitoring/vault/config.hcl`, порт 8200  
 • Сгенерировать root-token и CA  

[ ] Интегрировать `hvac` в calc-service, etl-service, risk-engine  
 • Чтение DB credentials и API keys из Vault при старте  
 • Исключить `.env` из Docker build  
 • DoD: сервисы стартуют без . env, читают секреты из Vault  

[ ] Перенести конфиденциальные переменные (DB URI, API keys, Telegram tokens)  
[ ] Настроить Alertmanager webhook (реальный Telegram / Slack)  
[ ] Business metrics (anti-dumping %, goszakup errors)


---

## Stage 7 — mTLS между сервисами

[ ] Сгенерировать внутренний CA и клиентские сертификаты  
[ ] Настроить Nginx reverse proxy с mutual TLS (ssl_verify_client on)  
[ ] Обновить healthcheck на GET /health (с TLS)  
[ ] Проверить: `curl --cert client.pem --key client.key` → 200, без сертификата → 403  

---

## Stage 7 — Audit + Logging + Testing

[ ] Создать `shared/audit.py` — класс `AuditLogger.log_access(user_id, resource, action)`  
[ ] Интегрировать во все FastAPI-сервисы  
[ ] Настроить log retention в Loki (3 года, сжатие после 180 дней)  
[ ] Прогнать нагрузочные тесты (Locust ≥ 1000 req/min, P95 < 500 ms)  
[ ] Выполнить `make security-scan` → bandit + snyk + dependency-check (0 critical)

### 📊 Stage 7 — Summary
DoD:
- Все сервисы защищены rate-limiter’ом
- Vault интегрирован во все FastAPI-сервисы
- mTLS включён между gateway и risk-engine
- AuditLogger ведёт централизованные логи (retention = 3 года)
- Security scan проходит без high-severity уязвимостей

---

## 🧾 Документация и CI

[ ] Добавить `STAGE7_SECURITY_AUDIT_PLAN.md` в репозиторий  
[ ] Обновить `.github/workflows/ci-optimized.yml` для тестов валидации и security scan  
[ ] Подготовить README раздел «Безопасность и мониторинг»  
[ ] DoD: CI зелёный, security-scan 0 critical, все тесты пройдены.


### Финализация

- [ ] Финальные тесты и безопасность (нагрузочные тесты + rate limits)
  DoD: make test-priority4 + security scan (bandit/snyk) зелёные; нагрузочные тесты ≥1000 req/min без деградации

## Синхронизация с Makefile

- Проверка целей: `make smoke`, `make test-priority3`, `make test-priority4` – доступны.

- Карта проверок:

  - `make smoke` – базовые smoke по сервисам
  - `make test-priority3` – E2E пайплайн (ETL → Chroma → Web UI)
  - `make test-priority4` – Flowise pytest + gateway E2E + метрики

- [ ] Запуск пилота с фокус-группой (10-20 компаний)
  DoD: подписаны договоры с ≥10 компаниями, собраны отзывы, подготовлен отчёт по метрикам пилота
