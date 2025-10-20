# 🚀 Быстрый запуск ZakupAI

## ✅ Проблема "Connection failed" РЕШЕНА!

Firefox теперь успешно подключается к **http://localhost:8080**

## 🔧 Что было сделано

### 1. Исправлена конфигурация Nginx

- ✅ Настроено проксирование `/attachments` → `zakupai-web:8000`
- ✅ Добавлен SPA fallback для React Router
- ✅ Кэширование статических файлов
- ✅ Корректная передача заголовков

### 2. Исправлен Docker Compose

- ✅ Правильные зависимости сервисов
- ✅ Health checks для стабильного запуска
- ✅ Единая сеть для всех контейнеров

## 🚀 Команды для запуска

### Вариант 1: Полная система (медленно, все зависимости)

```bash
# Остановить всё и пересобрать
docker compose down
docker compose up -d --build

# Ожидание: 5-10 минут (PyTorch загружается долго)
```

### Вариант 2: Быстрый запуск (только web + gateway)

```bash
# Остановить всё
docker compose down

# Собрать минимальный web сервис
docker build -f web/Dockerfile.minimal -t zakupai-web-minimal web/

# Создать сеть
docker network create zakupai-test

# Запустить web сервис
docker run -d --name test-web --network zakupai-test \
  -e GATEWAY_URL=http://gateway -e ZAKUPAI_API_KEY=test \
  zakupai-web-minimal

# Запустить gateway
docker run -d --name test-gateway --network zakupai-test \
  -p 8080:80 \
  -v $(pwd)/gateway/nginx-minimal.conf:/etc/nginx/nginx.conf:ro \
  nginx:alpine

# Проверить работу
curl http://localhost:8080/attachments
```

## 🌐 Проверка в браузере

После запуска откройте в Firefox:

- **✅ http://localhost:8080/** - главная страница
- **✅ http://localhost:8080/attachments** - OCR документы
- **✅ http://localhost:8080/upload** - загрузка прайсов

## 🐛 Troubleshooting

### Если Firefox показывает "Попытка соединения не удалась":

1. **Проверить статус контейнеров:**

```bash
docker ps | grep -E "(gateway|web)"
```

2. **Проверить логи:**

```bash
docker logs test-gateway
docker logs test-web
```

3. **Проверить порт 8080:**

```bash
ss -tlnp | grep :8080
```

4. **Проверить прямое подключение:**

```bash
curl -I http://localhost:8080/health
```

### Если страница пустая:

1. **Проверить nginx конфигурацию:**

```bash
docker exec test-gateway nginx -t
```

2. **Проверить upstream:**

```bash
docker exec test-gateway nslookup test-web
```

## 🎯 Результат

**🎉 РАБОТАЕТ!**

- Firefox успешно подключается к http://localhost:8080
- Страница `/attachments` отображается корректно
- Nginx корректно проксирует запросы к веб-сервису
- React SPA маршрутизация работает через gateway

## 🧹 Очистка (при необходимости)

```bash
# Остановить тестовые контейнеры
docker rm -f test-web test-gateway

# Удалить тестовую сеть
docker network rm zakupai-test

# Или полная очистка Docker Compose
docker compose down --volumes --remove-orphans
```

______________________________________________________________________

**✨ Готово!** ZakupAI теперь доступен через единый порт 8080 со всей функциональностью фронтенда! 🚀
