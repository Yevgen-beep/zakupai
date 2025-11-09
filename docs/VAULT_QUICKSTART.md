# Vault Migration Quick Start Guide

## 📦 Complete Artifact Inventory

### Documentation
```
docs/
├── VAULT_MIGRATION_STAGE7_TO_STAGE9.md    # Full migration guide with roadmap
└── VAULT_QUICKSTART.md                     # This file - quick reference
```

### Configurations

#### Stage 7 (Manual File Backend)
```
monitoring/vault/config/
└── stage7-config.hcl                       # Manual unseal, file storage, no TLS
```

#### Stage 8 (Auto-Unseal File Backend)
```
monitoring/vault/
├── config/secure/
│   └── config.hcl                          # Auto-unseal, file storage, no TLS
├── scripts/
│   ├── auto-unseal.sh                      # Auto-unseal entrypoint (AES-256)
│   └── encrypt-unseal.sh                   # Interactive key encryption tool
└── creds/
    ├── README.md                           # Security documentation
    ├── .gitkeep
    ├── vault-unseal-key.enc                # Encrypted key (gitignored)
    └── .unseal-password                    # Master password (gitignored)

docker-compose.override.stage8.vault-secure.yml  # Stage 8 override
```

#### Stage 9 (Production B2 + TLS + Audit)
```
monitoring/vault/
├── config/secure/
│   └── config-stage9.hcl                   # B2 S3 storage, TLS, audit
├── tls/
│   ├── README.md                           # TLS management guide
│   ├── vault-cert.pem                      # Public cert (gitignored)
│   └── vault-key.pem                       # Private key (gitignored)
├── logs/
│   ├── .gitkeep
│   ├── audit.log                           # Audit trail (gitignored)
│   └── vault.log                           # Server logs (gitignored)
└── tests/
    └── smoke-stage9.sh                     # 15 comprehensive tests

docker-compose.override.stage9.vault-prod.yml     # Stage 9 override
```

### Migration Scripts
```
scripts/
├── vault-migrate-stage8.sh                 # Stage 7 → 8 migration
└── vault-migrate-stage9.sh                 # Stage 8 → 9 migration (+ backup mode)
```

### Monitoring
```
monitoring/prometheus/alerts/
└── vault.yml                               # 18 alert rules (availability, performance, security)
```

### Makefile Targets
```makefile
# Stage deployment
stage7                  # Apply Stage 7 (manual unseal)
stage8                  # Apply Stage 8 (auto-unseal file)
stage9                  # Apply Stage 9 (B2 + TLS + audit)

# Stage 8 operations
vault-secure-init       # Initialize Vault (5 keys, threshold 3)
vault-secure-status     # Check status + auto-unseal logs
vault-secure-backup     # Backup to local tarball
vault-secure-test       # Test AppRole access

# Stage 9 operations
vault-prod-status       # Check status + audit log
vault-prod-backup       # Backup to B2 bucket
vault-tls-renew         # Generate/renew TLS certificates
smoke-stage9            # Run comprehensive smoke tests

# Rollback
rollback-stage8         # Stage 8 → Stage 7
rollback-stage9         # Stage 9 → Stage 8
```

---

## 🚀 Quick Migration Path

### Step 1: Stage 7 → Stage 8 (Auto-Unseal)

**Time**: ~10 minutes
**Downtime**: ~5 minutes

```bash
# 1. Generate master password
openssl rand -base64 32 > monitoring/vault/.unseal-password
chmod 600 monitoring/vault/.unseal-password

# 2. Run migration
./scripts/vault-migrate-stage8.sh

# 3. Verify
make vault-secure-status
docker restart vault
sleep 10
vault status  # Should be unsealed automatically
```

### Step 2: Stage 8 → Stage 9 (Production B2 + TLS)

**Time**: ~26 minutes
**Downtime**: ~10 minutes

```bash
# 1. Setup B2 credentials
export B2_APPLICATION_KEY_ID="your_key_id"
export B2_APPLICATION_KEY="your_app_key"

# 2. Generate TLS certificates
make vault-tls-renew

# 3. Run migration
./scripts/vault-migrate-stage9.sh

# 4. Verify
make smoke-stage9
```

---

## 🔐 Security Checklist

### Before Migration
- [ ] Backup all unseal keys securely (1Password/Bitwarden)
- [ ] Root token saved in encrypted storage
- [ ] `.gitignore` includes all sensitive files
- [ ] File permissions: `chmod 600 monitoring/vault/creds/*`

### Stage 8 Validation
- [ ] `vault status` shows `Sealed: false`
- [ ] `docker restart vault` → auto-unseals
- [ ] All AppRoles accessible
- [ ] Encrypted key + master password backed up

