# ===========================================
# Vault Policy — calc-service
# ===========================================
# Grants calc-service read-only access to:
# - zakupai/data/db (database credentials)
# - zakupai/data/api (API keys)
#
# Usage:
#   vault policy write calc-service /vault/policies/calc-service-policy.hcl

# Database credentials
path "zakupai/data/db" {
  capabilities = ["read"]
}

# API keys
path "zakupai/data/api" {
  capabilities = ["read"]
}

# List secrets (for debugging)
path "zakupai/metadata/*" {
  capabilities = ["list"]
}
