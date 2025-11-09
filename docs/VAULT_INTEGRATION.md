# Vault Integration Guide

## Overview

ZakupAI uses HashiCorp Vault for centralized secrets management across all microservices. This document describes the architecture, setup process, and best practices.

## Architecture

### Secrets Structure

```
zakupai/ (KV v2 engine)
├── shared/
│   ├── db          # PostgreSQL credentials
│   ├── redis       # Redis connection details
│   ├── jwt         # JWT signing keys
│   ├── goszakup    # Government API tokens
│   ├── n8n         # n8n workflow automation
│   └── flowise     # Flowise AI workflows
├── services/
│   ├── etl/
│   │   ├── openai    # OpenAI API key
│   │   └── telegram  # Telegram bot tokens
│   ├── calc/
│   │   └── config    # Calc service configuration
│   └── risk/
│       └── config    # Risk engine configuration
└── backup/
    └── b2        # Backblaze B2 credentials
```

### Authentication Model

- **AppRole Auth**: Production authentication method
  - Each service has its own AppRole with specific policies
  - `ROLE_ID`: Fixed identifier (can be in environment)
  - `SECRET_ID`: Rotatable secret (24h TTL, should be in Docker secrets)

- **Token Auth**: Development fallback
  - Root token for local development only
  - Never use in production

### Access Control

Each service has a dedicated policy granting minimal required permissions:

