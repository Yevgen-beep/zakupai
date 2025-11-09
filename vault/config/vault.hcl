# ============================================================================
# HashiCorp Vault Configuration for ZakupAI
# ============================================================================

# Storage backend - File storage for development/staging
storage "file" {
  path = "/vault/data"
}

# TCP listener - TLS disabled for internal Docker network
# IMPORTANT: Enable TLS in production with valid certificates
listener "tcp" {
  address         = "0.0.0.0:8200"
  tls_disable     = true
  # For production, uncomment and configure TLS:
  # tls_disable   = false
  # tls_cert_file = "/vault/tls/vault.crt"
  # tls_key_file  = "/vault/tls/vault.key"
}

# Telemetry for Prometheus monitoring
telemetry {
  prometheus_retention_time = "30s"
  disable_hostname          = true
}

# Security settings
disable_mlock = true  # Required for Docker
ui            = true  # Enable web UI

# API address for internal service discovery
api_addr      = "http://vault:8200"
# For production with TLS:
# api_addr    = "https://vault:8200"

# Cluster configuration (for future HA setup)
# cluster_addr = "https://vault:8201"

# Log level
log_level = "info"  # Options: trace, debug, info, warn, error

# Maximum lease TTL
max_lease_ttl = "168h"  # 7 days

# Default lease TTL
default_lease_ttl = "24h"  # 1 day
