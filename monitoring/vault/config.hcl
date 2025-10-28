# ===========================================
# Vault Configuration — ZakupAI Development
# ===========================================
# This config uses file storage and dev-friendly settings.
# For production: switch to raft storage + TLS.

storage "file" {
  path = "/vault/file"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = 1
}

# Disable mlock for container environments
disable_mlock = true

# Enable Web UI
ui = true

# Prometheus metrics endpoint
# Note: unauthenticated_metrics_access removed in Vault 1.17+
telemetry {
  prometheus_retention_time = "24h"
  disable_hostname          = true
}

# API address (must match listener for standalone mode)
#api_addr = "http://127.0.0.1:8200"
