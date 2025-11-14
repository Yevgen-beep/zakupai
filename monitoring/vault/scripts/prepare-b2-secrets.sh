#!/usr/bin/env bash
set -euo pipefail

CREDS_DIR="monitoring/vault/creds"
mkdir -p "${CREDS_DIR}"

read -rp "Введите B2 Application Key ID: " KEY_ID
read -rsp "Введите B2 Application Key (секрет): " KEY_SECRET
echo

echo "${KEY_ID}" > "${CREDS_DIR}/b2_access_key_id"
echo "${KEY_SECRET}" > "${CREDS_DIR}/b2_secret_key"

chmod 600 "${CREDS_DIR}/b2_access_key_id" "${CREDS_DIR}/b2_secret_key"

cat <<'MSG'
✅ B2 secrets files созданы (monitoring/vault/creds/)
➤ Эти файлы git-игнорятся, не коммить.
MSG
