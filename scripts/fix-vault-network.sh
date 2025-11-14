#!/usr/bin/env bash
# ============================================================================
# Quick Fix: Vault Network Error (Stage 9)
# ============================================================================
# Problem: "network 96a79ee9f42a... not found"
# Cause: Orphaned network references in container metadata
# Solution: Clean slate + recreate

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Fixing Vault Network Issue (Stage 9) ===${NC}\n"

# ============================================================================
# Step 1: Stop and remove ALL containers
# ============================================================================
echo -e "${YELLOW}1️⃣  Stopping all containers...${NC}"

docker compose -f docker-compose.yml \
  -f docker-compose.override.stage9.vault-prod.yml \
  down --remove-orphans --volumes 2>/dev/null || true

# Also remove any vault-related containers manually
docker rm -f zakupai-vault zakupai-vault-tls-init-1 2>/dev/null || true

echo -e "${GREEN}✅ Containers removed${NC}\n"

# ============================================================================
# Step 2: Prune networks (removes orphaned network references)
# ============================================================================
echo -e "${YELLOW}2️⃣  Pruning unused networks...${NC}"

docker network prune -f

echo -e "${GREEN}✅ Networks pruned${NC}\n"

# ============================================================================
# Step 3: Recreate required external networks
# ============================================================================
echo -e "${YELLOW}3️⃣  Creating required networks...${NC}"

# Check if networks exist, create if not
docker network inspect zakupai_zakupai-network >/dev/null 2>&1 || \
  docker network create zakupai_zakupai-network

docker network inspect zakupai_monitoring-net >/dev/null 2>&1 || \
  docker network create zakupai_monitoring-net

echo -e "${GREEN}✅ Networks ready${NC}\n"

# ============================================================================
# Step 4: Validate compose configuration
# ============================================================================
echo -e "${YELLOW}4️⃣  Validating compose configuration...${NC}"

docker compose -f docker-compose.yml \
  -f docker-compose.override.stage9.vault-prod.yml \
  config > /dev/null

echo -e "${GREEN}✅ Compose config valid${NC}\n"

# ============================================================================
# Step 5: Recreate vault with clean state
# ============================================================================
echo -e "${YELLOW}5️⃣  Starting Vault with clean network state...${NC}"

docker compose -f docker-compose.yml \
  -f docker-compose.override.stage9.vault-prod.yml \
  up -d --force-recreate vault

echo -e "${GREEN}✅ Vault started${NC}\n"

# ============================================================================
# Step 6: Verify
# ============================================================================
echo -e "${YELLOW}6️⃣  Verifying Vault status...${NC}"

sleep 5

# Check init container
if docker ps -a | grep -q "zakupai-vault-tls-init"; then
    echo -e "Init container: $(docker inspect zakupai-vault-tls-init-1 --format '{{.State.Status}}')"
fi

# Check vault container
if docker ps | grep -q "zakupai-vault"; then
    echo -e "${GREEN}✅ Vault container running${NC}"
    docker logs --tail=20 zakupai-vault
else
    echo -e "${RED}❌ Vault not running${NC}"
    docker logs --tail=50 zakupai-vault 2>/dev/null || true
    exit 1
fi

echo -e "\n${GREEN}=== Network Fix Complete ===${NC}"
echo -e "${YELLOW}Check Vault health: docker exec zakupai-vault vault status${NC}"