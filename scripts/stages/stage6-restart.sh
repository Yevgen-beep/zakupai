#!/bin/bash
set -e

echo "=== ♻️ ZakupAI Stage6: Полный рестарт окружения ==="
BASE_COMPOSE="-f docker-compose.yml -f docker-compose.override.stage6.yml -f docker-compose.override.stage6.monitoring.yml -f docker-compose.override.prod.yml"

# 1️⃣ Остановка и очистка
echo "[1] 🧹 Останавливаем контейнеры и чистим сеть..."
docker compose $BASE_COMPOSE down -v --remove-orphans || true

echo "[2] 🧽 Очищаем dangling-образы..."
docker image prune -af -q || true

# 2️⃣ Пересборка и запуск
echo "[3] 🚀 Собираем и запускаем все сервисы..."
docker compose $BASE_COMPOSE up -d --build

# 3️⃣ Ожидание запуска
echo "[4] ⏳ Ожидание стабилизации контейнеров..."
sleep 15

# 4️⃣ Проверка статусов
echo "[5] 🔍 Проверяем состояние контейнеров:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 5️⃣ Мини-проверка критичных сервисов
echo
echo "=== 🩺 Быстрая health-проверка основных эндпоинтов ==="
declare -A ENDPOINTS=(
  ["Gateway"]="http://localhost:8080/health"
  ["Grafana"]="http://localhost:3001"
  ["Prometheus"]="http://localhost:9095/-/ready"
  ["Flowise"]="http://localhost:3000"
  ["n8n"]="http://localhost:5678"
)

for service in "${!ENDPOINTS[@]}"; do
  url="${ENDPOINTS[$service]}"
  status=$(curl -s -o /dev/null -w "%{http_code}" "$url" || true)
  if [ "$status" == "200" ]; then
    echo "✅ $service OK ($url)"
  elif [ "$status" == "302" ] || [ "$status" == "301" ]; then
    echo "⚠️  $service редирект ($url)"
  else
    echo "❌ $service недоступен ($url)"
  fi
done

# 6️⃣ Smoke-тест, если есть
if [ -f "./stage6-smoke.sh" ]; then
  echo
  echo "=== 🔬 Запуск stage6-smoke.sh ==="
  ./stage6-smoke.sh || echo "⚠️  Smoke-тест завершён с предупреждениями"
else
  echo
  echo "ℹ️  Smoke-тест не найден (stage6-smoke.sh). Пропускаем."
fi

echo
echo "=== ✅ Рестарт ZakupAI завершён. Проверяй Grafana на http://localhost:3001 ==="
