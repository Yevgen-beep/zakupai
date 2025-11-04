# Admin Policy
# Full access to all Zakupai secrets for administration and migration

# Full access to all Zakupai KV v2 secrets
path "zakupai/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Full access to metadata
path "zakupai/metadata/*" {
  capabilities = ["read", "list"]
}

# AppRole management
path "auth/approle/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Policy management
path "sys/policies/acl/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Token management
path "auth/token/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Audit log access
path "sys/audit" {
  capabilities = ["read", "list"]
}

path "sys/audit/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# Health and seal status
path "sys/health" {
  capabilities = ["read"]
}

path "sys/seal-status" {
  capabilities = ["read"]
}

# Mount management
path "sys/mounts/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
