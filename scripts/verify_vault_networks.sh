#!/bin/bash
set -e

echo "=== ZakupAI Vault Network Verification ==="
echo ""

# ===============================================
# NETWORK CHECKS
# ===============================================
echo "[1/5] Verifying networks exist..."
for net in zakupai_zakupai-network zakupai_monitoring-net; do
  if docker network ls | grep -q "$net"; then
    echo "  ✅ $net"
  else
    echo "  ❌ $net NOT FOUND"
    exit 1
  fi
done

# Check monitoring-net is internal
if docker network inspect zakupai_monitoring-net | grep -q '"Internal": true'; then
  echo "  ✅ monitoring-net is internal (secure)"
else
  echo "  ⚠️  monitoring-net is not internal"
fi

# ===============================================
# COMPOSE VALIDATION
# ===============================================
echo "[2/5] Validating compose configuration..."
docker compose -f docker-compose.yml \
  -f docker-compose.override.stage9.vault-prod.yml \
  config > /dev/null && echo "  ✅ YAML syntax valid" || {
    echo "  ❌ Invalid configuration"
    exit 1
  }

# ===============================================
# VAULT STATUS
# ===============================================
echo "[3/5] Checking Vault status..."
if docker ps --format '{{.Names}}' | grep -q zakupai-vault; then
  docker exec zakupai-vault vault status || true
else
  echo "  ⚠️  Vault container not running"
fi

# ===============================================
# DNS RESOLUTION
# ===============================================
echo "[4/5] Testing DNS resolution from services..."
for service in calc-service risk-engine etl-service; do
  container="zakupai-${service}"
  if docker ps --format '{{.Names}}' | grep -q "$container"; then
    if docker exec "$container" getent hosts vault &>/dev/null; then
      ip=$(docker exec "$container" getent hosts vault | awk '{print $1}')
      echo "  ✅ $service → vault resolves to $ip"
    else
      echo "  ❌ $service cannot resolve vault"
    fi
  else
    echo "  ⚠️  $container not running (skipped)"
  fi
done

# ===============================================
# PROMETHEUS SCRAPING
# ===============================================
echo "[5/5] Testing Prometheus connectivity to Vault..."
if docker ps --format '{{.Names}}' | grep -q zakupai-prometheus; then
  if docker exec zakupai-prometheus wget -qO- --timeout=5 \
     http://vault:8200/v1/sys/metrics?format=prometheus 2>/dev/null | head -n 5; then
    echo "  ✅ Prometheus can scrape Vault metrics"
  else
    echo "  ❌ Prometheus cannot reach Vault"
  fi
else
  echo "  ⚠️  Prometheus not running (skipped)"
fi

echo ""
echo "=========================================="
echo "✅ Verification complete!"
echo "=========================================="
