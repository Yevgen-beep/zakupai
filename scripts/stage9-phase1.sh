#!/usr/bin/env bash
# Stage 9 — Phase 1 (Quick Wins, PROD-ready)
set -euo pipefail

echo "=== 🚀 Stage 9 — Phase 1 (Quick Wins, PROD-ready) ==="

# --------- CONFIG ---------
VAULT_ADDR="https://vault:8200"
export VAULT_SKIP_VERIFY=true
export VAULT_ADDR

ROOT_TOKEN_FILE="monitoring/vault/creds/root_token.txt"
POLICY_FILE="monitoring/vault/policies/zakupai-policy.hcl"
GW_CONF="gateway/nginx.prod.conf"
CREDS_DIR="monitoring/vault/creds"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="logs/stage9-phase1-${TIMESTAMP}.log"
BACKUP_DIR="backups/stage9-phase1-${TIMESTAMP}"

mkdir -p logs backups "$BACKUP_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "Лог:    $LOG_FILE"
echo "Backup: $BACKUP_DIR"
echo ""

# --------- [0] ENV CHECK ---------
echo "[0/10] Проверка окружения..."

if ! command -v jq >/dev/null 2>&1; then
  echo "❌ Не найден jq (apt install jq)"
  exit 1
fi

if ! docker ps --filter "name=zakupai-vault" --filter "status=running" | grep -q zakupai-vault; then
  echo "❌ zakupai-vault не запущен!"
  exit 1
fi

# --------- Wait Vault ---------
echo "⏳ Ожидание готовности Vault (до 60 сек)..."

MAX_WAIT=60
for i in $(seq 1 $MAX_WAIT); do
  if docker exec -e VAULT_SKIP_VERIFY=true zakupai-vault \
       vault status >/dev/null 2>&1; then
    echo "✓ Vault отвечает на vault status [${i}s]"
    break
  fi

  if [[ $i -eq $MAX_WAIT ]]; then
    echo "❌ Vault не готов после ${MAX_WAIT}s"
    docker logs zakupai-vault --tail=50
    exit 1
  fi

  sleep 1
done

# --------- [root token] ---------
if [[ ! -f "$ROOT_TOKEN_FILE" ]]; then
  echo "❌ Нет файла root_token.txt"
  exit 1
fi

export VAULT_TOKEN=$(cat "$ROOT_TOKEN_FILE")
echo "✓ Root token найден (${VAULT_TOKEN:0:8}...)"

# --------- sealed-state ---------
SEALED=$(docker exec \
  -e VAULT_SKIP_VERIFY=true \
  -e VAULT_ADDR=https://vault:8200 \
  -e VAULT_TOKEN="$VAULT_TOKEN" \
  zakupai-vault \
  vault status -format=json | jq -r '.sealed')

if [[ "$SEALED" != "false" ]]; then
  echo "❌ Vault запечатан (sealed=$SEALED)"
  exit 1
fi

echo "✓ Vault unsealed"

# --------- [1/10] Vault Status ---------
echo "[1/10] Проверка состояния Vault..."
docker exec -e VAULT_SKIP_VERIFY=true -e VAULT_TOKEN="$VAULT_TOKEN" zakupai-vault \
  vault status
echo "✓ Vault status OK"

# --------- [2/10] Enable KV v2 ---------
echo "[2/10] Включаем KV v2 по пути zakupai/ ..."

if docker exec -e VAULT_SKIP_VERIFY=true -e VAULT_TOKEN="$VAULT_TOKEN" zakupai-vault \
    vault secrets list -format=json | jq -e '."zakupai/"' >/dev/null 2>&1; then
    echo "(i) zakupai/ уже включён"
else
    docker exec -e VAULT_SKIP_VERIFY=true -e VAULT_TOKEN="$VAULT_TOKEN" zakupai-vault \
      vault secrets enable -path=zakupai kv-v2
    echo "✓ zakupai/ включён"
fi

# --------- [3/10] Create structure ---------
echo "[3/10] Создание структуры zakupai/config/*..."
for path in db redis app; do
  docker exec -e VAULT_SKIP_VERIFY=true -e VAULT_TOKEN="$VAULT_TOKEN" zakupai-vault \
    vault kv put "zakupai/config/$path" placeholder=true >/dev/null
done
echo "✓ Структура создана"

# --------- [4/10] Enable AppRole ---------
echo "[4/10] Включаем AppRole..."
if docker exec -e VAULT_SKIP_VERIFY=true -e VAULT_TOKEN="$VAULT_TOKEN" zakupai-vault \
     vault auth list -format=json | jq -e '."approle/"' >/dev/null 2>&1; then
   echo "(i) AppRole уже включён"
