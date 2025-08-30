[![CI](https://github.com/Yevgen-beep/zakupai/actions/workflows/ci.yml/badge.svg)](https://github.com/Yevgen-beep/zakupai/actions/workflows/ci.yml)

# ZakupAI

MVP-платформа для автоматизации госзакупок РК: поиск и разбор лотов, быстрые TL;DR, риск-скоринг, финкалькулятор (НДС/маржа/пени), генерация писем/жалоб, интеграции с n8n/Flowise и API сервисы на FastAPI.

## Development

### Environment Configuration

Проект поддерживает три окружения с соответствующими конфигурациями:

#### Development (`dev`)

```bash
# Запуск development окружения
cp .env.dev .env
docker-compose -f docker-compose.yml -f docker-compose.override.dev.yml --profile dev up -d

# Доступные сервисы:
# - Gateway: http://localhost:8080
# - Web Panel: http://localhost:8081
# - Adminer (DB GUI): http://localhost:8082
# - Direct service ports: 7001-7003, 7010
```

**Особенности dev:**

- Открытый CORS для localhost
- CSRF отключен
- Подробные логи (debug)
- Swagger UI включен
- Прямой доступ к портам сервисов
- Adminer для работы с БД

#### Staging (`stage`)

```bash
# Запуск staging окружения
cp .env.stage .env
docker-compose -f docker-compose.yml -f docker-compose.override.stage.yml --profile stage up -d

# Мониторинг:
# - Prometheus: http://localhost:9090
```

**Особенности stage:**

- CORS только для stage доменов
- CSRF включен
- Умеренные rate limits
- Swagger UI включен для тестирования
- Prometheus мониторинг
- Audit logging включен

#### Production (`prod`)

```bash
# Запуск production окружения
cp .env.prod .env
docker-compose -f docker-compose.yml -f docker-compose.override.prod.yml --profile prod up -d
```

**Особенности prod:**

- Строгий CORS только для production доменов
- CSRF включен с secure cookies
- Жесткие rate limits (60 req/min)
- Swagger UI отключен
- Полные security headers (CSP, HSTS, etc.)
- Resource limits для контейнеров
- Grafana + Prometheus стек
- SSL/TLS настройки

#### Переменные окружения

- **CORS_ORIGINS**: Разрешенные origin'ы для CORS
- **CSRF_ENABLED**: Включение CSRF защиты
- **SECURE_COOKIES**: Использование secure флага для cookies
- **RATE_LIMIT_RPM**: Лимит запросов в минуту
- **ENABLE_SWAGGER**: Включение Swagger UI

### Pre-commit Hooks

Проект использует pre-commit хуки для проверки кода перед коммитами:

```bash
# Установка pre-commit и зависимостей
pip install pre-commit ruff black isort yamllint mdformat mdformat-gfm bandit

# Установка хуков
pre-commit install

# Запуск проверок на всех файлах
pre-commit run --all-files
```

Хуки включают:

- Форматирование Python кода (ruff, black, isort)
- Проверка YAML файлов (yamllint)
- Форматирование Markdown (mdformat)
- Базовые проверки (trailing whitespace, large files)
- Security checks for Python code (bandit)
