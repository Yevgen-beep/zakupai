# ZakupAI Documentation

Полная техническая документация платформы ZakupAI для автоматизации государственных закупок РК.

## 📋 Оглавление

### 🏗 Архитектура и компоненты

- **[architecture.md](architecture.md)** - Общая архитектура платформы, микросервисы, базы данных
- **[billing-service.md](billing-service.md)** - Сервис управления пользователями, API ключами и подписками

### 🔧 Интеграции и автоматизация

- **[telegram-bot-billing-integration.md](telegram-bot-billing-integration.md)** - Интеграция Telegram бота с Billing Service
- **[n8n-flowise-integration.md](n8n-flowise-integration.md)** - AI-автоматизация через n8n и Flowise

### 🚀 DevOps и эксплуатация

- **[deployment.md](deployment.md)** - Развертывание в dev/stage/prod окружениях
- **[devops-monitoring.md](devops-monitoring.md)** - Мониторинг, метрики, логирование, алерты

### 🔒 Безопасность

- **[security.md](security.md)** - Аутентификация, валидация, CORS, SAST, защита от атак

## 🚀 Быстрый старт

### Development

```bash
# Клонируем репозиторий
git clone https://github.com/your-org/zakupai.git
cd zakupai

# Запускаем dev окружение
make dev

# Проверяем работоспособность
make health-check
make smoke-all
```

### Production

```bash
# Настраиваем production конфигурацию
cp .env.prod .env

# Запускаем с мониторингом
make prod

# Проверяем деплоймент
make health-check
```

## 📊 Ключевые компоненты

