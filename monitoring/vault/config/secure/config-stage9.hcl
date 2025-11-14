# Vault Configuration - Stage 9 (Production B2 + TLS + Audit)
# Purpose: Hardened Vault deployment on Backblaze B2 with TLS + audit logging

ui = true
disable_mlock = true  # Docker requirement

# Production Storage backend — Backblaze B2
storage "s3" {
  endpoint            = "https://s3.eu-central-003.backblazeb2.com"
  bucket              = "zakupai-vault"
  region              = "eu-central-003"
  s3_force_path_style = true
  disable_ssl         = false
  max_parallel        = 128
}

# Old fallback backend (disabled)
# storage "file" {
#   path = "/vault/file"
# }

# HTTPS listener
listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_disable   = false
  tls_cert_file = "/vault/tls/vault.crt"
  tls_key_file  = "/vault/tls/vault.key"

  # Supported cipher suites (comma-separated string as required by Vault 1.15)
  tls_min_version   = "tls12"
  tls_cipher_suites = "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256"

  telemetry {
    unauthenticated_metrics_access = false
  }
}

# Audit log to local volume (shipped to SIEM later)
audit {
  file {
    file_path      = "/vault/logs/audit.log"
    mode           = "0600"
    hmac_accessor  = true
    fallback       = true
  }
}

telemetry {
  prometheus_retention_time = "30s"
  disable_hostname          = false
  usage_gauge_period        = "10m"
}

api_addr     = "https://vault:8200"
cluster_addr = "https://vault:8201"
log_level    = "info"
log_format   = "json"

max_lease_ttl     = "768h"
default_lease_ttl = "168h"
plugin_directory  = "/vault/plugins"
