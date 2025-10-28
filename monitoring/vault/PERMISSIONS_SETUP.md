# Vault Permissions and Ownership Setup

**⚠️ DOCUMENTATION ONLY — DO NOT EXECUTE AUTOMATICALLY**

This document describes the required file permissions and ownership for secure Vault operation.
All commands must be executed manually by a system administrator.

---

## 🎯 Overview

Vault requires specific file permissions to operate securely:
- TLS certificates must be readable by Vault process (UID 100)
- Private keys must be protected (600 permissions)
- Data directory must be writable by Vault only
- Token files must be protected from unauthorized access

---

## 📋 Prerequisites

- Docker container running as UID 100 (vault user)
- Host file system with proper ownership support
- Root or sudo access on Docker host

---

## 🔐 TLS Certificates

### Location: `monitoring/vault/tls/`

```bash
# Navigate to TLS directory
cd /home/mint/projects/claude_sandbox/zakupai/monitoring/vault/tls

# CA Certificate (public)
chmod 644 ca.crt
chown 100:1000 ca.crt

# CA Private Key (highly sensitive)
chmod 600 ca.key
chown 100:1000 ca.key

# Server Certificate (public)
chmod 644 server.crt
chown 100:1000 server.crt

# Server Private Key (highly sensitive)
chmod 600 server.key
chown 100:1000 server.key

# Verify permissions
ls -la
```

**Expected Output:**
```
-rw-r--r-- 1 100 1000 ca.crt
-rw------- 1 100 1000 ca.key
-rw-r--r-- 1 100 1000 server.crt
-rw------- 1 100 1000 server.key
```

**Explanation:**
- UID 100: Vault user inside container
- GID 1000: Docker group on host
- 644: Readable by all, writable by owner
- 600: Only owner can read/write

---

## 💾 Vault Data Directory

### Location: `monitoring/vault/data/`

```bash
# Create data directory if not exists
mkdir -p monitoring/vault/data

# Set ownership to Vault user
chown -R 100:1000 monitoring/vault/data

# Restrict access to owner only
chmod 700 monitoring/vault/data

# Set sticky bit (optional, for shared systems)
chmod +t monitoring/vault/data

# Verify permissions
ls -ld monitoring/vault/data
```

**Expected Output:**
```
drwx------ 2 100 1000 monitoring/vault/data
```

**Explanation:**
- 700: Only owner (Vault) can read/write/execute
- Prevents other users from accessing Vault data
- Critical for security in multi-tenant environments

---

## 🎫 Token Files

### Location: `monitoring/vault/creds/`

```bash
# Create credentials directory
mkdir -p monitoring/vault/creds

# Root token (most sensitive)
chmod 400 monitoring/vault/creds/root.token
chown root:root monitoring/vault/creds/root.token

# Unseal keys (highly sensitive)
chmod 400 monitoring/vault/creds/unseal-keys.txt
chown root:root monitoring/vault/creds/unseal-keys.txt

# Service tokens (sensitive)
chmod 600 monitoring/vault/creds/*.token
chown root:docker monitoring/vault/creds/*.token

# Restrict directory access
chmod 700 monitoring/vault/creds
chown root:docker monitoring/vault/creds

# Verify permissions
ls -la monitoring/vault/creds
```

**Expected Output:**
```
drwx------ 2 root docker .
-r-------- 1 root root   root.token
-r-------- 1 root root   unseal-keys.txt
-rw------- 1 root docker calc-service.token
-rw------- 1 root docker risk-engine.token
-rw------- 1 root docker etl-service.token
-rw------- 1 root docker monitoring.token
```

**Explanation:**
- 400: Read-only by owner (for root token and unseal keys)
- 600: Read/write by owner (for service tokens)
- root:root: Only root can access
- root:docker: Docker group can read (for mounting as secrets)

---

## 📄 Configuration Files

### Location: `monitoring/vault/`

```bash
# Config files (readable by Vault)
chmod 644 monitoring/vault/config.hcl
chmod 644 monitoring/vault/config-tls.hcl
chown 100:1000 monitoring/vault/config*.hcl

# Policy files (readable by Vault)
chmod 644 monitoring/vault/policies/*.hcl
chown -R 100:1000 monitoring/vault/policies/

# Scripts (executable)
chmod 755 monitoring/vault/tls/generate-certs.sh
chmod 755 monitoring/vault/init-vault.sh

# Verify
ls -la monitoring/vault/*.hcl
ls -la monitoring/vault/policies/
```

**Expected Output:**
```
-rw-r--r-- 1 100 1000 config.hcl
-rw-r--r-- 1 100 1000 config-tls.hcl
-rwxr-xr-x 1 user user generate-certs.sh
-rwxr-xr-x 1 user user init-vault.sh
```

---

## 🐋 Docker Volume Permissions

### Docker Volume: `vault_data`

```bash
# Find volume location
docker volume inspect zakupai_vault_data | jq -r '.[0].Mountpoint'

# Example: /var/lib/docker/volumes/zakupai_vault_data/_data

# Set ownership
sudo chown -R 100:1000 /var/lib/docker/volumes/zakupai_vault_data/_data

# Set permissions
sudo chmod 700 /var/lib/docker/volumes/zakupai_vault_data/_data

# Verify
sudo ls -ld /var/lib/docker/volumes/zakupai_vault_data/_data
```

**Note:** Docker named volumes typically handle permissions automatically.
Only adjust if you encounter permission errors.

---

