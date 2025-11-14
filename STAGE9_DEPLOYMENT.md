# Stage 9 Vault Deployment Guide

## Problem Fixed

**Critical Issue**: Docker secrets for Backblaze B2 credentials were not mounted into Vault container, causing:
```
cat: can't open '/run/secrets/b2_access_key_id': Permission denied
```

**Root Cause**:
- B2 credential files had restrictive permissions (600 root:root)
- TLS certificates existed but weren't copied to docker volume
- Missing automated preparation and validation

## Solution Overview

This fix provides:
1. Automated preparation script (fixes permissions, creates volumes)
2. Configuration validation script (checks all prerequisites)
3. Automated deployment script (starts Vault and verifies success)
4. Comprehensive documentation

---

## Quick Start (Recommended)

### Step 1: Prepare Environment
```bash
# Run as root to fix file permissions
sudo ./scripts/prepare-stage9-vault.sh
```

This script:
- Fixes B2 secrets file permissions (600 → 644)
- Creates vault_tls volume
- Copies TLS certificates with correct ownership
- Creates vault_logs volume
- Validates Docker Compose configuration
- Ensures all networks exist

### Step 2: Verify Configuration
```bash
# Run as regular user
./scripts/verify-stage9-config.sh
```

This script checks:
- Docker secrets files exist with correct permissions
- TLS certificates are present
- Docker volumes exist
- Docker networks are configured
- No conflicts with other override files
- Vault configuration is valid

### Step 3: Deploy Vault
```bash
# Run as regular user
./scripts/start-stage9-vault.sh
```

This script:
- Validates configuration
- Stops existing Vault (if running)
- Starts Vault with Stage 9 configuration
- Waits for initialization
- Verifies Docker secrets are mounted
- Checks for errors in logs
- Displays Vault status

---

## Manual Deployment (Alternative)

If you prefer manual control:

### 1. Fix File Permissions
```bash
sudo chmod 644 ./monitoring/vault/creds/b2_access_key_id
sudo chmod 644 ./monitoring/vault/creds/b2_secret_key
```

### 2. Create and Populate TLS Volume
```bash
docker volume create zakupai_vault_tls

docker run --rm \
    -v zakupai_vault_tls:/vault/tls \
    -v $(pwd)/monitoring/vault/tls:/source:ro \
    alpine:latest \
    sh -c "
        cp /source/vault.crt /vault/tls/vault.crt && \
        cp /source/vault.key /vault/tls/vault.key && \
        chown -R 100:100 /vault/tls && \
        chmod 640 /vault/tls/vault.key && \
        chmod 644 /vault/tls/vault.crt
    "
```

### 3. Create Logs Volume
```bash
docker volume create zakupai_vault_logs

docker run --rm \
    -v zakupai_vault_logs:/vault/logs \
    alpine:latest \
    sh -c "chown -R 100:100 /vault/logs && chmod 755 /vault/logs"
```

### 4. Validate Configuration
```bash
docker compose -f docker-compose.yml \
    -f docker-compose.override.stage9.vault-prod.yml \
    config -q
```

### 5. Start Vault
```bash
docker compose -f docker-compose.yml \
    -f docker-compose.override.stage9.vault-prod.yml \
    up -d vault --force-recreate
```

### 6. Verify Deployment
```bash
# Check container is running
docker ps | grep zakupai-vault

# Verify secrets mounted
docker exec zakupai-vault ls -la /run/secrets/

# Expected output:
# -r--------    1 root     root            25 Nov 13 XX:XX b2_access_key_id
# -r--------    1 root     root            31 Nov 13 XX:XX b2_secret_key

# Check logs
docker logs zakupai-vault --tail=50

# Should NOT see:
# ❌ "Permission denied"
# ❌ "can't open"

# Check Vault status
docker exec zakupai-vault vault status

# Expected output:
# Storage Type: s3
# Sealed: false (if auto-unseal configured)
```

---

## Verification Checklist

After deployment, verify:

