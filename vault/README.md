# HashiCorp Vault for ZakupAI

Production-ready secrets management for ZakupAI microservices platform.

## Quick Start

### 1. Start Vault

```bash
docker-compose up -d vault

# Vault auto-initializes and unseals on first run
# Root token and unseal keys saved to vault/data/init.json
```

### 2. Initialize Secrets Structure

```bash
# Export root token (from vault/data/init.json)
export VAULT_TOKEN=$(jq -r '.root_token' vault/data/init.json)
export VAULT_ADDR=http://localhost:8200

# Run initialization
docker-compose exec vault /vault/scripts/init-vault.sh
```

### 3. Create AppRoles

```bash
# Generate AppRole credentials for all services
docker-compose exec vault /vault/scripts/setup-approles.sh

# Copy credentials to .env.vault
docker-compose exec vault cat /vault/data/approle-credentials.env > .env.vault
chmod 600 .env.vault
```

### 4. Migrate Secrets

```bash
# Migrate from your existing .env file
docker-compose exec vault /vault/scripts/migrate-secrets.sh /app/.env

# Verify migration
docker-compose exec vault vault kv list zakupai/shared
```

### 5. Configure Services

Add to your docker-compose override:

```yaml
services:
  etl-service:
    env_file:
      - .env.vault
    environment:
      - VAULT_ENABLED=true
      - VAULT_ADDR=http://vault:8200
```

## Directory Structure

```
vault/
├── config/
│   ├── vault.hcl              # Main Vault configuration
│   ├── config.hcl             # Additional config (empty placeholder)
│   └── policies/              # Access control policies
│       ├── etl-service.hcl
│       ├── calc-service.hcl
│       ├── risk-engine.hcl
│       ├── telegram-bot.hcl
│       └── admin.hcl
├── scripts/
│   ├── init-and-start.sh      # Auto-init and unseal (Docker entrypoint)
│   ├── init-vault.sh          # KV structure setup
│   ├── setup-approles.sh      # AppRole creation
│   ├── migrate-secrets.sh     # .env → Vault migration
│   ├── rotate-secrets.sh      # SECRET_ID rotation
│   └── README.md              # Script documentation (this file)
├── data/                      # Vault storage (gitignored)
│   ├── .gitkeep
│   ├── init.json              # Root token and unseal keys
│   ├── .env.vault             # AppRole credentials
│   └── approle-credentials.env # Latest credentials
└── logs/                      # Audit logs (auto-created)
    └── audit.log              # All Vault operations
```

## Scripts Overview

### init-and-start.sh

Auto-initialization script that runs when Vault container starts:

- Starts Vault server
- Initializes if first run (creates root token, unseal key)
- Auto-unseals Vault
- Saves credentials to `/vault/data/init.json` and `/vault/data/.env.vault`

**Security Note**: Use Docker volumes, never bind mounts, to prevent secrets from leaking to host filesystem.

### init-vault.sh

One-time setup script:

```bash
# Prerequisites
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=<root-token>

# Run
docker-compose exec vault /vault/scripts/init-vault.sh
```

Creates:
- KV v2 secrets engine at `zakupai/`
- Audit logging to `/vault/logs/audit.log`
- AppRole auth method
- Initial secret structure with placeholders

### setup-approles.sh

Creates AppRoles and policies for all services:

```bash
# Prerequisites
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=<admin-token>

# Run
docker-compose exec vault /vault/scripts/setup-approles.sh

# Output: /vault/data/approle-credentials.env
```

For each service:
- Creates policy from `/vault/config/policies/<service>.hcl`
- Creates AppRole with appropriate TTLs
- Generates ROLE_ID and SECRET_ID
- Saves credentials to environment file

Token TTLs:
- **Services**: 1h default, 4h max
- **Admin**: 24h default, 168h (1 week) max

### migrate-secrets.sh

Migrates secrets from .env to Vault:

```bash
# Prerequisites
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=<admin-token>

# Migrate from default .env
docker-compose exec vault /vault/scripts/migrate-secrets.sh

# Migrate from specific file
docker-compose exec vault /vault/scripts/migrate-secrets.sh /path/to/.env
```