## 🔒 SELinux Context (RHEL/CentOS/Fedora)

If using SELinux, set appropriate security contexts:

```bash
# Check if SELinux is enabled
getenforce

# Set context for Vault data
chcon -R -t container_file_t monitoring/vault/data/

# Set context for TLS certificates
chcon -R -t container_file_t monitoring/vault/tls/

# Set context for credentials
chcon -R -t container_file_t monitoring/vault/creds/

# Make changes persistent
semanage fcontext -a -t container_file_t "monitoring/vault/data(/.*)?"
semanage fcontext -a -t container_file_t "monitoring/vault/tls(/.*)?"
semanage fcontext -a -t container_file_t "monitoring/vault/creds(/.*)?"

# Restore contexts
restorecon -R monitoring/vault/
```

---

## 🧪 Verification

### Test Vault Can Read Files

```bash
# Start Vault container
docker-compose -f docker-compose.yml \
  -f docker-compose.override.monitoring.yml \
  up -d vault

# Check Vault logs for permission errors
docker-compose logs vault | grep -i permission

# Test TLS certificate access
docker exec zakupai-vault ls -la /vault/tls/

# Test data directory access
docker exec zakupai-vault ls -la /vault/file/

# Test config file access
docker exec zakupai-vault cat /vault/config/config.hcl
```

### Test Service Can Read Tokens

```bash
# Test calc-service can read token
docker exec zakupai-calc-service cat /run/secrets/calc-service-token

# Or if using environment variable
docker exec zakupai-calc-service env | grep VAULT_TOKEN
```

---

## 🚨 Common Permission Issues

### Issue 1: "permission denied" on server.key

**Symptom:**
```
Error initializing listener of type tcp: error loading TLS cert:
open /vault/tls/server.key: permission denied
```

**Solution:**
```bash
chmod 600 monitoring/vault/tls/server.key
chown 100:1000 monitoring/vault/tls/server.key
```

### Issue 2: Vault can't write to data directory

**Symptom:**
```
Error initializing storage of type file: mkdir /vault/file: permission denied
```

**Solution:**
```bash
sudo chown -R 100:1000 monitoring/vault/data/
sudo chmod 700 monitoring/vault/data/
```

### Issue 3: Service can't read token file

**Symptom:**
```
VaultClientError: Vault token not found. Set VAULT_TOKEN or VAULT_TOKEN_FILE
```

**Solution:**
```bash
chmod 600 monitoring/vault/creds/calc-service.token
chown root:docker monitoring/vault/creds/calc-service.token

# Verify Docker can mount as secret
docker secret inspect calc-service-token
```

### Issue 4: Root owns everything (Docker volume issue)

**Symptom:**
```
drwxr-xr-x 2 root root monitoring/vault/data
```

**Solution:**
```bash
# Stop Vault
docker-compose stop vault

# Fix ownership
sudo chown -R 100:1000 monitoring/vault/data/

# Restart Vault
docker-compose start vault
```

---

## 🔐 Security Hardening

### 1. Disable Password Authentication (SSH)

If accessing Vault host via SSH:

```bash
# Edit /etc/ssh/sshd_config
PasswordAuthentication no
PubkeyAuthentication yes

# Restart SSH
systemctl restart sshd
```

### 2. Restrict File System Access

```bash
# Mount Vault volumes with noexec, nosuid
# In docker-compose.override.monitoring.yml:
volumes:
  vault_data:
    driver_opts:
      type: none
      o: bind,noexec,nosuid,nodev
      device: /opt/vault/data
```

### 3. Enable AppArmor Profile (Ubuntu/Debian)

```bash
# Install AppArmor utilities
apt-get install apparmor-utils

# Create Vault profile
cat > /etc/apparmor.d/docker-vault <<EOF
profile docker-vault flags=(attach_disconnected,mediate_deleted) {
  #include <abstractions/base>

  /vault/file/ rw,
  /vault/file/** rw,
  /vault/tls/* r,
  /vault/config/* r,

  deny /proc/** w,
  deny /sys/** w,
}
EOF

# Load profile
apparmor_parser -r /etc/apparmor.d/docker-vault

# Apply to container in docker-compose:
security_opt:
  - apparmor:docker-vault
```

---

## 📊 Permission Summary Table

| Path | Owner | Group | Permissions | Purpose |
|------|-------|-------|-------------|---------|
| `vault/tls/ca.crt` | 100 | 1000 | 644 | Public CA cert |
| `vault/tls/ca.key` | 100 | 1000 | 600 | Private CA key |
| `vault/tls/server.crt` | 100 | 1000 | 644 | Server cert |
| `vault/tls/server.key` | 100 | 1000 | 600 | Server private key |
| `vault/data/` | 100 | 1000 | 700 | Vault storage |
| `vault/creds/root.token` | root | root | 400 | Root token |
| `vault/creds/unseal-keys.txt` | root | root | 400 | Unseal keys |
| `vault/creds/*.token` | root | docker | 600 | Service tokens |
| `vault/config.hcl` | 100 | 1000 | 644 | Config file |
| `vault/policies/*.hcl` | 100 | 1000 | 644 | Policy files |

---

## 📚 References

- [Vault Production Hardening](https://developer.hashicorp.com/vault/tutorials/operations/production-hardening)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [Linux File Permissions](https://wiki.archlinux.org/title/File_permissions_and_attributes)

---

**Generated:** 2025-10-27
**ZakupAI DevOps Team**
**Security Level:** 🔴 CRITICAL
