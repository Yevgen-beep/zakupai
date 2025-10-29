#!/bin/sh
# Скрипт инициализации Vault для ZakupAI (Stage 7 — Phase 3)
# Повторный запуск безопасен: команды проверяют текущее состояние и не ломают уже настроенный Vault.

set -eu

# ⚙️ Базовые пути и параметры
VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
export VAULT_ADDR                                   # CLI внутри контейнера ходит на локальный Vault API

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
CREDS_DIR="/vault/creds"
INIT_FILE="${CREDS_DIR}/init.json"
POLICY_PATH="${SCRIPT_DIR}/policies/zakupai-policy.hcl"

umask 077                                              # Гарантируем приватные права на создаваемые файлы
mkdir -p "${CREDS_DIR}"

log() {
  # Логируем в единообразном формате для будущих аудит-скриптов
  printf '[vault-init] %s\n' "$*"
}

# 🔍 Чтение текущего статуса Vault (возможны коды 0/1/2/4; не считаем их ошибкой)
STATUS_JSON="$(vault status -format=json 2>/dev/null || true)"
initialized="$(printf '%s' "${STATUS_JSON:-false}" | jq -r '.initialized // false' 2>/dev/null || printf 'false')"
sealed="$(printf '%s' "${STATUS_JSON:-true}" | jq -r '.sealed // true' 2>/dev/null || printf 'true')"

if [ "${initialized}" != "true" ]; then
  log "Vault не инициализирован — выполняю vault operator init"
  vault operator init -key-shares=5 -key-threshold=3 -format=json > "${INIT_FILE}.tmp"
  mv "${INIT_FILE}.tmp" "${INIT_FILE}"
else
  log "Vault уже инициализирован — пропускаю init"
fi

if [ ! -f "${INIT_FILE}" ]; then
  log "❌ Не найден ${INIT_FILE}. Без него невозможно продолжить."
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  log "❌ jq не установлен. Добавьте его в образ Vault."
  exit 1
fi

UNSEAL_KEYS="$(jq -r '.unseal_keys_b64[]' "${INIT_FILE}" 2>/dev/null || true)"
ROOT_TOKEN="$(jq -r '.root_token' "${INIT_FILE}" 2>/dev/null || true)"

if [ -z "${ROOT_TOKEN}" ] || [ "${ROOT_TOKEN}" = "null" ]; then
  log "❌ В ${INIT_FILE} отсутствует Initial Root Token. Проверьте файл вручную."
  exit 1
fi

UNSEAL_COUNT="$(printf '%s\n' "${UNSEAL_KEYS}" | sed '/^$/d' | wc -l | tr -d ' ')"
if [ "${UNSEAL_COUNT:-0}" -lt 3 ]; then
  log "❌ Найдено недостаточно unseal-ключей (${UNSEAL_COUNT}). Проверьте содержимое ${INIT_FILE}."
  exit 1
fi

# 💾 Сохраняем ключи и токен в отдельные файлы (удобно монтировать в сервисы как read-only)
idx=1
printf '%s\n' "${UNSEAL_KEYS}" | while IFS= read -r key; do
  [ -n "${key}" ] || continue
  printf '%s\n' "${key}" > "${CREDS_DIR}/unseal_key_${idx}.txt"
  idx=$((idx + 1))
done
printf '%s\n' "${ROOT_TOKEN}" > "${CREDS_DIR}/root_token.txt"

# 🔓 Распечатка (unseal) — достаточно трёх ключей
if [ "${sealed}" = "true" ]; then
  log "Vault запечатан — выполняю unseal тремя ключами"
  count=0
  printf '%s\n' "${UNSEAL_KEYS}" | while [ "${count}" -lt 3 ]; do
    read -r key || break
    [ -n "${key}" ] || continue
    vault operator unseal "${key}" >/dev/null
    count=$((count + 1))
  done
else
  log "Vault уже в состоянии unsealed — пропускаю unseal"
fi

# 🛡️ Аутентификация для дальнейших операций (используем переменную окружения, а не vault login)
VAULT_TOKEN="${ROOT_TOKEN}"
export VAULT_TOKEN

# 🔐 Включаем auth backend AppRole
if ! vault auth list -format=json 2>/dev/null | grep -q '"approle/"'; then
  log "Включаю AppRole auth backend"
  vault auth enable approle >/dev/null
else
  log "AppRole уже включён"
fi

# 📦 Включаем KV v2 по пути zakupai
if ! vault secrets list -format=json 2>/dev/null | grep -q '"zakupai/"'; then
  log "Включаю KV v2 по пути zakupai/"
  vault secrets enable -path=zakupai kv-v2 >/dev/null
else
  log "KV zakupai/ уже включён"
fi

# 📜 Включаем PKI для будущих TLS-сертификатов
if ! vault secrets list -format=json 2>/dev/null | grep -q '"pki/"'; then
  log "Включаю PKI backend"
  vault secrets enable -path=pki pki >/dev/null
  vault secrets tune -max-lease-ttl=8760h pki >/dev/null   # 1 год для выдаваемых сертификатов
else
  log "PKI backend уже активен"
fi

# 🛡️ Политика доступа ZakupAI
if [ ! -f "${POLICY_PATH}" ]; then
  log "❌ Не найден файл политики ${POLICY_PATH}"
  exit 1
fi
log "Обновляю политику zakupai-policy"
vault policy write zakupai-policy "${POLICY_PATH}" >/dev/null

# 👥 Создаём AppRole для сервисов и Alertmanager
for role in etl-service calc-service risk-engine alertmanager; do
  log "Обновляю AppRole ${role}"
  vault write "auth/approle/role/${role}" \
    secret_id_ttl="24h" \
    token_ttl="1h" \
    token_max_ttl="4h" \
    token_policies="zakupai-policy" >/dev/null

  ROLE_ID="$(vault read -field=role_id "auth/approle/role/${role}/role-id")"
  printf '%s\n' "${ROLE_ID}" > "${CREDS_DIR}/${role}_role_id.txt"

  SECRET_ID="$(vault write -f -field=secret_id "auth/approle/role/${role}/secret-id")"
  printf '%s\n' "${SECRET_ID}" > "${CREDS_DIR}/${role}_secret_id.txt"
done

# 🔑 Тестовый секрет KV zakupai/app
log "Создаю/обновляю тестовый KV zakupai/app"
vault kv put zakupai/app \
  DATABASE_URL="postgresql://zakupai:zakupai@zakupai-db:5432/zakupai" \
  GOSZAKUP_TOKEN="dummy-goszakup-token" \
  TELEGRAM_BOT_TOKEN="dummy-bot-token" >/dev/null

# ✅ Вывод финального статуса
if vault status >/dev/null 2>&1; then
  log "Vault готов к работе."
else
  log "Предупреждение: vault status вернул ненулевой код, проверьте вручную."
fi

# 🔐 Выводим root token только в stdout с напоминанием — его нужно отозвать после настройки
printf 'Initial root token: %s\n' "${ROOT_TOKEN}"
printf '⚠️  После настройки выдайте операционный токен и отзовите root-токен!\n'

# 🧹 Удаляем переменную, чтобы root-token не остался в окружении контейнера
unset VAULT_TOKEN

exit 0
