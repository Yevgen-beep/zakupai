#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE_CMD=(docker compose --profile stage6 \
  -f "$ROOT_DIR/docker-compose.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.monitoring.yml" \
  -f "$ROOT_DIR/monitoring/vault/docker-compose.override.stage6.vault.yml")

CREDS_DIR="$ROOT_DIR/monitoring/vault/creds"
TLS_CA="$ROOT_DIR/monitoring/vault/tls/ca.pem"
TOKEN_FILE="$CREDS_DIR/service.token"
METRICS_TOKEN_FILE="$CREDS_DIR/metrics.token"
PROM_METRICS_DEST="$ROOT_DIR/monitoring/prometheus/vault-metrics.token"
ROOT_TOKEN_FILE="$CREDS_DIR/root.token"
UNSEAL_FILE="$ROOT_DIR/monitoring/vault/unseal.key"
INIT_JSON="$CREDS_DIR/init.json"
BACKUP_DIR="$ROOT_DIR/monitoring/vault/backups"

mkdir -p "$CREDS_DIR" "$BACKUP_DIR"
chmod 755 "$CREDS_DIR"

compose_exec() {
  "${COMPOSE_CMD[@]}" exec -T "$@"
}

log() {
  printf '==> %s\n' "$*"
}

log "Starting Vault container (stage6 profile)"
"${COMPOSE_CMD[@]}" up -d vault

log "Waiting for Vault API to respond"
for _ in $(seq 1 30); do
  if curl -sk --connect-timeout 2 https://localhost:8200/v1/sys/health >/dev/null; then
    break
  fi
  sleep 2
done

VAULT_STATUS=$(compose_exec vault sh -c 'VAULT_ADDR=https://127.0.0.1:8200 VAULT_CACERT=/vault/tls/ca.pem vault status -format=json' || true)
INITIALIZED=$(printf '%s' "$VAULT_STATUS" | jq -r '.initialized // false' 2>/dev/null || echo false)
SEALED=$(printf '%s' "$VAULT_STATUS" | jq -r '.sealed // true' 2>/dev/null || echo true)

if [[ $INITIALIZED != true ]]; then
  log "Initializing Vault (1 key share / threshold)"
  INIT_OUTPUT=$(compose_exec vault sh -c 'VAULT_ADDR=https://127.0.0.1:8200 VAULT_CACERT=/vault/tls/ca.pem vault operator init -key-shares=1 -key-threshold=1 -format=json')
  printf '%s\n' "$INIT_OUTPUT" > "$INIT_JSON"
  chmod 600 "$INIT_JSON"
  ROOT_TOKEN=$(printf '%s' "$INIT_OUTPUT" | jq -r '.root_token')
  UNSEAL_KEY=$(printf '%s' "$INIT_OUTPUT" | jq -r '.unseal_keys_b64[0]')
  printf '%s\n' "$UNSEAL_KEY" > "$UNSEAL_FILE"
  chmod 600 "$UNSEAL_FILE"
  printf '%s\n' "$ROOT_TOKEN" > "$ROOT_TOKEN_FILE"
  chmod 600 "$ROOT_TOKEN_FILE"
  log "Vault initialized; unseal key and root token stored."
else
  log "Vault already initialized"
  if [[ -f "$ROOT_TOKEN_FILE" ]]; then
    ROOT_TOKEN=$(<"$ROOT_TOKEN_FILE")
  else
    echo "Root token file missing; aborting." >&2
    exit 1
  fi
  if [[ -f "$UNSEAL_FILE" ]]; then
    UNSEAL_KEY=$(<"$UNSEAL_FILE")
  else
    echo "Unseal key file missing; aborting." >&2
    exit 1
  fi
fi

if [[ $SEALED == true ]]; then
  log "Unsealing Vault"
  compose_exec vault sh -c "VAULT_ADDR=https://127.0.0.1:8200 VAULT_CACERT=/vault/tls/ca.pem vault operator unseal $UNSEAL_KEY" >/dev/null
else
  log "Vault already unsealed"
fi

log "Enabling ZakupAI KV store"
compose_exec vault sh -c 'VAULT_ADDR=https://127.0.0.1:8200 VAULT_CACERT=/vault/tls/ca.pem VAULT_TOKEN='"$ROOT_TOKEN"' vault secrets enable -path=zakupai kv-v2' >/dev/null 2>&1 || true

log "Enabling audit log"
compose_exec vault sh -c 'VAULT_ADDR=https://127.0.0.1:8200 VAULT_CACERT=/vault/tls/ca.pem VAULT_TOKEN='"$ROOT_TOKEN"' vault audit enable -path=file file file_path=/vault/file/audit.log' >/dev/null 2>&1 || true

set -a
source "$ROOT_DIR/.env"
set +a

