# Vault Initialization Guide — ZakupAI

**⚠️ MANUAL PROCESS ONLY**
This guide describes the Vault initialization steps. **DO NOT run these commands automatically.**
All commands must be executed manually by a human operator with proper security clearance.

---

## 🎯 Overview

Vault initialization is a one-time process that:
1. Generates master keys and root token
2. Unseals the Vault
3. Enables secrets engines
4. Creates policies
5. Generates service tokens

**Security Level:** 🔴 **CRITICAL**
Only authorized personnel should perform these steps.

---

## 📋 Prerequisites

- Vault container running and accessible
- TLS certificates generated (if using config-tls.hcl)
- Terminal access to Docker host
- Secure storage for root token and unseal keys

---

## 🚀 Step 1: Start Vault in Sealed State

```bash
# Start Vault container
docker-compose -f docker-compose.yml \
  -f docker-compose.override.monitoring.yml \
  up -d vault

# Wait for Vault to be ready (will be sealed)
sleep 10

# Check Vault status (should show "sealed": true)
docker exec zakupai-vault vault status
```

Expected output:
```
Sealed: true
...
```

---

## 🔐 Step 2: Initialize Vault

**⚠️ This step generates master keys and root token. Run ONCE only.**

### Production Mode (5 keys, threshold 3):

```bash
docker exec zakupai-vault vault operator init \
  -key-shares=5 \
  -key-threshold=3 \
  -format=json > vault-init-output.json

# Display initialization output
cat vault-init-output.json | jq
```

### Development Mode (1 key, threshold 1):

```bash
docker exec zakupai-vault vault operator init \
  -key-shares=1 \
  -key-threshold=1 \
  -format=json > vault-init-output.json

# Display initialization output
cat vault-init-output.json | jq
```

### Extract Keys and Token:

```bash
# Extract root token
export VAULT_ROOT_TOKEN=$(cat vault-init-output.json | jq -r '.root_token')
echo "Root Token: ${VAULT_ROOT_TOKEN}"

# Extract unseal keys
cat vault-init-output.json | jq -r '.unseal_keys_b64[]' > vault-unseal-keys.txt

# Save to secure locations
echo "${VAULT_ROOT_TOKEN}" > monitoring/vault/creds/root.token
cp vault-unseal-keys.txt monitoring/vault/creds/unseal-keys.txt

# Set strict permissions
chmod 600 monitoring/vault/creds/*.token
chmod 600 monitoring/vault/creds/unseal-keys.txt
```

**🔒 CRITICAL: Securely store these files offline. Never commit to git.**

---

## 🔓 Step 3: Unseal Vault

Vault must be unsealed after initialization or restart.

### Production (threshold 3):

```bash
# Operator 1 provides key 1
docker exec zakupai-vault vault operator unseal <KEY_1>

# Operator 2 provides key 2
docker exec zakupai-vault vault operator unseal <KEY_2>

# Operator 3 provides key 3
docker exec zakupai-vault vault operator unseal <KEY_3>

# Verify unsealed
docker exec zakupai-vault vault status
```

### Development (threshold 1):

```bash
# Read unseal key
export UNSEAL_KEY=$(head -n1 vault-unseal-keys.txt)

# Unseal Vault
docker exec zakupai-vault vault operator unseal ${UNSEAL_KEY}

# Verify unsealed
docker exec zakupai-vault vault status
```

Expected output:
```
Sealed: false
...
```

---

## 🔧 Step 4: Login and Configure

```bash
# Login with root token
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault login ${VAULT_ROOT_TOKEN}

# Verify authentication
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault token lookup
```

---

## 📦 Step 5: Enable KV Secrets Engine

```bash
# Enable KV v2 at zakupai/ mount
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault secrets enable -path=zakupai kv-v2

# Verify
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault secrets list
```

Expected output:
```
Path          Type         ...
----          ----         ...
zakupai/      kv           ...
```

---

## 🔑 Step 6: Create Secrets

### Database Credentials:

