# Stage 7 Phase 2 — Execution Plan & Verification

**Status:** ✅ Ready for Deployment
**Date:** 2025-10-27
**Branch:** `feature/stage7-phase2-vault-auth`
**Commit:** `stage7: integrate Vault + Secrets Management (Phase 2)`

---

## 🎯 Executive Summary

Stage 7 Phase 2 integrates HashiCorp Vault for centralized secrets management across all ZakupAI services. This phase includes:

- **Vault deployment** with TLS support and production-ready configuration
- **Secrets integration** for 9 services (calc, risk, etl, billing, goszakup, embedding, doc, web, bot)
- **Business metrics** for anti-dumping detection and Goszakup API monitoring
- **Monitoring integration** (Prometheus, Alertmanager, Grafana)
- **Audit logging** for compliance tracking
- **Backup encryption** documentation and strategy

**⚠️ Backward Compatibility:** All services maintain `.env` fallback when Vault is unavailable or sealed.

---

## 📦 Changes Overview

### 1. Vault Infrastructure

**New Files:**
- `monitoring/vault/config.hcl` — Dev config (HTTP, file storage)
- `monitoring/vault/config-tls.hcl` — Production config (HTTPS, TLS)
- `monitoring/vault/tls/generate-certs.sh` — Self-signed cert generation
- `monitoring/vault/policies/*.hcl` — 5 security policies (calc, risk, etl, monitoring, admin)
- `monitoring/vault/VAULT_INITIALIZATION.md` — Complete initialization guide
- `monitoring/vault/PERMISSIONS_SETUP.md` — File permissions documentation
- `monitoring/vault/creds/README.md` — Token management guide

**Modified Files:**
- `docker-compose.yml` — Added Vault service + dependencies (calc, risk, etl)
- `docker-compose.override.monitoring.yml` — Monitoring stack with Vault

### 2. Secrets Integration

**Updated Services (9 total):**
- `services/billing-service/main.py` + `requirements.txt`
- `services/goszakup-api/main.py` + `requirements.txt`
- `services/embedding-api/main.py` + `requirements.txt`
- `services/doc-service/main.py` + `requirements.txt`
- `services/calc-service/main.py` (already had Vault)
- `services/risk-engine/main.py` (already had Vault)
- `services/etl-service/main.py` (already had Vault)
- `web/main.py` + `requirements.txt`
- `bot/config.py` + `requirements.txt`

**Pattern:** All services use `bootstrap_vault()` with graceful `.env` fallback.

**New Files:**
- `scripts/vault-env.sh` — Vault secrets loader for Flowise/n8n

### 3. Business Metrics

**Modified Files:**
- `services/risk-engine/metrics.py` — Added HTTP server (port 9102) + 4 new metrics:
  - `anti_dumping_ratio` (Gauge)
  - `goszakup_errors_total{error_type}` (Counter)
  - `risk_assessments_total{risk_level}` (Counter)
  - `rnu_validations_total{result}` (Counter)
- `monitoring/prometheus/prometheus.yml` — Added `risk-engine-business` job

### 4. Monitoring Integration

**Modified Files:**
- `monitoring/prometheus/prometheus.yml` — Updated Vault scrape job with `bearer_token_file`, `ca_file`
- `monitoring/alertmanager/alertmanager.yml` — Configured Telegram webhook
- `monitoring/alertmanager/entrypoint.sh` — Vault integration steps (manual)

### 5. Compliance & Audit

**Modified Files:**
- `services/billing-service/main.py` — Audit logging for API key creation
- `services/goszakup-api/main.py` — Audit logging for search operations
- `web/main.py` — Audit middleware for all POST/PUT/DELETE requests
- `backup/entrypoint.sh` — Audit logging for service lifecycle
- `backup/backup.sh` — Audit logging for backup operations

**New Files:**
- `backup/BACKUP_ENCRYPTION_GUIDE.md` — Encryption strategy + B2 integration

### 6. Documentation

**New Files:**
- `STAGE7_PHASE2_DEPLOYMENT.md` — Master deployment guide
- `STAGE7_PHASE2_SUMMARY.md` — Phase 2 deliverables summary
- `STAGE7_PHASE2_EXECUTION_PLAN.md` — This file

**Modified Files:**
- `.gitignore` — Added Vault tokens, certificates, data directories

---

## 🚀 Deployment Steps

### Pre-Deployment Checklist

- [ ] Review all configuration files
- [ ] Ensure `.gitignore` excludes sensitive files
- [ ] Backup current `.env` files
- [ ] Verify Docker Compose version >= 1.29

### Step 1: Start Vault (Dev Mode — HTTP)

