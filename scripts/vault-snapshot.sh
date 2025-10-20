#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE_CMD=(docker compose --profile stage6 \
  -f "$ROOT_DIR/docker-compose.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.monitoring.yml" \
  -f "$ROOT_DIR/monitoring/vault/docker-compose.override.stage6.vault.yml")

SNAP_NAME="snapshot-$(date +%F).snap"
DEST_PATH="/vault/data/${SNAP_NAME}"

KEYS_FILE="$ROOT_DIR/.secrets/vault-keys.txt"
if [[ ! -f $KEYS_FILE ]]; then
  echo "Root keys file not found at $KEYS_FILE" >&2
  exit 1
fi
ROOT_TOKEN=$(grep 'Initial Root Token' "$KEYS_FILE" | awk '{print $4}' | head -n1)

"${COMPOSE_CMD[@]}" exec -T vault env \
  VAULT_ADDR=https://127.0.0.1:8200 \
  VAULT_CACERT=/vault/tls/ca.pem \
  VAULT_TOKEN="$ROOT_TOKEN" \
  vault operator raft snapshot save "$DEST_PATH"

printf 'Vault snapshot saved at %s inside the container.\n' "$DEST_PATH"