log "Syncing secrets from .env into Vault"
compose_exec vault env   VAULT_ADDR=https://127.0.0.1:8200   VAULT_CACERT=/vault/tls/ca.pem   VAULT_TOKEN="$ROOT_TOKEN"   POSTGRES_DB="$POSTGRES_DB"   POSTGRES_USER="$POSTGRES_USER"   POSTGRES_PASSWORD="$POSTGRES_PASSWORD"   DATABASE_URL="$DATABASE_URL"   sh -c "vault kv put zakupai/db POSTGRES_DB="$POSTGRES_DB" POSTGRES_USER="$POSTGRES_USER" POSTGRES_PASSWORD="$POSTGRES_PASSWORD" DATABASE_URL="$DATABASE_URL"" >/dev/null

compose_exec vault env   VAULT_ADDR=https://127.0.0.1:8200   VAULT_CACERT=/vault/tls/ca.pem   VAULT_TOKEN="$ROOT_TOKEN"   API_KEY="$API_KEY"   X_API_KEY="$X_API_KEY"   sh -c "vault kv put zakupai/api API_KEY="$API_KEY" X_API_KEY="$X_API_KEY"" >/dev/null

compose_exec vault env   VAULT_ADDR=https://127.0.0.1:8200   VAULT_CACERT=/vault/tls/ca.pem   VAULT_TOKEN="$ROOT_TOKEN"   GOSZAKUP_TOKEN="$GOSZAKUP_TOKEN"   GOSZAKUP_API_URL="$GOSZAKUP_API_URL"   sh -c "vault kv put zakupai/goszakup GOSZAKUP_TOKEN="$GOSZAKUP_TOKEN" GOSZAKUP_API_URL="$GOSZAKUP_API_URL"" >/dev/null

compose_exec vault env   VAULT_ADDR=https://127.0.0.1:8200   VAULT_CACERT=/vault/tls/ca.pem   VAULT_TOKEN="$ROOT_TOKEN"   TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN"   TELEGRAM_ADMIN_ID="$TELEGRAM_ADMIN_ID"   sh -c "vault kv put zakupai/telegram TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" TELEGRAM_ADMIN_ID="$TELEGRAM_ADMIN_ID"" >/dev/null

compose_exec vault env   VAULT_ADDR=https://127.0.0.1:8200   VAULT_CACERT=/vault/tls/ca.pem   VAULT_TOKEN="$ROOT_TOKEN"   B2_KEY_ID="$B2_KEY_ID"   B2_APP_KEY="$B2_APP_KEY"   B2_BUCKET="$B2_BUCKET"   B2_PREFIX="$B2_PREFIX"   BACKUP_RETENTION_DAYS="$BACKUP_RETENTION_DAYS"   sh -c "vault kv put zakupai/backup B2_KEY_ID="$B2_KEY_ID" B2_APP_KEY="$B2_APP_KEY" B2_BUCKET="$B2_BUCKET" B2_PREFIX="$B2_PREFIX" BACKUP_RETENTION_DAYS="$BACKUP_RETENTION_DAYS"" >/dev/null

log "Creating zakupai-services policy"
compose_exec vault env VAULT_ADDR=https://127.0.0.1:8200 VAULT_CACERT=/vault/tls/ca.pem VAULT_TOKEN="$ROOT_TOKEN" \
  sh -c 'printf "%s\n" "path \"zakupai/data/*\" { capabilities = [\"read\"] }" | vault policy write zakupai-services -' >/dev/null 2>&1 || true

log "Issuing service token"
SERVICE_TOKEN_JSON=$(compose_exec vault sh -c 'VAULT_ADDR=https://127.0.0.1:8200 VAULT_CACERT=/vault/tls/ca.pem VAULT_TOKEN='"$ROOT_TOKEN"' vault token create -policy=zakupai-services -period=720h -renewable=true -format=json')
SERVICE_TOKEN=$(printf '%s' "$SERVICE_TOKEN_JSON" | jq -r '.auth.client_token')
printf '%s\n' "$SERVICE_TOKEN" > "$TOKEN_FILE"
chmod 600 "$TOKEN_FILE"

log "Creating zakupai-metrics policy"
compose_exec vault env VAULT_ADDR=https://127.0.0.1:8200 VAULT_CACERT=/vault/tls/ca.pem VAULT_TOKEN="$ROOT_TOKEN" \
  sh -c 'printf "%s\n" "path \"sys/metrics\" { capabilities = [\"read\"] }" | vault policy write zakupai-metrics -' >/dev/null 2>&1 || true

log "Issuing metrics token"
METRICS_TOKEN_JSON=$(compose_exec vault sh -c 'VAULT_ADDR=https://127.0.0.1:8200 VAULT_CACERT=/vault/tls/ca.pem VAULT_TOKEN='"$ROOT_TOKEN"' vault token create -policy=zakupai-metrics -period=720h -renewable=true -format=json')
METRICS_TOKEN=$(printf '%s' "$METRICS_TOKEN_JSON" | jq -r '.auth.client_token')
printf '%s\n' "$METRICS_TOKEN" > "$METRICS_TOKEN_FILE"
chmod 644 "$METRICS_TOKEN_FILE"
cp "$METRICS_TOKEN_FILE" "$PROM_METRICS_DEST"
chmod 644 "$PROM_METRICS_DEST"

log "Vault bootstrap completed"
