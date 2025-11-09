# Vault Operations - CLI Reference

Систематизированный справочник команд для администрирования HashiCorp Vault.

---

## 📋 Содержание

1. [Initialization & Unsealing](#initialization--unsealing)
2. [Status & Health](#status--health)
3. [KV Operations](#kv-operations)
4. [AppRole Management](#approle-management)
5. [Policy Management](#policy-management)
6. [Token Management](#token-management)
7. [Snapshot & Backup](#snapshot--backup)
8. [Audit](#audit)
9. [TLS & Security](#tls--security)
10. [Troubleshooting](#troubleshooting)

---

## 1. Initialization & Unsealing

### Initialize Vault

```bash
# Standard init (5 keys, threshold 3)
vault operator init -key-shares=5 -key-threshold=3

# Init with JSON output (recommended)
vault operator init -key-shares=5 -key-threshold=3 -format=json | tee vault-init-output.json

# Init with PGP keys (advanced security)
vault operator init \
    -key-shares=5 \
    -key-threshold=3 \
    -pgp-keys="keybase:user1,keybase:user2,..."
```

### Unseal Vault

```bash
# Manual unseal (need 3 keys)
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>

# Unseal with piped key
echo "key_here" | vault operator unseal -

# Check unseal progress
vault status | grep "Unseal Progress"
```

### Seal Vault

```bash
# Seal Vault (requires root or sudo token)
vault operator seal

# Seal with reason
vault operator seal -format=json
```

### Rekey Operation

```bash
# Start rekey (change unseal keys)
vault operator rekey -init -key-shares=5 -key-threshold=3

# Provide old keys
vault operator rekey -key=<old_key1>
vault operator rekey -key=<old_key2>
vault operator rekey -key=<old_key3>

# Cancel rekey
vault operator rekey -cancel
```

---

## 2. Status & Health

### Vault Status

```bash
# Basic status
vault status

# JSON output
vault status -format=json

# Check specific fields
vault status -format=json | jq '.sealed'
vault status -format=json | jq '.version'

# Check via API
curl -s http://127.0.0.1:8200/v1/sys/health

# HTTPS with self-signed cert
curl -sk https://127.0.0.1:8200/v1/sys/health
```

### Health Endpoints

```bash
# Health check (unsealed and initialized)
curl http://127.0.0.1:8200/v1/sys/health

# Response codes:
# 200 - unsealed and active
# 429 - unsealed and standby
# 472 - disaster recovery mode
# 473 - performance standby
# 501 - not initialized
# 503 - sealed

# Health with parameters
curl "http://127.0.0.1:8200/v1/sys/health?standbyok=true&sealedcode=200"
```

### Metrics

```bash
# Prometheus format
curl http://127.0.0.1:8200/v1/sys/metrics?format=prometheus

# JSON format
curl http://127.0.0.1:8200/v1/sys/metrics

# Specific metric
curl -s http://127.0.0.1:8200/v1/sys/metrics?format=prometheus | \
    grep vault_core_unsealed
```

---

## 3. KV Operations

### List Secrets

```bash
# List all paths in engine
vault kv list zakupai/

# List specific path
vault kv list zakupai/gateway/

# List recursively (custom script)
for path in $(vault kv list -format=json zakupai/ | jq -r '.[]'); do
    echo "zakupai/$path"
    vault kv list "zakupai/$path" 2>/dev/null || true
done
```

### Read Secrets

```bash
# Read secret
vault kv get zakupai/gateway/db

# JSON output
vault kv get -format=json zakupai/gateway/db

# Extract specific field
vault kv get -format=json zakupai/gateway/db | jq -r '.data.data.password'

# Read specific version
vault kv get -version=2 zakupai/gateway/db

# Read metadata
vault kv metadata get zakupai/gateway/db
```

### Write Secrets

```bash
# Write new secret
vault kv put zakupai/gateway/db \
    host="postgres" \
    port="5432" \
    database="zakupai" \
    username="user" \
    password="pass"

# Write from file
vault kv put zakupai/gateway/config @config.json

# Write from stdin
cat <<EOF | vault kv put zakupai/gateway/api -
{
  "api_key": "abc123",
  "api_secret": "xyz789"
}
EOF

# Patch (update specific fields)
vault kv patch zakupai/gateway/db password="new_password"
```

### Delete & Restore

```bash
# Soft delete (can be restored)
vault kv delete zakupai/gateway/old-config

# Delete specific version
vault kv delete -versions=2 zakupai/gateway/db

# Permanently delete (unrecoverable)
vault kv destroy -versions=2 zakupai/gateway/db

# Restore deleted secret
vault kv undelete -versions=2 zakupai/gateway/db

# Metadata operations
vault kv metadata delete zakupai/gateway/old-config
```

### Versioning

```bash
# Enable versioning
vault kv enable-versioning zakupai/

# Set max versions
vault kv metadata put -max-versions=10 zakupai/gateway/db

# Get all versions
vault kv metadata get zakupai/gateway/db

# Rollback to previous version
OLD_DATA=$(vault kv get -version=1 -format=json zakupai/gateway/db | jq '.data.data')
echo "$OLD_DATA" | vault kv put zakupai/gateway/db -
```

---

## 4. AppRole Management

### Create AppRole

```bash
# Create new AppRole
vault write auth/approle/role/my-service \
    token_ttl=1h \
    token_max_ttl=24h \
    secret_id_ttl=0 \
    token_policies="my-service-policy"

# With CIDR restriction
vault write auth/approle/role/my-service \
    token_ttl=1h \
    token_max_ttl=24h \
    secret_id_ttl=0 \
    token_policies="my-service-policy" \
    secret_id_bound_cidrs="10.0.0.0/8"
```

### Get Role ID & Secret ID

```bash
# Get Role ID
vault read auth/approle/role/my-service/role-id

# Get Role ID (JSON)
ROLE_ID=$(vault read -format=json auth/approle/role/my-service/role-id | jq -r '.data.role_id')

# Generate Secret ID
vault write -f auth/approle/role/my-service/secret-id

# Generate Secret ID with metadata
vault write auth/approle/role/my-service/secret-id \
    metadata="environment=production"

# Generate Secret ID (JSON)
SECRET_ID=$(vault write -f -format=json auth/approle/role/my-service/secret-id | jq -r '.data.secret_id')
```

### List & Inspect

```bash
# List all AppRoles
vault list auth/approle/role

# Read AppRole configuration
vault read auth/approle/role/my-service

# List Secret ID accessors
vault list auth/approle/role/my-service/secret-id

# Inspect specific Secret ID accessor
vault write auth/approle/role/my-service/secret-id/lookup \
    secret_id_accessor=<accessor>
```

### Login with AppRole

```bash
# Login
vault write auth/approle/login \
    role_id="$ROLE_ID" \
    secret_id="$SECRET_ID"

# Login and extract token
VAULT_TOKEN=$(vault write -format=json auth/approle/login \
    role_id="$ROLE_ID" \
    secret_id="$SECRET_ID" | jq -r '.auth.client_token')

# Use token
VAULT_TOKEN=$VAULT_TOKEN vault kv get zakupai/my-service/db
```

### Revoke & Destroy

```bash
# Destroy specific Secret ID
vault write auth/approle/role/my-service/secret-id-accessor/destroy \
    secret_id_accessor=<accessor>

# Delete AppRole
vault delete auth/approle/role/my-service
```

---

## 5. Policy Management

### Create Policy

```bash
# From file
vault policy write my-service-policy my-service-policy.hcl

# From stdin
vault policy write my-service-policy - <<EOF
path "zakupai/my-service/*" {
  capabilities = ["read", "list"]
}
EOF
```

### List & Read Policies

```bash
# List all policies
vault policy list

# Read policy
vault policy read my-service-policy

# Format as HCL
vault policy read -format=hcl my-service-policy
```

### Test Policy

```bash
# Check token capabilities
vault token capabilities zakupai/my-service/db

# Check specific token capabilities
vault token capabilities <token> zakupai/my-service/db

# Test with specific policy
vault policy fmt my-service-policy.hcl
```

### Delete Policy

```bash
# Delete policy
vault policy delete my-service-policy
```

---

## 6. Token Management

### Create Token

```bash
# Create root token (emergency only)
vault token create -policy=root

# Create token with specific policy
vault token create -policy=my-service-policy

# Create token with TTL
vault token create -policy=my-service-policy -ttl=1h

# Create orphan token
vault token create -orphan -policy=my-service-policy

# Create token with metadata
vault token create -policy=my-service-policy \
    -metadata="environment=production" \
    -metadata="service=gateway"
```

### Token Lookup

```bash
# Lookup current token
vault token lookup

# Lookup specific token
vault token lookup <token>

# Lookup self (authenticated)
vault token lookup-self

# Check token capabilities
vault token capabilities zakupai/gateway/db
```

### Token Renewal

```bash
# Renew current token
vault token renew

# Renew specific token
vault token renew <token>

# Renew with specific increment
vault token renew -increment=1h <token>
```

### Token Revocation

```bash
# Revoke current token
vault token revoke -self

# Revoke specific token
vault token revoke <token>

# Revoke all tokens for accessor
vault token revoke -accessor <accessor>

# Revoke all tokens under path
vault token revoke -mode=path auth/approle
```

---

## 7. Snapshot & Backup

### Create Snapshot

```bash
# Create Raft snapshot (if using Raft storage)
vault operator raft snapshot save backup.snap

# Check snapshot
file backup.snap
ls -lh backup.snap
```

### Restore Snapshot

```bash
# Restore from snapshot
vault operator raft snapshot restore backup.snap

# Force restore (ignore warnings)
vault operator raft snapshot restore -force backup.snap
```

### Backup KV Data

```bash
# Export all secrets (custom script)
#!/bin/bash
for path in $(vault kv list -format=json zakupai/ | jq -r '.[]'); do
    echo "Backing up zakupai/$path"
    vault kv get -format=json "zakupai/$path" > "backup-${path//\//-}.json"
done

# Backup with timestamp
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
vault kv get -format=json zakupai/gateway/db > "backup-gateway-db-$TIMESTAMP.json"
```

### Restore KV Data

```bash
# Restore secret from file
vault kv put zakupai/gateway/db @backup-gateway-db.json

# Restore with transformation
jq '.data.data' backup-gateway-db.json | vault kv put zakupai/gateway/db -
```

---

## 8. Audit

### Enable Audit

```bash
# Enable file audit
vault audit enable file file_path=/vault/logs/audit.log

# Enable with log rotation
vault audit enable file \
    file_path=/vault/logs/audit.log \
    log_raw=false \
    hmac_accessor=true \
    mode=0600

# Enable syslog audit
vault audit enable syslog tag="vault" facility="LOCAL7"
```

### List Audit Devices

```bash
# List all audit devices
vault audit list

# Detailed list
vault audit list -detailed
```

### Disable Audit

```bash
# Disable audit device
vault audit disable file/

# Disable specific device
vault audit disable syslog/
```

### Query Audit Log

```bash
# View recent entries
tail -100 /vault/logs/audit.log | jq

# Filter by operation
grep '"operation":"read"' /vault/logs/audit.log | jq

# Filter by path
grep '"path":"zakupai/gateway/db"' /vault/logs/audit.log | jq

# Count by user
jq -r '.auth.display_name' /vault/logs/audit.log | sort | uniq -c | sort -rn

# Failed requests
jq 'select(.error != null and .error != "")' /vault/logs/audit.log
```

---

## 9. TLS & Security

### Generate TLS Certificate

```bash
# Self-signed certificate (development)
openssl req -x509 -nodes -newkey rsa:4096 -days 365 \
    -keyout vault-key.pem \
    -out vault-cert.pem \
    -subj "/CN=vault.zakupai.local" \
    -addext "subjectAltName=DNS:vault.zakupai.local,DNS:localhost,IP:127.0.0.1"

# Set permissions
chmod 600 vault-key.pem
chmod 644 vault-cert.pem
```

### Verify Certificate

```bash
# Check certificate details
openssl x509 -in vault-cert.pem -text -noout

# Check expiry
openssl x509 -in vault-cert.pem -noout -enddate

# Check if expires in 30 days
openssl x509 -in vault-cert.pem -noout -checkend 2592000

# Verify certificate chain
openssl verify vault-cert.pem
```

### Test TLS Connection

```bash
# Test HTTPS connection
curl -v https://127.0.0.1:8200/v1/sys/health

# Test with specific cert
curl --cacert vault-cert.pem https://vault.zakupai.local:8200/v1/sys/health

# Test with client certificate
curl --cert client-cert.pem --key client-key.pem \
    https://vault.zakupai.local:8200/v1/sys/health

# OpenSSL s_client
openssl s_client -connect 127.0.0.1:8200 -servername vault.zakupai.local
```

---

## 10. Troubleshooting

### Debug Logging

```bash
# Enable debug logging
export VAULT_LOG_LEVEL=debug
vault status

# Trace level (very verbose)
export VAULT_LOG_LEVEL=trace
vault status

# Check server logs
docker logs vault -f

# Filter for errors
docker logs vault --tail 100 | grep -i error
```

### Connection Issues

```bash
# Test connectivity
curl -v http://127.0.0.1:8200/v1/sys/health

# Check if port is open
nc -zv 127.0.0.1 8200
telnet 127.0.0.1 8200

# Check Docker network
docker network inspect backend

# Test from inside container
docker exec vault nc -zv vault.zakupai.local 8200
```

### Permission Issues

```bash
# Check current token
vault token lookup

# Check token capabilities
vault token capabilities zakupai/gateway/db

# List policies
vault token lookup | grep policies

# Read policy
vault policy read gateway-policy

# Test with specific token
VAULT_TOKEN=<token> vault kv get zakupai/gateway/db
```

### Performance Issues

```bash
# Check metrics
curl -s http://127.0.0.1:8200/v1/sys/metrics?format=prometheus | \
    grep vault_core_handle_request

# Check storage latency
curl -s http://127.0.0.1:8200/v1/sys/metrics?format=prometheus | \
    grep vault_storage

# Check container resources
docker stats vault --no-stream

# Check host system
top -b -n 1 | grep vault
iostat -x 1 5
```

### Seal Issues

```bash
# Check seal status
vault status | grep Sealed

# Check logs for seal events
docker logs vault | grep -i seal

# Test auto-unseal
docker restart vault
sleep 30
vault status

# Manual unseal with diagnostics
vault operator unseal -verbose <key>
```

---

## Quick Reference Card

### Most Used Commands

```bash
# Status
vault status
vault status -format=json | jq '.sealed'

# Read secret
vault kv get zakupai/service/path

# Write secret
vault kv put zakupai/service/path key=value

# Login with AppRole
vault write auth/approle/login role_id=$ROLE_ID secret_id=$SECRET_ID

# Create token
vault token create -policy=my-policy

# List policies
vault policy list

# Check health
curl http://127.0.0.1:8200/v1/sys/health

# Audit log
tail -f /vault/logs/audit.log | jq
```

---

**Автор:** ZakupAI DevOps Team
**Версия:** 1.0
**Дата:** 2025-11-07
