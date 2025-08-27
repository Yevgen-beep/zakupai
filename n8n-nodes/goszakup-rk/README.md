# goszakup-rk

n8n нода для интеграции с API госзакупок Казахстана (goszakup.gov.kz).

## Функциональность

### Ресурсы

- **Lots** - лоты/тендеры
- **Tenders** - тендеры
- **Plans** - планы закупок
- **Subjects** - субъекты закупок

### Операции

#### Lots (лоты)

- `Get All` - получить все лоты
- `Get by ID` - получить лот по ID
- `Search` - поиск лотов

#### Tenders (тендеры)

- `Get All` - получить все тендеры
- `Get by ID` - получить тендер по ID
- `Search` - поиск тендеров

#### Plans (планы)

- `Get All` - получить все планы
- `Get by ID` - получить план по ID

#### Subjects (субъекты)

- `Get All` - получить всех субъектов
- `Get by BIN` - получить субъекта по БИН

### Фильтры

- Диапазон дат (dateFrom/dateTo)
- Статус (published, active, completed, cancelled)
- Пагинация (limit/returnAll)
- Поисковые запросы

### Аутентификация

Нода использует API токен для доступа к Goszakup API.

## Установка

1. Скопировать папку в директорию пользовательских нод n8n
1. Установить зависимости: `npm install`
1. Собрать проект: `npm run build`
1. Перезапустить n8n

## Настройка

1. Создать учетные данные "Goszakup API"
1. Указать API Token и Base URL
1. Использовать ноду в workflow

## Пример использования

```json
// Получить активные лоты
{
  "resource": "lots",
  "operation": "getAll",
  "additionalFields": {
    "status": "active",
    "dateFrom": "2024-01-01"
  },
  "limit": 10
}

// Поиск тендеров по строительству
{
  "resource": "tenders",
  "operation": "search",
  "query": "строительство",
  "additionalFields": {
    "status": "published"
  }
}
```

## API Endpoints

- `/v3/lots` - лоты
- `/v3/tenders` - тендеры
- `/v3/plans` - планы закупок
- `/v3/subjects` - субъекты закупок

## Интеграция с Zakupai

Эта нода является частью проекта Zakupai и интегрируется с:

- calc-service (расчет финансовых показателей)
- risk-engine (оценка рисков)
- doc-service (генерация документов)
- embedding-api (поиск и индексация)
