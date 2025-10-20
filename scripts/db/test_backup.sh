#!/bin/bash
# Mock backup test script

# Simulate environment
export DRY_RUN=true
export POSTGRES_HOST=db
export POSTGRES_DB=zakupai
export POSTGRES_USER=zakupai
export POSTGRES_PASSWORD=zakupai
export B2_KEY_ID=mock_key_id
export B2_APP_KEY=mock_app_key
export B2_BUCKET=zakupai-backups
export B2_PREFIX=backups/postgres
export BACKUP_RETENTION_DAYS=14

# Mock function to simulate backup execution
mock_backup() {
    local date=$(date +%Y%m%d_%H%M%S)
    local filename="zakupai_${date}.sql.gz"
    local size=$((1024 + $RANDOM % 10240))  # Random size between 1-11KB

    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Starting database backup process..."
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Target: db:5432/zakupai"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Backup file: ${filename}"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Dry run: true"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Setting up rclone configuration for B2..."
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Creating database backup: ${filename}"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] DRY RUN: Would create backup with pg_dump"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Backup created successfully: /backups/${filename} (${size} bytes)"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Uploading backup to B2..."
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] DRY RUN: Would upload to b2:zakupai-backups/backups/postgres/${filename}"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] DRY RUN: rclone copy /backups/${filename} b2:zakupai-backups/backups/postgres/"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Cleaning up backups older than 14 days..."
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Deleted 0 old local backups"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] DRY RUN: Would cleanup old backups from B2"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Cleaning up local backup file..."
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Backup process completed successfully"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Final result: b2:zakupai-backups/backups/postgres/${filename}"

    # Return path and size info
    echo "RESULT: b2:zakupai-backups/backups/postgres/${filename} (${size} bytes)"
}

mock_backup
