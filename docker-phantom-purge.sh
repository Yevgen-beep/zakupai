#!/usr/bin/env bash
#
# docker-phantom-purge.sh
# Safe Docker phantom container cleanup tool
#
# Purpose: Remove phantom/stale container states while preserving:
#   - Working images
#   - Named volumes (database data)
#   - Networks (unless orphaned)
#   - Running containers
#
# Safety features:
#   - Dry-run mode by default
#   - Explicit confirmation required
#   - Preserves production data
#   - Detailed logging
#
# Usage:
#   ./docker-phantom-purge.sh --dry-run     # Preview actions
#   ./docker-phantom-purge.sh --execute     # Execute cleanup

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

MODE="${1:---dry-run}"
CONTAINER_NAME="${2:-zakupai-flowise}"
PROJECT_NAME="zakupai"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="docker_phantom_purge_${TIMESTAMP}.log"

echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Docker Phantom Container Cleanup Tool${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "Mode: ${YELLOW}${MODE}${NC}"
echo -e "Target: ${YELLOW}${CONTAINER_NAME}${NC}"
echo -e "Log: ${YELLOW}${LOG_FILE}${NC}"
echo ""

# Initialize log
cat > "$LOG_FILE" <<EOF
Docker Phantom Container Cleanup Log
====================================
Date: $(date)
Mode: ${MODE}
Target: ${CONTAINER_NAME}
Project: ${PROJECT_NAME}

EOF

# Function to log actions
log_action() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"

    case "$level" in
        "INFO")
            echo -e "${BLUE}ℹ${NC} $message"
            ;;
        "WARN")
            echo -e "${YELLOW}⚠${NC} $message"
            ;;
        "ERROR")
            echo -e "${RED}✗${NC} $message"
            ;;
        "SUCCESS")
            echo -e "${GREEN}✓${NC} $message"
            ;;
        "ACTION")
            echo -e "${MAGENTA}▶${NC} $message"
            ;;
    esac
}

# Function to execute or simulate command
run_cmd() {
    local description="$1"
    shift
    local cmd="$@"

    log_action "ACTION" "$description"
    echo "  Command: $cmd" >> "$LOG_FILE"

    if [[ "$MODE" == "--execute" ]]; then
        if eval "$cmd" >> "$LOG_FILE" 2>&1; then
            log_action "SUCCESS" "Executed: $description"
            return 0
        else
            log_action "ERROR" "Failed: $description"
            return 1
        fi
    else
        log_action "INFO" "[DRY-RUN] Would execute: $description"
        return 0
    fi
}

