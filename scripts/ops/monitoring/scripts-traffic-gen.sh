#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
COMPOSE=(docker compose --profile stage6 \
  -f "$ROOT_DIR/docker-compose.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.monitoring.yml" \
  -f "$ROOT_DIR/monitoring/vault/docker-compose.override.stage6.vault.yml")

DEFAULT_ITERATIONS=5
ITERATIONS=${ITERATIONS:-$DEFAULT_ITERATIONS}
if [[ $# -gt 0 ]]; then
  ITERATIONS=$1
fi

SLEEP_BETWEEN=${SLEEP_BETWEEN:-0.5}
DOC_API_KEY=${DOC_API_KEY:-}

if [[ -z $DOC_API_KEY && -f "$ROOT_DIR/.env" ]]; then
  DOC_API_KEY=$(grep -E '^API_KEY=' "$ROOT_DIR/.env" | tail -n1 | cut -d'=' -f2-)
fi

DOC_API_KEY=${DOC_API_KEY:-changeme}

declare -A SERVICE_DEFAULT_PORTS=(
  [calc-service]=8000
  [risk-engine]=8000
  [doc-service]=8000
  [embedding-api]=8000
  [etl-service]=8000
  [goszakup-api]=8001
  [billing-service]=8000
)

compose_port() {
  local service=$1
  local port=$2
  "${COMPOSE[@]}" port "$service" "$port" 2>/dev/null | awk -F: 'NF>1 {print $2}' || true
}

generate_traffic() {
  local service=$1
  local port=$2
  local base_url="http://localhost:${port}"

  echo "→ Sending test requests to ${service} (${base_url})"

  # /health
  if curl -sf --max-time 5 "${base_url}/health" >/dev/null; then
    echo "   ✅ ${service} /health OK"
  else
    echo "   ⚠️  ${service} /health failed or timed out"
  fi

  # /metrics (optional)
  if curl -sf --max-time 5 "${base_url}/metrics" >/dev/null; then
    echo "   ✅ ${service} /metrics OK"
  else
    echo "   ⚠️  ${service} /metrics not available"
  fi
}

echo "=== 🚦 Stage6 Synthetic Traffic Generator ==="
echo "Iterations: ${ITERATIONS}"

declare -A RESULTS

for service in "${!SERVICE_DEFAULT_PORTS[@]}"; do
  port=$(compose_port "$service" "${SERVICE_DEFAULT_PORTS[$service]}")
  if [[ -z "$port" ]]; then
    echo "⚠️  No port found for $service — skipping"
    RESULTS[$service]="❌ no port"
    continue
  fi

  for ((i=1; i<=ITERATIONS; i++)); do
    generate_traffic "$service" "$port" || true
    sleep "$SLEEP_BETWEEN"
  done
  RESULTS[$service]="✅ ok"
done

echo ""
echo "=== 🧾 Traffic Generation Summary ==="
for service in "${!RESULTS[@]}"; do
  printf "%-20s %s\n" "$service" "${RESULTS[$service]}"
done

echo ""
echo "✅ Synthetic traffic generation completed. Prometheus should now see activity."