```bash
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault kv put zakupai/db \
    POSTGRES_USER="zakupai_user" \
    POSTGRES_PASSWORD="$(openssl rand -base64 32)" \
    POSTGRES_DB="zakupai" \
    POSTGRES_HOST="zakupai-db" \
    POSTGRES_PORT="5432"

# Generate DATABASE_URL
DB_PASS=$(docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault kv get -field=POSTGRES_PASSWORD zakupai/db)

docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault kv patch zakupai/db \
    DATABASE_URL="postgresql://zakupai_user:${DB_PASS}@zakupai-db:5432/zakupai"
```

### API Keys:

```bash
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault kv put zakupai/api \
    API_KEY="$(openssl rand -hex 32)" \
    ZAKUPAI_API_KEY="$(openssl rand -hex 32)"
```

### Goszakup Token:

```bash
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault kv put zakupai/goszakup \
    GOSZAKUP_TOKEN="your-actual-goszakup-token-here"
```

### Monitoring Credentials:

```bash
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault kv put zakupai/monitoring \
    TELEGRAM_BOT_TOKEN="your-telegram-bot-token" \
    TELEGRAM_CHAT_ID="your-telegram-chat-id"
```

---

## 🛡️ Step 7: Create Policies

```bash
# Copy policies to container
docker cp monitoring/vault/policies zakupai-vault:/vault/

# Apply policies
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault policy write calc-service /vault/policies/calc-service-policy.hcl

docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault policy write risk-engine /vault/policies/risk-engine-policy.hcl

docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault policy write etl-service /vault/policies/etl-service-policy.hcl

docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault policy write monitoring /vault/policies/monitoring-policy.hcl

docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault policy write admin /vault/policies/admin-policy.hcl

# Verify policies
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault policy list
```

---

## 🎫 Step 8: Generate Service Tokens

### Calc Service Token:

```bash
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault token create \
    -policy=calc-service \
    -ttl=8760h \
    -display-name="calc-service" \
    -format=json | jq -r '.auth.client_token' \
    > monitoring/vault/creds/calc-service.token

chmod 600 monitoring/vault/creds/calc-service.token
```

### Risk Engine Token:

```bash
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault token create \
    -policy=risk-engine \
    -ttl=8760h \
    -display-name="risk-engine" \
    -format=json | jq -r '.auth.client_token' \
    > monitoring/vault/creds/risk-engine.token

chmod 600 monitoring/vault/creds/risk-engine.token
```

### ETL Service Token:

```bash
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault token create \
    -policy=etl-service \
    -ttl=8760h \
    -display-name="etl-service" \
    -format=json | jq -r '.auth.client_token' \
    > monitoring/vault/creds/etl-service.token

chmod 600 monitoring/vault/creds/etl-service.token
```

### Monitoring Token:

```bash
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault token create \
    -policy=monitoring \
    -ttl=8760h \
    -display-name="monitoring" \
    -format=json | jq -r '.auth.client_token' \
    > monitoring/vault/creds/monitoring.token

chmod 600 monitoring/vault/creds/monitoring.token
```

---

## 🔄 Step 9: Configure Services

Update `.env` or service environment variables:

```bash
# For calc-service
export VAULT_ADDR=https://vault:8200
export VAULT_TOKEN=$(cat monitoring/vault/creds/calc-service.token)
export VAULT_SKIP_VERIFY=false  # true for dev without TLS
export VAULT_CACERT=/vault-ca/ca.crt

# For risk-engine
export VAULT_ADDR=https://vault:8200
export VAULT_TOKEN=$(cat monitoring/vault/creds/risk-engine.token)
export VAULT_SKIP_VERIFY=false
export VAULT_CACERT=/vault-ca/ca.crt

# For etl-service
export VAULT_ADDR=https://vault:8200
export VAULT_TOKEN=$(cat monitoring/vault/creds/etl-service.token)
export VAULT_SKIP_VERIFY=false
export VAULT_CACERT=/vault-ca/ca.crt
```

Or add to `docker-compose.override.monitoring.yml`:

