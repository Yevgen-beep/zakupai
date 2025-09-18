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

## 🔧 Этап 1. Техническая база (1–2 мес.)

### API и коннекторы

- [ ] Разобрать API v2/v3 + GraphQL (Lots, TrdBuy, Contract, Rnu, Subjects)
- [ ] Сделать универсальный коннектор с динамическим выбором API
- [ ] Добавить обработку вложений (PDF + OCR + ChromaDB)
- [ ] Настроить хранилище (PostgreSQL + ChromaDB)

### Интеграции

- [ ] Интегрировать n8n (cron поиск + уведомления)
- [ ] Интегрировать Flowise (TL;DR шаблоны + проверка подстав)

______________________________________________________________________

## 📊 Этап 2. Аналитика и сервисы (2–3 мес.)

### Анализ и проверки

- [ ] Проверка поставщиков (Rnu + Subjects)
- [ ] Анализ рентабельности (API Alibaba/1688 + ROI расчёт)
- [ ] Анализ рисков (подставные лоты + рейтинг)

### Автоматизация

- [ ] Автогенерация документов (заявки, жалобы, гарантийные письма)
- [ ] Мониторинг конкурентов (история + демпинг)

______________________________________________________________________

## 🖥️ Этап 3. Интерфейсы и интеграции (1–2 мес.)

### Интерфейсы

- [ ] Улучшенные уведомления (Telegram-бот + email + веб-дашборд)
- [ ] Персонализированные алерты (ROI > 20% + риск подстав + фильтры)

### Внешние интеграции

- [ ] Интеграции (Alibaba/1688 + юридические шаблоны + проверка долгов)

Sprint 4 - Master Checklist (Hybrid, Final)

# ========================= Week 1 - Quick Wins

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

# ========================= Week 2 - Фичи ядра

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

# ========================= Week 3 - Расширения

\[ \] Доработка RNU-валидации
\[ \] добавить TTL кеша (24ч) для результатов
\[ \] расширить проверку статусов участников
\[ \] интегрировать уведомления о блокировках
DoD: уведомления приходят не позже 5 мин после обновления статуса

\[ \] Улучшение поиска
\[ \] оптимизировать SQL-запросы под большие выборки
\[ \] добавить сортировку по сумме и дате
\[ \] покрыть интеграционными тестами /api/search/advanced
DoD: поиск по 100k лотам ≤2 сек, сортировка работает корректно

\[ \] Flowise агенты (MVP)
\[ \] complaint-generator: генерация жалобы по лоту (текстовый вывод)
\[ \] supplier-finder: поиск поставщиков (через Satu.kz/ChromaDB)
DoD: complaint-generator выдает валидный текст с номером лота, причиной и датой; supplier-finder получает данные в формате, совместимом с ChromaDB

# ========================= Week 4 - UI + Тесты

\[ \] Web UI доработки
\[ \] импорт прайсов CSV
\[ \] TL;DR анализа лота на странице /lot/{id}
\[ \] реализовать автодополнение в поиске
DoD: импорт работает для файлов ≤5 MB, TL;DR отображается \<1 сек

\[ \] Flowise агенты (финализация)
\[ \] complaint-generator: улучшить формат жалобы (PDF/Word)
\[ \] supplier-finder: фильтры по региону и бюджету
DoD: PDF открывается без ошибок, фильтры дают корректный список

\[ \] E2E тестирование
\[ \] pytest сценарии для batch upload + RNU + advanced search
\[ \] bash smoke-тесты для новых эндпоинтов
\[ \] интеграция в CI/CD (priority4-integration job)
DoD: критические сценарии (импорт CSV, валидация RNU) покрыты тестами, CI проходит без ошибок

\[ \] Performance & Monitoring
\[ \] нагрузочное тестирование новых фич (Locust/JMeter)
\[ \] алерты в Grafana для batch upload и поиска
\[ \] мониторинг latency, error rate, CPU usage
DoD: нагрузочный тест выдерживает ≥1000 запросов/мин, алерты срабатывают в Grafana

### Финализация

- [ ] Финальные тесты и безопасность (нагрузочные тесты + rate limits)
- [ ] Запуск пилота с фокус-группой (10-20 компаний)
