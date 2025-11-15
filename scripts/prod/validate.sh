#!/usr/bin/env bash
set -euo pipefail

REQUIRED=(
  "compose/networks.yml"
  "compose/vault.prod.yml"
  "compose/gateway.prod.yml"
  "compose/monitoring.prod.yml"
  "compose/workflows.prod.yml"
  "gateway/nginx.prod.conf"
  "scripts/prod/deploy.sh"
  "scripts/prod/unseal-vault.sh"
  "scripts/prod/rollback.sh"
  "scripts/prod/validate.sh"
  "docs/deployment/PROD_BOOT_ORDER.md"
)

echo "=== VALIDATION ==="
ERR=0

for f in "${REQUIRED[@]}"; do
  if [[ -f "$f" ]]; then
    echo "\u2713 $f"
  else
    echo "\u274c Missing: $f"
    ((ERR++)) || true
  fi
done

if [[ $ERR -eq 0 ]]; then
  echo "SUCCESS"
else
  echo "FAILED"
  exit 1
fi