# Safety check: Confirm execution mode
if [[ "$MODE" == "--execute" ]]; then
    echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  WARNING: EXECUTE MODE${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "This will permanently remove phantom container states."
    echo ""
    echo "Protected items (will NOT be removed):"
    echo "  - Named volumes (database data)"
    echo "  - Images"
    echo "  - Running containers"
    echo "  - Active networks"
    echo ""
    read -p "Type 'YES' to confirm: " confirmation

    if [[ "$confirmation" != "YES" ]]; then
        log_action "INFO" "Cleanup cancelled by user"
        echo -e "${YELLOW}Cleanup cancelled.${NC}"
        exit 0
    fi
    echo ""
fi

# P1: Stop phantom container (if running)
log_action "INFO" "=== STEP 1: Stop Container ==="

if docker ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    CONTAINER_STATE=$(docker inspect "${CONTAINER_NAME}" --format='{{.State.Status}}')
    log_action "WARN" "Container is ${CONTAINER_STATE}"

    if [[ "$CONTAINER_STATE" == "running" ]]; then
        run_cmd "Stop running container" "docker stop ${CONTAINER_NAME}"
    fi
else
    log_action "INFO" "Container not running"
fi

# P2: Remove container from Docker API
log_action "INFO" "=== STEP 2: Remove Container ==="

if docker ps -a --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    run_cmd "Remove container from Docker" "docker rm -f ${CONTAINER_NAME}"
else
    log_action "INFO" "Container not in Docker API"
fi

# P3: Disconnect from networks
log_action "INFO" "=== STEP 3: Network Cleanup ==="

NETWORKS=$(docker network ls --filter "name=${PROJECT_NAME}" --format "{{.Name}}" || true)
if [[ -n "$NETWORKS" ]]; then
    for net in $NETWORKS; do
        if docker network inspect "$net" 2>/dev/null | grep -q "\"${CONTAINER_NAME}\""; then
            log_action "WARN" "Container attached to network: $net"
            run_cmd "Disconnect from network $net" "docker network disconnect -f $net ${CONTAINER_NAME} 2>/dev/null || true"
        else
            log_action "INFO" "Container not in network: $net"
        fi
    done
else
    log_action "INFO" "No project networks found"
fi

# P4: Clean containerd namespace
log_action "INFO" "=== STEP 4: containerd Cleanup ==="

if command -v ctr &>/dev/null; then
    if sudo ctr -n moby containers ls 2>&1 | grep -q "${CONTAINER_NAME}"; then
        log_action "WARN" "Found in containerd moby namespace"
        run_cmd "Remove from containerd containers" "sudo ctr -n moby containers rm ${CONTAINER_NAME}"
    else
        log_action "INFO" "Not in containerd containers"
    fi

    if sudo ctr -n moby tasks ls 2>&1 | grep -q "${CONTAINER_NAME}"; then
        log_action "WARN" "Found task in containerd"
        run_cmd "Kill containerd task" "sudo ctr -n moby tasks kill ${CONTAINER_NAME}"
        run_cmd "Remove containerd task" "sudo ctr -n moby tasks rm ${CONTAINER_NAME}"
    else
        log_action "INFO" "No containerd tasks"
    fi
else
    log_action "INFO" "containerd (ctr) not available"
fi

# P5: Clean filesystem artifacts
log_action "INFO" "=== STEP 5: Filesystem Cleanup ==="

# Find container ID if exists
CONTAINER_ID=$(docker ps -a --filter "name=${CONTAINER_NAME}" --format "{{.ID}}" || echo "")

if [[ -n "$CONTAINER_ID" ]] && sudo test -d "/var/lib/docker/containers/${CONTAINER_ID}"; then
    log_action "WARN" "Found container directory: ${CONTAINER_ID}"
    run_cmd "Remove container directory" "sudo rm -rf /var/lib/docker/containers/${CONTAINER_ID}"
else
    log_action "INFO" "No container directory found"
fi

# P6: Clean runtime bundles
log_action "INFO" "=== STEP 6: Runtime Bundle Cleanup ==="

if [[ -n "$CONTAINER_ID" ]] && sudo test -d "/run/docker/containerd/daemon/io.containerd.runtime.v2.task/moby/${CONTAINER_ID}"; then
    log_action "WARN" "Found runtime bundle"
    run_cmd "Remove runtime bundle" "sudo rm -rf /run/docker/containerd/daemon/io.containerd.runtime.v2.task/moby/${CONTAINER_ID}"
else
    log_action "INFO" "No runtime bundles"
fi

# P7: Clean systemd units
log_action "INFO" "=== STEP 7: systemd Unit Cleanup ==="

SYSTEMD_UNIT=$(systemctl list-units --all --no-pager --no-legend | grep -i "${CONTAINER_NAME}" | awk '{print $1}' || true)
if [[ -n "$SYSTEMD_UNIT" ]]; then
    log_action "WARN" "Found systemd unit: $SYSTEMD_UNIT"
    run_cmd "Stop systemd unit" "sudo systemctl stop $SYSTEMD_UNIT"
    run_cmd "Reset failed systemd unit" "sudo systemctl reset-failed $SYSTEMD_UNIT || true"
else
    log_action "INFO" "No systemd units"
fi

# P8: Clean cgroups
log_action "INFO" "=== STEP 8: cgroup Cleanup ==="

CGROUP_PATHS=$(sudo find /sys/fs/cgroup -name "*${CONTAINER_NAME}*" 2>/dev/null || true)
if [[ -n "$CGROUP_PATHS" ]]; then
    log_action "WARN" "Found cgroup directories"
    while IFS= read -r cgroup_path; do
        if [[ -n "$cgroup_path" ]]; then
            run_cmd "Remove cgroup $cgroup_path" "sudo rmdir $cgroup_path 2>/dev/null || true"
        fi
    done <<< "$CGROUP_PATHS"
else
    log_action "INFO" "No cgroup directories"
fi

# P9: Prune Docker system (safe)
log_action "INFO" "=== STEP 9: Docker System Prune ==="

run_cmd "Prune stopped containers" "docker container prune -f"
log_action "INFO" "Skipping volume prune (preserving data)"
log_action "INFO" "Skipping image prune (preserving images)"

# P10: Validate cleanup
log_action "INFO" "=== STEP 10: Validation ==="

if docker ps -a --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    log_action "ERROR" "Container still exists in Docker!"
else
    log_action "SUCCESS" "Container removed from Docker"
fi

if docker network inspect "${PROJECT_NAME}-network" 2>/dev/null | grep -q "\"${CONTAINER_NAME}\""; then
    log_action "ERROR" "Container still in network!"
else
    log_action "SUCCESS" "Container removed from networks"
fi

# P11: Restart Docker (optional, commented out)
log_action "INFO" "=== STEP 11: Docker Daemon ==="
log_action "INFO" "Docker restart not required for this cleanup"
# Uncomment if needed:
# run_cmd "Restart Docker daemon" "sudo systemctl restart docker"

# Summary
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Cleanup complete!${NC}"
echo -e "Log file: ${YELLOW}${LOG_FILE}${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

if [[ "$MODE" == "--dry-run" ]]; then
    echo -e "${YELLOW}This was a DRY-RUN. No changes were made.${NC}"
    echo ""
    echo "To execute cleanup:"
    echo "  ./docker-phantom-purge.sh --execute"
else
    echo -e "${GREEN}Changes have been applied.${NC}"
    echo ""
    echo "Verify with:"
    echo "  docker ps -a | grep ${CONTAINER_NAME}"
    echo "  docker compose ps"
fi

echo ""
echo "Next steps:"
echo "  1. docker compose up -d    # Start fresh containers"
echo "  2. docker compose ps       # Verify all services"
echo "  3. docker compose logs -f  # Monitor logs"
