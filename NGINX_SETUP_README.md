# Настройка Nginx Gateway для веб-приложения ZakupAI

## Что было изменено

### 1. Конфигурация nginx.conf

- Добавлены upstream `etl` и `web` для ETL-сервиса и веб-приложения
- Настроено проксирование для `/static/`, `/api/` и всех остальных маршрутов к веб-сервису
- Добавлено кэширование статических файлов с proxy_cache
- Настроено gzip сжатие для оптимизации
- Добавлены rate limits для веб-запросов (120 req/min)
- Настроены правильные заголовки (Host, X-Real-IP, X-Forwarded-For, etc.)
- Добавлена обработка ошибок с fallback механизмами

### 2. Docker Compose

- Добавлены зависимости gateway от web и etl-service
- Исправлена циклическая зависимость (web теперь зависит от сервисов, но не от gateway)

## Команды для применения

```bash
# 1. Остановить текущие контейнеры
docker compose down

# 2. Пересобрать и запустить с новой конфигурацией
docker compose up -d --build

# 3. Проверить статус всех сервисов
docker compose ps

# 4. Проверить логи gateway
docker compose logs gateway

# 5. Проверить работу веб-приложения
curl -I http://localhost:8080/
curl -I http://localhost:8080/attachments
```

## Тестирование

После запуска следующие URL должны работать:

- http://localhost:8080/ - главная страница
- http://localhost:8080/attachments - страница OCR документов
- http://localhost:8080/upload - страница загрузки прайсов
- http://localhost:8080/lot/{id} - страница анализа лота
- http://localhost:8080/api/\* - API запросы веб-приложения
- http://localhost:8080/static/\* - статические файлы (CSS, JS)

Сервисы API:

- http://localhost:8080/calc/health
- http://localhost:8080/risk/health
- http://localhost:8080/doc/health
- http://localhost:8080/emb/health
- http://localhost:8080/etl/health

## Оптимизация и особенности

### Кэширование

- Статические файлы кэшируются на 1 час
- HTML страницы не кэшируются (динамический контент)
- Используется proxy_cache с автоматической очисткой

### Сжатие

- Gzip сжатие для text/css, application/json, text/javascript
- Минимальный размер для сжатия: 1KB
- Уровень сжатия: 6 (оптимальный баланс CPU/размер)

### Rate Limiting

- API сервисы: 60 запросов/минута
- Веб-приложение: 120 запросов/минута
- Burst режим для обработки пиковых нагрузок

### Обработка ошибок

- 404 ошибки перенаправляются к веб-приложению (SPA поддержка)
- 502/503/504 показывают страницу обслуживания
- Автоматический failover с proxy_cache_use_stale

## Альтернативные подходы

### 1. Разделение по поддоменам

```nginx
server_name api.zakupai.local;  # для API
server_name app.zakupai.local;  # для веб-приложения
```

### 2. Балансировка нагрузки

```nginx
upstream web {
    server zakupai-web-1:8000;
    server zakupai-web-2:8000;
    # least_conn; или ip_hash; для sticky sessions
}
```

### 3. SSL терминация

```nginx
listen 443 ssl http2;
ssl_certificate /etc/ssl/certs/zakupai.crt;
ssl_certificate_key /etc/ssl/private/zakupai.key;
```

## Мониторинг

```bash
# Проверить статус кэша
curl -I http://localhost:8080/static/style.css | grep X-Cache-Status

# Проверить сжатие
curl -H "Accept-Encoding: gzip" -I http://localhost:8080/ | grep Content-Encoding

# Мониторинг логов в реальном времени
docker compose logs -f gateway
```

## Troubleshooting

### Если страница не открывается:

1. Проверить, что web контейнер запущен: `docker compose ps web`
1. Проверить логи web сервиса: `docker compose logs web`
1. Проверить доступность: `curl http://localhost:8082/` (прямое подключение)

### Если статические файлы не загружаются:

1. Проверить nginx логи: `docker compose logs gateway`
1. Проверить кэш: удалить `/tmp/nginx_cache` в gateway контейнере
1. Проверить права доступа к статическим файлам

### Если API недоступно:

1. Проверить, что все сервисы запущены
1. Проверить rate limits в логах nginx
1. Тестировать прямое подключение к сервисам на их портах