| Service | Shared Access | Service-Specific Access |
|---------|--------------|------------------------|
| **etl-service** | db, redis, jwt, goszakup | services/etl/* |
| **calc-service** | db, redis, jwt, goszakup | services/calc/* |
| **risk-engine** | db, redis, jwt, goszakup | services/risk/* |
| **telegram-bot** | db, redis, jwt, goszakup, n8n, flowise | services/etl/telegram |
| **admin** | Full access | All paths |

### Token Lifecycle

```
┌─────────────────┐
│  AppRole Login  │
│  (ROLE_ID +     │
│   SECRET_ID)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Token Created  │
│  TTL: 1h        │
│  Max TTL: 4h    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Token Renewable │◄──── Auto-renewal by HVAC client
│  (before expiry)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Token Expires  │
│  (after 4h max) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Re-authenticate│
│  with AppRole   │
└─────────────────┘
```

## Setup Instructions

### 1. Initialize Vault

```bash
# Start Vault container
docker-compose up -d vault

# Wait for Vault to be ready
docker-compose exec vault vault status

# Export root token (from vault/data/init.json)
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=<root-token>

# Run initialization script
docker-compose exec vault /vault/scripts/init-vault.sh
```

This script:
- Enables KV v2 engine at path `zakupai/`
- Enables audit logging to `/vault/logs/audit.log`
- Enables AppRole authentication
- Creates initial secret structure with placeholders

### 2. Create AppRoles and Policies

```bash
# Setup AppRoles for all services
docker-compose exec vault /vault/scripts/setup-approles.sh

# Credentials are saved to /vault/data/approle-credentials.env
docker-compose exec vault cat /vault/data/approle-credentials.env > .env.vault
chmod 600 .env.vault
```

### 3. Migrate Secrets from .env

```bash
# Backup your .env file
cp .env .env.backup

# Run migration script
docker-compose exec vault /vault/scripts/migrate-secrets.sh /app/.env

# Verify secrets were migrated
docker-compose exec vault vault kv list zakupai/shared
docker-compose exec vault vault kv get zakupai/shared/db
```

### 4. Configure Services

Update `docker-compose.override.stage7.vault.yml`:

```yaml
services:
  etl-service:
    environment:
      - VAULT_ENABLED=true
      - VAULT_ADDR=http://vault:8200
      - VAULT_ROLE_ID=${VAULT_ETL_SERVICE_ROLE_ID}
      - VAULT_SECRET_ID=${VAULT_ETL_SERVICE_SECRET_ID}
      - VAULT_KV_MOUNT=zakupai
      - VAULT_FALLBACK=true  # Fallback to .env if Vault unavailable
    depends_on:
      vault:
        condition: service_healthy
```

### 5. Test Integration

```bash
# Start services with Vault integration
docker-compose -f docker-compose.yml -f docker-compose.override.stage7.vault.yml up -d

# Check logs for Vault authentication
docker-compose logs etl-service | grep -i vault

# Expected output:
# ✅ Vault authentication successful (AppRole)
# ✅ Loaded secrets from Vault: zakupai/shared/db
```

### 6. Health Checks

Each service exposes Vault status in `/health` endpoint:

```bash
curl http://localhost:7000/health | jq .vault

{
  "status": "healthy",
  "authenticated": true,
  "method": "approle",
  "token_ttl": 3456,
  "secrets_loaded": [
    "shared/db",
    "shared/redis",
    "services/etl/openai"
  ]
}
```

## Development Workflow

### Local Development (without Vault)

For rapid local development, you can disable Vault:

```bash
# .env.local
VAULT_ENABLED=false
POSTGRES_USER=dev_user
POSTGRES_PASSWORD=dev_password
# ... other local secrets
```

### Local Development (with Vault)

```bash
# Start Vault locally
docker-compose up -d vault

# Use root token for local auth
export VAULT_TOKEN=<root-token-from-init.json>

# Services will use token auth in development
VAULT_ENABLED=true
VAULT_ADDR=http://localhost:8200
VAULT_TOKEN=${VAULT_TOKEN}
```

## Secrets Rotation

### AppRole SECRET_ID Rotation

Rotate SECRET_IDs weekly (recommended):

```bash
# Rotate all services
docker-compose exec vault /vault/scripts/rotate-secrets.sh

# Rotate specific service
docker-compose exec vault /vault/scripts/rotate-secrets.sh etl-service

# Apply new credentials (zero-downtime rolling update)
for service in etl-service calc-service risk-engine; do
  docker-compose up -d --no-deps $service
  sleep 10  # Wait for health check
done
```

**Important**: Old SECRET_IDs remain valid for 24h (TTL), allowing graceful rotation.

### JWT Secret Rotation

Rotate JWT secrets monthly (or after security incident):

```bash
# WARNING: This invalidates all user sessions!
docker-compose exec vault /vault/scripts/rotate-secrets.sh --jwt

# Restart all services to pick up new JWT keys
docker-compose restart etl-service calc-service risk-engine telegram-bot
```

## Monitoring & Observability

### Prometheus Metrics

Vault exposes metrics at `http://vault:8200/v1/sys/metrics?format=prometheus`

Key metrics:
- `vault_core_unsealed`: Vault seal status (1 = unsealed)
- `vault_token_count`: Number of active tokens
- `vault_secret_kv_count`: Number of secrets stored

### Audit Logging

All Vault operations are logged to `/vault/logs/audit.log`:

```bash
# View recent audit events
docker-compose exec vault tail -f /vault/logs/audit.log | jq .

# Search for failed authentications
docker-compose exec vault grep -i "auth.*failure" /vault/logs/audit.log
```

### Grafana Dashboard

Import the Vault monitoring dashboard:

```bash
# Dashboard JSON: monitoring/grafana/dashboards/vault-health.json
# Includes:
# - Authentication success/failure rate
# - Secret access patterns
# - Token TTL distribution
# - Service health by Vault status
```

## Security Best Practices

### 1. Principle of Least Privilege

- Each service has minimal required permissions
- No service can access another service's secrets
- Admin policy only for migration and maintenance

### 2. Secret Rotation

- **SECRET_IDs**: Weekly automated rotation
- **JWT keys**: Monthly manual rotation
- **Database passwords**: Quarterly rotation
- **API tokens**: Follow provider recommendations

### 3. Audit Trail

- All secret access is logged
- Audit logs stored with 90-day retention
- Alerts for suspicious patterns:
  - Failed authentication attempts (>3 in 5 min)
  - Secret access outside business hours
  - Bulk secret enumeration attempts

### 4. Backup & Disaster Recovery

```bash
# Backup Vault data (automated daily)
docker-compose exec vault tar czf /vault/backups/vault-data-$(date +%Y%m%d).tar.gz /vault/data

# Backup to Backblaze B2
docker-compose exec vault \
  b2 sync /vault/backups/ b2://zakupai-vault-backups/

# Recovery procedure:
# 1. Restore /vault/data from backup
# 2. Unseal Vault with recovery keys
# 3. Verify audit log integrity
# 4. Test service authentication
```

### 5. Network Security

- Vault accessible only within Docker network
- TLS required in production (configure in vault.hcl)
- No direct external access to Vault
- API access via authenticated gateway only

## Troubleshooting

### Service Can't Authenticate

```bash
# Check Vault status
docker-compose exec vault vault status

# Verify AppRole exists
docker-compose exec vault vault read auth/approle/role/etl-service

# Check credentials in environment
docker-compose exec etl-service env | grep VAULT_

# Test authentication manually
docker-compose exec vault vault write auth/approle/login \
  role_id="$VAULT_ETL_SERVICE_ROLE_ID" \
  secret_id="$VAULT_ETL_SERVICE_SECRET_ID"
```

### Secret Not Found

```bash
# List available secrets
docker-compose exec vault vault kv list zakupai/shared

# Check secret content
docker-compose exec vault vault kv get zakupai/shared/db

# Verify service policy allows access
docker-compose exec vault vault policy read etl-service
```

### Token Expired

Services automatically renew tokens. If manual intervention needed:

```bash
# Check token TTL
docker-compose exec vault vault token lookup

# Renew token manually (services do this automatically)
docker-compose exec vault vault token renew

# If expired, re-authenticate with AppRole
# Services handle this automatically via HVAC client
```

### Vault Sealed After Restart

```bash
# Check seal status
docker-compose exec vault vault status

# Unseal (requires unseal key from init.json)
docker-compose exec vault vault operator unseal <unseal-key>

# Or use auto-unseal script (for development only)
docker-compose restart vault  # Auto-unseal in init-and-start.sh
```

## Compliance & Governance

### Astana Hub Requirements

✅ **Data Sovereignty**: Vault data stored locally in Docker volumes
✅ **Access Audit**: Complete audit trail of all secret access
✅ **Encryption**: Secrets encrypted at rest (Vault's storage encryption)
✅ **Access Control**: Role-based access with minimal privileges
✅ **Rotation**: Automated SECRET_ID rotation, manual JWT rotation

### Explainable AI Requirements

✅ **Transparency**: All API key usage logged and attributable
✅ **Traceability**: Audit logs link API calls to specific services
✅ **Accountability**: Each service has identifiable AppRole
✅ **Reproducibility**: Secret versions tracked in Vault KV v2

## Migration Checklist

- [ ] Vault initialized and unsealed
- [ ] AppRoles created for all services
- [ ] Secrets migrated from .env to Vault
- [ ] Services configured with ROLE_ID and SECRET_ID
- [ ] Health checks passing with Vault integration
- [ ] Fallback to .env tested (Vault unavailable scenario)
- [ ] Audit logging verified
- [ ] Prometheus metrics collection configured
- [ ] Grafana dashboards imported
- [ ] Backup automation tested
- [ ] Rotation scripts tested in staging
- [ ] Team trained on Vault operations
- [ ] .env.backup secured and archived
- [ ] Original .env cleaned of secrets

## References

- [HashiCorp Vault Documentation](https://developer.hashicorp.com/vault/docs)
- [AppRole Auth Method](https://developer.hashicorp.com/vault/docs/auth/approle)
- [KV v2 Secrets Engine](https://developer.hashicorp.com/vault/docs/secrets/kv/kv-v2)
- [HVAC Python Client](https://hvac.readthedocs.io/)
- [Vault Security Model](https://developer.hashicorp.com/vault/docs/internals/security)
