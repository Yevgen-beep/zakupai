# Vault Configuration - Stage 7 (Manual File Backend)
# Purpose: Development/Testing environment with manual unseal
# Security: TLS disabled, manual unseal required after restart

ui = true
disable_mlock = true  # Required for Docker environments

# Storage: Local file backend
storage "file" {
  path = "/vault/data"
}

# Listener: HTTP only (no TLS)
listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_disable   = true

  # Telemetry
  telemetry {
    unauthenticated_metrics_access = true
  }
}

# Telemetry: Prometheus metrics
telemetry {
  prometheus_retention_time = "30s"
  disable_hostname          = false

  # Metrics prefixes
  usage_gauge_period = "10m"
}

# API settings
api_addr = "http://127.0.0.1:8200"

# Logging
log_level = "info"
log_format = "json"

# Maximum lease TTL
max_lease_ttl = "768h"
default_lease_ttl = "768h"
