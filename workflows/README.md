# ZakupAI Workflows

Коллекция рабочих процессов для автоматизации операций ZakupAI.

## n8n Workflows

### 1. Lot Processing Pipeline (`lot-processing-pipeline.json`)

**Назначение**: Комплексная обработка лотов с анализом рисков и уведомлениями

**Триггер**: Webhook `zakupai-lot-process`

**Функции**:

- Получение данных лота из Goszakup API
- Расчет маржи через calc-service
- Оценка рисков через risk-engine
- Проверка на "горячий лот" (риск > 70% или маржа > 15%)
- Генерация TL;DR сводки
- Отправка уведомлений в Telegram при обнаружении горячих лотов
- Обновление статуса лота

**Настройка**:

```env
ZAKUPAI_API_KEY=your-api-key
TELEGRAM_HOT_LOTS_CHANNEL=@your_hot_lots_channel
```

### 2. Daily Lot Scanner (`daily-lot-scanner.json`)

**Назначение**: Ежедневное сканирование новых лотов

**Расписание**: 9:00, 14:00, 18:00 (Алматы)

**Функции**:

- Получение новых лотов за последние 24 часа
- Пакетная обработка лотов (по 5 штук)
- Агрегация результатов и статистики
- Отправка сводки администратору
- Автоматические уведомления о горячих лотах

**Настройка**:

```env
TELEGRAM_ADMIN_CHANNEL=@your_admin_channel
TELEGRAM_HOT_LOTS_CHANNEL=@your_hot_lots_channel
```

### 3. Price Monitor (`price-monitor.json`)

**Назначение**: Мониторинг цен и обновление данных

**Расписание**: 6:00, 12:00, 20:00 (Алматы)

**Функции**:

- Проверка актуальности источников цен
- Обновление устаревших данных (старше 6 часов)
- Пересчет маржи для затронутых лотов
- Отчет о состоянии ценовых источников

## Flowise Chatflow

### ZakupAI Assistant (`zakupai-assistant-chatflow.json`)

**Назначение**: Интеллектуальный ассистент для работы с закупками

**Возможности**:

- 🔍 **Lot Reader**: Поиск и анализ лотов по номеру/URL
- ⚠️ **Risk Explain**: Объяснение оценки рисков
- 💰 **Finance Calc**: Финансовые расчеты (маржа, НДС, штрафы)
- 📄 **Template Gen**: Генерация документов и писем

**Модель**: GPT-4 (temperature: 0.3)
**Память**: Buffer Memory для сохранения контекста диалога
**Язык**: Русский

**Пример диалога**:

```
Пользователь: Проанализируй лот 12345
Ассистент: *использует lot_reader* → *использует risk_explain* → *использует finance_calc* → комплексный анализ
```

## Установка и настройка

### n8n

1. Импортируйте JSON файлы через n8n UI
1. Настройте credentials:
   - `goszakup-credentials` - API ключи Goszakup
   - `telegram-bot-credentials` - токен Telegram бота
1. Создайте переменные среды в n8n
1. Активируйте workflow

### Flowise

1. Импортируйте chatflow через Flowise UI
1. Настройте OpenAI credential
1. Настройте ZakupAI API ключи для инструментов
1. Протестируйте интеграцию

## Переменные среды

```env
# ZakupAI API
ZAKUPAI_API_KEY=your-zakupai-api-key

# Telegram
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_HOT_LOTS_CHANNEL=@hot_lots_channel
TELEGRAM_ADMIN_CHANNEL=@admin_channel

# Goszakup API
GOSZAKUP_TOKEN=your-goszakup-token

# OpenAI (для Flowise)
OPENAI_API_KEY=your-openai-key
```

## Мониторинг

Все workflow включают:

- Обработку ошибок
- Логирование действий
- Уведомления об ошибках
- Метрики выполнения

## Развертывание

Workflow автоматически интегрируются с:

- Docker Compose окружением ZakupAI
- Сетью `zakupai_default`
- API Gateway на порту 8080
- PostgreSQL базой данных

Для продакшена рекомендуется:

- Настроить backup workflow
- Добавить monitoring alerting
- Использовать секреты вместо переменных среды