```yaml
services:
  calc-service:
    environment:
      VAULT_ADDR: https://vault:8200
      VAULT_TOKEN_FILE: /run/secrets/calc-service-token
    secrets:
      - calc-service-token

secrets:
  calc-service-token:
    file: ./monitoring/vault/creds/calc-service.token
```

---

## 🧪 Step 10: Verification

```bash
# Test service token
export VAULT_TOKEN=$(cat monitoring/vault/creds/calc-service.token)

docker exec -e VAULT_TOKEN=${VAULT_TOKEN} zakupai-vault \
  vault kv get zakupai/db

# Should return database credentials

# Restart services
docker-compose restart calc-service risk-engine etl-service

# Check logs
docker-compose logs calc-service | grep -i vault
docker-compose logs risk-engine | grep -i vault
docker-compose logs etl-service | grep -i vault

# Should see: "Vault bootstrap success"
```

---

## 🔒 Step 11: Secure Root Token

**CRITICAL SECURITY STEP**

```bash
# Revoke root token after setup
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault token revoke ${VAULT_ROOT_TOKEN}

# Or create a new admin token and revoke root
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault token create \
    -policy=admin \
    -ttl=24h \
    -display-name="admin-daily" \
    > monitoring/vault/creds/admin.token

# Then revoke root
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault token revoke ${VAULT_ROOT_TOKEN}

# Store root token offline, delete from server
rm monitoring/vault/creds/root.token
```

---

## 📊 File Permissions Summary

**⚠️ DO NOT RUN — DOCUMENTATION ONLY**

These commands show the correct permissions. Apply manually:

```bash
# TLS certificates
chmod 600 monitoring/vault/tls/server.key monitoring/vault/tls/ca.key
chmod 644 monitoring/vault/tls/server.crt monitoring/vault/tls/ca.crt

# Vault data directory (file storage)
chown -R 100:1000 monitoring/vault/data/
chmod 700 monitoring/vault/data/

# Token files
chown root:docker monitoring/vault/creds/*.token
chmod 600 monitoring/vault/creds/*.token

# Unseal keys
chown root:root monitoring/vault/creds/unseal-keys.txt
chmod 400 monitoring/vault/creds/unseal-keys.txt
```

---

## 🆘 Troubleshooting

### Vault is Sealed After Restart

```bash
# Unseal using saved keys
export UNSEAL_KEY=$(head -n1 vault-unseal-keys.txt)
docker exec zakupai-vault vault operator unseal ${UNSEAL_KEY}
```

### Token Expired

```bash
# Create new token with admin policy
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault token create -policy=calc-service -ttl=8760h
```

### Permission Denied

```bash
# Check policy assignment
docker exec -e VAULT_TOKEN=${YOUR_TOKEN} zakupai-vault \
  vault token lookup

# Verify policy allows access
docker exec -e VAULT_TOKEN=${VAULT_ROOT_TOKEN} zakupai-vault \
  vault policy read calc-service
```

---

## 🔐 Security Checklist

- [ ] Vault initialized with appropriate key shares (5 for prod, 1 for dev)
- [ ] Root token saved securely offline
- [ ] Unseal keys distributed to key holders
- [ ] Policies created for each service
- [ ] Service tokens generated with minimal privileges
- [ ] Root token revoked after initial setup
- [ ] TLS certificates properly configured (production)
- [ ] File permissions set correctly
- [ ] Audit logging enabled (production)
- [ ] Auto-unseal configured (production)
- [ ] Backup strategy in place
- [ ] `.gitignore` includes all token files

---

## 📚 References

- [Vault Initialization](https://developer.hashicorp.com/vault/docs/commands/operator/init)
- [Vault Policies](https://developer.hashicorp.com/vault/docs/concepts/policies)
- [KV Secrets Engine](https://developer.hashicorp.com/vault/docs/secrets/kv/kv-v2)
- [Token Authentication](https://developer.hashicorp.com/vault/docs/auth/token)

---

**Generated:** 2025-10-27
**ZakupAI DevOps Team**
**Security Level:** 🔴 CRITICAL
