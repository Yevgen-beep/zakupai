#!/bin/bash
set -e

echo "=== ♻️ ZakupAI Stage6: Автоматическое применение фикса Grafana ==="

PATCH_FILE="stage6_grafana_fix.diff"

# 1️⃣ Проверка наличия патча
if [ ! -f "$PATCH_FILE" ]; then
  echo "❌ Файл $PATCH_FILE не найден!"
  exit 1
fi

# 2️⃣ Автоматическая правка путей внутри патча (grafana → monitoring/grafana)
if grep -q "grafana/provisioning" "$PATCH_FILE"; then
  echo "🔧 Исправляем пути внутри патча..."
  sed -i 's|grafana/|monitoring/grafana/|g' "$PATCH_FILE"
fi

# 3️⃣ Применяем патч
echo "📦 Применяем $PATCH_FILE ..."
if git apply "$PATCH_FILE" 2>/dev/null; then
  echo "✅ Патч успешно применён через git"
else
  echo "⚙️ git apply не сработал, пробуем patch..."
  patch -p1 < "$PATCH_FILE" || {
    echo "❌ Не удалось применить патч. Проверь пути в проекте."
    exit 1
  }
fi

# 4️⃣ Проверяем, что изменения действительно внесены
echo "🔍 Проверяем наличие обновлённых запросов в Grafana dashboard..."
grep -R "max(probe_success{job=\"zakupai-bot-health\"})" monitoring/grafana/provisioning/dashboards/overview/ >/dev/null || {
  echo "❌ Изменения для Bot Status не найдены!"
  exit 1
}
grep -R "max(probe_success{job=\"external-api-goszakup\"})" monitoring/grafana/provisioning/dashboards/ops/ >/dev/null || {
  echo "❌ Изменения для External API не найдены!"
  exit 1
}

echo "✅ Обновлённые запросы найдены."

# 5️⃣ Перезапускаем Grafana
echo "🚀 Перезапускаем Grafana..."
docker compose --profile stage6 \
  -f docker-compose.yml \
  -f docker-compose.override.stage6.yml \
  -f docker-compose.override.stage6.monitoring.yml \
  restart grafana

echo "⏳ Ждём 10 секунд, пока Grafana перечитает дашборды..."
sleep 10

# 6️⃣ Проверка логов Grafana
echo "🧾 Проверяем логи Grafana на ошибки..."
docker logs zakupai-grafana 2>&1 | grep -i "error" && echo "⚠️ Найдены ошибки!" || echo "✅ Ошибок не обнаружено."

# 7️⃣ Проверка через Prometheus
echo "📊 Проверяем probe_success..."
docker exec zakupai-prometheus wget -qO- "http://localhost:9090/api/v1/query?query=max(probe_success{job=\"zakupai-bot-health\"})" | jq '.data.result[0].value' || true

# 8️⃣ Финальное сообщение
echo
echo "🎯 Всё готово!"
echo "Проверь панели Grafana:"
echo "→ Overview Dashboard:   http://localhost:3030/d/zakupai-overview"
echo "→ Platform Ops Dashboard: http://localhost:3030/d/zakupai-platform-ops"
echo
echo "Если панели всё ещё красные, перезапусти Grafana вручную и обнови страницу (Ctrl+F5)."
