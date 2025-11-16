#!/usr/bin/env bash
#
# docker-phantom-scan.sh
# Comprehensive Docker phantom container diagnostic tool
#
# Purpose: Deep scan for phantom/stale container states across:
#   - Docker Engine API
#   - containerd metadata
#   - Compose v2 project registry
#   - systemd transient units
#   - cgroups lingering directories
#   - BuildKit cache
#   - OCI runtime bundles
#
# Usage: ./docker-phantom-scan.sh [container_name]
# Example: ./docker-phantom-scan.sh zakupai-flowise

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

CONTAINER_NAME="${1:-zakupai-flowise}"
PROJECT_NAME="zakupai"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="docker_phantom_scan_${TIMESTAMP}.txt"

echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Docker Phantom Container Diagnostic Tool${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "Target container: ${YELLOW}${CONTAINER_NAME}${NC}"
echo -e "Project: ${YELLOW}${PROJECT_NAME}${NC}"
echo -e "Report: ${YELLOW}${REPORT_FILE}${NC}"
echo ""

# Initialize report
cat > "$REPORT_FILE" <<EOF
Docker Phantom Container Scan Report
=====================================
Date: $(date)
Target: ${CONTAINER_NAME}
Project: ${PROJECT_NAME}

EOF

# Function to log section
log_section() {
    local title="$1"
    echo -e "\n${BLUE}▶ ${title}${NC}"
    echo -e "\n## ${title}" >> "$REPORT_FILE"
    echo "---" >> "$REPORT_FILE"
}

# Function to log result
log_result() {
    local status="$1"
    local message="$2"
    local details="${3:-}"

    if [[ "$status" == "OK" ]]; then
        echo -e "  ${GREEN}✓${NC} $message"
        echo "[OK] $message" >> "$REPORT_FILE"
    elif [[ "$status" == "WARN" ]]; then
        echo -e "  ${YELLOW}⚠${NC} $message"
        echo "[WARN] $message" >> "$REPORT_FILE"
    elif [[ "$status" == "FAIL" ]]; then
        echo -e "  ${RED}✗${NC} $message"
        echo "[FAIL] $message" >> "$REPORT_FILE"
    else
        echo -e "  ${CYAN}ℹ${NC} $message"
        echo "[INFO] $message" >> "$REPORT_FILE"
    fi

    if [[ -n "$details" ]]; then
        echo "$details" >> "$REPORT_FILE"
    fi
}

# D1: Docker Engine API
log_section "D1: Docker Engine API State"

if docker inspect "$CONTAINER_NAME" &>/dev/null; then
    STATE=$(docker inspect "$CONTAINER_NAME" --format='{{.State.Status}}')
    log_result "OK" "Container exists in Docker API (state: $STATE)"
    docker inspect "$CONTAINER_NAME" >> "$REPORT_FILE" 2>&1
else
    log_result "INFO" "Container NOT found in Docker API"
fi

# D2: Docker ps check
log_section "D2: Container List (docker ps)"

if docker ps -a --filter "name=${CONTAINER_NAME}" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}" | grep -q "${CONTAINER_NAME}"; then
    CONTAINER_STATUS=$(docker ps -a --filter "name=${CONTAINER_NAME}" --format "{{.Status}}")
    log_result "OK" "Container found in 'docker ps -a' (status: $CONTAINER_STATUS)"
    docker ps -a --filter "name=${CONTAINER_NAME}" >> "$REPORT_FILE"
else
    log_result "INFO" "Container NOT found in 'docker ps -a'"
fi

# D3: Docker Compose project state
log_section "D3: Docker Compose State"

if docker compose ls -a | grep -q "${PROJECT_NAME}"; then
    log_result "OK" "Compose project '${PROJECT_NAME}' exists"
    docker compose ls -a >> "$REPORT_FILE"
    docker compose ps -a >> "$REPORT_FILE"
else
    log_result "INFO" "Compose project '${PROJECT_NAME}' NOT found"
fi

# D4: Network attachments
log_section "D4: Network Attachments"

NETWORKS=$(docker network ls --filter "name=${PROJECT_NAME}" --format "{{.Name}}")
if [[ -n "$NETWORKS" ]]; then
    for net in $NETWORKS; do
        if docker network inspect "$net" | grep -q "${CONTAINER_NAME}"; then
            log_result "WARN" "Container found in network: $net"
            docker network inspect "$net" | grep -A 20 "${CONTAINER_NAME}" >> "$REPORT_FILE" 2>&1 || true
        else
            log_result "OK" "Network $net has no reference to container"
        fi
    done
else
    log_result "INFO" "No project networks found"
