# ZakupAI Backup Encryption & Backblaze Integration Guide

**Status:** 🟡 Partially Implemented
**Last Updated:** 2025-10-27
**Security Level:** 🔴 CRITICAL

---

## 🎯 Overview

This document describes backup encryption, local mirroring, and Backblaze B2 integration for ZakupAI database backups.

**Current Implementation:**
- ✅ Automated daily backups (pg_dump + gzip)
- ✅ Backblaze B2 upload via rclone
- ✅ Retention policy (14 days)
- ✅ Audit logging (backup creation, upload, errors)
- ⚠️  **Encryption: NOT YET IMPLEMENTED** (planned for Stage 7 Phase 3)

---

## 📦 Current Backup Architecture

### Backup Flow

```
┌─────────────────────────────────────────────────────────────┐
│  1. PostgreSQL Database (zakupai-db)                        │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ pg_dump
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Local Backup File (zakupai_YYYYMMDD_HHMMSS.sql.gz)    │
│     Location: /backups/ (Docker volume)                     │
│     Compression: gzip                                        │
│     🔴 Unencrypted (plaintext compressed SQL)               │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ rclone copy
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Backblaze B2 Cloud Storage                              │
│     Bucket: ${B2_BUCKET}                                     │
│     Path: backups/postgres/                                  │
│     🔴 Unencrypted (B2 server-side encryption only)         │
└─────────────────────────────────────────────────────────────┘
```

### Backup Schedule

- **Frequency:** Daily at 03:00 Asia/Almaty
- **Cron:** `0 3 * * *` (defined in `backup/Dockerfile`)
- **Retention:** 14 days (configurable via `BACKUP_RETENTION_DAYS`)

### Audit Logging

All backup operations are logged to `/backups/audit.log`:

```json
{"timestamp":"2025-10-27T03:00:01+06:00","event":"backup_create_start","status":"info","details":"Starting backup for database zakupai","backup_file":"zakupai_20251027_030001.sql.gz"}
{"timestamp":"2025-10-27T03:00:15+06:00","event":"backup_create_complete","status":"success","details":"Backup created successfully, size: 45678901 bytes","backup_file":"zakupai_20251027_030001.sql.gz"}
{"timestamp":"2025-10-27T03:00:16+06:00","event":"backup_upload_start","status":"info","details":"Uploading to B2 bucket zakupai-backups","backup_file":"zakupai_20251027_030001.sql.gz"}
{"timestamp":"2025-10-27T03:00:45+06:00","event":"backup_upload_complete","status":"success","details":"Uploaded to b2:zakupai-backups/backups/postgres/zakupai_20251027_030001.sql.gz","backup_file":"zakupai_20251027_030001.sql.gz"}
```

---

## 🔒 Planned: Client-Side Encryption (Stage 7 Phase 3)

### Encryption Strategy

**Algorithm:** AES-256-GCM (via GPG or age)
**Key Management:** Vault secrets engine

### Updated Backup Flow (Future)

```
┌─────────────────────────────────────────────────────────────┐
│  1. PostgreSQL Database                                      │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ pg_dump + gzip
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Compressed Backup (*.sql.gz)                            │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ gpg --symmetric --cipher-algo AES256
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Encrypted Backup (*.sql.gz.gpg)                         │
│     🔐 AES-256-GCM encrypted                                │
│     Passphrase: Loaded from Vault (zakupai/backup)          │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ rclone copy
                   ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Backblaze B2 Cloud Storage                              │
│     🔐 Double-encrypted (client + B2 server-side)           │
└─────────────────────────────────────────────────────────────┘
```

### Implementation Steps (NOT YET DONE)

#### 1. Install Encryption Tools

```dockerfile
# In backup/Dockerfile
RUN apk add --no-cache gnupg age
```

#### 2. Store Encryption Key in Vault

```bash
# Manual step: Store backup encryption passphrase in Vault
vault kv put zakupai/backup \
  GPG_PASSPHRASE="$(openssl rand -base64 32)"

# Verify
vault kv get -field=GPG_PASSPHRASE zakupai/backup
```

#### 3. Update backup.sh with Encryption

