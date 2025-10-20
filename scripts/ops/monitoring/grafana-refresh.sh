#!/bin/bash
set -e

echo "🔄 [1/5] Останавливаю Grafana..."
docker stop zakupai-grafana >/dev/null 2>&1 || true

echo "🧹 [2/5] Очищаю кеш и старые дашборды..."
docker run --rm \
  -v zakupai_grafana-data:/var/lib/grafana \
  alpine sh -c 'rm -rf /var/lib/grafana/plugins/* /var/lib/grafana/dashboards/* /var/lib/grafana/dashboards_cache/* 2>/dev/null || true'

echo "📦 [3/5] Применяю свежие provisioning-файлы..."
docker compose --profile stage6 up -d grafana

echo "⏳ [4/5] Жду 10 секунд, пока Grafana стартует..."
sleep 10

echo "🧠 [5/5] Проверяю подключение к Prometheus..."
curl -s -u admin:admin "http://localhost:3030/api/datasources/uid/zakupai-prom/health" | jq

echo "✅ Готово! Grafana перезапущена и перечитала dashboard JSON-файлы."
echo "➡️ Открой http://localhost:3030/d/zakupai-platform-ops (admin/admin)"
echo "⚠️ Если всё ещё 'No data' — обнови страницу через Ctrl+Shift+R или открой в инкогнито."
