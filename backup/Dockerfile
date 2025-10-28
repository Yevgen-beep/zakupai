FROM alpine:3.18

RUN apk add --no-cache \
    postgresql-client \
    rclone \
    bash \
    curl \
    gzip \
    tzdata \
    dcron

RUN cp /usr/share/zoneinfo/Asia/Almaty /etc/localtime && \
    echo "Asia/Almaty" > /etc/timezone

RUN adduser -D -s /bin/bash backup && \
    mkdir -p /backups /scripts /home/backup/.config/rclone && \
    chown -R backup:backup /home/backup

# === исправленные пути ===
COPY backup/backup.sh /scripts/backup.sh
COPY backup/entrypoint.sh /scripts/entrypoint.sh
COPY backup/crontab /etc/crontabs/backup

RUN chmod +x /scripts/*.sh && chmod 600 /etc/crontabs/backup

USER backup
ENTRYPOINT ["/scripts/entrypoint.sh"]
