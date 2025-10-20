#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE=(docker compose --profile stage6 \
  -f "$ROOT_DIR/docker-compose.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.monitoring.yml" \
  -f "$ROOT_DIR/monitoring/vault/docker-compose.override.stage6.vault.yml")

KEYS_FILE="$ROOT_DIR/.secrets/vault-keys.txt"
if [[ ! -f $KEYS_FILE ]]; then
  echo "Root keys file not found at $KEYS_FILE" >&2
  exit 1
fi
ROOT_TOKEN=$(grep 'Initial Root Token' "$KEYS_FILE" | awk '{print $4}' | head -n1)

VAULT_ENV=(env VAULT_ADDR=https://127.0.0.1:8200 VAULT_CACERT=/vault/tls/ca.pem VAULT_TOKEN="$ROOT_TOKEN")

cat <<'POL' | "${COMPOSE[@]}" exec -T vault "${VAULT_ENV[@]}" vault policy write zakupai-metrics -
path "sys/metrics" {
  capabilities = ["read"]
}
POL

METRICS_TOKEN=$("${COMPOSE[@]}" exec -T vault "${VAULT_ENV[@]}" vault token create -policy=zakupai-metrics -ttl=720h -format=json | jq -r '.auth.client_token')

printf '%s\n' "$METRICS_TOKEN" > "$ROOT_DIR/.secrets/vault-metrics-token.txt"
printf '%s\n' "$METRICS_TOKEN" > "$ROOT_DIR/monitoring/prometheus/vault-metrics.token"
chmod 600 "$ROOT_DIR/.secrets/vault-metrics-token.txt" "$ROOT_DIR/monitoring/prometheus/vault-metrics.token"

"${COMPOSE[@]}" restart prometheus >/dev/null

echo "Rotated metrics token and restarted Prometheus."
