#!/usr/bin/env bash
set -euo pipefail

COMPOSE_CMD=(docker compose --profile stage6 \
  -f docker-compose.yml \
  -f docker-compose.override.stage6.yml \
  -f docker-compose.override.stage6.monitoring.yml \
  -f monitoring/vault/docker-compose.override.stage6.vault.yml)

jq() {
  command jq "$@"
}

curl_json() {
  local url=$1
  shift
  curl -s --fail "$url" "$@"
}

echo "=== 🔍 Stage6 Monitoring Smoke Test ==="

# 1. Проверка Prometheus targets
printf '[1] Prometheus targets\n'
curl_json "http://localhost:9095/api/v1/targets" | jq '.data.activeTargets[] | {job: .labels.job, endpoint: .discoveredLabels.__address__, state: .health}'

# 2. Проверка Prometheus rules
printf '[2] Prometheus rules\n'
curl_json "http://localhost:9095/api/v1/rules" | jq '.data.groups[] | {name: .name, rules: [.rules[].name]}'

# 3. Проверка активных алертов
printf '[3] Prometheus alerts\n'
curl_json "http://localhost:9095/api/v1/alerts" | jq '.data'

# 4. Проверка Alertmanager
printf '[4] Alertmanager alerts\n'
curl_json "http://localhost:9093/api/v2/alerts" | jq

# 5. Проверка Loki readiness
printf '[5] Loki readiness\n'
curl -s --fail http://localhost:3100/ready

# 6. Проверка лейблов Loki
printf '[6] Loki labels\n'
curl_json "http://localhost:3100/loki/api/v1/labels" | jq '.data'

# 7. Проверка nginx-exporter
printf '[7] nginx-exporter metrics\n'
if ! curl -sf http://nginx-exporter:9113/metrics | grep -q nginx_connections_active; then
  curl -sf http://localhost:9113/metrics | grep -q nginx_connections_active || {
    echo "Nginx metrics missing"
    exit 1
  }
fi

# 8. Получение последних логов из ETL service
printf '[8] Loki logs (etl-service)\n'
curl -G -s "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={service="etl-service"}' \
  --data-urlencode 'limit=5' | jq '.data.result[].values'

# 9. Grafana datasources API (внутри сети)
printf '[9] Grafana datasources (container)\n'
GRAFANA_DS_OUTPUT=$("${COMPOSE_CMD[@]}" exec -T grafana sh -c 'curl -s -u admin:admin http://grafana:3000/api/datasources' || true)
if [[ -z ${GRAFANA_DS_OUTPUT} ]]; then
  echo "warning: grafana container curl failed, falling back to localhost" >&2
else
  echo "${GRAFANA_DS_OUTPUT}" | jq '.[] | {name: .name, type: .type, url: .url}'
fi

# 10. Grafana datasources (host)
printf '[10] Grafana datasources (localhost)\n'
GRAFANA_LOCAL=$(curl -s -u admin:admin http://localhost:3030/api/datasources)
if [[ -z ${GRAFANA_LOCAL} ]]; then
  echo "Grafana localhost API returned empty response" >&2
  exit 1
fi
echo "${GRAFANA_LOCAL}" | jq '.[] | {name: .name, type: .type, url: .url}'

# 11. Vault health endpoint (HTTPS)
printf '[11] Vault health\n'
VAULT_HEALTH_CONTAINER=$("${COMPOSE_CMD[@]}" exec -T grafana sh -c 'curl -sk https://vault:8200/v1/sys/health' || true)
if [[ -n ${VAULT_HEALTH_CONTAINER} ]]; then
  echo "${VAULT_HEALTH_CONTAINER}" | jq
else
  VAULT_HEALTH_HOST=$(curl -sk https://localhost:8200/v1/sys/health || true)
  if [[ -z ${VAULT_HEALTH_HOST} ]]; then
    echo "Vault health endpoint is unreachable" >&2
    exit 1
  fi
  echo "${VAULT_HEALTH_HOST}" | jq
fi

printf '=== ✅ Stage6 Monitoring Smoke Test Completed ===\n'
