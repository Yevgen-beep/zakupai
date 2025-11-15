#!/usr/bin/env bash
set -euo pipefail

CREDS="monitoring/vault/creds"

echo "=== Vault Manual Unseal ==="

SEALED=$(docker exec -e VAULT_SKIP_VERIFY=true zakupai-vault \
  vault status -format=json | jq -r '.sealed')

if [[ "$SEALED" == "false" ]]; then
  echo "Vault already unsealed"
  exit 0
fi

for i in 1 2 3; do
  KEY=$(cat "$CREDS/unseal_key_${i}.txt")
  echo "Applying key $i..."
  docker exec -e VAULT_SKIP_VERIFY=true zakupai-vault vault operator unseal "$KEY"
done

docker exec -e VAULT_SKIP_VERIFY=true zakupai-vault vault status
