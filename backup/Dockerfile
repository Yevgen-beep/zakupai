FROM alpine:3.18

# Install required packages
RUN apk add --no-cache \
    postgresql-client \
    rclone \
    bash \
    curl \
    gzip \
    tzdata \
    dcron \
    && rm -rf /var/cache/apk/*

# Set timezone
RUN cp /usr/share/zoneinfo/Asia/Almaty /etc/localtime && \
    echo "Asia/Almaty" > /etc/timezone

# Create backup user and directories
RUN adduser -D -s /bin/bash backup && \
    mkdir -p /backups /scripts /home/backup/.config/rclone && \
    chown -R backup:backup /backups /scripts /home/backup

# Copy scripts
COPY backup.sh /scripts/backup.sh
COPY entrypoint.sh /scripts/entrypoint.sh
RUN chmod +x /scripts/*.sh

# Setup cron
COPY crontab /etc/crontabs/backup
RUN chmod 600 /etc/crontabs/backup

# Switch to backup user
USER backup
WORKDIR /home/backup

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep crond >/dev/null || exit 1

ENTRYPOINT ["/scripts/entrypoint.sh"]
CMD ["crond", "-f", "-l", "2"]
