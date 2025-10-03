#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE_CMD=(docker compose --profile stage6 \
  -f "$ROOT_DIR/docker-compose.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.yml" \
  -f "$ROOT_DIR/docker-compose.override.stage6.monitoring.yml" \
  -f "$ROOT_DIR/monitoring/vault/docker-compose.override.stage6.vault.yml")

BACKUP_DIR="$ROOT_DIR/monitoring/vault/backups"
mkdir -p "$BACKUP_DIR"

STAMP=$(date +%Y%m%d%H%M%S)
SNAPSHOT="$BACKUP_DIR/vault-file-$STAMP.tar.gz"

"${COMPOSE_CMD[@]}" exec -T vault sh -c 'tar czf - -C /vault file' > "$SNAPSHOT"
chmod 600 "$SNAPSHOT"
printf 'Snapshot written to %s\n' "$SNAPSHOT"
