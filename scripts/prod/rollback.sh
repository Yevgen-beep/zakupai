#!/usr/bin/env bash
set -euo pipefail

LAST=$(ls -t backups/compose-*.yml | head -1)

if [[ -z "$LAST" ]]; then
  echo "No backups found"
  exit 1
fi

echo "Rolling back to $LAST"
docker compose -f "$LAST" up -d --remove-orphans
