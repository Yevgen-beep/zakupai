#!/bin/bash
set -euo pipefail

echo "=== ZakupAI Vault Network Migration ==="

# ===============================================
# PRE-FLIGHT CHECKS
# ===============================================
echo "[Pre-flight] Checking system state..."

if docker ps --format '{{.Names}}' | grep -q zakupai-vault; then
  echo "⚠️  Vault is running. Checking seal status..."
  if docker exec zakupai-vault vault status 2>/dev/null | grep -q "Sealed.*false"; then
    echo "❌ ERROR: Vault is unsealed and active"
    echo "Please seal vault before migration: docker exec zakupai-vault vault operator seal"
    exit 1
  fi
fi

# Check for active connections
if docker compose ps 2>/dev/null | grep -q "Up"; then
  echo "⚠️  WARNING: Active services detected:"
  docker compose ps
  read -p "Stop all services before migration? (yes/no): " response
  [[ "$response" == "yes" ]] && docker compose down || exit 1
fi

# ===============================================
# BACKUP PHASE
# ===============================================
echo "[1/6] Backing up existing volumes..."
BACKUP_DIR="./backups/vault-migration-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

if docker volume ls | grep -q zakupai_vault_data; then
  echo "  → Backing up vault_data..."
  docker run --rm \
    -v zakupai_vault_data:/data:ro \
    -v "$(pwd)/$BACKUP_DIR":/backup \
    alpine tar czf /backup/vault_data.tar.gz -C /data .
fi

if docker volume ls | grep -q zakupai_vault_logs; then
  echo "  → Backing up vault_logs..."
  docker run --rm \
    -v zakupai_vault_logs:/logs:ro \
    -v "$(pwd)/$BACKUP_DIR":/backup \
    alpine tar czf /backup/vault_logs.tar.gz -C /logs .
fi

echo "✅ Backups saved to: $BACKUP_DIR"

# ===============================================
# VOLUME MIGRATION
# ===============================================
echo "[2/6] Creating canonical volumes..."
docker volume create zakupai_vault-data 2>/dev/null || true
docker volume create zakupai_vault-logs 2>/dev/null || true

echo "[3/6] Migrating data to new volumes..."
if docker volume ls | grep -q zakupai_vault_data; then
  echo "  → Migrating vault_data → vault-data..."
  docker run --rm \
    -v zakupai_vault_data:/from:ro \
    -v zakupai_vault-data:/to \
    alpine sh -c 'cp -a /from/. /to/'
fi

if docker volume ls | grep -q zakupai_vault_logs; then
  echo "  → Migrating vault_logs → vault-logs..."
  docker run --rm \
    -v zakupai_vault_logs:/from:ro \
    -v zakupai_vault-logs:/to \
    alpine sh -c 'cp -a /from/. /to/'
fi

# ===============================================
# NETWORK SETUP
# ===============================================
echo "[4/6] Creating production networks..."
docker network create zakupai_zakupai-network 2>/dev/null || \
  echo "  ℹ️  zakupai_zakupai-network already exists"

docker network create --internal zakupai_monitoring-net 2>/dev/null || \
  echo "  ℹ️  zakupai_monitoring-net already exists"

# ===============================================
# VALIDATION
# ===============================================
echo "[5/6] Validating configuration..."
docker compose -f docker-compose.yml \
  -f docker-compose.override.stage9.vault-prod.yml \
  config > /dev/null || {
    echo "❌ ERROR: Invalid compose configuration"
    exit 1
  }

# ===============================================
# SERVICE RESTART
# ===============================================
echo "[6/6] Restarting Vault with new configuration..."
docker compose -f docker-compose.yml \
  -f docker-compose.override.stage9.vault-prod.yml \
  up -d vault

# Wait for Vault to be responsive
echo "Waiting for Vault to start..."
for i in {1..30}; do
  if docker exec zakupai-vault vault status &>/dev/null; then
    echo "✅ Vault is responsive"
    break
  fi
  sleep 2
done

docker exec zakupai-vault vault status || true

echo ""
echo "=========================================="
echo "✅ Migration complete!"
echo "=========================================="
echo "Backups location: $BACKUP_DIR"
echo ""
echo "Next steps:"
echo "  1. Unseal vault: docker exec zakupai-vault vault operator unseal"
echo "  2. Run verification: ./scripts/verify_vault_networks.sh"
echo "  3. Test service connectivity"
echo ""
echo "Rollback instructions: docs/NETWORK_ROLLBACK.md"
