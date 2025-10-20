#!/bin/bash
set -e

# Setup rclone config directory permissions
mkdir -p /home/backup/.config/rclone
chown -R backup:backup /home/backup/.config

# Validate required environment variables
if [ -z "$POSTGRES_PASSWORD" ]; then
    echo "ERROR: POSTGRES_PASSWORD is not set"
    exit 1
fi

if [ -z "$B2_KEY_ID" ] || [ -z "$B2_APP_KEY" ] || [ -z "$B2_BUCKET" ]; then
    echo "ERROR: B2 credentials (B2_KEY_ID, B2_APP_KEY, B2_BUCKET) are not set"
    exit 1
fi

echo "Starting backup service with cron schedule..."
echo "Timezone: $(cat /etc/timezone)"
echo "Current time: $(date)"
echo "Next backup: 03:00 Asia/Almaty"

# Start crond in foreground
exec "$@"