```bash
# In backup/backup.sh

encrypt_backup() {
    log "Encrypting backup with GPG..."
    audit_log "backup_encrypt_start" "info" "Encrypting backup file"

    # Load passphrase from Vault
    if [ -n "$VAULT_TOKEN" ] && [ -n "$VAULT_ADDR" ]; then
        GPG_PASSPHRASE=$(vault kv get -field=GPG_PASSPHRASE zakupai/backup)
    else
        log "ERROR: Vault credentials not available for encryption"
        audit_log "backup_encrypt_complete" "error" "Vault credentials missing"
        exit 1
    fi

    # Encrypt with GPG
    echo "$GPG_PASSPHRASE" | gpg \
        --batch \
        --yes \
        --passphrase-fd 0 \
        --symmetric \
        --cipher-algo AES256 \
        --output "${BACKUP_PATH}.gpg" \
        "$BACKUP_PATH"

    # Verify encryption
    if [ ! -f "${BACKUP_PATH}.gpg" ]; then
        log "ERROR: Encrypted backup not created"
        audit_log "backup_encrypt_complete" "error" "Encryption failed"
        exit 1
    fi

    # Update backup path to encrypted file
    BACKUP_PATH="${BACKUP_PATH}.gpg"
    BACKUP_FILENAME="${BACKUP_FILENAME}.gpg"

    local encrypted_size=$(stat -c%s "$BACKUP_PATH")
    log "Backup encrypted successfully (${encrypted_size} bytes)"
    audit_log "backup_encrypt_complete" "success" "Encryption successful, size: ${encrypted_size} bytes"
}

# Update main() to call encrypt_backup()
main() {
    # ... existing code ...
    create_backup
    encrypt_backup  # ← Add this
    upload_backup
    # ... existing code ...
}
```

#### 4. Document Decryption Process

```bash
# To decrypt a backup:

# 1. Download from B2
rclone copy b2:zakupai-backups/backups/postgres/zakupai_20251027_030001.sql.gz.gpg ./

# 2. Get passphrase from Vault
export VAULT_ADDR=https://vault:8200
export VAULT_TOKEN=<your-token>
GPG_PASSPHRASE=$(vault kv get -field=GPG_PASSPHRASE zakupai/backup)

# 3. Decrypt
echo "$GPG_PASSPHRASE" | gpg \
    --batch \
    --yes \
    --passphrase-fd 0 \
    --decrypt \
    --output zakupai_20251027_030001.sql.gz \
    zakupai_20251027_030001.sql.gz.gpg

# 4. Decompress and restore
gunzip zakupai_20251027_030001.sql.gz
psql -U zakupai -d postgres -f zakupai_20251027_030001.sql
```

---

## 🗂️ Local Mirroring Strategy

### Current Setup

**Local Backups:**
- Location: `/backups/` (Docker volume `backup_data`)
- Retention: 14 days
- Cleanup: Automatic via `cleanup_old_backups()`

**Backblaze B2:**
- Remote location: `b2:zakupai-backups/backups/postgres/`
- Retention: 14 days (cleaned via rclone)
- Purpose: Off-site disaster recovery

### Recommended: Local NAS Mirror (Future Enhancement)

```bash
# In backup.sh, add local mirror step

mirror_to_nas() {
    log "Mirroring backup to local NAS..."
    audit_log "backup_mirror_start" "info" "Mirroring to NAS"

    local NAS_PATH="${NAS_MOUNT_PATH:-/mnt/nas/zakupai-backups}"

    if [ ! -d "$NAS_PATH" ]; then
        log "WARNING: NAS mount not available at $NAS_PATH"
        audit_log "backup_mirror_complete" "warning" "NAS not mounted"
        return
    fi

    # Copy encrypted backup to NAS
    cp "$BACKUP_PATH" "$NAS_PATH/"

    if [ $? -eq 0 ]; then
        log "Backup mirrored to NAS successfully"
        audit_log "backup_mirror_complete" "success" "Mirrored to ${NAS_PATH}"
    else
        log "ERROR: Failed to mirror backup to NAS"
        audit_log "backup_mirror_complete" "error" "Mirror failed"
    fi
}

# Update main()
main() {
    create_backup
    encrypt_backup
    mirror_to_nas    # ← Local NAS copy
    upload_backup    # ← Off-site B2 copy
    cleanup_old_backups
    cleanup_local
}
```

---

## 🔐 Backblaze B2 Configuration

### Current Setup

**Authentication:**
```bash
# Environment variables (set in docker-compose.yml or .env)
B2_KEY_ID=your-b2-key-id
B2_APP_KEY=your-b2-application-key
B2_BUCKET=zakupai-backups
B2_PREFIX=backups/postgres
```

**rclone Configuration:**
Generated automatically in `backup.sh`:

```ini
[b2]
type = b2
account = ${B2_KEY_ID}
key = ${B2_APP_KEY}
hard_delete = true
```

### Vault Integration (Planned)

Move B2 credentials to Vault:

```bash
# Store in Vault
vault kv put zakupai/backup \
  B2_KEY_ID="your-key-id" \
  B2_APP_KEY="your-app-key" \
  B2_BUCKET="zakupai-backups" \
  GPG_PASSPHRASE="your-encryption-passphrase"

# Load in backup.sh
if [ -n "$VAULT_TOKEN" ]; then
    B2_KEY_ID=$(vault kv get -field=B2_KEY_ID zakupai/backup)
    B2_APP_KEY=$(vault kv get -field=B2_APP_KEY zakupai/backup)
    B2_BUCKET=$(vault kv get -field=B2_BUCKET zakupai/backup)
fi
```

