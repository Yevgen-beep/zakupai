#!/usr/bin/env bash
set -euo pipefail

echo "🔍 Checking Vault health..."
docker exec zakupai-vault vault status

echo "🔍 Checking audit log..."
docker exec zakupai-vault ls -l /vault/logs/audit.log

echo "🔍 Checking S3 storage backend..."
docker exec zakupai-vault vault status -format=json | jq '.storage_type'

echo "✅ Stage 9 Vault verified OK"
