#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
COMPOSE_CMD=(docker compose --profile stage6 \
  -f "$ROOT_DIR/docker-compose.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.monitoring.yml" \
  -f "$ROOT_DIR/monitoring/vault/docker-compose.override.stage6.vault.yml")

jq() { command jq "$@"; }

curl_json() {
  local url=$1
  shift
  curl -sS --fail "$url" "$@"
}

compose_port() {
  local service=$1
  local port=$2
  "${COMPOSE_CMD[@]}" port "$service" "$port" | awk -F: '{print $2}'
}

DEFAULT_PROM_PORT=9095
DEFAULT_GRAFANA_PORT=3030
DEFAULT_VAULT_PORT=8200
DEFAULT_LOKI_PORT=3100

PROM_PORT=${PROM_PORT:-$(compose_port prometheus 9090)}
PROM_PORT=${PROM_PORT:-$DEFAULT_PROM_PORT}
GRAFANA_PORT=${GRAFANA_PORT:-$(compose_port grafana 3000)}
GRAFANA_PORT=${GRAFANA_PORT:-$DEFAULT_GRAFANA_PORT}
VAULT_PORT=${VAULT_PORT:-$(compose_port vault 8200)}
VAULT_PORT=${VAULT_PORT:-$DEFAULT_VAULT_PORT}
LOKI_PORT=${LOKI_PORT:-$(compose_port loki 3100)}
LOKI_PORT=${LOKI_PORT:-$DEFAULT_LOKI_PORT}
NGINX_EXPORTER_PORT=$(compose_port nginx-exporter 9113)

if [[ $GRAFANA_PORT != "3030" ]]; then
  if docker ps --format '{{.Ports}}' --filter name=zakupai-grafana | grep -q '3030->3000'; then
    GRAFANA_PORT=3030
  fi
fi

if [[ -z $PROM_PORT || -z $GRAFANA_PORT || -z $VAULT_PORT || -z $LOKI_PORT || -z $NGINX_EXPORTER_PORT ]]; then
  echo "Failed to resolve one or more service ports" >&2
  exit 1
fi

echo "=== 🔍 Stage6 Monitoring Smoke Test ==="

prom_get() {
  local path=$1
  curl_json "http://localhost:${PROM_PORT}${path}"
}

prom_query() {
  local expr=$1
  curl -sS --fail --get "http://localhost:${PROM_PORT}/api/v1/query" \
    --data-urlencode "query=${expr}"
}

# 0. Warm-up traffic for SLO metrics
printf '[0] Generating synthetic traffic\n'
TRAFFIC_ITERATIONS=${ITERATIONS:-5}
ITERATIONS="$TRAFFIC_ITERATIONS" "$ROOT_DIR/scripts/traffic-gen.sh"
sleep 5

# Loki API smoke check
printf '[Loki] API endpoints\n'
LOKI_LABELS_RESPONSE=$(curl -sS "http://localhost:${LOKI_PORT}/loki/api/v1/labels")
if [[ $(jq -r '.status' <<<"$LOKI_LABELS_RESPONSE") != "success" ]]; then
  echo "Loki labels endpoint did not return success" >&2
  exit 1
fi
jq <<<"$LOKI_LABELS_RESPONSE"

LOKI_METRICS_RAW=$(curl -sS "http://localhost:${LOKI_PORT}/metrics")
if [[ -z $LOKI_METRICS_RAW ]]; then
  echo "Loki metrics endpoint returned no data" >&2
  exit 1