---

## 🧪 Testing Backup & Restore

### Test Backup Creation

```bash
# Dry run test
docker exec zakupai-db-backup /app/backup.sh DRY_RUN=true

# Real backup test
docker exec zakupai-db-backup /app/backup.sh

# Check audit log
docker exec zakupai-db-backup cat /backups/audit.log | jq
```

### Test Restore

```bash
# 1. Download latest backup from B2
rclone copy b2:zakupai-backups/backups/postgres/ ./test-restore/ --include "zakupai_*.sql.gz" --max-age 1d

# 2. Find latest file
LATEST=$(ls -t ./test-restore/zakupai_*.sql.gz | head -1)

# 3. Restore to test database
gunzip -c "$LATEST" | docker exec -i zakupai-db psql -U zakupai -d zakupai_test

# 4. Verify data
docker exec -it zakupai-db psql -U zakupai -d zakupai_test -c "SELECT COUNT(*) FROM lots;"
```

---

## 📊 Backup Monitoring

### Prometheus Metrics (Future)

Add backup metrics to `backup/backup.sh`:

```bash
# In backup.sh

update_metrics() {
    local backup_size=$1
    local upload_duration=$2

    cat > /backups/metrics.prom <<EOF
# HELP zakupai_backup_size_bytes Size of latest backup
# TYPE zakupai_backup_size_bytes gauge
zakupai_backup_size_bytes ${backup_size}

# HELP zakupai_backup_timestamp_seconds Timestamp of latest backup
# TYPE zakupai_backup_timestamp_seconds gauge
zakupai_backup_timestamp_seconds $(date +%s)

# HELP zakupai_backup_upload_duration_seconds Duration of last upload
# TYPE zakupai_backup_upload_duration_seconds gauge
zakupai_backup_upload_duration_seconds ${upload_duration}

# HELP zakupai_backup_success Success status of latest backup (1=success, 0=failure)
# TYPE zakupai_backup_success gauge
zakupai_backup_success 1
EOF
}
```

Expose via node-exporter textfile collector:
```yaml
# In docker-compose.yml
db-backup:
  volumes:
    - backup_data:/backups
    - ./monitoring/node-exporter/textfile:/textfile
```

---

## 🔄 Backup Rotation Policy

### Current: 14-Day Rolling Window

```bash
# Automatic cleanup in backup.sh
cleanup_old_backups() {
    # Local: Delete files older than RETENTION_DAYS
    find /backups -name "zakupai_*.sql.gz" -mtime +${RETENTION_DAYS} -delete

    # B2: Delete remote files older than RETENTION_DAYS
    # (via date comparison in filename)
}
```

### Recommended: 3-2-1 Backup Strategy

- **3** copies of data
  - 1 production database
  - 1 local backup (`/backups/`)
  - 1 off-site backup (Backblaze B2)
- **2** different media types
  - Local: SSD/HDD
  - Remote: Cloud object storage
- **1** off-site backup
  - Backblaze B2

**Future Enhancement:**
- Add NAS mirror (4th copy)
- Add weekly/monthly archive retention (long-term compliance)

---

## 🛡️ Security Recommendations

### Current State

✅ **Implemented:**
- Credentials in environment variables
- TLS for B2 uploads (via rclone)
- Audit logging for all operations
- Automated retention/cleanup

🔴 **Missing (High Priority):**
- Client-side encryption (GPG/age)
- Vault integration for credentials
- Encrypted local storage

⚠️ **Risks:**
- Backups contain plaintext sensitive data
- B2 credentials in environment variables (should be in Vault)
- No encryption at rest

### Action Plan

**Stage 7 Phase 3:**
1. Implement GPG encryption in `backup.sh`
2. Move B2 credentials to Vault (`zakupai/backup`)
3. Add backup metrics to Prometheus
4. Test restore procedure monthly

**Future:**
5. Add NAS local mirror
6. Implement weekly/monthly archive retention
7. Automate restore testing

---

## 📚 References

- [Backblaze B2 Documentation](https://www.backblaze.com/b2/docs/)
- [rclone B2 Backend](https://rclone.org/b2/)
- [GPG Encryption Guide](https://www.gnupg.org/gph/en/manual.html)
- [PostgreSQL Backup & Restore](https://www.postgresql.org/docs/current/backup.html)

---

## 📞 Support

**For backup issues:**
1. Check audit log: `docker exec zakupai-db-backup cat /backups/audit.log`
2. Check container logs: `docker-compose logs db-backup`
3. Verify B2 credentials: `docker exec zakupai-db-backup rclone config show`
4. Test B2 connectivity: `docker exec zakupai-db-backup rclone ls b2:zakupai-backups/`

---

**Generated:** 2025-10-27
**ZakupAI DevOps Team**
**Security Level:** 🔴 CRITICAL
