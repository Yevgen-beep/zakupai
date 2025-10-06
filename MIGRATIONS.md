# Руководство по работе с миграциями Alembic

## Структура миграций

Каждый сервис имеет собственные миграции:

```
services/
├── billing-service/
│   ├── alembic.ini
│   ├── migrations/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   └── app/models.py
├── calc-service/
│   ├── alembic.ini
│   ├── migrations/
│   └── app/models.py
...
```

## Инициализация миграций

Для нового сервиса:

```bash
cd services/new-service
alembic init migrations
# Настройте alembic.ini и migrations/env.py
```

## Создание миграций

### Автогенерация

```bash
# Через Makefile (рекомендуется)
make mig-revision SERVICE=billing-service m="add user table"

# Напрямую
cd services/billing-service
alembic revision --autogenerate -m "add user table"
```

### Ручные миграции

```bash
make mig-revision SERVICE=billing-service m="custom data migration"
# Затем отредактируйте созданный файл миграции
```

## Применение миграций

### Staging/Dev

```bash
# Upgrade до head
make mig-upgrade SERVICE=billing-service

# Downgrade на одну версию
make mig-downgrade SERVICE=billing-service r="-1"

# Stamp текущую БД как head (baseline)
make mig-stamp SERVICE=billing-service
```

### Production (БЕЗОПАСНО)

**ВСЕГДА** используйте dry-run перед production:

```bash
# 1. Сначала сгенерируйте SQL
make mig-sql SERVICE=billing-service > migration.sql

# 2. Проверьте SQL вручную
cat migration.sql

# 3. Протестируйте на копии production данных

# 4. Только после проверки - применяйте на production
make mig-upgrade SERVICE=billing-service
```

## Baseline для существующих БД

Если БД уже содержит таблицы:

```bash
# 1. Создайте initial миграцию с пустым upgrade/downgrade
make mig-revision SERVICE=billing-service m="initial baseline"

# 2. Отметьте БД как содержащую эту миграцию
make mig-stamp SERVICE=billing-service
```

## Работа с merge conflicts

При конфликте миграций:

```bash
# 1. Найти heads
cd services/billing-service
alembic heads

# 2. Создать merge миграцию
alembic merge -m "merge migration conflict" <revision1> <revision2>
```

## Порядок применения миграций

### Staging:

1. Остановите сервисы
1. Создайте backup БД
1. Примените миграции
1. Запустите тесты
1. Запустите сервисы

### Production:

1. **Mandatory dry-run**: `make mig-sql SERVICE=...`
1. Создайте backup БД
1. Применяйте миграции в maintenance window
1. Мониторинг после применения

## Ревью миграций

Проверяйте в PR:

- [ ] Миграция не содержит DROP без backup
- [ ] Используется транзакционная миграция где возможно
- [ ] Есть rollback plan (downgrade)
- [ ] Добавлены индексы для новых колонок
- [ ] Нет блокирующих операций на больших таблицах
- [ ] SQL выглядит корректно в dry-run

## Troubleshooting

### "Target database is not up to date"

```bash
alembic stamp head  # Если БД в актуальном состоянии
```

### "Can't locate revision identifier"

```bash
alembic history  # Проверить историю
alembic current  # Текущая версия БД
```

### Rollback при ошибке

```bash
# Если миграция упала частично
make mig-downgrade SERVICE=billing-service r="-1"
# Исправить проблему и повторить upgrade
```

## CI/CD интеграция

GitHub Actions автоматически тестирует миграции при изменениях в:

- `services/*/migrations/**`
- `services/*/app/models.py`

Локально запуск migration runners:

```bash
# Stage6 stack с migration runners
docker compose -f docker-compose.yml -f docker-compose.override.stage6.yml --profile stage6 up migration-runner-billing

# Автоматический запуск миграций для всех сервисов Stage6
./stage6-migrations.sh
```

## Dockerfile.migration

Для выполнения миграций используется специальный образ `Dockerfile.migration`:

### Назначение:

- Обеспечивает наличие всех необходимых зависимостей для Alembic
- Единый образ для всех сервисов (избегаем дублирования)
- Изолированная среда для миграций

### Зависимости:

```dockerfile
alembic==1.13.1        # Основная библиотека миграций
sqlalchemy==2.0.25     # ORM для работы с БД
psycopg2-binary==2.9.9 # PostgreSQL драйвер
fastapi==0.104.1       # Для совместимости с моделями сервисов
pydantic==2.5.2        # Для валидации данных
```

### Принцип работы:

1. Образ собирается с общими зависимостями
1. Код конкретного сервиса монтируется через volume в `/app`
1. Alembic выполняется в контексте конкретного сервиса
1. DATABASE_URL берётся из переменных окружения с fallback

## Stage6 Automation Script

Для удобного управления миграциями всех сервисов создан скрипт `stage6-migrations.sh`:

### Возможности скрипта:

- Проверка текущего статуса миграций всех сервисов
- Dry-run с показом SQL (для предварительного просмотра)
- Безопасное применение миграций с подтверждением
- Финальная проверка статуса после применения

### Использование:

```bash
# Запуск автоматизированных миграций
./stage6-migrations.sh

# Скрипт выполнит 4 фазы:
# 1. Проверка текущего статуса
# 2. Dry-run (SQL preview)
# 3. Применение миграций (с подтверждением)
# 4. Финальная проверка
```

### Безопасность:

- Показывает SQL перед применением
- Требует подтверждения пользователя
- Завершается при ошибке (set -e)
- Проверяет финальный статус
