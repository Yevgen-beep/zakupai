# Policy for Telegram Bot
# Access to shared secrets and bot-specific secrets

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

# Bot-specific Telegram token
path "zakupai/data/services/etl/telegram" {
  capabilities = ["read"]
}

# Goszakup API token
path "zakupai/data/shared/goszakup" {
  capabilities = ["read"]
}

# n8n and Flowise integrations
path "zakupai/data/shared/n8n" {
  capabilities = ["read"]
}

path "zakupai/data/shared/flowise" {
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
