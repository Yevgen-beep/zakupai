#!/usr/bin/env bash
set -euo pipefail

echo "=== 🔍 Stage6 Monitoring Smoke Test ==="

# 1. Проверка Prometheus targets
echo "[1] Prometheus targets"
curl -s http://localhost:9095/targets | jq '.data.activeTargets[] | {job: .labels.job, endpoint: .discoveredLabels.__address__, state: .health}'

# 2. Проверка Prometheus rules
echo "[2] Prometheus rules"
curl -s http://localhost:9095/rules | jq '.data.groups[].name'

# 3. Проверка активных алертов
echo "[3] Prometheus alerts"
curl -s http://localhost:9095/alerts | jq '.data'

# 4. Проверка Alertmanager
echo "[4] Alertmanager alerts"
curl -s http://localhost:9093/api/v2/alerts | jq

# 5. Проверка Loki readiness
echo "[5] Loki readiness"
curl -s http://localhost:3100/ready

# 6. Проверка лейблов Loki
echo "[6] Loki labels"
curl -s http://localhost:3100/loki/api/v1/labels | jq '.data'

# 7. Получение последних логов из ETL service
echo "[7] Loki logs (etl-service)"
curl -G -s "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={service="etl-service"}' \
  --data-urlencode 'limit=5' | jq '.data.result[].values'

# 8. Проверка Grafana datasources (Prometheus + Loki)
echo "[8] Grafana datasources"
curl -s http://admin:admin@localhost:3030/api/datasources | jq '.[] | {name: .name, type: .type, url: .url}'

echo "=== ✅ Stage6 Monitoring Smoke Test Completed ==="