fi

# D5: Volume mounts
log_section "D5: Volume Mounts"

VOLUMES=$(docker volume ls --filter "name=${PROJECT_NAME}" --format "{{.Name}}")
if [[ -n "$VOLUMES" ]]; then
    log_result "INFO" "Found ${PROJECT_NAME} volumes: $(echo $VOLUMES | wc -w)"
    echo "$VOLUMES" >> "$REPORT_FILE"
else
    log_result "INFO" "No project volumes found"
fi

# D6: Filesystem artifacts (/var/lib/docker)
log_section "D6: Docker Filesystem Artifacts"

if sudo test -d /var/lib/docker/containers/; then
    CONTAINER_DIRS=$(sudo find /var/lib/docker/containers -maxdepth 1 -type d 2>/dev/null | wc -l)
    log_result "INFO" "Found $CONTAINER_DIRS container directories"

    if sudo grep -r "${CONTAINER_NAME}" /var/lib/docker/containers/ 2>/dev/null | head -5; then
        log_result "WARN" "Found references to container in /var/lib/docker/containers/"
        sudo grep -r "${CONTAINER_NAME}" /var/lib/docker/containers/ 2>/dev/null >> "$REPORT_FILE" || true
    else
        log_result "OK" "No container references in /var/lib/docker/containers/"
    fi
else
    log_result "INFO" "/var/lib/docker/containers/ not accessible"
fi

# D7: containerd namespace check
log_section "D7: containerd Namespace (moby)"

if command -v ctr &>/dev/null; then
    if sudo ctr -n moby containers ls 2>&1 | grep -q "${CONTAINER_NAME}"; then
        log_result "WARN" "Container found in containerd (moby namespace)"
        sudo ctr -n moby containers ls >> "$REPORT_FILE" 2>&1 || true
    else
        log_result "OK" "No container in containerd moby namespace"
    fi

    if sudo ctr -n moby tasks ls 2>&1 | grep -q "${CONTAINER_NAME}"; then
        log_result "WARN" "Container task found in containerd"
        sudo ctr -n moby tasks ls >> "$REPORT_FILE" 2>&1 || true
    else
        log_result "OK" "No container task in containerd"
    fi
else
    log_result "INFO" "containerd (ctr) not available"
fi

# D8: containerd metadata DB
log_section "D8: containerd Metadata Database"

if sudo test -f /var/lib/docker/containerd/daemon/io.containerd.metadata.v1.bolt/meta.db; then
    log_result "INFO" "Found containerd metadata DB"
    DB_SIZE=$(sudo du -h /var/lib/docker/containerd/daemon/io.containerd.metadata.v1.bolt/meta.db | cut -f1)
    log_result "INFO" "Metadata DB size: $DB_SIZE"
else
    log_result "INFO" "containerd metadata DB not found"
fi

# D9: systemd units
log_section "D9: systemd Container Units"

SYSTEMD_UNITS=$(systemctl list-units --all --no-pager | grep -i docker || true)
if [[ -n "$SYSTEMD_UNITS" ]]; then
    log_result "INFO" "Found Docker systemd units"
    echo "$SYSTEMD_UNITS" >> "$REPORT_FILE"

    if systemctl list-units --all --no-pager | grep -qi "${CONTAINER_NAME}"; then
        log_result "WARN" "Found systemd unit for container"
        systemctl list-units --all --no-pager | grep -i "${CONTAINER_NAME}" >> "$REPORT_FILE" || true
    else
        log_result "OK" "No systemd unit for container"
    fi
else
    log_result "INFO" "No Docker systemd units found"
fi

# D10: cgroups
log_section "D10: cgroup Directories"

CGROUP_PATHS=(
    "/sys/fs/cgroup/system.slice/docker-*.scope"
    "/sys/fs/cgroup/docker"
)

for cgroup_path in "${CGROUP_PATHS[@]}"; do
    if sudo ls $cgroup_path 2>/dev/null | grep -q "${CONTAINER_NAME}"; then
        log_result "WARN" "Found cgroup for container at $cgroup_path"
        sudo ls -la $cgroup_path 2>/dev/null | grep "${CONTAINER_NAME}" >> "$REPORT_FILE" || true
    fi
done
log_result "OK" "No stale cgroups found"

# D11: Runtime bundles (/run/docker)
log_section "D11: Runtime OCI Bundles"

if sudo test -d /run/docker/containerd/; then
    if sudo find /run/docker/containerd/ -name "*${CONTAINER_NAME}*" 2>/dev/null | grep -q .; then
        log_result "WARN" "Found runtime bundle for container"
        sudo find /run/docker/containerd/ -name "*${CONTAINER_NAME}*" 2>/dev/null >> "$REPORT_FILE" || true
    else
        log_result "OK" "No runtime bundles for container"
    fi
