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
  "${COMPOSE[@]}" port "$service" "$port" | awk -F: 'NF>1 {print $2}'
}

declare -A SERVICE_HOST_PORTS=()
for svc in "${!SERVICE_DEFAULT_PORTS[@]}"; do
  resolved=$(compose_port "$svc" "${SERVICE_DEFAULT_PORTS[$svc]}" || true)
  if [[ -z $resolved ]]; then
    echo "Failed to resolve host port for $svc" >&2
    exit 1
  fi
  SERVICE_HOST_PORTS[$svc]=$resolved
done

CALC_URL="http://localhost:${SERVICE_HOST_PORTS[calc-service]}"
RISK_URL="http://localhost:${SERVICE_HOST_PORTS[risk-engine]}"
DOC_URL="http://localhost:${SERVICE_HOST_PORTS[doc-service]}"
EMBED_URL="http://localhost:${SERVICE_HOST_PORTS[embedding-api]}"
ETL_URL="http://localhost:${SERVICE_HOST_PORTS[etl-service]}"
GOSZAKUP_URL="http://localhost:${SERVICE_HOST_PORTS[goszakup-api]}"
BILLING_URL="http://localhost:${SERVICE_HOST_PORTS[billing-service]}"

CALC_PREFIX="$CALC_URL/calc"
RISK_PREFIX="$RISK_URL/risk"
DOC_PREFIX="$DOC_URL/doc"
EMBED_PREFIX="$EMBED_URL/emb"

printf -v BILLING_CREATE_PAYLOAD '{"tg_id": %d, "email": "smoke+%s@zakupai.test"}' 424242 "$(date +%s)"

CALC_OK_PAYLOAD='{"amount": 1000, "vat_rate": 12, "include_vat": true, "lot_id": 1001}'
CALC_FAIL_PAYLOAD='{"amount": -1, "vat_rate": 12, "include_vat": true, "lot_id": 1001}'
RISK_OK_PAYLOAD='{"lot_id": 1001}'
RISK_FAIL_PAYLOAD='{"lot_id": -1}'
DOC_OK_PAYLOAD='{"lot_id": 1001}'
DOC_FAIL_PAYLOAD='{"lot_id": -1}'
EMBED_OK_PAYLOAD='{"text": "zakupai embedding warmup", "dim": 32}'
EMBED_FAIL_PAYLOAD='{"text": "fail", "dim": -1}'
ETL_FAIL_PAYLOAD='{"days": 0}'
GOSZAKUP_FAIL_PAYLOAD='{"keyword": "zakupai", "limit": 5, "api_version": "graphql_v2"}'
BILLING_USAGE_FAIL='{"api_key": "invalid", "endpoint": "calc", "requests": -1}'

AUTH_HEADERS=(-H "X-API-Key: ${DOC_API_KEY}")

do_curl() {
  local label=$1
  local expect_failure=$2
  shift 2

  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" "$@" || true)

  if [[ $expect_failure == "true" ]]; then
    if [[ $http_code =~ ^[45] ]]; then
      :
    else
      echo "  ⚠️  $label expected failure but returned HTTP $http_code" >&2
    fi
  else
    if [[ ! $http_code =~ ^2 ]]; then
      echo "  ⚠️  $label returned HTTP $http_code" >&2
    fi
  fi

  printf '%s:%s ' "$label" "$http_code"
}

echo "→ Generating traffic for ZakupAI core services"
for ((i=1; i<=ITERATIONS; i++)); do
  printf '• iteration %d ' "$i"

  do_curl calc-ok false "$CALC_PREFIX/calc/vat" \
    -H 'Content-Type: application/json' \
    --data "$CALC_OK_PAYLOAD"

  do_curl risk-info false "$RISK_PREFIX/info" \
    "${AUTH_HEADERS[@]}"

  do_curl doc-info false "$DOC_PREFIX/info" \
    "${AUTH_HEADERS[@]}"

  do_curl embed-ok false "$EMBED_PREFIX/embed" \
    -H 'Content-Type: application/json' \
    --data "$EMBED_OK_PAYLOAD"

  do_curl billing-create false "$BILLING_URL/billing/create_key" \
    -H 'Content-Type: application/json' \
    --data "$BILLING_CREATE_PAYLOAD"

  do_curl goszakup-health false "$GOSZAKUP_URL/health"

  do_curl etl-health false "$ETL_URL/health"

  do_curl calc-bad true "$CALC_PREFIX/calc/vat" \
    -H 'Content-Type: application/json' \
    --data "$CALC_FAIL_PAYLOAD"

  do_curl risk-bad true "$RISK_PREFIX/risk/score" \
    -H 'Content-Type: application/json' \
    --data "$RISK_FAIL_PAYLOAD"

  do_curl doc-bad true "$DOC_PREFIX/tldr" \
    -H 'Content-Type: application/json' \
    "${AUTH_HEADERS[@]}" \
    --data "$DOC_FAIL_PAYLOAD"

  do_curl embed-bad true "$EMBED_PREFIX/embed" \
    -H 'Content-Type: application/json' \
    --data "$EMBED_FAIL_PAYLOAD"

  do_curl etl-bad true "$ETL_URL/run" \
    -H 'Content-Type: application/json' \
    --data "$ETL_FAIL_PAYLOAD"

  do_curl goszakup-search false "$GOSZAKUP_URL/search" \
    -H 'Content-Type: application/json' \
    --data "$GOSZAKUP_FAIL_PAYLOAD"

  do_curl billing-usage false "$BILLING_URL/billing/usage" \
    -H 'Content-Type: application/json' \
    --data "$BILLING_USAGE_FAIL"

  printf '\n'
  sleep "$SLEEP_BETWEEN"
done

echo "→ Traffic generation finished"
sleep 2
