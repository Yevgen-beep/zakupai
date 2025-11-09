# Vault Initialization Scripts

## Security Requirements

### CRITICAL: Docker Volume Configuration

All Vault scripts write sensitive data to `/vault/data`:
- `init.json` - Contains unseal keys and root token
- `.env.vault` - Contains root token for application use

**NEVER use bind mounts for `/vault/data`!**

### Safe Configuration (Docker Volume)
```yaml
volumes:
  - vault-data:/vault/data  # ✅ SAFE - Data stays in Docker volume
```

### UNSAFE Configuration (Bind Mount)
```yaml
volumes:
  - ./vault/data:/vault/data  # ❌ DANGEROUS - Secrets written to host filesystem
```

## Environment Variables

### VAULT_SECRETS_PATH
Scripts respect the `VAULT_SECRETS_PATH` environment variable (default: `/vault/data`).

For testing with alternative paths:
```yaml
environment:
  VAULT_SECRETS_PATH: /tmp/vault-test-secrets
```

## Files Excluded from Git

The following patterns are excluded via `.gitignore`:
- `vault/data/*` (except `.gitkeep`)
- `vault/scripts/*.sh` (except this README)
- All `*.env*` files
- All TLS artifacts (`*.key`, `*.crt`, `*.csr`, `*.srl`)

## Production Recommendations

1. Use external secret management (AWS Secrets Manager, Azure Key Vault)
2. Implement proper TLS with valid certificates
3. Enable audit logging
4. Use AppRole authentication for applications
5. Never commit the auto-init scripts to production images