```bash
# 1. Start Vault container
docker-compose up -d vault

# 2. Wait for Vault to be ready (sealed state)
sleep 10

# 3. Check Vault status
curl http://localhost:8200/v1/sys/health
# Expected: {"initialized":false,"sealed":true,...}
```

### Step 2: Initialize Vault

```bash
# Option A: Quick dev setup (HTTP, 1 key)
./monitoring/vault/init-vault.sh

# Option B: Production setup (TLS, 5 keys)
# See: monitoring/vault/VAULT_INITIALIZATION.md
```

### Step 3: Configure Services

```bash
# Set Vault environment variables
export VAULT_ADDR=http://vault:8200
export VAULT_TOKEN=$(cat .vault-token)

# For services in docker-compose.yml, add:
# environment:
#   VAULT_ADDR: http://vault:8200
#   VAULT_TOKEN: ${VAULT_TOKEN}

# Or use docker secrets (production):
# secrets:
#   - source: vault_token
#     target: /run/secrets/vault-token
```

### Step 4: Restart Services

```bash
# Restart services to load secrets from Vault
docker-compose restart calc-service risk-engine etl-service \
  billing-service goszakup-api embedding-api doc-service \
  web-ui zakupai-bot

# Check logs for "Vault bootstrap success"
docker-compose logs -f calc-service | grep -i vault
docker-compose logs -f risk-engine | grep -i vault
docker-compose logs -f etl-service | grep -i vault
```

### Step 5: Enable Business Metrics

```bash
# Add to docker-compose.yml or .env
services:
  risk-engine:
    environment:
      METRICS_PORT: 9102

# Restart risk-engine
docker-compose restart risk-engine
```

---

## 🧪 Verification Steps (DoD)

### ✅ 1. Vault Health Check

```bash
# Check Vault is initialized and unsealed
curl http://localhost:8200/v1/sys/health

# Expected output:
{
  "initialized": true,
  "sealed": false,
  "standby": false,
  "performance_standby": false,
  "replication_performance_mode": "disabled",
  "replication_dr_mode": "disabled",
  "server_time_utc": 1698412345,
  "version": "1.17.0",
  "cluster_name": "vault-cluster-abc123",
  "cluster_id": "abc123-def456"
}
```

**Pass Criteria:** `initialized: true`, `sealed: false`

### ✅ 2. Services Start Without .env

```bash
# Backup .env files
mv .env .env.backup
mv bot/.env bot/.env.backup

# Restart services (they should use Vault)
docker-compose restart calc-service risk-engine etl-service

# Check logs for Vault bootstrap
docker-compose logs calc-service | grep "Vault bootstrap success"
docker-compose logs risk-engine | grep "Vault bootstrap success"
docker-compose logs etl-service | grep "Vault bootstrap success"

# Restore .env files
mv .env.backup .env
mv bot/.env.backup bot/.env
```

**Pass Criteria:** Services start successfully, logs show "Vault bootstrap success"

### ✅ 3. Prometheus Metrics — Business Metrics

```bash
# Check risk-engine business metrics endpoint
curl http://localhost:9102/metrics | grep anti_dumping

# Expected output:
# HELP anti_dumping_ratio Anti-dumping violations detected per 100 analyzed lots
# TYPE anti_dumping_ratio gauge
anti_dumping_ratio 0.0

# HELP goszakup_errors_total Total errors from Goszakup API
# TYPE goszakup_errors_total counter
goszakup_errors_total{error_type="timeout"} 0.0
goszakup_errors_total{error_type="auth_error"} 0.0

# Check Prometheus is scraping
curl http://localhost:9095/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="risk-engine-business")'
```

**Pass Criteria:** Metrics endpoint returns data, Prometheus scrapes successfully

### ✅ 4. Alertmanager — Telegram Notification

```bash
# Check Alertmanager configuration
docker exec zakupai-alertmanager amtool config show

# Expected: Telegram receiver configured

# Send test alert
curl -X POST http://localhost:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[
    {
      "labels": {
        "alertname": "VaultTestAlert",
        "severity": "info",
        "service": "vault"
      },
      "annotations": {
        "summary": "Stage 7 Phase 2 verification test",
        "description": "Testing Alertmanager → Telegram integration"
      }
    }
  ]'

# Check Alertmanager UI
# http://localhost:9093/#/alerts

# Verify Telegram notification received
# Check your Telegram chat for the alert
```

**Pass Criteria:** Alert visible in Alertmanager UI, Telegram notification received (if configured)

### ✅ 5. Swagger UI — Calc Service

```bash
# Check calc-service Swagger documentation
curl -s http://localhost:7001/calc/docs | grep -q "Swagger UI"
echo $?  # Should output: 0

# Open in browser
# http://localhost:7001/calc/docs
```

