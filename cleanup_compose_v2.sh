#!/usr/bin/env bash
set -euo pipefail

TARGETS=(
  "/var/lib/docker/compose"
  "/var/lib/docker/compose/compose-v2"
  "/var/lib/docker/compose/desktop-compose"
)

echo "[INFO] Searching stale compose projects..."

for dir in "${TARGETS[@]}"; do
  if [[ -d "$dir" ]]; then
    echo "[SCAN] $dir"

    sudo find "$dir" -type f -iname "*zakupai*" -print -exec rm -f {} +
    sudo find "$dir" -type f -iname "*n8n*" -print -exec rm -f {} +
    sudo find "$dir" -type f -iname "*flowise*" -print -exec rm -f {} +
    sudo find "$dir" -type f -iname "*ofelia*" -print -exec rm -f {} +

    sudo find "$dir" -type d -iname "*zakupai*" -print -exec rm -rf {} +
    sudo find "$dir" -type d -iname "*n8n*" -print -exec rm -rf {} +
    sudo find "$dir" -type d -iname "*flowise*" -print -exec rm -rf {} +
    sudo find "$dir" -type d -iname "*ofelia*" -print -exec rm -rf {} +

  fi
done

echo "[INFO] Done."
