# Stage 7 Vault Fix Summary  
**Date:** 2025-11-09  
**Maintainer:** ZakupAI DevOps Team  
**Related files:** `STAGE7_VAULT_FIX_REPORT.md`, `VAULT_MIGRATION_STAGE7_TO_STAGE9.md`, `README-final.md`

---

## 1. Root Cause Analysis

**Symptom:**  
Vault failed to start with  

Error initializing listener of type tcp: listen tcp4 0.0.0.0:8200: bind: address already in use

even though no process actually listened on port 8200 (`lsof`, `fuser`, `ss` — all empty).

**Diagnosis:**  
Vault’s entrypoint (`/usr/local/bin/docker-entrypoint.sh`) automatically injects  
`-config=/vault/config`.  
When `-config=/vault/config/vault-config.hcl` is passed manually, the same file is loaded twice.  
Vault tries to start **two listeners on 0.0.0.0:8200**, causing a *false port conflict*.

---

## 2. Fix Implementation

### Configuration Reorganization
- Legacy Stage 7 configs moved into  
  `monitoring/vault/config/stage7/`  

monitoring/vault/config/stage7/
├── config.hcl
└── stage7-config.hcl

- Active config remains at  
`monitoring/vault/config/vault-config.hcl`.

### References Updated
- **Compose files:**  
- `docker-compose.yml`  
- `docker-compose.override.stage7.yml`  
- **Makefile:** updated `stage7` and `rollback-stage8` targets.  
- **Docs:**  
- `README-final.md`  
- `VAULT_QUICKSTART.md`  
- `VAULT_MIGRATION_STAGE7_TO_STAGE9.md`  
- `STAGE7_VAULT_FIX_REPORT.md`

All old paths (`config/stage7-config.hcl`) replaced by  
`config/stage7/config.hcl`.

---

## 3. Corrected Run Command

**✅ Recommended:**
```bash
docker run --rm \
--cap-add IPC_LOCK \
-p 8200:8200 \
-v zakupai_vault-data:/vault/file \
-v $(pwd)/monitoring/vault/config:/vault/config \
hashicorp/vault:1.15 server

Optional (explicit file):
docker run --rm \
  --entrypoint vault \
  --cap-add IPC_LOCK \
  -p 8200:8200 \
  -v zakupai_vault-data:/vault/file \
  -v $(pwd)/monitoring/vault/config:/vault/config \
  hashicorp/vault:1.15 server -config=/vault/config/vault-config.hcl

4. Verification

Test container start
docker run -d --name vault-test \
  --cap-add IPC_LOCK \
  -p 8200:8200 \
  -v zakupai_vault-data:/vault/file \
  -v $(pwd)/monitoring/vault/config:/vault/config \
  hashicorp/vault:1.15 server

Check health
curl -s -o - -w '\nHTTP %{http_code}\n' http://127.0.0.1:8200/v1/sys/health

Expected output:
{"initialized":false,"sealed":true,"standby":false,"performance_standby":false}
HTTP 501
→ Vault successfully reachable on port 8200.

Cleanup
docker rm -f vault-test

5. Observations

The auto-unseal.sh script in Stage 8 override currently fails (/bin/bash not found).
→ Must be converted to /bin/sh or use a custom image with bash installed.

docker-entrypoint.sh in hashicorp/vault:1.15 always appends its own config path — avoid passing -config twice.

6. Deliverables
| File                                          | Purpose                  | Status   |
| --------------------------------------------- | ------------------------ | -------- |
| `monitoring/vault/config/stage7/config.hcl`   | Canonical Stage 7 config | ✅ Active |
| `docker-compose.yml` / `.override.stage7.yml` | Updated mounts           | ✅ Fixed  |
| `Makefile`                                    | Stage switch commands    | ✅ Fixed  |
| `README-final.md`                             | Updated vault tree       | ✅ Synced |
| `VAULT_QUICKSTART.md`                         | Updated structure docs   | ✅ Synced |
| `VAULT_MIGRATION_STAGE7_TO_STAGE9.md`         | Rollback instructions    | ✅ Synced |
| `STAGE7_VAULT_FIX_REPORT.md`                  | Reference diff           | ✅ Added  |

7. Validation Result
| Check                  | Result | Details                        |
| ---------------------- | ------ | ------------------------------ |
| Port 8200 availability | ✅      | `curl` reachable               |
| Duplicate listener     | ❌      | Eliminated                     |
| Vault logs             | ✅      | No errors                      |
| Config references      | ✅      | All updated                    |
| Compose validation     | ✅      | Passed `docker compose config` |
| Volume integrity       | ✅      | `zakupai_vault-data` OK        |


8. Recommended Next Steps

Update any local or CI scripts still using
-config=/vault/config/vault-config.hcl.

Adapt auto-unseal.sh for /bin/sh if needed.

Rebuild vault service via:
docker compose up -d vault --force-recreate

Verify full Stage 7 initialization:
vault operator init
vault operator unseal
vault status

Commit the changes:
git add monitoring/vault/config/stage7/ \
        docker-compose.yml \
        docker-compose.override.stage7.yml \
        Makefile \
        README-final.md \
        docs/VAULT_QUICKSTART.md \
        docs/VAULT_MIGRATION_STAGE7_TO_STAGE9.md \
        STAGE7_VAULT_FIX_REPORT.md \
        docs/STAGE7_VAULT_FIX_SUMMARY.md

git commit -m "fix(vault): resolve duplicate listener issue + relocate Stage7 configs"


Verified environment:
Linux Mint 21 • Docker 25.0 • Vault 1.15
Status: ✅ Stable after refactor
Next stage: integrate Stage 8 Auto-Unseal override
