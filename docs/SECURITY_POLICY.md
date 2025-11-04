# 🔐 SECURITY POLICY — ZakupAI Vault & Secrets Infrastructure

**Last Updated:** 2025-11-04  
**Branch:** `feature/stage7-phase3-vault-hvac`  
**Commit:** `0c0d7b27f99c71ad497a91c6f1a286a4cbf77ae1`

---

## 1. Overview

This document defines the security policy for Vault, Backblaze B2, and secret management within the ZakupAI infrastructure.

All sensitive data — including Vault tokens, unseal keys, and cloud credentials — are now isolated from the Git repository and stored only within container volumes or secret management backends.

---

## 2. Vault Security Configuration

**Base Image:** HashiCorp Vault 1.15 (with `jq` preinstalled)  
**Deployment:** Docker container with dedicated volume mount  
**Policy Goals:**
- No real tokens or secrets inside the repository.
- All `vault/data/*` files ignored by Git, except `.gitkeep`.
- All initialization output (`init.json`, `.env.vault`, `unseal-keys.txt`) kept **outside** the repo.

### 2.1. File System Layout

| Path | Purpose | Git Policy |
|------|----------|------------|
| `vault/data/` | Persistent data store for Vault | Ignored |
| `vault/scripts/init-and-start.sh` | Vault bootstrap script | Allowed, sanitized |
| `vault/scripts/README.md` | Security documentation | Allowed |
| `vault/config/vault.hcl` | Active Vault config (file storage backend) | Allowed |
| `vault/config/config.hcl` | Empty placeholder (safe) | Allowed |

### 2.2. Security Variables
`VAULT_SECRETS_PATH` defines the directory used to store initialized secrets:
```bash
VAULT_SECRETS_PATH=/vault/data

This ensures secrets are never written into bind-mounted source code directories.

3. Git Security Controls
3.1. .gitignore Rules (Hardened)

vault/data/* and monitoring/vault/* are ignored.

TLS certificates and keys are excluded (*.crt, *.key, *.csr, *.srl).

Local .env, .log, .bak, and .tmp files excluded globally.

Only safe templates (.gitkeep, openssl.cnf, generate-certs.sh) remain tracked.

3.2. Secrets Whitelist

Only these files are permitted under version control:
vault/data/.gitkeep
monitoring/vault/creds/.gitkeep
monitoring/vault/tls/.gitkeep
monitoring/vault/tls/openssl.cnf
monitoring/vault/tls/generate-certs.sh

4. Backblaze B2 Integration

Service: Backblaze B2 Cloud Storage
Bucket: zakupai-backups
Integration: via rclone inside db-backup container

Security Requirements

No B2 credentials are stored in .env or Git.

Credentials fetched dynamically from Vault at runtime.

Old B2 App Keys must be revoked upon each rotation or exposure.

5. Key Rotation Policy
Component	Rotation Trigger	Method
Vault Root & Unseal Keys	After initialization or exposure	vault operator rekey
Vault Tokens	After environment rebuild	Regenerate via vault token create
Backblaze B2 App Key	After any backup configuration change	Revoke and recreate key in B2 Console
TLS Certificates	Every 180 days or on key compromise	Reissue via generate-certs.sh

6. Validation Procedures
Verify .gitignore coverage:
git check-ignore -v vault/data/init.json

Validate no secrets in index:
git ls-files -z | xargs -0 grep -IEn 'hvs\.|root_token|B2_APP_KEY|unseal|-----BEGIN' || echo "✅ Clean"

Test Vault health:
docker exec zakupai-vault vault status

Test B2 backup upload:
docker exec -u backup zakupai-db-backup /scripts/backup_wrapper.sh

7. Enforcement & Review

Owner: DevOps Lead (Vault Maintainer)

Review cadence: every 30 days or upon change to:

Vault configuration

Backup pipeline

Any .env-related component

CI/CD Enforcement: Add pre-commit hook scanning for VAULT_TOKEN, B2_KEY_ID, B2_APP_KEY, and PEM blocks.

8. Compliance Summary

✅ No plaintext secrets in repo
✅ Secure .gitignore coverage
✅ Secrets dynamically loaded at runtime via Vault API
✅ Documentation added (vault/scripts/README.md, SECURITY_POLICY.md)
✅ End-to-end backup to Backblaze B2 verified
✅ TLS and Vault keys rotation policy defined

9. Future Recommendations

Integrate HashiCorp Vault Agent Injector for automated token renewal.

Add Git pre-push secret scan via gitleaks or trufflehog.

Move Vault audit logs to a centralized logging backend (e.g. Loki + Grafana).

Enforce signing of all commits touching vault/ or backup/.

Result:
The Vault + Backup security chain is fully hardened.
The current configuration meets internal DevSecOps standards and can be safely deployed in production.