Features:
- Creates backup before migration
- Non-destructive (doesn't delete .env)
- Categorizes secrets automatically:
  - Database credentials → `zakupai/shared/db`
  - Redis → `zakupai/shared/redis`
  - JWT keys → `zakupai/shared/jwt`
  - API tokens → appropriate service paths
- Validates migration success

### rotate-secrets.sh

Rotates AppRole SECRET_IDs and optionally JWT secrets:

```bash
# Rotate all service SECRET_IDs
docker-compose exec vault /vault/scripts/rotate-secrets.sh

# Rotate specific service
docker-compose exec vault /vault/scripts/rotate-secrets.sh etl-service

# Rotate JWT secrets (requires confirmation)
docker-compose exec vault /vault/scripts/rotate-secrets.sh --jwt
```

Rotation process:
1. Generates new SECRET_ID for each service
2. Old SECRET_IDs remain valid for 24h (TTL)
3. Saves new credentials to `/vault/data/approle-credentials-rotated.env`
4. Services can be updated without downtime

**Recommended Schedule**: Weekly via cron or n8n workflow

## AppRole Authentication

### Development (Token Auth)

```bash
# Use root token directly
export VAULT_TOKEN=<root-token>
```

### Production (AppRole Auth)

```yaml
# docker-compose.override.stage7.vault.yml
environment:
  - VAULT_ADDR=http://vault:8200
  - VAULT_ROLE_ID=${VAULT_ETL_SERVICE_ROLE_ID}
  - VAULT_SECRET_ID=${VAULT_ETL_SERVICE_SECRET_ID}
```

Services authenticate automatically using HVAC client.

## Access Policies

### etl-service

```hcl
# Shared: db, redis, jwt, goszakup
# Service-specific: services/etl/openai, services/etl/telegram
```

### calc-service

```hcl
# Shared: db, redis, jwt, goszakup
# Service-specific: services/calc/config
```

### risk-engine

```hcl
# Shared: db, redis, jwt, goszakup
# Service-specific: services/risk/config
```

### telegram-bot

```hcl
# Shared: db, redis, jwt, goszakup, n8n, flowise
# Service-specific: services/etl/telegram
```

### admin

```hcl
# Full access to all zakupai/* secrets
# AppRole and policy management
# Audit log access
```

## Common Operations

### View Secret

```bash
vault kv get zakupai/shared/db
```

### Update Secret

```bash
vault kv put zakupai/shared/db \
  POSTGRES_USER=zakupai_user \
  POSTGRES_PASSWORD=new_password
```

### List Secrets

```bash
vault kv list zakupai/shared
vault kv list zakupai/services/etl
```

### Check AppRole Status

```bash
# Get Role ID
vault read auth/approle/role/etl-service/role-id

# List all roles
vault list auth/approle/role
```

### Test Authentication

```bash
# Login with AppRole
vault write auth/approle/login \
  role_id="$VAULT_ETL_SERVICE_ROLE_ID" \
  secret_id="$VAULT_ETL_SERVICE_SECRET_ID"

# Returns token for service use
```

### View Audit Log

```bash
# Real-time monitoring
tail -f vault/logs/audit.log | jq .

# Search for failed auth
grep -i "auth.*failure" vault/logs/audit.log
```

## Security Considerations

### ⚠️ CRITICAL

1. **Never commit secrets**:
   - `vault/data/*` is gitignored
   - `.env.vault` is gitignored
   - `approle-credentials.env` is gitignored

2. **Use Docker volumes, not bind mounts**:
   ```yaml
   # ✅ SAFE
   volumes:
     - vault-data:/vault/data

   # ❌ DANGEROUS
   volumes:
     - ./vault/data:/vault/data  # Secrets written to host!
   ```

3. **Secure the root token**:
   - Never expose `init.json` publicly
   - Use admin AppRole for operations instead
   - Revoke root token after setup:
     ```bash
     vault token revoke <root-token>
     ```

4. **Rotate secrets regularly**:
   - SECRET_IDs: Weekly
   - JWT keys: Monthly
   - Database passwords: Quarterly

5. **Monitor audit logs**:
   - Alert on failed authentications
   - Review access patterns
   - Investigate anomalies

### Production Hardening

1. **Enable TLS**:
   ```hcl
   # vault.hcl
   listener "tcp" {
     tls_cert_file = "/vault/tls/vault.crt"
     tls_key_file  = "/vault/tls/vault.key"
   }
   ```

2. **Use external storage**:
   - Consul for HA
   - PostgreSQL for managed solution
   - Avoid file backend in production

3. **Implement disaster recovery**:
   - Regular snapshots
   - Offsite backups
   - Tested restore procedures

4. **Network segmentation**:
   - Vault on private network
   - No direct external access
   - Gateway authentication required

## Troubleshooting

### Vault Sealed

```bash
# Check status
vault status

# Unseal (requires unseal key from init.json)
vault operator unseal <unseal-key>

# Or restart container (auto-unseal)
docker-compose restart vault
```

### Authentication Failed

```bash
# Verify credentials
echo $VAULT_ROLE_ID
echo $VAULT_SECRET_ID

# Check AppRole exists
vault read auth/approle/role/etl-service

# Regenerate SECRET_ID
vault write -f auth/approle/role/etl-service/secret-id
```

### Secret Not Found

```bash
# List available paths
vault kv list zakupai/shared
vault kv list zakupai/services

# Check policy allows access
vault policy read etl-service
```

### Audit Log Not Created

```bash
# Verify audit backend enabled
vault audit list

# Re-enable if missing
vault audit enable file file_path=/vault/logs/audit.log
```

## Support

For detailed documentation, see:
- [../docs/VAULT_INTEGRATION.md](../docs/VAULT_INTEGRATION.md) - Complete integration guide
- [HashiCorp Vault Docs](https://developer.hashicorp.com/vault/docs)
- [HVAC Python Client](https://hvac.readthedocs.io/)

For issues, check:
- Docker logs: `docker-compose logs vault`
- Audit log: `tail -f vault/logs/audit.log`
- Service health: `curl http://localhost:7000/health | jq .vault`