- [ ] Container is running: `docker ps | grep zakupai-vault`
- [ ] Secrets mounted: `docker exec zakupai-vault ls -la /run/secrets/`
- [ ] No permission errors: `docker logs zakupai-vault | grep -i "permission denied"`
- [ ] Vault status: `docker exec zakupai-vault vault status`
- [ ] Storage backend: Check logs for "s3" or "backblaze"
- [ ] Auto-unseal working: Vault should unseal automatically
- [ ] TLS enabled: VAULT_ADDR should be https://

---

## Architecture

### Docker Secrets Flow
```
Host filesystem:
  monitoring/vault/creds/b2_access_key_id (644)
  monitoring/vault/creds/b2_secret_key (644)

                    ↓
Docker Compose declares secrets:
  secrets:
    b2_access_key_id:
      file: ./monitoring/vault/creds/b2_access_key_id
    b2_secret_key:
      file: ./monitoring/vault/creds/b2_secret_key

                    ↓
Mounted into container:
  /run/secrets/b2_access_key_id (400 root:root)
  /run/secrets/b2_secret_key (400 root:root)

                    ↓
vault-b2-entrypoint.sh reads secrets:
  export AWS_ACCESS_KEY_ID=$(cat /run/secrets/b2_access_key_id)
  export AWS_SECRET_ACCESS_KEY=$(cat /run/secrets/b2_secret_key)

                    ↓
Vault connects to B2:
  storage "s3" {
    endpoint = "https://s3.us-west-004.backblazeb2.com"
    bucket   = "zakupai-vault"
  }
```

### Volume Structure
```
vault_tls (Docker volume)
├── vault.crt (644 vault:vault)
└── vault.key (640 vault:vault)

vault_logs (Docker volume)
├── audit.log
└── vault.log
```

---

## Troubleshooting

### Issue: "Permission denied" on secrets

**Symptom**:
```
cat: can't open '/run/secrets/b2_access_key_id': Permission denied
```

**Solution**:
```bash
sudo ./scripts/prepare-stage9-vault.sh
```

Or manually:
```bash
sudo chmod 644 ./monitoring/vault/creds/b2_access_key_id
sudo chmod 644 ./monitoring/vault/creds/b2_secret_key
docker compose restart vault
```

---

### Issue: TLS certificates not found

**Symptom**:
```
⚠️ TLS certificates not found in volume
```

**Solution**:
```bash
# Generate certificates if missing
cd monitoring/vault/tls
./generate-certs.sh

# Run prepare script
sudo ./scripts/prepare-stage9-vault.sh
```

---

### Issue: Network not found

**Symptom**:
```
Error response from daemon: network zakupai_zakupai-network not found
```

**Solution**:
```bash
docker network create zakupai_zakupai-network
docker network create zakupai_monitoring-net
docker network create zakupai_ai-network
```

Or use existing script:
```bash
./scripts/fix-vault-network.sh
```

---

### Issue: Vault stays sealed

**Symptom**:
```
Sealed: true
```

**Solution**:

1. Check auto-unseal configuration:
```bash
docker exec zakupai-vault ls -la /vault/creds/
# Should see: vault-unseal-key.enc
```

2. Check master password:
```bash
docker exec zakupai-vault ls -la /vault/.unseal-password
```

3. Check logs for unseal errors:
```bash
docker logs zakupai-vault | grep -i unseal
```

4. Manual unseal (if auto-unseal not configured):
```bash
docker exec -it zakupai-vault vault operator unseal
```

---

### Issue: Cannot connect to B2

**Symptom**:
```
Error initializing storage of type s3: connection refused
```

**Solution**:

1. Verify credentials are correct:
```bash
cat monitoring/vault/creds/b2_access_key_id
cat monitoring/vault/creds/b2_secret_key
```

2. Verify B2 bucket exists:
```bash
# Use B2 CLI or web interface to check bucket "zakupai-vault"
```

3. Test B2 connectivity:
```bash
curl -I https://s3.us-west-004.backblazeb2.com
```

4. Check Vault config:
```bash
cat monitoring/vault/config/secure/config-stage9.hcl | grep -A 10 'storage "s3"'
```

---

## Configuration Files

