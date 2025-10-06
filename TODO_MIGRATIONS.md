# TODO: Интеграция Alembic миграций

## ✅ Выполнено

- [x] Docker: migration-runner-\* сервисы в docker-compose.override.stage6.yml
- [x] Makefile: цели mig-\* с защитой от пустого SERVICE
- [x] GitHub Actions: workflow для тестирования миграций
- [x] Документация: MIGRATIONS.md с полным гайдом
- [x] README.md: раздел "Работа с миграциями" с примерами

## 📋 Инвентаризация существующих миграций

- [ ] **billing-service**: проверить наличие alembic.ini и migrations/
- [ ] **calc-service**: проверить наличие alembic.ini и migrations/
- [ ] **doc-service**: проверить наличие alembic.ini и migrations/
- [ ] **embedding-api**: проверить наличие alembic.ini и migrations/
- [ ] **etl-service**: проверить наличие alembic.ini и migrations/
- [ ] **risk-engine**: проверить наличие alembic.ini и migrations/

## 🏗️ Инициализация недостающих миграций

- [ ] Создать alembic init для сервисов без миграций
- [ ] Настроить database URL в alembic.ini для каждого сервиса
- [ ] Настроить migrations/env.py для подключения к моделям

## 📏 Naming Conventions

- [ ] Установить единые соглашения по именованию миграций:
  - `YYYY_MM_DD_HHMM_descriptive_name.py`
  - Использовать автогенерацию: `alembic revision --autogenerate -m "описание"`
- [ ] Документировать в MIGRATIONS.md правила именования

## 🎯 Baseline для существующих БД

- [ ] Создать baseline миграции для существующих production таблиц
- [ ] Stamp existing databases как содержащие baseline ревизии
- [ ] Задокументировать процедуру baseline в MIGRATIONS.md

## 🔄 CI/CD интеграция

- [x] GitHub Actions workflow для тестирования миграций
- [ ] Добавить migration runners в production deployment pipeline
- [ ] Настроить уведомления при неудачных миграциях в CI
- [ ] Добавить проверку совместимости миграций (нет конфликтующих heads)

## 🚀 Production deployment

- [ ] Создать процедуру для применения миграций в production:
  - [ ] Pre-flight checks (backup, dry-run)
  - [ ] Maintenance mode
  - [ ] Migration execution
  - [ ] Rollback procedure
  - [ ] Health checks
- [ ] Настроить автоматические backups перед миграциями
- [ ] Документировать emergency rollback процедуру

## 🔍 Ревью процесс

- [ ] Установить код-ревью для всех миграций:
  - [ ] Проверка на блокирующие операции
  - [ ] Проверка наличия индексов
  - [ ] Проверка rollback-возможности
  - [ ] Проверка на data loss риски
- [ ] Создать checklist для ревьюверов миграций
- [ ] Добавить pre-commit hooks для валидации миграций

## 📊 Мониторинг и логирование

- [ ] Настроить логирование выполнения миграций
- [ ] Добавить метрики времени выполнения миграций
- [ ] Настроить алерты при неудачных миграциях
- [ ] Создать дашборд для мониторинга состояния миграций

## 🛠️ Инструменты и автоматизация

- [ ] Создать скрипт для batch применения миграций ко всем сервисам
- [ ] Добавить команду `make mig-status` для проверки состояния всех сервисов
- [ ] Создать скрипт для автоматической генерации миграций при изменении models.py
- [ ] Добавить integration tests для миграций

## 📝 Документация

- [x] Основной гайд MIGRATIONS.md
- [x] Раздел в README.md
- [ ] Troubleshooting guide для распространенных проблем
- [ ] Video tutorial для команды по работе с миграциями
- [ ] Документация по emergency procedures

## ⚡ Оптимизация

- [ ] Проанализировать производительность больших миграций
- [ ] Настроить параллельное выполнение миграций (где возможно)
- [ ] Оптимизировать размер Docker образов с migration runners
- [ ] Настроить кеширование зависимостей для CI pipeline

## 🔒 Безопасность

- [ ] Проверить права доступа для migration runners
- [ ] Настроить encrypted storage для sensitive миграций
- [ ] Добавить audit log для всех migration операций
- [ ] Проверить что нет credential leakage в migration logs
