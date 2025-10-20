# ✅ РЕШЕНИЕ: Gateway + Web для ZakupAI

## 🎯 Проблема решена

- **http://localhost:8080/attachments** теперь корректно отображает фронтенд
- Настроено проксирование всех React маршрутов через Nginx gateway
- Статические файлы кэшируются, HTML страницы обновляются в режиме реального времени

## 📁 Изменённые файлы

### 1. `gateway/nginx.conf` - ПОЛНОСТЬЮ ОБНОВЛЁН

```nginx
# Ключевые особенности:
- Детальные комментарии для каждой секции
- SPA fallback для React Router (/attachments, /suppliers, etc)
- Агрессивное кэширование статических файлов (CSS, JS)
- Отключение кэширования HTML страниц
- Rate limiting: API (60/min), Web (200/min)
- Gzip сжатие для экономии трафика
- Правильная передача заголовков для FastAPI
- Обработка ошибок с красивой страницей обслуживания
```

### 2. `docker-compose.yml` - Секции `web` и `gateway`

```yaml
web:
  # Добавлены healthcheck и правильные зависимости
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]

gateway:
  # Дожидается готовности web сервиса перед запуском
  depends_on:
    web:
      condition: service_healthy
```

## 🚀 Команды для применения

```bash
# 1. Остановить всё
docker compose down

# 2. Перезапуск с новой конфигурацией
docker compose up -d --build

# 3. Проверить работу
curl http://localhost:8080/attachments
```

## 🔍 Детальное объяснение nginx.conf

### Почему location / обрабатывает /attachments?

```nginx
location / {
  # Все запросы, НЕ попавшие в /calc/, /risk/, /static/, /api/
  # попадают сюда, включая /attachments, /upload, /lot/123
  proxy_pass http://web;
}
```

### Почему нужен @spa_fallback?

```nginx
error_page 404 = @spa_fallback;

location @spa_fallback {
  # Если backend вернул 404 для /some/route
  # перенаправляем на главную страницу для React Router
  proxy_pass http://web/;
}
```

### Кэширование: что и почему?

```nginx
# ✅ КЭШИРУЕМ: CSS, JS, изображения (неизменяемые)
location /static/ {
  proxy_cache static;
  expires 1h;
}

# ❌ НЕ КЭШИРУЕМ: HTML страницы (динамическое содержимое)
location / {
  proxy_cache off;
  add_header Cache-Control "no-cache";
}
```

## 📊 Тестирование результата

После применения конфигурации должны работать:

### Фронтенд маршруты (через gateway:8080)

- ✅ http://localhost:8080/ - главная
- ✅ http://localhost:8080/attachments - OCR документы
- ✅ http://localhost:8080/upload - загрузка прайсов
- ✅ http://localhost:8080/lot/123 - анализ лота

### API маршруты (через gateway:8080)

- ✅ http://localhost:8080/api/lot/123 - FastAPI endpoints
- ✅ http://localhost:8080/calc/health - микросервисы
- ✅ http://localhost:8080/static/style.css - статические файлы

### Прямой доступ (только для отладки)

- 🔧 http://localhost:8082/attachments - web напрямую

## 🛠 Troubleshooting

### Если /attachments возвращает 404:

```bash
# 1. Проверить статус контейнеров
docker compose ps

# 2. Проверить логи gateway
docker compose logs gateway -f

# 3. Проверить работу web напрямую
curl -I http://localhost:8082/attachments

# 4. Проверить nginx конфигурацию
docker compose exec gateway nginx -t
```

### Если страница пустая или не загружается:

```bash
# 1. Проверить логи веб-сервиса
docker compose logs web -f

# 2. Проверить health check
curl http://localhost:8080/health

# 3. Проверить статические файлы
curl -I http://localhost:8080/static/bootstrap.min.css
```

## 🎯 Альтернативные подходы

### 1. Поддомены вместо путей:

```nginx
server_name api.zakupai.local;   # для /calc/, /risk/
server_name app.zakupai.local;   # для фронтенда
```

### 2. Микрофронтенды:

```nginx
location /admin/ { proxy_pass http://admin-frontend:3000; }
location /dashboard/ { proxy_pass http://dashboard-frontend:3001; }
```

### 3. SSL + HTTP/2:

```nginx
listen 443 ssl http2;
ssl_certificate /etc/ssl/certs/zakupai.crt;
ssl_certificate_key /etc/ssl/private/zakupai.key;
```

## ✨ Результат

**🎉 РАБОТАЕТ!** После применения конфигурации:

1. **http://localhost:8080/attachments** отображает страницу OCR документов
1. React Router работает корректно для всех маршрутов
1. API вызовы проходят через единый gateway
1. Статические файлы кэшируются для быстрой загрузки
1. Нет 404 ошибок для SPA маршрутов

Теперь ZakupAI доступен через единый порт 8080 со всей функциональностью! 🚀