fi
mapfile -t LOKI_METRICS_LINES <<<"$LOKI_METRICS_RAW"
for ((i=0; i<${#LOKI_METRICS_LINES[@]} && i<10; i++)); do
  printf '%s\n' "${LOKI_METRICS_LINES[$i]}"
done

# 1. Prometheus targets health
printf '[1] Prometheus targets\n'
TARGETS_JSON=$(prom_get "/api/v1/targets")
REQUIRED_JOBS=(prometheus calc-service risk-engine doc-service embedding-api etl-service goszakup-api billing-service nginx vault)
for job in "${REQUIRED_JOBS[@]}"; do
  if ! jq -e --arg job "$job" '.data.activeTargets[] | select(.labels.job == $job and .health == "up")' <<<"$TARGETS_JSON" >/dev/null; then
    echo "Target $job is not UP" >&2
    exit 1
  fi
done
jq '.data.activeTargets[] | {job: .labels.job, endpoint: .labels.instance, health: .health}' <<<"$TARGETS_JSON"

# 2. Prometheus SLO rules present
printf '[2] Prometheus SLO recording rules\n'
RULES_JSON=$(prom_get "/api/v1/rules")
if ! jq -e '.data.groups[] | select(.name == "slo")' <<<"$RULES_JSON" >/dev/null; then
  echo "SLO rule group missing" >&2
  exit 1
fi
jq '.data.groups[] | select(.name == "slo") | {name, rules: [.rules[].name]}' <<<"$RULES_JSON"

# 3. SLO metric queries
printf '[3] SLO metric evaluation\n'
SLO_QUERIES=(api_error_ratio api_error_ratio_by_service api_p95_latency)
for query in "${SLO_QUERIES[@]}"; do
  RESULT=$(prom_query "$query")
  if [[ $(jq -r '.data.result | length' <<<"$RESULT") -eq 0 ]]; then
    echo "Query ${query} returned no data" >&2
    exit 1
  fi
  if ! jq -e 'any((.data.result // [])[]; ((.value[1] == "+Inf") or (try (.value[1] | tonumber) catch 0) > 0))' <<<"$RESULT" >/dev/null; then
    echo "Query ${query} did not return a non-zero value" >&2
    exit 1
  fi
  jq '.data.result' <<<"$RESULT"
done

# 4. nginx-exporter metrics via DNS and localhost
printf '[4] nginx-exporter metrics\n'
if ! "${COMPOSE_CMD[@]}" exec -T grafana sh -c 'curl -sf http://nginx-exporter:9113/metrics | grep -q nginx_connections_active'; then
  echo "nginx-exporter metrics unavailable inside network" >&2
  exit 1
fi
if ! curl -sf "http://localhost:${NGINX_EXPORTER_PORT}/metrics" | grep -q nginx_connections_active; then
  echo "nginx-exporter metrics unavailable on host port" >&2
  exit 1
fi
printf 'nginx-exporter metrics OK\n'

# 5. Grafana datasources (default + Loki)
printf '[5] Grafana datasources\n'
DS_PAYLOAD=$(curl -sS -u admin:admin "http://localhost:${GRAFANA_PORT}/api/datasources")
if [[ $(jq '[.[] | select(.name == "Prometheus" and .isDefault == true)] | length' <<<"$DS_PAYLOAD") -eq 0 ]]; then
  echo "Prometheus datasource missing or not default" >&2
  exit 1
fi
if [[ $(jq '[.[] | select(.name == "Loki")] | length' <<<"$DS_PAYLOAD") -eq 0 ]]; then
  echo "Loki datasource missing" >&2
  exit 1
fi
jq '.[] | {name, type, url, isDefault}' <<<"$DS_PAYLOAD"

# 6. Grafana dashboards structure
printf '[6] Grafana dashboards\n'
DASHBOARDS=$(curl -sS -u admin:admin "http://localhost:${GRAFANA_PORT}/api/search?type=dash-db")
for folder in overview apis security; do
  if [[ $(jq --arg folder "$folder" '[.[] | select(.folderTitle == $folder)] | length' <<<"$DASHBOARDS") -eq 0 ]]; then
    echo "No dashboards found in folder ${folder}" >&2
    exit 1
  fi
done
jq '.[] | {folder: .folderTitle, title: .title}' <<<"$DASHBOARDS"

# 7. Vault health sealed=false
printf '[7] Vault health\n'
VAULT_HEALTH=$(curl -sk "https://localhost:${VAULT_PORT}/v1/sys/health")
if [[ $(jq -r '.sealed' <<<"$VAULT_HEALTH") != "false" ]]; then
  echo "Vault is sealed, attempting auto-unseal..." >&2
  if [[ -x "$ROOT_DIR/scripts/vault-unseal.sh" ]]; then
    "$ROOT_DIR/scripts/vault-unseal.sh"
    sleep 2
    VAULT_HEALTH=$(curl -sk "https://localhost:${VAULT_PORT}/v1/sys/health")
    if [[ $(jq -r '.sealed' <<<"$VAULT_HEALTH") != "false" ]]; then
      echo "Vault unseal failed" >&2
      exit 1
    fi
    echo "Vault unsealed successfully"
  else
    echo "vault-unseal.sh not found or not executable" >&2
    exit 1
  fi
fi
jq <<<"$VAULT_HEALTH"

# 8. Vault metrics exposed
printf '[8] Vault metrics\n'
VAULT_METRICS_TOKEN_FILE="$ROOT_DIR/monitoring/prometheus/vault-metrics.token"
if [[ -f $VAULT_METRICS_TOKEN_FILE ]]; then
  VAULT_METRICS=$(curl -sk -H "X-Vault-Token: $(<"$VAULT_METRICS_TOKEN_FILE")" "https://localhost:${VAULT_PORT}/v1/sys/metrics?format=prometheus")
else
  VAULT_METRICS=$(curl -sk "https://localhost:${VAULT_PORT}/v1/sys/metrics?format=prometheus")
fi
if ! grep -q '^vault_' <<<"$VAULT_METRICS"; then
  echo "Vault metrics endpoint returned no vault_ metrics" >&2
  exit 1
fi
printf '%s\n' "$(head -n 10 <<<"$VAULT_METRICS")"

# 9. Loki labels and logs
printf '[9] Loki API\n'
NOW_NS=$(date +%s%N)
NEXT_NS=$((NOW_NS + 1000))
PAYLOAD=$(cat <<EOF
{"streams":[
  {"stream":{"job":"audit","service":"smoke-test"},"values":[["$NOW_NS","stage6 smoke-test log"]]},
  {"stream":{"job":"synthetic","service":"calc-service"},"values":[["$NEXT_NS","stage6 calc-service synthetic log"]]}
]}
EOF
)
curl -sS -H 'Content-Type: application/json' -X POST "http://localhost:${LOKI_PORT}/loki/api/v1/push" -d "$PAYLOAD" >/dev/null
LABELS=$(curl -sS "http://localhost:${LOKI_PORT}/loki/api/v1/labels")
if [[ $(jq -r '.status' <<<"$LABELS") != "success" ]]; then
  echo "Loki labels request failed" >&2
  exit 1
fi
if ! jq -e '.data[] | select(. == "service")' <<<"$LABELS" >/dev/null; then
  echo "Loki labels response missing service label" >&2
  exit 1
fi
SERVICE_VALUES=$(curl -sS "http://localhost:${LOKI_PORT}/loki/api/v1/label/service/values")
if [[ $(jq -r '.status' <<<"$SERVICE_VALUES") != "success" ]]; then
  echo "Loki service label values query failed" >&2
  exit 1
fi
if ! jq -e '.data[] | select(. == "calc-service")' <<<"$SERVICE_VALUES" >/dev/null; then
  echo "Loki service label lacks calc-service" >&2
  exit 1
fi
jq '(.data // [])[:10]' <<<"$SERVICE_VALUES"
LOGS=$(curl -G -sS "http://localhost:${LOKI_PORT}/loki/api/v1/query_range" \
  --data-urlencode 'query={service="calc-service"}' \
  --data-urlencode 'limit=20')
if [[ $(jq -r '.status' <<<"$LOGS") != "success" ]]; then
  echo "Loki log query failed" >&2
  exit 1
fi
if [[ $(jq '(.data.result // []) | length' <<<"$LOGS") -eq 0 ]]; then
  echo "Loki log query returned no results" >&2
  exit 1
fi
jq '(.data.result // [])[:1]' <<<"$LOGS"

# 10. hvac integration logs
printf '[10] Vault client logs\n'
LOG_OK=true
declare -A CONTAINER_NAMES=(
  [calc-service]=zakupai-calc-service
  [risk-engine]=zakupai-risk-engine
  [etl-service]=zakupai-etl-service
)
set +o pipefail
for svc in "${!CONTAINER_NAMES[@]}"; do
  container=${CONTAINER_NAMES[$svc]}
  if ! docker logs "$container" 2>&1 | grep -q -E "vault_bootstrap_success|Vault bootstrap success"; then
    echo "No Vault bootstrap success log found for $svc" >&2
    LOG_OK=false
  fi
done
set -o pipefail
if [[ $LOG_OK != true ]]; then
  exit 1
fi

# 10b. Ensure no finance_calcs warnings remain
printf '[10b] Service log sanity\n'
for container in zakupai-calc-service zakupai-risk-engine zakupai-etl-service; do
  if docker logs "$container" 2>&1 | grep -qi 'finance_calcs insert failed'; then
    echo "finance_calcs warnings present in $container logs" >&2
    exit 1
  fi
done
printf '  ✓ no finance_calcs warnings\n'

# 11. Loki logcli check
printf '[11] Loki logcli query\n'
if ! docker run --rm --network zakupai_zakupai-network grafana/logcli:latest \
  --addr=http://loki:3100 query '{service="calc-service"}' --limit=5 >/tmp/logcli.out 2>/tmp/logcli.err; then
  cat /tmp/logcli.err >&2
  exit 1
fi
head -n 20 /tmp/logcli.out

printf '=== 📊 UI endpoints ===\n'
printf 'Grafana:   http://localhost:%s\n' "$GRAFANA_PORT"
printf 'Prometheus: http://localhost:%s\n' "$PROM_PORT"
printf 'Vault:     https://localhost:%s/ui/vault/\n' "$VAULT_PORT"
printf 'Loki:      http://localhost:%s\n' "$LOKI_PORT"
printf '=== ✅ Stage6 Monitoring Smoke Test Completed ===\n'
