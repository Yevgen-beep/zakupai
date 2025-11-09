# Vault Configuration - Stage 9 (Production B2 + TLS + Audit)
# Purpose: Production environment with S3 storage, TLS, and audit logging
# Security: Full encryption in-transit and at-rest, comprehensive audit trail

ui = true
disable_mlock = true  # Required for Docker environments

# Storage: Backblaze B2 (S3-compatible)
storage "s3" {
  # Backblaze B2 S3-compatible endpoint
  endpoint = "https://s3.us-west-004.backblazeb2.com"

  bucket = "zakupai-vault-storage"
  region = "us-west-004"

  # Credentials from environment variables:
  # AWS_ACCESS_KEY_ID (B2 Application Key ID)
  # AWS_SECRET_ACCESS_KEY (B2 Application Key)

  # S3-specific settings
  s3_force_path_style = true
  disable_ssl         = false

  # Performance tuning
  max_parallel = 128
}

# Listener: HTTPS with TLS
listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_disable   = false

  # TLS certificates
  tls_cert_file = "/vault/tls/vault-cert.pem"
  tls_key_file  = "/vault/tls/vault-key.pem"

  # TLS configuration
  tls_min_version = "tls12"
  tls_cipher_suites = [
    "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
    "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
    "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
    "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256"
  ]

  # Telemetry
  telemetry {
    unauthenticated_metrics_access = true
  }
}

# Audit logging
audit {
  file {
    file_path = "/vault/logs/audit.log"

    # Log format
    log_raw = false
    hmac_accessor = true
    mode = "0600"

    # Fallback on failure
    fallback = true
  }
}

# Telemetry: Prometheus metrics
telemetry {
  prometheus_retention_time = "30s"
  disable_hostname          = false

  # Metrics prefixes
  usage_gauge_period = "10m"
}

# API settings (HTTPS)
api_addr = "https://vault.zakupai.local:8200"
cluster_addr = "https://vault.zakupai.local:8201"

# Logging
log_level = "info"
log_format = "json"

# Maximum lease TTL
max_lease_ttl = "768h"
default_lease_ttl = "768h"

# Plugin directory
plugin_directory = "/vault/plugins"

# HA settings (for future clustering)
# Note: Currently single-node, but S3 storage supports HA
ha_storage {
  enabled = false
}