### Stage 9 Validation
- [ ] TLS certificate valid: `openssl x509 -in monitoring/vault/tls/vault-cert.pem -noout -dates`
- [ ] Audit log writing: `tail -f monitoring/vault/logs/audit.log`
- [ ] B2 storage active: `b2 ls zakupai-vault-storage`
- [ ] Prometheus alerts loaded: Check Grafana
- [ ] Daily backups scheduled: `crontab -l | grep vault`

---

## 📊 Architecture Comparison

| Feature | Stage 7 | Stage 8 | Stage 9 |
|---------|---------|---------|---------|
| **Unseal** | Manual (3/5 keys) | Auto (AES-256) | Auto (AES-256) |
| **Storage** | File (local) | File (local) | S3 (B2) |
| **TLS** | ❌ | ❌ | ✅ |
| **Audit** | ❌ | ❌ | ✅ |
| **Backups** | Manual | Local daily | B2 daily |
| **HA Ready** | ❌ | ❌ | ✅ (S3-based) |
| **Production** | ❌ Dev | ⚠️ Staging | ✅ Production |
| **Encryption at Rest** | File system | File system | B2 server-side |
| **Auto-Recovery** | ❌ | ✅ | ✅ |

---

## 🧪 Testing Commands

### Stage 8 Tests
```bash
# Status check
make vault-secure-status

# Auto-unseal test
docker restart vault && sleep 10 && vault status

# AppRole access test
vault kv list zakupai/

# Backup test
make vault-secure-backup
```

### Stage 9 Tests
```bash
# Comprehensive smoke tests (15 tests)
make smoke-stage9

# TLS verification
curl https://127.0.0.1:8200/v1/sys/health

# Audit log verification
tail -f monitoring/vault/logs/audit.log

# B2 storage verification
b2 ls zakupai-vault-storage

# Performance test
time vault kv get zakupai/gateway/approle  # Should be <100ms
```

---

## 🔧 Troubleshooting

### Vault sealed after restart (Stage 8)
```bash
# Check logs
docker logs vault --tail 50

# Verify encrypted key exists
ls -lh monitoring/vault/creds/vault-unseal-key.enc

# Manual decrypt test
openssl enc -d -aes-256-cbc -md sha256 -pbkdf2 -iter 250000 \
    -in monitoring/vault/creds/vault-unseal-key.enc \
    -pass file:monitoring/vault/.unseal-password
```

### B2 upload fails (Stage 9)
```bash
# Re-authorize
b2 authorize-account "$B2_APPLICATION_KEY_ID" "$B2_APPLICATION_KEY"

# Check bucket
b2 get-bucket zakupai-vault-storage

# Test upload
echo "test" > test.txt
b2 upload-file zakupai-vault-storage test.txt test.txt
```

### TLS certificate invalid
```bash
# Check certificate
openssl x509 -in monitoring/vault/tls/vault-cert.pem -text -noout

# Regenerate
make vault-tls-renew
docker restart vault
```

### High latency (>100ms)
```bash
# Check B2 connectivity
time curl https://s3.us-west-004.backblazeb2.com

# Check container resources
docker stats vault

# Check Prometheus metrics
curl -s http://localhost:8200/v1/sys/metrics?format=prometheus | grep handle_request
```

---

## 📞 Emergency Procedures

### Rollback Stage 8 → Stage 7
```bash
make rollback-stage8
# Then manually unseal: vault operator unseal <key>
```

### Rollback Stage 9 → Stage 8
```bash
make rollback-stage9
# Auto-unseal will resume on file backend
```

### Complete Vault Reinstall (Data Loss)
```bash
# 1. Backup everything
make vault-prod-backup  # or vault-secure-backup

# 2. Stop and remove
docker-compose down vault
docker volume rm vault_data

# 3. Start fresh
docker-compose up -d vault
make vault-secure-init

# 4. Restore policies and AppRoles manually
```

---

## 🎯 Success Criteria (DoD)

### Stage 8
- [x] Vault auto-unseals after `docker restart vault`
- [x] Unseal keys encrypted AES-256 + PBKDF2 ≥250k
- [x] Plain-text keys removed from Git
- [x] `.unseal-password` in `.gitignore`
- [x] Healthcheck validates `Sealed=false`
- [x] All AppRoles work unchanged

### Stage 9
- [x] B2 storage connected and active
- [x] TLS certificate valid and auto-renewed
- [x] Audit log writing and rotating
- [x] Backups automated to B2 (cron)
- [x] Prometheus alerts configured
- [x] `make smoke-stage9` passes all 15 tests
- [x] Latency <100ms (p99)

---

## 📚 References

- [Full Migration Guide](./VAULT_MIGRATION_STAGE7_TO_STAGE9.md)
- [Vault Documentation](https://developer.hashicorp.com/vault/docs)
- [Backblaze B2 S3 API](https://www.backblaze.com/b2/docs/s3_compatible_api.html)
- [Prometheus Alerting](https://prometheus.io/docs/alerting/latest/overview/)

---

**Version**: 1.0
**Date**: 2025-11-07
**Maintainer**: ZakupAI DevOps Team
