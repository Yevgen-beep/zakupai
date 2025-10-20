#!/usr/bin/env bash
set -euo pipefail

PROM_URL=${PROM_URL:-http://localhost:9095}
LOKI_URL=${LOKI_URL:-http://localhost:3100}
GRAFANA_URL=${GRAFANA_URL:-http://localhost:3001}
ALERTMANAGER_URL=${ALERTMANAGER_URL:-http://localhost:9093}

curl_safe() {
  local url=$1
  curl -sS --fail "$url" 2>/dev/null || echo "unreachable"
}

prom_status=$(curl_safe "${PROM_URL}/-/healthy")
loki_status=$(curl_safe "${LOKI_URL}/ready")

grafana_raw=$(curl_safe "${GRAFANA_URL}/api/health")
if command -v jq >/dev/null 2>&1; then
  grafana_status=$(printf '%s' "$grafana_raw" | jq -r '.database // "unknown"')
else
  grafana_status=$(printf '%s' "$grafana_raw" | sed -n 's/.*"database":"\([^"]*\)".*/\1/p')
  grafana_status=${grafana_status:-$grafana_raw}
fi

alert_status=$(curl_safe "${ALERTMANAGER_URL}/-/healthy")

echo "Prometheus: ${prom_status}"
echo "Loki: ${loki_status}"
echo "Grafana: ${grafana_status}"
echo "Alertmanager: ${alert_status}"