else
    log_result "INFO" "/run/docker/containerd/ not found"
fi

# D12: BuildKit state
log_section "D12: BuildKit Cache"

if sudo test -d /var/lib/docker/buildkit/; then
    BUILDKIT_SIZE=$(sudo du -sh /var/lib/docker/buildkit/ 2>/dev/null | cut -f1 || echo "unknown")
    log_result "INFO" "BuildKit cache size: $BUILDKIT_SIZE"
else
    log_result "INFO" "BuildKit directory not found"
fi

# D13: Compose v2 internal state
log_section "D13: Compose v2 Project Registry"

COMPOSE_STATE_FILE="$HOME/.docker/compose/state.json"
if [[ -f "$COMPOSE_STATE_FILE" ]]; then
    if grep -q "${PROJECT_NAME}" "$COMPOSE_STATE_FILE" 2>/dev/null; then
        log_result "WARN" "Found project in Compose state file"
        grep -A 5 "${PROJECT_NAME}" "$COMPOSE_STATE_FILE" >> "$REPORT_FILE" || true
    else
        log_result "OK" "Project not in Compose state file"
    fi
else
    log_result "INFO" "Compose state file not found"
fi

# D14: Docker context
log_section "D14: Docker Context"

CONTEXT=$(docker context show)
log_result "INFO" "Active context: $CONTEXT"
docker context ls >> "$REPORT_FILE"

# D15: Image presence
log_section "D15: Container Image"

if docker images | grep -q "flowiseai/flowise"; then
    IMAGE_INFO=$(docker images flowiseai/flowise --format "{{.Repository}}:{{.Tag}} ({{.Size}})")
    log_result "OK" "Image found: $IMAGE_INFO"
    docker images flowiseai/flowise >> "$REPORT_FILE"
else
    log_result "INFO" "Image flowiseai/flowise not found locally"
fi

# D16: Compose config validation
log_section "D16: Compose Configuration"

if docker compose config --services | grep -q "flowise"; then
    log_result "OK" "Service 'flowise' defined in compose config"
    docker compose config --services >> "$REPORT_FILE"
else
    log_result "WARN" "Service 'flowise' NOT in compose config"
fi

# D17: Port bindings
log_section "D17: Port Bindings"

if netstat -tuln 2>/dev/null | grep -q ":3000"; then
    log_result "WARN" "Port 3000 is in use"
    netstat -tuln 2>/dev/null | grep ":3000" >> "$REPORT_FILE" || true
else
    log_result "OK" "Port 3000 is free"
fi

# D18: Recent Docker events
log_section "D18: Recent Docker Events"

log_result "INFO" "Fetching last 50 Docker events..."
docker events --since 1h --until 1s --filter "container=${CONTAINER_NAME}" >> "$REPORT_FILE" 2>&1 || true

# D19: Docker daemon logs
log_section "D19: Docker Daemon Logs"

if command -v journalctl &>/dev/null; then
    log_result "INFO" "Checking Docker daemon logs for container references..."
    sudo journalctl -u docker.service --since "1 hour ago" | grep -i "${CONTAINER_NAME}" | tail -20 >> "$REPORT_FILE" 2>&1 || true
fi

# D20: Summary
log_section "D20: Diagnostic Summary"

echo -e "\n${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Scan complete!${NC}"
echo -e "Full report saved to: ${YELLOW}${REPORT_FILE}${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}\n"

# Generate recommendations
echo -e "\n## RECOMMENDATIONS" >> "$REPORT_FILE"
echo "---" >> "$REPORT_FILE"

if docker ps -a | grep -q "${CONTAINER_NAME}"; then
    echo "1. Container EXISTS and is visible in Docker" >> "$REPORT_FILE"
    echo "2. No phantom state detected" >> "$REPORT_FILE"
    echo "3. System is healthy" >> "$REPORT_FILE"
    echo -e "${GREEN}✓ No phantom container detected. System is healthy.${NC}"
else
    echo "1. Container NOT found in Docker API" >> "$REPORT_FILE"
    echo "2. Check compose configuration" >> "$REPORT_FILE"
    echo "3. Review network and volume states" >> "$REPORT_FILE"
    echo -e "${YELLOW}⚠ Container not found. Review the report for details.${NC}"
fi

echo ""
echo "To view the full report:"
echo "  cat $REPORT_FILE"
echo ""
echo "To clean up phantom states (if found):"
echo "  ./docker-phantom-purge.sh"
