#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SECRETS_DIR="$ROOT_DIR/.secrets"
mkdir -p "$SECRETS_DIR"

COMPOSE_CMD=(docker compose --profile stage6 \
  -f "$ROOT_DIR/docker-compose.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.monitoring.yml" \
  -f "$ROOT_DIR/monitoring/vault/docker-compose.override.stage6.vault.yml")

KEYS_FILE="$SECRETS_DIR/vault-keys.txt"

if [[ -f "$KEYS_FILE" ]]; then
  echo "\"$KEYS_FILE\" already exists. Refusing to overwrite." >&2
  exit 1
fi

"${COMPOSE_CMD[@]}" up -d vault >/dev/null

VAULT_CMD=("${COMPOSE_CMD[@]}" exec -T vault env VAULT_ADDR=https://127.0.0.1:8200 VAULT_CACERT=/vault/tls/ca.pem)

STATUS_JSON=$("${VAULT_CMD[@]}" vault status -format=json 2>/dev/null || true)
if [[ -n "$STATUS_JSON" ]] && jq -e '.initialized' <<<"$STATUS_JSON" >/dev/null 2>&1; then
  if [[ $(jq -r '.initialized' <<<"$STATUS_JSON") == "true" ]]; then
    echo "Vault is already initialized" >&2
    exit 1
  fi
fi

"${VAULT_CMD[@]}" vault operator init -key-shares=5 -key-threshold=3 >"$KEYS_FILE"
chmod 600 "$KEYS_FILE"

printf 'Vault initialised. Unseal keys and root token stored at %s\n' "$KEYS_FILE"
