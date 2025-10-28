# Stage 7 Phase 2 — Vault Setup Guide

**Status:** ✅ Configuration Complete
**Date:** 2025-10-27
**Branch:** `feature/stage7-phase2-vault-auth`

---

## 🎯 Overview

This guide walks you through setting up HashiCorp Vault for ZakupAI secrets management. All configuration files have been generated and are ready for deployment.

---

## 📋 Prerequisites

- Docker and Docker Compose installed
- `jq` command-line tool (for parsing JSON)
- Access to ZakupAI repository

---

## 🚀 Quick Start

### 1. Start Vault Container

```bash
# Start Vault service
docker-compose up -d vault

# Verify Vault is running
docker ps | grep vault
curl http://localhost:8200/v1/sys/health
```

### 2. Initialize Vault

```bash
# Make init script executable
chmod +x monitoring/vault/init-vault.sh

# Run initialization
./monitoring/vault/init-vault.sh
```

The script will:
- Initialize Vault with dev-friendly settings (1 key share)
- Create `.vault-token` file with root token
- Enable KV v2 secrets engine at `zakupai/`
- Create sample secrets for development

**⚠️ IMPORTANT:** Save the output! The root token and unseal key are displayed only once.

### 3. Configure Service Environment

Add to your `.env` file or export:

```bash
export VAULT_ADDR=http://vault:8200
export VAULT_TOKEN=$(cat .vault-token)
```

For services running in Docker:

```bash
# In docker-compose.yml or .env
VAULT_ADDR=http://vault:8200
VAULT_TOKEN=<your-token-from-.vault-token>
```

### 4. Update Secrets with Production Values

```bash
export VAULT_TOKEN=$(cat .vault-token)

# Update Goszakup token
docker exec -e VAULT_TOKEN=${VAULT_TOKEN} zakupai-vault \
  vault kv put zakupai/goszakup \
    GOSZAKUP_TOKEN="your-real-token-here"

# Update database credentials
docker exec -e VAULT_TOKEN=${VAULT_TOKEN} zakupai-vault \
  vault kv put zakupai/db \
    POSTGRES_USER="zakupai_user" \
    POSTGRES_PASSWORD="your-strong-password" \
    POSTGRES_DB="zakupai" \
    POSTGRES_HOST="zakupai-db" \
    POSTGRES_PORT="5432" \
    DATABASE_URL="postgresql://zakupai_user:your-strong-password@zakupai-db:5432/zakupai"

# Update Telegram bot token for Alertmanager
docker exec -e VAULT_TOKEN=${VAULT_TOKEN} zakupai-vault \
  vault kv put zakupai/monitoring \
    TELEGRAM_BOT_TOKEN="your-bot-token" \
    TELEGRAM_CHAT_ID="your-chat-id"
```

### 5. Restart Services

```bash
# Restart services that use Vault
docker-compose restart calc-service risk-engine etl-service

# Check logs to verify Vault bootstrap
docker-compose logs calc-service | grep -i vault
docker-compose logs risk-engine | grep -i vault
docker-compose logs etl-service | grep -i vault
```

---

## 🔍 Verification

### Check Vault Status

```bash
export VAULT_TOKEN=$(cat .vault-token)

# Vault system health
docker exec -e VAULT_TOKEN=${VAULT_TOKEN} zakupai-vault \
  vault status

# List secrets engines
docker exec -e VAULT_TOKEN=${VAULT_TOKEN} zakupai-vault \
  vault secrets list

# Read a secret
docker exec -e VAULT_TOKEN=${VAULT_TOKEN} zakupai-vault \
  vault kv get zakupai/db
```

### Verify Service Integration

```bash
# Check calc-service health
curl http://localhost:7001/health

# Check risk-engine health
curl http://localhost:7002/health

# Check etl-service health
curl http://localhost:7011/health

# Check Prometheus metrics (should include vault_* metrics)
curl http://localhost:8200/v1/sys/metrics?format=prometheus
```

### Test Alertmanager Configuration

```bash
# Check Alertmanager config
docker exec zakupai-alertmanager \
  amtool config show

# Send test alert
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{
    "labels": {"alertname": "TestAlert", "severity": "warning"},
    "annotations": {"summary": "Test alert from ZakupAI"}
  }]'
```

---

## 📊 Secrets Structure

Vault secrets are organized under the `zakupai/` KV v2 mount:

```
zakupai/
├── db                 # Database credentials
│   ├── POSTGRES_USER
│   ├── POSTGRES_PASSWORD
│   ├── POSTGRES_DB
│   ├── POSTGRES_HOST
│   ├── POSTGRES_PORT
│   └── DATABASE_URL
├── api                # API keys
│   ├── API_KEY
│   └── ZAKUPAI_API_KEY
├── goszakup          # Goszakup integration
│   └── GOSZAKUP_TOKEN
└── monitoring        # Alerting credentials
    ├── TELEGRAM_BOT_TOKEN
    └── TELEGRAM_CHAT_ID
```

