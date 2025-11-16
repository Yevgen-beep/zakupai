#!/usr/bin/env bash
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "Run as root (sudo) so /var/lib/docker is readable."; exit 1; }

LOG="/var/log/zakupai-stale-scan-$(date +%Y%m%d-%H%M%S).log"
PATTERN='zakupai|n8n|flowise|ofelia|compose-project|compose-v2'
SCAN_PATHS=(
  /var/lib/docker/containers
  /var/lib/docker/overlay2
  /var/lib/docker/volumes
  /var/lib/docker/buildkit
  /var/lib/docker/compose
  /var/lib/docker/compose/compose-v2
  /var/lib/docker/compose/desktop-compose
  /etc/docker
  /home/*/.docker
  /home/*/.local/share/docker
  /home/*/.local/share/containers
)
CLEAN_GLOBS=(
  "/var/lib/docker/compose/*zakupai*"
  "/var/lib/docker/compose/compose-v2/*zakupai*"
  "/var/lib/docker/compose/desktop-compose/*zakupai*"
  "/home/*/.docker/compose/*zakupai*"
  "/home/*/.docker/compose/desktop-compose/*zakupai*"
)

echo "ZakupAI stale Docker state scan started at $(date)" | tee "$LOG"

if command -v rg >/dev/null 2>&1; then
  read -r -a SCANNER <<<"rg -n -i --color=never -e $PATTERN"
else
  read -r -a SCANNER <<<"grep -R -n -i -E $PATTERN"
fi

for path in "${SCAN_PATHS[@]}"; do
  [[ -e $path ]] || continue
  echo "[SCAN] $path" | tee -a "$LOG"
  while IFS=: read -r file lineno snippet; do
    [[ -f $file ]] || continue
    ftype=$(file -b "$file" 2>/dev/null || echo "unknown")
    echo "$file | $ftype | line $lineno | $snippet" | tee -a "$LOG"
  done < <("${SCANNER[@]}" "$path" 2>/dev/null || true)
done

shopt -s nullglob
for glob in "${CLEAN_GLOBS[@]}"; do
  for match in $glob; do
    [[ -e $match ]] || continue
    echo "[REMOVE] $match" | tee -a "$LOG"
    rm -rf -- "$match"
  done
done
shopt -u nullglob

echo "[PRUNE] docker system prune --force"   | tee -a "$LOG"
docker system prune --force                 | tee -a "$LOG"
echo "[PRUNE] docker container prune --force" | tee -a "$LOG"
docker container prune --force              | tee -a "$LOG"
echo "[PRUNE] docker network prune --force"  | tee -a "$LOG"
docker network prune --force                | tee -a "$LOG"

echo "Inspection + cleanup complete. Report: $LOG"
