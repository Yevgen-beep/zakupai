[![CI](https://github.com/Yevgen-beep/zakupai/actions/workflows/ci.yml/badge.svg)](https://github.com/Yevgen-beep/zakupai/actions/workflows/ci.yml)

# ZakupAI

MVP-платформа для автоматизации госзакупок РК: поиск и разбор лотов, быстрые TL;DR, риск-скоринг, финкалькулятор (НДС/маржа/пени), генерация писем/жалоб, интеграции с n8n/Flowise и API сервисы на FastAPI.

## Development

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
