# ETL Service CI Integration

Добавлен автоматический smoke test для ETL Service в GitHub Actions pipeline.

## 🚀 Что тестируется

### `etl-smoke-test` job:

1. **📄 Создание тестовых PDF файлов**

   - Генерация mock PDF из текстовых данных
   - Fallback механизм без тяжелых зависимостей

1. **🗄️ Применение PostgreSQL миграций**

   - Создание таблицы `attachments`
   - Полнотекстовые индексы для русского языка
   - Foreign key constraints

1. **🔍 OCR Loader обработка**

   - Извлечение текста из PDF файлов
   - Сохранение в PostgreSQL
   - Проверка дубликатов

1. **📊 Верификация данных**

   - SQL запросы для проверки содержимого
   - Полнотекстовый поиск на русском языке
   - Подсчет обработанных записей

## ⚙️ Технические особенности

- **Минимальные зависимости**: Только `psycopg2-binary` и `python-dotenv`
- **Fallback стратегия**: `ocr_loader_simple.py` для CI без PyMuPDF/ChromaDB
- **Логирование**: Все логи сохраняются как артефакты GitHub Actions
- **Таймауты**: 60 секунд на ожидание PostgreSQL
- **Кэширование**: pip cache для ускорения сборки

## 📋 Workflow интеграция

```yaml
etl-smoke-test:
  runs-on: ubuntu-latest
  needs: migrate
  steps:
    - Checkout кода
    - Установка Python 3.11
    - Старт PostgreSQL через docker compose
    - Установка минимальных зависимостей
    - Запуск ./services/etl-service/smoke_test.sh
    - Загрузка логов как артефакты
```

## 🎯 Результат

При успешном прохождении теста:

- ✅ Создано 2 mock PDF файла (37971907.pdf, 37971908.pdf)
- ✅ Применена миграция с индексами
- ✅ Обработано и сохранено 2 записи в `attachments`
- ✅ Работает полнотекстовый поиск по содержимому
- 🎉 **"Smoke test finished successfully!"**

Тест также добавлен в матрицу `build` для компиляции Docker контейнера `etl-service`.