**Pass Criteria:** Swagger UI loads successfully

### ✅ 6. Risk Engine — Explain Endpoint

```bash
# Test risk explanation endpoint
curl -X GET "http://localhost:7002/risk/explain/123" \
  -H "Content-Type: application/json"

# Expected: 200 OK with risk explanation JSON
# (Note: May return 404 if lot 123 doesn't exist, which is acceptable)

# Test health endpoint
curl http://localhost:7002/health

# Expected:
{"status":"ok"}
```

**Pass Criteria:** Service responds with valid HTTP response

---

## 🔄 Rollback Procedure

### Scenario 1: Vault Initialization Failed

```bash
# 1. Stop Vault
docker-compose stop vault

# 2. Remove Vault data
docker volume rm zakupai_vault_data
rm -f .vault-token .vault-unseal-key

# 3. Services automatically fall back to .env
# Verify services are running:
docker-compose ps

# 4. Check service logs
docker-compose logs calc-service | grep "Vault load failed"
# Expected: "Vault load failed: ... Using .env fallback."
```

### Scenario 2: Service Fails to Load Secrets

```bash
# 1. Check Vault connectivity
docker exec zakupai-calc-service env | grep VAULT_ADDR
docker exec zakupai-calc-service env | grep VAULT_TOKEN

# 2. Test Vault authentication
export VAULT_TOKEN=$(cat .vault-token)
vault status
vault token lookup

# 3. Verify secrets exist
vault kv list zakupai/
vault kv get zakupai/db

# 4. If Vault is sealed, unseal it
vault operator unseal $(cat .vault-unseal-key)

# 5. Restart affected service
docker-compose restart calc-service
```

### Scenario 3: Complete Rollback to .env Only

```bash
# 1. Stop Vault
docker-compose stop vault

# 2. Remove Vault from docker-compose.yml dependencies
# Edit docker-compose.yml:
#   calc-service:
#     depends_on:
#       - db
#       # - vault  # ← Comment out or remove

# 3. Restart all services
docker-compose restart

# 4. Verify services use .env
docker-compose logs calc-service | grep "Vault load failed"
# Expected: "Vault load failed: ... Using .env fallback."

# 5. Services continue running with .env secrets
```

### Scenario 4: Revoke Compromised Tokens

```bash
# If a service token is compromised:

# 1. Revoke the compromised token
export VAULT_TOKEN=$(cat .vault-token)
vault token revoke <compromised-token>

# 2. Generate new token with same policy
vault token create \
  -policy=calc-service \
  -ttl=8760h \
  -display-name="calc-service-new" \
  > monitoring/vault/creds/calc-service.token

# 3. Update service environment
# In docker-compose.yml or .env:
export VAULT_TOKEN=$(cat monitoring/vault/creds/calc-service.token)

# 4. Restart service
docker-compose restart calc-service

# 5. Verify new token works
docker-compose logs calc-service | grep "Vault bootstrap success"
```

---

## 📊 Definition of Done (DoD)

| Criterion | Verification Command | Expected Result | Status |
|-----------|---------------------|-----------------|--------|
| **Vault Health** | `curl http://localhost:8200/v1/sys/health` | `{"initialized":true,"sealed":false}` | ⬜ |
| **Vault Unsealed** | `docker exec zakupai-vault vault status` | `Sealed: false` | ⬜ |
| **Services Start** | `docker-compose ps` | All services `Up` | ⬜ |
| **Vault Bootstrap** | `docker-compose logs calc-service \| grep Vault` | `Vault bootstrap success` | ⬜ |
| **Secrets Loaded** | Services use DB credentials from Vault | Services connect to DB | ⬜ |
| **Business Metrics** | `curl localhost:9102/metrics \| grep anti_dumping` | Metrics exposed | ⬜ |
| **Prometheus Scrape** | Check `http://localhost:9095/targets` | `risk-engine-business` UP | ⬜ |
| **Alertmanager Config** | `docker exec zakupai-alertmanager amtool config show` | Telegram receiver present | ⬜ |
| **Telegram Alert** | Send test alert via API | Notification received | ⬜ |
| **Calc Swagger** | `curl http://localhost:7001/calc/docs` | Swagger UI loads | ⬜ |
| **Risk Explain** | `curl http://localhost:7002/risk/explain/123` | 200 OK or 404 | ⬜ |
| **Audit Logs** | `docker exec zakupai-db-backup cat /backups/audit.log` | JSON audit events | ⬜ |
| **Backup Works** | `docker exec zakupai-db-backup /app/backup.sh` | Backup created | ⬜ |
| **Fallback Works** | Stop Vault, restart services | Services use `.env` | ⬜ |