| Компонент           | Порт  | Описание                              | Документация                                     |
| ------------------- | ----- | ------------------------------------- | ------------------------------------------------ |
| **API Gateway**     | :8080 | Nginx reverse proxy с rate limiting   | [architecture.md](architecture.md#api-gateway)   |
| **Billing Service** | :7004 | Управление пользователями и лимитами  | [billing-service.md](billing-service.md)         |
| **Calc Service**    | :7001 | Финансовые расчеты (НДС, маржа, пени) | [architecture.md](architecture.md#calc-service)  |
| **Risk Engine**     | :7002 | Риск-скоринг и анализ тендеров        | [architecture.md](architecture.md#risk-engine)   |
| **Doc Service**     | :7003 | TL;DR, генерация документов, PDF      | [architecture.md](architecture.md#doc-service)   |
| **Embedding API**   | :7010 | Векторизация и поиск документов       | [architecture.md](architecture.md#embedding-api) |

## 🤖 AI и автоматизация

| Инструмент       | URL                  | Назначение                           | Документация                                                                  |
| ---------------- | -------------------- | ------------------------------------ | ----------------------------------------------------------------------------- |
| **Telegram Bot** | @TenderFinderBot_bot | Основной интерфейс для пользователей | [telegram-bot-billing-integration.md](telegram-bot-billing-integration.md)    |
| **Flowise**      | :3000                | Визуальные AI-воркфлоу               | [n8n-flowise-integration.md](n8n-flowise-integration.md#flowise-custom-tools) |
| **n8n**          | :5678                | Автоматизация бизнес-процессов       | [n8n-flowise-integration.md](n8n-flowise-integration.md#n8n-custom-nodes)     |
| **Web UI**       | :8082                | Веб-интерфейс, загрузка прайсов      | [architecture.md](architecture.md#web-ui)                                     |

## 📈 Мониторинг и метрики

| Сервис           | URL   | Назначение              | Документация                                              |
| ---------------- | ----- | ----------------------- | --------------------------------------------------------- |
| **Prometheus**   | :9090 | Сбор метрик             | [devops-monitoring.md](devops-monitoring.md#prometheus)   |
| **Grafana**      | :3001 | Дашборды и визуализация | [devops-monitoring.md](devops-monitoring.md#grafana)      |
| **Alertmanager** | :9093 | Управление алертами     | [devops-monitoring.md](devops-monitoring.md#alertmanager) |

## 🔐 Безопасность

### Основные принципы

- **X-API-Key аутентификация** для всех API запросов
- **Billing Service валидация** с контролем лимитов Free/Premium
- **Rate limiting** на уровне Nginx Gateway
- **Input validation** через Pydantic модели
- **SAST сканирование** в CI/CD пайплайне

Подробнее: [security.md](security.md)

## 💰 Монетизация и тарифы

| План        | Запросов/день | Запросов/час | Стоимость    | Особенности                                     |
| ----------- | ------------- | ------------ | ------------ | ----------------------------------------------- |
| **Free**    | 100           | 20           | 0 ₸          | Базовый анализ тендеров                         |
| **Premium** | 5,000         | 500          | 10,000 ₸/мес | PDF экспорт, риск-скоринг, генерация документов |

Подробнее: [billing-service.md](billing-service.md#%D1%81%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D0%B0-%D0%BB%D0%B8%D0%BC%D0%B8%D1%82%D0%BE%D0%B2)

## 🌍 Окружения развертывания

### Development

- Local Docker развертывание
- Debug логирование
- Hot reload для разработки
- Моки внешних API

### Staging

- Production-like конфигурация
- Тестовые платежи
- Monitoring включен
- Автоматическое тестирование

### Production

- Managed database (RDS)
- SSL/TLS шифрование
- Полный мониторинг стек
- Автоматические бэкапы
- Kaspi + Stripe интеграция

Подробнее: [deployment.md](deployment.md#%D0%BE%D0%BA%D1%80%D1%83%D0%B6%D0%B5%D0%BD%D0%B8%D1%8F)

## 🛠 CI/CD Pipeline

### Automated Testing

```yaml
Test → SAST Scan → Build Images → Smoke Tests → Deploy
```

### Security Gates

- **Bandit** - SAST для Python кода
- **Safety** - проверка зависимостей на уязвимости
- **Semgrep** - дополнительный security анализ
- **Pre-commit hooks** - проверки перед коммитом

Подробнее: [deployment.md](deployment.md#cicd-pipeline)

## 📚 API Reference

### Основные эндпоинты

**Billing Service:**

```bash
POST /billing/create_key     # Создание API ключа
POST /billing/validate_key   # Валидация ключа и лимитов
POST /billing/usage          # Логирование использования
GET  /billing/stats/{tg_id}  # Статистика пользователя
```

**Calc Service:**

```bash
POST /calc/vat      # Расчет НДС
POST /calc/margin   # Анализ маржинальности
POST /calc/penalty  # Расчет пени и штрафов
```

**Risk Engine:**

```bash
POST /risk/score           # Риск-скоринг лота
GET  /risk/explain/{id}    # Объяснение рисков
```

**Doc Service:**

```bash
POST /tldr                 # Краткое описание лота
POST /letters/generate     # Генерация документов
POST /render/pdf          # PDF экспорт
```

## 🎯 Roadmap

### MVP (Completed) ✅

- Все основные сервисы реализованы
- Billing Service с Free/Premium планами
- Telegram bot интеграция
- Базовый мониторинг и бэкапы

### Production (In Progress) 🚧

- Kaspi API + Stripe интеграция
- Отдельный Billing сервер с изоляцией
- Advanced мониторинг и алерты
- Performance оптимизация

### Future Enhancements 🔮

- Machine Learning для предсказания выигрыша
- Blockchain интеграция для audit trail
- Mobile приложение
- White Label решения для партнеров

## 🤝 Contributing

### Структура проекта

```
zakupai/
├── services/           # Микросервисы
│   ├── billing-service/
│   ├── calc-service/
│   ├── risk-engine/
│   └── doc-service/
├── bot/               # Telegram bot
├── web/               # Web UI
├── docs/              # Документация
├── monitoring/        # Prometheus, Grafana
└── scripts/           # Утилиты развертывания
```

### Development процесс

1. Fork репозитория
1. Создайте feature branch
1. Следуйте code style (black, ruff, isort)
1. Добавьте тесты для новой функциональности
1. Убедитесь что проходят security проверки
1. Создайте Pull Request

## 📞 Поддержка

- **Technical Issues**: GitHub Issues
- **Security Issues**: security@zakupai.site
- **Business Inquiries**: hello@zakupai.site
- **Telegram Support**: @zakupai_support

______________________________________________________________________

**ZakupAI** - автоматизация государственных закупок с использованием ИИ
© 2024 ZakupAI Team. Документация обновлена: $(date +%Y-%m-%d)