---

## 🔐 Security Best Practices

### Development Environment

✅ **Current Setup (Safe for Dev):**
- Single unseal key
- HTTP (no TLS)
- Root token stored in `.vault-token`
- File storage backend

### Production Recommendations

🔒 **Upgrade for Production:**

1. **Enable TLS:**
   ```hcl
   listener "tcp" {
     address     = "0.0.0.0:8200"
     tls_cert_file = "/vault/tls/vault.crt"
     tls_key_file  = "/vault/tls/vault.key"
   }
   ```

2. **Use Raft Storage:**
   ```hcl
   storage "raft" {
     path    = "/vault/data"
     node_id = "zakupai-vault-1"
   }
   ```

3. **Initialize with 5 keys, threshold 3:**
   ```bash
   vault operator init -key-shares=5 -key-threshold=3
   ```

4. **Rotate Root Token:**
   ```bash
   vault token revoke <old-root-token>
   vault operator generate-root
   ```

5. **Use AppRole for Services:**
   ```bash
   vault auth enable approle
   vault write auth/approle/role/calc-service \
     policies=calc-policy \
     token_ttl=1h
   ```

6. **Enable Audit Logging:**
   ```bash
   vault audit enable file file_path=/vault/logs/audit.log
   ```

---

## 📈 Monitoring & Metrics

### Prometheus Integration

Vault metrics are exposed at: `http://localhost:8200/v1/sys/metrics?format=prometheus`

Add to `monitoring/prometheus/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'vault'
    static_configs:
      - targets: ['vault:8200']
    metrics_path: '/v1/sys/metrics'
    params:
      format: ['prometheus']
```

### Business Metrics

New metrics added in `services/risk-engine/metrics.py`:

- `anti_dumping_ratio` — Anti-dumping violations per 100 lots
- `goszakup_errors_total{error_type}` — Goszakup API errors
- `risk_assessments_total{risk_level}` — Risk assessments by level
- `rnu_validations_total{result}` — RNU validation results

Access at: `http://localhost:7002/metrics`

---

## 🛠️ Troubleshooting

### Vault Won't Start

**Problem:** Container exits immediately

```bash
# Check logs
docker-compose logs vault

# Common issues:
# 1. Port 8200 already in use
sudo lsof -i :8200

# 2. Permission issues with volume
sudo chown -R 100:1000 ./monitoring/vault/data
```

### Vault Sealed After Restart

**Problem:** Services can't connect to Vault

```bash
# Check seal status
docker exec zakupai-vault vault status

# Unseal using saved key
UNSEAL_KEY=$(cat .vault-unseal-key)
docker exec zakupai-vault vault operator unseal ${UNSEAL_KEY}
```

### Services Can't Load Secrets

**Problem:** `VaultClientError: Authentication failed`

```bash
# Verify token is set
docker exec zakupai-calc-service env | grep VAULT_TOKEN

# Check token validity
docker exec -e VAULT_TOKEN=${VAULT_TOKEN} zakupai-vault \
  vault token lookup

# Verify secrets exist
docker exec -e VAULT_TOKEN=${VAULT_TOKEN} zakupai-vault \
  vault kv list zakupai/
```

### Alertmanager Not Sending Notifications

**Problem:** Alerts not reaching Telegram

```bash
# Check Alertmanager logs
docker-compose logs alertmanager

# Verify webhook config
docker exec zakupai-alertmanager cat /etc/alertmanager/alertmanager.yml

# Test webhook manually
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}&text=Test from Alertmanager"
```

---

## 📚 Next Steps

After completing Vault setup:

1. ✅ **Remove `.env` files from Dockerfiles** (Optional: already using Vault)
2. 🔧 **Configure Grafana dashboards** for business metrics
3. 🚀 **Stage 7 Phase 3:** JWT authentication + API keys via billing-service
4. 🔐 **Production hardening:** TLS, AppRole, audit logging

---

## 🔗 References

- [Vault Documentation](https://developer.hashicorp.com/vault/docs)
- [hvac Python Client](https://hvac.readthedocs.io/)
- [Prometheus Metrics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Alertmanager Configuration](https://prometheus.io/docs/alerting/latest/configuration/)

---

## 📞 Support

For issues or questions:
- Check [STAGE7_PHASE2_PLAN.md](STAGE7_PHASE2_PLAN.md) for detailed roadmap
- Review [TODO.md](TODO.md) Stage 7 section
- Check service logs: `docker-compose logs <service-name>`

**Generated:** 2025-10-27
**ZakupAI DevOps Team**