**Pass Criteria:** All checkboxes must be ✅ before considering Phase 2 complete.

---

## 🔐 Security Checklist

### Pre-Production

- [ ] TLS certificates generated (`./monitoring/vault/tls/generate-certs.sh`)
- [ ] Vault initialized with 5 keys (not 1)
- [ ] Root token saved securely offline
- [ ] Unseal keys distributed to key holders
- [ ] Service tokens generated with minimal policies
- [ ] Root token revoked after setup
- [ ] `.gitignore` excludes all token files
- [ ] Backup encryption key stored in Vault
- [ ] Prometheus metrics authentication enabled
- [ ] Alertmanager webhook uses HTTPS
- [ ] Audit logs reviewed and tested

### Post-Production

- [ ] Rotate root token monthly
- [ ] Rotate service tokens quarterly
- [ ] Review Vault audit logs weekly
- [ ] Test backup restore procedure monthly
- [ ] Update TLS certificates before expiry
- [ ] Monitor Vault metrics for anomalies
- [ ] Review access policies quarterly

---

## 📈 Monitoring & Alerts

### Prometheus Alerts (Recommended)

Add to `monitoring/prometheus/alerts.yml`:

```yaml
groups:
  - name: vault
    interval: 30s
    rules:
      - alert: VaultDown
        expr: up{job="vault"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Vault is down"
          description: "Vault has been down for more than 2 minutes"

      - alert: VaultSealed
        expr: vault_core_unsealed == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Vault is sealed"
          description: "Vault is sealed and services cannot access secrets"

      - alert: VaultTokenExpiringSoon
        expr: (vault_token_ttl_seconds - time()) < 86400
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Vault token expiring soon"
          description: "Token {{ $labels.display_name }} expires in less than 24 hours"

  - name: business_metrics
    interval: 5m
    rules:
      - alert: HighAntiDumpingRate
        expr: anti_dumping_ratio > 10
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High anti-dumping violation rate"
          description: "Anti-dumping ratio is {{ $value }}% (threshold: 10%)"

      - alert: GoszakupAPIErrors
        expr: rate(goszakup_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Goszakup API errors increasing"
          description: "Error rate: {{ $value }} errors/sec"
```

### Grafana Dashboards (Recommended)

1. **Vault Operations Dashboard**
   - Vault health status
   - Seal/unseal events
   - Token usage
   - Secret access patterns
   - Audit log events

2. **Business Metrics Dashboard**
   - Anti-dumping ratio trend
   - Goszakup API error rate
   - Risk assessment distribution
   - RNU validation success rate

---

## 🔮 Next Steps — Stage 7 Phase 3

**Timeline:** 2025-11-01 to 2025-11-08

**Features:**
1. **JWT Authentication**
   - User login with access/refresh tokens
   - Token validation middleware
   - Session management via Redis

2. **API Key Management**
   - API key generation via billing-service
   - Key rotation and revocation
   - Usage tracking per key

3. **Redis-backed Rate Limiter**
   - Distributed rate limiting across services
   - Per-user and per-key limits
   - Circuit breaker integration

4. **Gateway Auth Proxy**
   - Centralized authentication at gateway
   - Request forwarding with validated tokens
   - Auth bypass for public endpoints

**Documentation:** STAGE7_PHASE3_PLAN.md (to be created)

---

## 📚 References

- [STAGE7_PHASE2_DEPLOYMENT.md](STAGE7_PHASE2_DEPLOYMENT.md) — Master deployment guide
- [monitoring/vault/VAULT_INITIALIZATION.md](monitoring/vault/VAULT_INITIALIZATION.md) — Vault setup
- [monitoring/vault/PERMISSIONS_SETUP.md](monitoring/vault/PERMISSIONS_SETUP.md) — File permissions
- [backup/BACKUP_ENCRYPTION_GUIDE.md](backup/BACKUP_ENCRYPTION_GUIDE.md) — Backup strategy
- [Vault Production Hardening](https://developer.hashicorp.com/vault/tutorials/operations/production-hardening)

---

## 📞 Support

**For deployment issues:**
1. Check service logs: `docker-compose logs <service>`
2. Verify Vault status: `vault status`
3. Review audit logs: `docker exec zakupai-db-backup cat /backups/audit.log`
4. Test Vault connectivity: `vault kv list zakupai/`
5. Check Prometheus targets: `http://localhost:9095/targets`

**Emergency rollback:** See [Rollback Procedure](#-rollback-procedure)

---

**Generated:** 2025-10-27
**ZakupAI DevOps Team**
**Ready for Deployment:** ✅ YES

🎉 **Stage 7 Phase 2 configuration is complete and ready for deployment!**
