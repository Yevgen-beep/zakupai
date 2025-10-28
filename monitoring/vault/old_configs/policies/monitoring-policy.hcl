# ===========================================
# Vault Policy — monitoring
# ===========================================
# Grants monitoring services (Prometheus, Alertmanager) access to:
# - zakupai/data/monitoring (Telegram bot token, chat ID)
#
# Usage:
#   vault policy write monitoring /vault/policies/monitoring-policy.hcl

# Monitoring credentials (Telegram, Slack, PagerDuty, etc.)
path "zakupai/data/monitoring" {
  capabilities = ["read"]
}

# List secrets (for debugging)
path "zakupai/metadata/*" {
  capabilities = ["list"]
}
