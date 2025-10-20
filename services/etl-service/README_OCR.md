# OCR Loader для ETL Service

Модуль для обработки вложений (PDF/ZIP) с извлечением текста и сохранением в PostgreSQL + ChromaDB.

## 🚀 Возможности

- **OCR обработка**: Извлечение текста из PDF с OCR для сканированных документов
- **ZIP поддержка**: Обработка архивов с PDF файлами
- **Параллельная обработка**: ThreadPoolExecutor для быстрой обработки больших объемов
- **ChromaDB интеграция**: Семантический поиск по содержимому документов
- **RNU проверка**: Автоматические флаги риска для поставщиков
- **Pre-commit совместимость**: Код соответствует стандартам проекта

## 📁 Файлы

- `ocr_loader.py` - Основной модуль OCR загрузчика
- `attachments_migration.sql` - SQL миграция для таблицы attachments
- `test_ocr.py` - Утилита для создания тестовых PDF файлов
- `pdf/` - Папка с тестовыми файлами

## 🗄️ База данных

### Таблица attachments

```sql
CREATE TABLE attachments (
    id BIGSERIAL PRIMARY KEY,
    lot_id BIGINT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(10) DEFAULT 'pdf',
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_lot_file UNIQUE (lot_id, file_name)
);

-- Индексы для быстрого поиска
CREATE INDEX idx_attachments_lot_id ON attachments (lot_id);
CREATE INDEX idx_attachments_content_fulltext
ON attachments USING gin(to_tsvector('russian', content));
```

### RNU флаги риска

Добавлено поле `risk_flag` в таблицы `trdbuy` и `contracts`:

- 🟢 **Надёжный** - поставщик не найден в RNU
- ⚠ **Недобросовестный** - поставщик есть в реестре RNU
- ❓ **Неизвестно** - ошибка при проверке

## 📦 Установка зависимостей

```bash
cd services/etl-service
pip install -r requirements.txt
```

Дополнительно потребуется установить Tesseract OCR:

```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr tesseract-ocr-rus

# macOS
brew install tesseract tesseract-lang

# Проверка установки
tesseract --version
```

## 🔧 Настройка

1. **Создать таблицу attachments**:

```bash
psql -h localhost -U zakupai -d zakupai -f attachments_migration.sql
```

2. **Настроить переменные окружения**:

```bash
export DATABASE_URL="postgresql://zakupai:zakupai@localhost:5432/zakupai"
export CHROMA_URL="http://localhost:8000"  # опционально
```

## 🚀 Использование

### Базовое использование

```bash
cd services/etl-service

# Создать тестовые PDF (из текстовых файлов)
python test_ocr.py

# Обработать PDF файлы с сохранением только в PostgreSQL
python ocr_loader.py --path ./pdf/ --db postgresql://zakupai:zakupai@localhost:5432/zakupai

# С поддержкой ChromaDB для семантического поиска
python ocr_loader.py --path ./pdf/ --db postgresql://zakupai:zakupai@localhost:5432/zakupai --embed http://localhost:8000

# Verbose режим для отладки
python ocr_loader.py --path ./pdf/ --db postgresql://zakupai:zakupai@localhost:5432/zakupai --verbose
```

### Пример вывода

```
2025-09-11 15:30:00 - INFO - Found 2 files to process
2025-09-11 15:30:01 - INFO - Processing 37971908.pdf for lot 37971908
2025-09-11 15:30:02 - INFO - Stored content for lot 37971908, file 37971908.pdf
2025-09-11 15:30:02 - INFO - Stored in ChromaDB: attachment_id 1
2025-09-11 15:30:03 - INFO - Processing 37971907.pdf for lot 37971907
2025-09-11 15:30:04 - INFO - Processing complete: 2 files processed, 2 stored, 0 skipped

Results: {'processed': 2, 'stored': 2, 'skipped': 0}
```

## 🔍 Проверка результатов

### PostgreSQL

```sql
-- Проверить загруженные вложения
SELECT lot_id, file_name, LEFT(content, 200) as content_preview, created_at
FROM attachments
ORDER BY created_at DESC
LIMIT 5;

-- Полнотекстовый поиск по содержимому
SELECT lot_id, file_name, ts_rank(to_tsvector('russian', content), query) as rank
FROM attachments, to_tsquery('russian', 'компьютер | канцелярские') query
WHERE to_tsvector('russian', content) @@ query
ORDER BY rank DESC;
```

### ChromaDB

```python
import chromadb

client = chromadb.HttpClient(host="localhost", port=8000)
collection = client.get_collection("attachments")

# Семантический поиск
results = collection.query(
    query_texts=["поставка компьютеров"],
    n_results=5
)
print(results)
```

## ⚡ Производительность

- **Параллельная обработка**: До 4 файлов одновременно
- **OCR оптимизация**: 2x zoom для лучшего распознавания сканов
- **Пакетные операции**: Bulk insert в PostgreSQL
- **Дубликаты**: ON CONFLICT DO NOTHING для lot_id + filename

## 🛠️ Интеграция с ETL

Модуль RNU проверки автоматически добавляет флаги риска:

```python
# В etl.py добавлена функция check_rnu_risk_flags()
trdbuy_data = self.check_rnu_risk_flags(trdbuy_data)
contracts_data = self.check_rnu_risk_flags(contracts_data)
```

## 🧪 Тестирование

```bash
# Создать тестовые PDF файлы
python test_ocr.py

# Запустить полный тест
python ocr_loader.py --path ./pdf/ --db postgresql://zakupai:zakupai@localhost:5432/zakupai --verbose

# Проверить логи
tail -f ocr_loader.log
```

## ⚠️ Требования системы

- **Python 3.8+**
- **PostgreSQL** с полнотекстовым поиском
- **Tesseract OCR** с русским языком
- **ChromaDB** (опционально) для семантического поиска
- **4GB+ RAM** для обработки больших PDF файлов

## 🔧 Настройка производительности

```python
# В ocr_loader.py можно изменить:
max_workers=4          # Количество параллельных потоков
matrix=fitz.Matrix(2, 2)  # Zoom для OCR (больше = лучше качество, медленнее)
lang='rus+eng'         # Языки для OCR
config='--psm 6'       # Режим сегментации Tesseract
```

## 📝 Логирование

Логи сохраняются в файл `ocr_loader.log`:

- **INFO**: Прогресс обработки, успешные операции
- **WARNING**: Пропущенные файлы, ошибки OCR
- **ERROR**: Критические ошибки БД, ChromaDB

## 🚀 Следующие шаги

1. **Запуск в production**: Увеличить max_workers и test_limit
1. **Мониторинг**: Добавить метрики в Prometheus
1. **Масштабирование**: Использовать очереди для больших объемов
1. **ML улучшения**: Обучить модель на специфических документах госзакупок
