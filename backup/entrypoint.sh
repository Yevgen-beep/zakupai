#!/bin/bash
set -e

# ===========================================
# ZakupAI DB Backup Service Entrypoint
# ===========================================

AUDIT_LOG_FILE="${AUDIT_LOG_FILE:-/backups/audit.log}"

# Audit logging function
audit_log() {
    local event_type=$1
    local status=$2
    local details=$3

    echo "{\"timestamp\":\"$(date -Iseconds)\",\"event\":\"$event_type\",\"status\":\"$status\",\"details\":\"$details\"}" >> "$AUDIT_LOG_FILE"
}

audit_log "backup_service_start" "info" "Backup service initializing"

# Setup rclone config directory permissions
mkdir -p /home/backup/.config/rclone
chown -R backup:backup /home/backup/.config

# Validate required environment variables
if [ -z "$POSTGRES_PASSWORD" ]; then
    audit_log "backup_service_start" "error" "POSTGRES_PASSWORD not set"
    echo "ERROR: POSTGRES_PASSWORD is not set"
    exit 1
fi

if [ -z "$B2_KEY_ID" ] || [ -z "$B2_APP_KEY" ] || [ -z "$B2_BUCKET" ]; then
    audit_log "backup_service_start" "warning" "B2 credentials not set - Backblaze sync disabled"
    echo "WARNING: B2 credentials not set - Backblaze sync will be skipped"
fi

echo "Starting backup service with cron schedule..."
echo "Timezone: $(cat /etc/timezone)"
echo "Current time: $(date)"
echo "Next backup: 03:00 Asia/Almaty"
echo "Audit log: $AUDIT_LOG_FILE"

audit_log "backup_service_start" "success" "Backup service started successfully"

# Start crond in foreground
exec "$@"
