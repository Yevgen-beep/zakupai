# ===========================================
# Vault Policy — etl-service
# ===========================================
# Grants etl-service read-only access to:
# - zakupai/data/db (database credentials)
# - zakupai/data/goszakup (Goszakup API token)
#
# Usage:
#   vault policy write etl-service /vault/policies/etl-service-policy.hcl

# Database credentials
path "zakupai/data/db" {
  capabilities = ["read"]
}

# Goszakup API token
path "zakupai/data/goszakup" {
  capabilities = ["read"]
}

# List secrets (for debugging)
path "zakupai/metadata/*" {
  capabilities = ["list"]
}
