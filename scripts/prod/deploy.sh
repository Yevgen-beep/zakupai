#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILES=(
  "docker-compose.yml"
  "compose/networks.yml"
  "compose/vault.prod.yml"
  "compose/gateway.prod.yml"
  "compose/monitoring.prod.yml"
  "compose/workflows.prod.yml"
)

build_args() {
  for f in "${COMPOSE_FILES[@]}"; do
    echo "-f $f"
  done
}

echo "=== ZakupAI PROD Deployment ==="

mkdir -p backups
BACKUP="backups/compose-$(date +%Y%m%d-%H%M%S).yml"
docker compose $(build_args) config > "$BACKUP"

echo "Backup saved: $BACKUP"

docker compose $(build_args) pull
docker compose $(build_args) up -d --remove-orphans

echo "Sleeping 30s..."
sleep 30

docker compose $(build_args) ps
echo "DONE"
