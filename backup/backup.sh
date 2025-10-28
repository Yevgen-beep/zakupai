#!/bin/bash
set -euo pipefail

# Configuration
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILENAME="zakupai_${BACKUP_DATE}.sql.gz"
BACKUP_PATH="/backups/${BACKUP_FILENAME}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
DRY_RUN="${DRY_RUN:-false}"

# Database connection
DB_HOST="${POSTGRES_HOST:-db}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-zakupai}"
DB_USER="${POSTGRES_USER:-zakupai}"
DB_PASSWORD="${POSTGRES_PASSWORD}"

# B2 configuration
B2_KEY_ID="${B2_KEY_ID}"
B2_APP_KEY="${B2_APP_KEY}"
B2_BUCKET="${B2_BUCKET}"
B2_PREFIX="${B2_PREFIX:-backups/postgres}"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >&2
}

# Audit logging function
AUDIT_LOG_FILE="${AUDIT_LOG_FILE:-/backups/audit.log}"
audit_log() {
    local event_type=$1
    local status=$2
    local details=$3

    echo "{\"timestamp\":\"$(date -Iseconds)\",\"event\":\"$event_type\",\"status\":\"$status\",\"details\":\"$details\",\"backup_file\":\"${BACKUP_FILENAME:-}\"}" >> "$AUDIT_LOG_FILE"
}

setup_rclone() {
    log "Setting up rclone configuration for B2..."

    cat > /home/backup/.config/rclone/rclone.conf <<EOF
[b2]
type = b2
account = ${B2_KEY_ID}
key = ${B2_APP_KEY}
hard_delete = true
EOF

    chmod 600 /home/backup/.config/rclone/rclone.conf
}

create_backup() {
    log "Creating database backup: ${BACKUP_FILENAME}"
    audit_log "backup_create_start" "info" "Starting backup for database ${DB_NAME}"

    if [ "$DRY_RUN" = "true" ]; then
        log "DRY RUN: Would create backup with pg_dump"
        # Create mock backup file for testing
        echo "Mock backup data for ${DB_NAME} at $(date)" | gzip > "$BACKUP_PATH"
    else
        # Set password for pg_dump
        export PGPASSWORD="$DB_PASSWORD"

        # Create backup with compression
        pg_dump \
            --host="$DB_HOST" \
            --port="$DB_PORT" \
            --username="$DB_USER" \
            --dbname="$DB_NAME" \
            --verbose \
            --clean \
            --if-exists \
            --create \
            --format=plain \
        | gzip > "$BACKUP_PATH"

        unset PGPASSWORD
    fi

    # Check if backup was created successfully
    if [ ! -f "$BACKUP_PATH" ]; then
        log "ERROR: Backup file was not created"
        audit_log "backup_create_complete" "error" "Backup file not created"
        exit 1
    fi

    local backup_size=$(stat -c%s "$BACKUP_PATH")
    log "Backup created successfully: ${BACKUP_PATH} (${backup_size} bytes)"

    # Verify backup integrity
    if ! gzip -t "$BACKUP_PATH"; then
        log "ERROR: Backup file is corrupted"
        audit_log "backup_create_complete" "error" "Backup file corrupted"
        exit 1
    fi

    audit_log "backup_create_complete" "success" "Backup created successfully, size: ${backup_size} bytes"
}

upload_backup() {
    log "Uploading backup to B2..."
    audit_log "backup_upload_start" "info" "Uploading to B2 bucket ${B2_BUCKET}"

    local remote_path="b2:${B2_BUCKET}/${B2_PREFIX}/${BACKUP_FILENAME}"

    if [ "$DRY_RUN" = "true" ]; then
        log "DRY RUN: Would upload to ${remote_path}"
        log "DRY RUN: rclone copy ${BACKUP_PATH} b2:${B2_BUCKET}/${B2_PREFIX}/"
        audit_log "backup_upload_complete" "info" "DRY RUN: Upload skipped"
    else
        rclone copy "$BACKUP_PATH" "b2:${B2_BUCKET}/${B2_PREFIX}/" \
            --progress \
            --stats=10s \
            --transfers=1 \
            --checkers=1

        # Verify upload
        if rclone lsf "b2:${B2_BUCKET}/${B2_PREFIX}/" | grep -q "$BACKUP_FILENAME"; then
            log "Backup uploaded successfully to ${remote_path}"
            audit_log "backup_upload_complete" "success" "Uploaded to ${remote_path}"
        else
            log "ERROR: Backup upload verification failed"
            audit_log "backup_upload_complete" "error" "Upload verification failed"
            exit 1
        fi
    fi
}

cleanup_old_backups() {
    log "Cleaning up backups older than ${RETENTION_DAYS} days..."

    # Local cleanup
    find /backups -name "zakupai_*.sql.gz" -mtime +${RETENTION_DAYS} -delete
    local_deleted=$(find /backups -name "zakupai_*.sql.gz" -mtime +${RETENTION_DAYS} 2>/dev/null | wc -l)
    log "Deleted ${local_deleted} old local backups"

    # Remote cleanup
    if [ "$DRY_RUN" = "true" ]; then
        log "DRY RUN: Would cleanup old backups from B2"
    else
        # List remote backups and delete old ones
        rclone ls "b2:${B2_BUCKET}/${B2_PREFIX}/" | while read size filename; do
            # Extract date from filename (zakupai_YYYYMMDD_HHMMSS.sql.gz)
            if [[ $filename =~ zakupai_([0-9]{8})_[0-9]{6}\.sql\.gz$ ]]; then
                backup_date="${BASH_REMATCH[1]}"
                cutoff_date=$(date -d "${RETENTION_DAYS} days ago" +%Y%m%d)

                if [ "$backup_date" -lt "$cutoff_date" ]; then
                    log "Deleting old backup: $filename"
                    rclone delete "b2:${B2_BUCKET}/${B2_PREFIX}/$filename"
                fi
            fi
        done
    fi
}

cleanup_local() {
    log "Cleaning up local backup file..."
    rm -f "$BACKUP_PATH"
}

main() {
    log "Starting database backup process..."
    log "Target: ${DB_HOST}:${DB_PORT}/${DB_NAME}"
    log "Backup file: ${BACKUP_FILENAME}"
    log "Dry run: ${DRY_RUN}"

    # Validate required environment variables
    if [ -z "$DB_PASSWORD" ]; then
        log "ERROR: POSTGRES_PASSWORD is not set"
        exit 1
    fi

    if [ -z "$B2_KEY_ID" ] || [ -z "$B2_APP_KEY" ] || [ -z "$B2_BUCKET" ]; then
        log "ERROR: B2 credentials are not set"
        exit 1
    fi

    # Setup rclone
    setup_rclone

    # Create backup directory if it doesn't exist
    mkdir -p /backups

    # Perform backup steps
    create_backup
    upload_backup
    cleanup_old_backups
    cleanup_local

    log "Backup process completed successfully"
    log "Final result: b2:${B2_BUCKET}/${B2_PREFIX}/${BACKUP_FILENAME}"
}

# Handle signals for graceful shutdown
trap 'log "Backup process interrupted"; exit 130' INT TERM

main "$@"
