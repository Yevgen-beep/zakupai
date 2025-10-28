# ===========================================
# Vault Policy — admin
# ===========================================
# Full admin policy for DevOps team.
# Grants full access to all secrets under zakupai/
#
# Usage:
#   vault policy write admin /vault/policies/admin-policy.hcl

# Full access to all secrets
path "zakupai/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Manage policies
path "sys/policies/acl/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Manage auth methods
path "sys/auth/*" {
  capabilities = ["create", "read", "update", "delete", "sudo"]
}

# Manage secret engines
path "sys/mounts/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# View system health
path "sys/health" {
  capabilities = ["read"]
}

# View metrics
path "sys/metrics" {
  capabilities = ["read"]
}
