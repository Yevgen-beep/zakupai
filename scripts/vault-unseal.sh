#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
KEYS_FILE="$ROOT_DIR/.secrets/vault-keys.txt"

if [[ ! -f "$KEYS_FILE" ]]; then
  echo "Unseal keys not found at $KEYS_FILE" >&2
  exit 1
fi

COMPOSE_CMD=(docker compose --profile stage6 \
  -f "$ROOT_DIR/docker-compose.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.monitoring.yml" \
  -f "$ROOT_DIR/monitoring/vault/docker-compose.override.stage6.vault.yml")

mapfile -t UNSEAL_KEYS < <(grep -E 'Unseal Key [0-9]+:' "$KEYS_FILE" | awk '{print $4}' | head -n 5)
if (( "${#UNSEAL_KEYS[@]}" < 3 )); then
  echo "Expected at least 3 unseal keys in $KEYS_FILE" >&2
  exit 1
fi

VAULT_CMD=("${COMPOSE_CMD[@]}" exec -T vault env VAULT_ADDR=https://127.0.0.1:8200 VAULT_CACERT=/vault/tls/ca.pem)

for key in "${UNSEAL_KEYS[@]:0:3}"; do
  "${VAULT_CMD[@]}" vault operator unseal "$key" >/dev/null
  echo "Applied unseal key"
  sleep 1
done

printf 'Vault unseal complete.\n'
