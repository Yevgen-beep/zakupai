# ===========================================
# Vault Policy — risk-engine
# ===========================================
# Grants risk-engine read-only access to:
# - zakupai/data/db (database credentials)
# - zakupai/data/api (API keys)
# - zakupai/data/goszakup (Goszakup API token)
#
# Usage:
#   vault policy write risk-engine /vault/policies/risk-engine-policy.hcl

# Database credentials
path "zakupai/data/db" {
  capabilities = ["read"]
}

# API keys
path "zakupai/data/api" {
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
