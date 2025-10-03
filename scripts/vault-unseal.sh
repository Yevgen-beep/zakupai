#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE_CMD=(docker compose --profile stage6 \
  -f "$ROOT_DIR/docker-compose.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.monitoring.yml" \
  -f "$ROOT_DIR/monitoring/vault/docker-compose.override.stage6.vault.yml")

UNSEAL_FILE="$ROOT_DIR/monitoring/vault/unseal.key"
if [[ ! -f "$UNSEAL_FILE" ]]; then
  echo "Unseal key not found at $UNSEAL_FILE" >&2
  exit 1
fi

UNSEAL_KEY=$(<"$UNSEAL_FILE")

"${COMPOSE_CMD[@]}" exec -T vault sh -c "VAULT_ADDR=https://127.0.0.1:8200 VAULT_CACERT=/vault/tls/ca.pem vault operator unseal $UNSEAL_KEY"