### Main Files
- `docker-compose.override.stage9.vault-prod.yml` - Stage 9 Vault configuration
- `monitoring/vault/config/secure/config-stage9.hcl` - Vault server config
- `monitoring/vault/scripts/vault-b2-entrypoint.sh` - Secrets hydration script

### Credentials
- `monitoring/vault/creds/b2_access_key_id` - B2 access key (644)
- `monitoring/vault/creds/b2_secret_key` - B2 secret key (644)
- `monitoring/vault/creds/vault-unseal-key.enc` - Encrypted unseal key
- `monitoring/vault/.unseal-password` - Master password for unseal

### TLS
- `monitoring/vault/tls/vault.crt` - TLS certificate
- `monitoring/vault/tls/vault.key` - TLS private key

---

## Useful Commands

```bash
# View real-time logs
docker logs zakupai-vault --tail=50 -f

# Check Vault status
docker exec zakupai-vault vault status

# List mounted secrets
docker exec zakupai-vault ls -la /run/secrets/

# Check environment variables
docker exec zakupai-vault env | grep AWS

# Inspect container
docker inspect zakupai-vault

# Restart Vault
docker compose restart vault

# Stop Vault
docker compose down vault

# Remove and recreate
docker compose down vault && \
docker compose -f docker-compose.yml \
    -f docker-compose.override.stage9.vault-prod.yml \
    up -d vault --force-recreate

# View compose config
docker compose -f docker-compose.yml \
    -f docker-compose.override.stage9.vault-prod.yml \
    config | grep -A 20 "vault:"

# Check volume contents
docker run --rm -v zakupai_vault_tls:/tls alpine ls -la /tls

# Network inspection
docker network inspect zakupai_zakupai-network
docker network inspect zakupai_monitoring-net
```

---

## Security Considerations

1. **File Permissions**:
   - Host secrets files: 644 (readable by Docker daemon)
   - Container secrets: 400 root:root (read-only, root only)
   - TLS key in volume: 640 vault:vault

2. **Network Isolation**:
   - Vault has no exposed ports (ports: [])
   - Only accessible via internal Docker networks
   - TLS required for all connections

3. **Secrets Management**:
   - Never commit secrets to git
   - Use `.gitignore` for credentials
   - Rotate secrets regularly

4. **Audit Logging**:
   - All Vault operations logged to vault_logs volume
   - Review logs regularly for suspicious activity

---

## Next Steps

After successful deployment:

1. **Initialize Vault** (if first deployment):
   ```bash
   docker exec -it zakupai-vault vault operator init -key-shares=5 -key-threshold=3
   ```

2. **Configure Auto-Unseal**:
   - Save encrypted unseal keys
   - Test auto-unseal on restart

3. **Enable Audit Logging**:
   ```bash
   docker exec zakupai-vault vault audit enable file file_path=/vault/logs/audit.log
   ```

4. **Setup AppRole Authentication**:
   ```bash
   docker exec zakupai-vault vault auth enable approle
   ```

5. **Migrate Secrets to B2 Backend**:
   - Verify data is persisted to B2 bucket
   - Test disaster recovery

6. **Monitor and Alert**:
   - Configure Prometheus scraping
   - Setup Grafana dashboards
   - Configure alerting rules

---

## Rollback Plan

If Stage 9 deployment fails:

```bash
# Stop Stage 9 Vault
docker compose down vault

# Revert to Stage 8 (file backend)
docker compose -f docker-compose.yml \
    -f docker-compose.override.stage8.vault-secure.yml \
    up -d vault

# Or revert to Stage 7 (basic Vault)
docker compose -f docker-compose.yml \
    -f docker-compose.override.stage7.vault.yml \
    up -d vault
```

---

## Support

For issues or questions:
1. Check logs: `docker logs zakupai-vault`
2. Review this guide's troubleshooting section
3. Consult Vault documentation: https://developer.hashicorp.com/vault
4. Check project TODO: `docs/TODO.md`

---

## Change Log

### 2025-11-13 - Stage 9 Fix
- Fixed Docker secrets mounting issue
- Added automated preparation script
- Added configuration verification script
- Added automated deployment script
- Enhanced documentation
- Created comprehensive troubleshooting guide
