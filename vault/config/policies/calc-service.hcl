# Policy for Calc Service
# Access to shared secrets and calc-specific secrets

# Shared database access
path "zakupai/data/shared/db" {
  capabilities = ["read"]
}

# Shared Redis access
path "zakupai/data/shared/redis" {
  capabilities = ["read"]
}

# Shared JWT secret
path "zakupai/data/shared/jwt" {
  capabilities = ["read"]
}

# Calc-specific configuration
path "zakupai/data/services/calc/config" {
  capabilities = ["read"]
}

# Goszakup API token (shared by multiple services)
path "zakupai/data/shared/goszakup" {
  capabilities = ["read"]
}

# Allow token renewal
path "auth/token/renew-self" {
  capabilities = ["update"]
}

# Allow token lookup
path "auth/token/lookup-self" {
  capabilities = ["read"]
}
