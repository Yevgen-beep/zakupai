#!/usr/bin/env bash
set -euo pipefail

RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
BLUE="\033[0;34m"
NC="\033[0m"

log() {
  local level="$1"; shift
  printf "%b[%s]%b %s\n" "${BLUE}" "${level}" "${NC}" "$*"
}

log_success() {
  printf "%b[OK]%b %s\n" "${GREEN}" "${NC}" "$*"
}

log_warn() {
  printf "%b[WARN]%b %s\n" "${YELLOW}" "${NC}" "$*"
}

log_error() {
  printf "%b[ERROR]%b %s\n" "${RED}" "${NC}" "$*" >&2
}

die() {
  log_error "$@"
  exit 1
}

trap 'log_error "Script failed on line ${LINENO}. Check the output above for details."' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CREDS_DIR="${REPO_ROOT}/monitoring/vault/creds"
ACCESS_FILE="${CREDS_DIR}/b2_access_key_id"
SECRET_FILE="${CREDS_DIR}/b2_secret_key"
COMPOSE_BASE=(-f "${REPO_ROOT}/docker-compose.yml" -f "${REPO_ROOT}/docker-compose.override.stage9.vault-prod.yml")
GITIGNORE_FILE="${REPO_ROOT}/.gitignore"

umask 077

log "INFO" "=== Fixing Vault B2 Credentials ==="

if ! command -v docker >/dev/null 2>&1; then
  die "docker command not found. Install Docker before running this script."
fi

mkdir -p "${CREDS_DIR}"

ensure_gitignore_entry() {
  local entry="monitoring/vault/creds/b2_*"
  if [[ ! -f "${GITIGNORE_FILE}" ]]; then
    log_warn ".gitignore not found at ${GITIGNORE_FILE}. Create it to keep credentials out of git."
    return
  fi
  if grep -Fxq "${entry}" "${GITIGNORE_FILE}"; then
    log "INFO" ".gitignore already contains ${entry}"
  else
    printf '\n%s\n' "${entry}" >> "${GITIGNORE_FILE}"
    log_warn "Added ${entry} to .gitignore to prevent committing credentials."
  fi
}

ensure_gitignore_entry

if [[ -f "${ACCESS_FILE}" ]]; then
  CURRENT_KEY_ID="$(tr -d '[:space:]' < "${ACCESS_FILE}")"
  CURRENT_LEN=${#CURRENT_KEY_ID}
  if (( CURRENT_LEN > 0 )); then
    if (( CURRENT_LEN != 25 )); then
      log_warn "Current Key ID (${CURRENT_KEY_ID}) is ${CURRENT_LEN} characters. Expected 25."
    else
      log "INFO" "Current Key ID: ${CURRENT_KEY_ID} (${CURRENT_LEN} chars)"
    fi
  else
    log_warn "Current Key ID file exists but is empty."
  fi
else
  log_warn "No existing b2_access_key_id file found. A new one will be created."
fi

KEY_ID=""
KEY_SECRET=""

prompt_credentials() {
  local raw
  while true; do
    read -r -p "Enter NEW B2 Application Key ID (25 hex chars): " raw
    KEY_ID="$(printf '%s' "${raw}" | tr -d '[:space:]')"
    if [[ -z "${KEY_ID}" ]]; then
      log_error "Key ID cannot be empty."
      continue
    fi
    if [[ ! "${KEY_ID}" =~ ^[0-9a-fA-F]{25}$ ]]; then
      log_error "Key ID must be exactly 25 hexadecimal characters. Received ${#KEY_ID} chars."
      continue
    fi
    break
  done

  while true; do
    read -r -s -p "Enter NEW B2 Application Key (31+ chars): " raw
    printf "\n"
    KEY_SECRET="$(printf '%s' "${raw}" | tr -d '[:space:]')"
    if [[ -z "${KEY_SECRET}" ]]; then
      log_error "Application Key cannot be empty."
      continue
    fi
    # Backblaze application keys may include '/', '+', '=' and other symbols; enforce only minimum length.
    if (( ${#KEY_SECRET} < 31 )); then
      log_error "Application Key must be at least 31 characters. Received ${#KEY_SECRET}."
      continue
    fi
    break
  done
}

prompt_credentials
log_success "Credential validation passed."

backup_file() {
  local file_path="$1"
  if [[ -f "${file_path}" ]]; then
    local backup_path="${file_path}.backup.$(date +%Y%m%d%H%M%S)"
    cp "${file_path}" "${backup_path}"
    log "INFO" "Backup created: ${backup_path}"
  fi
}

log "INFO" "Backing up existing credential files (if present)..."
backup_file "${ACCESS_FILE}"
backup_file "${SECRET_FILE}"

log "INFO" "Writing new credential files with strict permissions..."
printf '%s' "${KEY_ID}" > "${ACCESS_FILE}"
printf '%s' "${KEY_SECRET}" > "${SECRET_FILE}"
chmod 600 "${ACCESS_FILE}" "${SECRET_FILE}"
log_success "Credential files updated at ${ACCESS_FILE} and ${SECRET_FILE}"

compose_cmd() {
  docker compose "${COMPOSE_BASE[@]}" "$@"
}

log "INFO" "Recreating ZakupAI Vault container..."
if ! compose_cmd down vault 2>/dev/null; then
  log_warn "docker compose down with explicit service failed. Running full down instead."
  compose_cmd down
fi

if docker ps -a --format '{{.Names}}' | grep -q '^zakupai-vault$'; then
  docker rm -f zakupai-vault >/dev/null
  log "INFO" "Removed existing zakupai-vault container."
else
  log_warn "zakupai-vault container not present; nothing to remove."
fi

compose_cmd up -d vault --force-recreate
log_success "Vault container recreated."

log "INFO" "Waiting 15 seconds for Vault to initialize..."
sleep 15

log "INFO" "Collecting recent logs (last 200 lines)..."
LOG_OUTPUT="$(docker logs zakupai-vault 2>&1 | tail -n 200)"
printf "%s\n" "${LOG_OUTPUT}"

status_container=$(docker ps --filter "name=zakupai-vault" --format '{{.Status}}' || true)
if [[ -z "${status_container}" ]]; then
  log_warn "zakupai-vault container is not running."
fi

if grep -q "InvalidAccessKeyId" <<< "${LOG_OUTPUT}"; then
  die "❌ FAILED: Vault reports InvalidAccessKeyId. Check the credentials and try again."
fi

if grep -qi "NoSuchBucket" <<< "${LOG_OUTPUT}"; then
  die "❌ FAILED: Backblaze reports the bucket is missing. Verify storage bucket configuration."
fi

if grep -q "Vault server started" <<< "${LOG_OUTPUT}"; then
  log_success "Vault server started successfully."
else
  die "❌ FAILED: 'Vault server started' not detected. Review logs above."
fi

log_success "=== SUCCESS === Vault is now connected to Backblaze B2."
log "INFO" "Next steps: 1) Unseal Vault if required. 2) Enable audit logging. 3) Continue Stage 9 migration."