else
   docker exec -e VAULT_SKIP_VERIFY=true -e VAULT_TOKEN="$VAULT_TOKEN" zakupai-vault \
     vault auth enable approle
   echo "✓ AppRole включён"
fi

# --------- [5/10] Policy ---------
echo "[5/10] Обновление политики zakupai-policy..."
docker exec -e VAULT_SKIP_VERIFY=true -e VAULT_TOKEN="$VAULT_TOKEN" zakupai-vault sh -c "
cat > /tmp/policy.hcl <<'EOF'
$(cat "$POLICY_FILE")
EOF
vault policy write zakupai-policy /tmp/policy.hcl
"
echo "✓ Политика обновлена"

# --------- [6/10] Create AppRole ---------
echo "[6/10] Создание AppRole zakupai-services..."
docker exec -e VAULT_SKIP_VERIFY=true -e VAULT_TOKEN="$VAULT_TOKEN" zakupai-vault \
  vault write auth/approle/role/zakupai-services \
    token_policies="zakupai-policy" \
    token_ttl="1h" \
    token_max_ttl="4h" \
    secret_id_ttl="24h" >/dev/null

echo "✓ AppRole создан"

# --------- [7/10] Save RoleID/SecretID ---------
echo "[7/10] Получение RoleID и SecretID..."
ROLE_ID=$(docker exec -e VAULT_SKIP_VERIFY=true -e VAULT_TOKEN="$VAULT_TOKEN" zakupai-vault \
  vault read -field=role_id auth/approle/role/zakupai-services/role-id)

SECRET_ID=$(docker exec -e VAULT_SKIP_VERIFY=true -e VAULT_TOKEN="$VAULT_TOKEN" zakupai-vault \
  vault write -f -field=secret_id auth/approle/role/zakupai-services/secret-id)

mkdir -p "$CREDS_DIR"
echo "$ROLE_ID" > "$CREDS_DIR/zakupai-services_role_id.txt"
echo "$SECRET_ID" > "$CREDS_DIR/zakupai-services_secret_id.txt"
chmod 600 "$CREDS_DIR"/zakupai-services_*id.txt

echo "✓ Credentials сохранены"

# --------- [8/10] Gateway health ---------
echo "[8/10] Добавление /vault/health в gateway..."

cp "$GW_CONF" "$BACKUP_DIR/nginx.prod.conf.backup"

if grep -q "location /vault/health" "$GW_CONF"; then
  echo "(i) Уже существует"
else
cat >> "$GW_CONF" <<'EOF'

  # --- Vault healthcheck (added by Stage 9) ---
  location /vault/health {
      proxy_pass https://vault:8200/v1/sys/health;
      proxy_ssl_verify off;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
  }
EOF
  echo "✓ /vault/health добавлен"
  docker compose restart gateway
fi

# --------- [9/10] Networks cleanup ---------
echo "[9/10] Очистка Docker сетей..."

UNUSED=$(docker network ls -q -f "name=zakupai" | while read -r net; do
  if [[ $(docker network inspect "$net" -f '{{len .Containers}}') -eq 0 ]]; then
    echo "$net"
  fi
done)

if [[ -n "$UNUSED" ]]; then
  echo "$UNUSED" | xargs docker network rm || true
  echo "✓ Неиспользуемые сети удалены"
else
  echo "(i) Нечего удалять"
fi

docker network ls | grep zakupai || echo "(нет zakupai сетей)"

# --------- [10/10] Smoke test ---------
# --------- [10/10] Smoke test ---------
echo "[10/10] Smoke test /vault/health..."

sleep 2

# Берём сырой ответ от gateway
RAW=$(curl -sS -m 5 http://localhost:8000/vault/health || echo "")

echo "→ Ответ /vault/health:"
echo "$RAW"
echo

# Пытаемся распарсить как JSON
if echo "$RAW" | jq . >/dev/null 2>&1; then
  echo "✓ Ответ выглядит как JSON"
else
  echo "❌ Ответ не JSON (или пустой), healthcheck не пройден"
  exit 1
fi

# Проверяем initialized/sealed
if echo "$RAW" | jq -e '.initialized == true and .sealed == false' >/dev/null 2>&1; then
  echo "✅ /vault/health: initialized=true, sealed=false — OK"
else
  echo "❌ Healthcheck: JSON получен, но флаги не совпадают:"
  echo "$RAW" | jq . || true
  exit 1
fi

echo ""
echo "=== ✅ ФАЗА 1 ЗАВЕРШЕНА ==="
echo "Следующий шаг → ФАЗА 2 (миграция сервисов на hvac)"
echo ""


