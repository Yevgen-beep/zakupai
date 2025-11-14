# Stage 9 Vault - Quick Start Guide

## 🎯 Problem Fixed
Docker secrets for B2 credentials were not mounting → Vault couldn't read credentials → Container failed

## ⚡ Solution (3 Commands)

### 1. Prepare (requires sudo)
```bash
sudo ./scripts/prepare-stage9-vault.sh
```
**What it does**:
- Fixes file permissions on B2 secrets (600 → 644)
- Creates vault_tls volume
- Copies TLS certificates
- Validates everything

### 2. Verify
```bash
./scripts/verify-stage9-config.sh
```
**What it does**:
- Checks all prerequisites
- Validates configuration
- Reports any issues

### 3. Deploy
```bash
./scripts/start-stage9-vault.sh
```
**What it does**:
- Starts Vault with Stage 9 config
- Waits for initialization
- Verifies secrets mounted
- Shows Vault status

---

## ✅ Expected Result

After running all 3 commands, you should see:

```bash
# Secrets are mounted:
docker exec zakupai-vault ls -la /run/secrets/
-r--------    1 root     root            25 Nov 13 XX:XX b2_access_key_id
-r--------    1 root     root            31 Nov 13 XX:XX b2_secret_key

# Vault is running:
docker exec zakupai-vault vault status
Storage Type: s3
Sealed: false

# No errors in logs:
docker logs zakupai-vault --tail=20
# Should NOT see "Permission denied" or "can't open"
```

---

## 🔍 Quick Verification

```bash
# 1. Container running?
docker ps | grep zakupai-vault

# 2. Secrets mounted?
docker exec zakupai-vault ls /run/secrets/

# 3. No errors?
docker logs zakupai-vault | grep -i "error\|denied"

# 4. Vault status?
docker exec zakupai-vault vault status
```

---

## 🚨 Troubleshooting

### Issue: Permission denied on secrets
```bash
sudo ./scripts/prepare-stage9-vault.sh
```

### Issue: TLS certificates not found
```bash
cd monitoring/vault/tls
./generate-certs.sh
sudo ./scripts/prepare-stage9-vault.sh
```

### Issue: Network not found
```bash
docker network create zakupai_zakupai-network
docker network create zakupai_monitoring-net
docker network create zakupai_ai-network
```

---

## 📚 Full Documentation

For detailed information, see:
- **Complete guide**: [STAGE9_DEPLOYMENT.md](STAGE9_DEPLOYMENT.md)
- **Technical details**: [STAGE9_FIX.patch](STAGE9_FIX.patch)
- **Vault admin guide**: [docs/VAULT_ADMIN_GUIDE.md](docs/VAULT_ADMIN_GUIDE.md)

---

## 🎓 Manual Alternative

If scripts don't work, do it manually:

```bash
# 1. Fix permissions
sudo chmod 644 ./monitoring/vault/creds/b2_access_key_id
sudo chmod 644 ./monitoring/vault/creds/b2_secret_key

# 2. Create TLS volume
docker volume create zakupai_vault_tls
docker run --rm \
    -v zakupai_vault_tls:/vault/tls \
    -v $(pwd)/monitoring/vault/tls:/source:ro \
    alpine:latest \
    sh -c "cp /source/vault.{crt,key} /vault/tls/ && \
           chown -R 100:100 /vault/tls && \
           chmod 640 /vault/tls/vault.key"

# 3. Start Vault
docker compose -f docker-compose.yml \
    -f docker-compose.override.stage9.vault-prod.yml \
    up -d vault --force-recreate

# 4. Verify
docker logs zakupai-vault --tail=50
docker exec zakupai-vault ls -la /run/secrets/
docker exec zakupai-vault vault status
```

---

## 💡 Key Changes

**Fixed in docker-compose.override.stage9.vault-prod.yml**:
- ✅ Secrets properly declared at top level
- ✅ Secrets mounted into vault service
- ✅ TLS volume with correct permissions
- ✅ Clear documentation and comments

**New Scripts**:
- `scripts/prepare-stage9-vault.sh` - Prepares environment
- `scripts/verify-stage9-config.sh` - Validates config
- `scripts/start-stage9-vault.sh` - Deploys Vault

---

## 🎉 Success Criteria

Deployment is successful when:
- ✅ Container runs: `docker ps | grep zakupai-vault`
- ✅ Secrets mounted: `docker exec zakupai-vault ls /run/secrets/`
- ✅ No permission errors in logs
- ✅ Vault unsealed: `sealed == false`
- ✅ Storage type is S3/B2
- ✅ Can read secrets: `docker exec zakupai-vault cat /run/secrets/b2_access_key_id`

---

**Next**: See [STAGE9_DEPLOYMENT.md](STAGE9_DEPLOYMENT.md) for full details and troubleshooting.
