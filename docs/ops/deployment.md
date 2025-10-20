# Deployment Guide

## Обзор

ZakupAI поддерживает три окружения развертывания: Development, Staging и Production. Каждое окружение имеет свои конфигурации, переменные среды и особенности развертывания.

## Окружения

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Development   │  │     Staging     │  │   Production    │
│                 │  │                 │  │                 │
│ • Local Docker  │  │ • Test Server   │  │ • Cloud/VPS     │
│ • Dev режим     │  │ • Stage БД      │  │ • Prod БД       │
│ • Моки данных   │  │ • Real API      │  │ • Мониторинг    │
│ • Debug логи    │  │ • Pre-prod тест │  │ • Backup/HA     │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Конфигурации окружений

### Development Environment

**Файлы:**

- `.env.dev` - переменные разработки
- `docker-compose.override.dev.yml` - dev override

**.env.dev:**

```bash
# Database
DB_HOST=zakupai-db
DB_PORT=5432
DB_NAME=zakupai_dev
DB_USER=zakupai
DB_PASSWORD=zakupai_dev_password

# API Keys
ZAKUPAI_API_KEY=dev-api-key-12345
TELEGRAM_BOT_TOKEN=123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA_DEV

# External Services
OLLAMA_BASE_URL=http://host.docker.internal:11434
OPENAI_API_KEY=sk-dev-key

# Logging
LOG_LEVEL=DEBUG

# Features
DEV_MODE=true
ENABLE_CORS=true
ENABLE_DEBUG=true

# Monitoring (отключено в dev)
ENABLE_MONITORING=false
```

**docker-compose.override.dev.yml:**

```yaml
version: '3.8'

services:
  # Dev-специфичные настройки
  calc-service:
    environment:
      - LOG_LEVEL=DEBUG
      - DEV_MODE=true
    volumes:
      - ./services/calc-service:/app:ro  # Hot reload

  risk-engine:
    environment:
      - LOG_LEVEL=DEBUG
      - DEV_MODE=true
    volumes:
      - ./services/risk-engine:/app:ro

  doc-service:
    environment:
      - LOG_LEVEL=DEBUG
      - DEV_MODE=true
    volumes:
      - ./services/doc-service:/app:ro

  billing-service:
    environment:
      - LOG_LEVEL=DEBUG
      - DEV_MODE=true
    volumes:
      - ./services/billing-service:/app:ro

  # Dev database с test data
  db:
    environment:
      POSTGRES_DB: zakupai_dev
    volumes:
      - ./db/dev-seed:/docker-entrypoint-initdb.d:ro

  # Disable monitoring in dev
  prometheus:
    profiles:
      - monitoring-dev
  grafana:
    profiles:
      - monitoring-dev
```

### Staging Environment

**Файлы:**

- `.env.stage` - staging переменные
- `docker-compose.override.stage.yml` - staging override

**.env.stage:**

```bash
# Database
DB_HOST=zakupai-db-stage
DB_PORT=5432
DB_NAME=zakupai_stage
DB_USER=zakupai_stage
DB_PASSWORD=complex_stage_password_123

# API Keys (staging keys)
ZAKUPAI_API_KEY=stage-api-key-abcdef123456
TELEGRAM_BOT_TOKEN=123456789:BBBBBBBBBBBBBBBBBBBBBBBBBbbbbbbb_STAGE

# External Services
OLLAMA_BASE_URL=http://ollama-stage:11434
OPENAI_API_KEY=sk-stage-key

# Logging
LOG_LEVEL=INFO

# Features
DEV_MODE=false
ENABLE_CORS=false
ENABLE_DEBUG=false

# Monitoring
ENABLE_MONITORING=true
PROMETHEUS_RETENTION=7d

# Backup
BACKUP_ENABLED=true
BACKUP_SCHEDULE="0 2 * * *"  # Daily at 2 AM
RCLONE_CONFIG=backblaze_stage
```

**docker-compose.override.stage.yml:**

```yaml
version: '3.8'

services:
  # Production-like settings но с staging данными
  calc-service:
    environment:
      - LOG_LEVEL=INFO
      - RATE_LIMIT_ENABLED=true
    restart: always

  risk-engine:
    environment:
      - LOG_LEVEL=INFO
      - RATE_LIMIT_ENABLED=true
    restart: always

  doc-service:
    environment:
      - LOG_LEVEL=INFO
      - RATE_LIMIT_ENABLED=true
    restart: always

  billing-service:
    environment:
      - LOG_LEVEL=INFO
      - PAYMENT_MODE=test  # Test payments
    restart: always

  # Staging database
  db:
    environment:
      POSTGRES_DB: zakupai_stage
    volumes:
      - postgres_stage_data:/var/lib/postgresql/data
      - ./db/stage-seed:/docker-entrypoint-initdb.d:ro

  # Enable monitoring
  prometheus:
    profiles:
      - stage
    environment:
      - PROMETHEUS_RETENTION_TIME=7d

  grafana:
    profiles:
      - stage
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=stage_admin_password

volumes:
  postgres_stage_data:
```

### Production Environment

**Файлы:**

- `.env.prod` - production переменные
- `docker-compose.override.prod.yml` - production override

**.env.prod:**

```bash
# Database (external RDS/managed)
DB_HOST=zakupai-prod-db.cluster-xyz.us-west-2.rds.amazonaws.com
DB_PORT=5432
DB_NAME=zakupai_prod
DB_USER=zakupai_prod
DB_PASSWORD=${ZAKUPAI_DB_PASSWORD}  # From secrets

# API Keys (production)
ZAKUPAI_API_KEY=${ZAKUPAI_PROD_API_KEY}  # From secrets
TELEGRAM_BOT_TOKEN=${TELEGRAM_PROD_TOKEN}  # From secrets

# External Services
OLLAMA_BASE_URL=https://ollama.zakupai.site
OPENAI_API_KEY=${OPENAI_PROD_KEY}

# Logging
LOG_LEVEL=WARNING
STRUCTURED_LOGS=true

# Features
DEV_MODE=false
ENABLE_CORS=false
ENABLE_DEBUG=false
RATE_LIMIT_STRICT=true

# Monitoring
ENABLE_MONITORING=true
PROMETHEUS_RETENTION=30d
ALERTMANAGER_ENABLED=true

# Backup
BACKUP_ENABLED=true
BACKUP_SCHEDULE="0 1 * * *"  # Daily at 1 AM
BACKUP_RETENTION_DAYS=30
RCLONE_CONFIG=backblaze_prod

# Security
SSL_ENABLED=true
CORS_ORIGINS=https://zakupai.site,https://admin.zakupai.site
TRUSTED_HOSTS=zakupai.site,api.zakupai.site

# Scaling
WORKER_PROCESSES=4
MAX_CONNECTIONS=1000
```

**docker-compose.override.prod.yml:**

```yaml
version: '3.8'

services:
  # Production optimized settings
  calc-service:
    environment:
      - LOG_LEVEL=WARNING
      - WORKERS=4
      - MAX_CONNECTIONS=100
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
    restart: always

  risk-engine:
    environment:
      - LOG_LEVEL=WARNING
      - WORKERS=4
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
    restart: always

  doc-service:
    environment:
      - LOG_LEVEL=WARNING
      - WORKERS=2
    deploy:
      resources:
        limits:
          memory: 768M
          cpus: '0.75'
    restart: always

  billing-service:
    environment:
      - LOG_LEVEL=WARNING
      - PAYMENT_MODE=production
      - KASPI_API_ENABLED=true
      - STRIPE_API_ENABLED=true
    restart: always

  # External managed database
  db:
    profiles:
      - local-db  # Отключено в продакшене

  # Full monitoring stack
  prometheus:
    profiles:
      - prod
    environment:
      - PROMETHEUS_RETENTION_TIME=30d
    volumes:
      - prometheus_prod_data:/prometheus

  grafana:
    profiles:
      - prod
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
      - GF_SERVER_ROOT_URL=https://monitoring.zakupai.site
    volumes:
      - grafana_prod_data:/var/lib/grafana

  # Backup service
  db-backup:
    profiles:
      - prod
    environment:
      - BACKUP_SCHEDULE=0 1 * * *
      - RCLONE_CONFIG_PATH=/config/rclone.conf
    volumes:
      - /opt/zakupai/backups:/backups
      - /opt/zakupai/config/rclone.conf:/config/rclone.conf:ro

volumes:
  prometheus_prod_data:
  grafana_prod_data:
```

## CI/CD Pipeline

### GitHub Actions Workflow

**.github/workflows/ci.yml:**

```yaml
name: ZakupAI CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: zakupai

jobs:
  # Lint and Test
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install ruff black isort bandit

    - name: Lint with ruff
      run: ruff check .

    - name: Format check with black
      run: black --check .

    - name: Import sorting check
      run: isort --check-only .

    - name: Security scan with bandit
      run: bandit -r services/ bot/ -f json -o bandit-report.json
      continue-on-error: true

    - name: Upload security report
      uses: actions/upload-artifact@v3
      with:
        name: bandit-report
        path: bandit-report.json

  # Build Images
  build:
    needs: test
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service: [calc-service, risk-engine, doc-service, billing-service, bot, web]
    steps:
    - uses: actions/checkout@v4

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Log in to Container Registry
      uses: docker/login-action@v3
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ${{ env.REGISTRY }}/${{ github.repository }}/${{ matrix.service }}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=sha,prefix={{branch}}-

    - name: Build and push Docker image
      uses: docker/build-push-action@v5
      with:
        context: ./services/${{ matrix.service }}
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

  # Smoke Tests
  smoke-test:
    needs: build
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Set up environment
      run: |
        cp .env.dev .env

    - name: Start services
      run: |
        docker-compose -f docker-compose.yml -f docker-compose.override.dev.yml up -d
        sleep 30  # Wait for services

    - name: Run smoke tests
      run: |
        make smoke-calc
        make smoke-risk
        make smoke-doc
        make smoke-billing

    - name: Collect logs
      if: failure()
      run: |
        docker-compose logs > failure-logs.txt

    - name: Upload failure logs
      if: failure()
      uses: actions/upload-artifact@v3
      with:
        name: failure-logs
        path: failure-logs.txt

  # Deploy to Staging
  deploy-staging:
    if: github.ref == 'refs/heads/develop'
    needs: [test, build, smoke-test]
    runs-on: ubuntu-latest
    environment: staging
    steps:
    - name: Deploy to staging
      uses: appleboy/ssh-action@v1.0.0
      with:
        host: ${{ secrets.STAGING_HOST }}
        username: ${{ secrets.STAGING_USER }}
        key: ${{ secrets.STAGING_SSH_KEY }}
        script: |
          cd /opt/zakupai
          git pull origin develop
          cp .env.stage .env
          docker-compose -f docker-compose.yml -f docker-compose.override.stage.yml pull
          docker-compose -f docker-compose.yml -f docker-compose.override.stage.yml up -d

  # Deploy to Production
  deploy-production:
    if: github.ref == 'refs/heads/main'
    needs: [test, build, smoke-test]
    runs-on: ubuntu-latest
    environment: production
    steps:
    - name: Deploy to production
      uses: appleboy/ssh-action@v1.0.0
      with:
        host: ${{ secrets.PROD_HOST }}
        username: ${{ secrets.PROD_USER }}
        key: ${{ secrets.PROD_SSH_KEY }}
        script: |
          cd /opt/zakupai
          git pull origin main
          cp .env.prod .env
          docker-compose -f docker-compose.yml -f docker-compose.override.prod.yml pull
          docker-compose -f docker-compose.yml -f docker-compose.override.prod.yml up -d --remove-orphans

          # Health check after deployment
          sleep 60
          curl -f http://localhost:8080/health || exit 1
```

### Makefile для развертывания

**Makefile:**

```makefile
# Environments
.PHONY: dev stage prod

dev:
	@echo "🔧 Starting Development environment..."
	cp .env.dev .env
	docker-compose -f docker-compose.yml -f docker-compose.override.dev.yml --profile dev up -d
	@echo "✅ Dev environment ready: http://localhost:8080"

stage:
	@echo "🎭 Starting Staging environment..."
	cp .env.stage .env
	docker-compose -f docker-compose.yml -f docker-compose.override.stage.yml --profile stage up -d
	@echo "✅ Stage environment ready"

prod:
	@echo "🚀 Starting Production environment..."
	cp .env.prod .env
	docker-compose -f docker-compose.yml -f docker-compose.override.prod.yml --profile prod up -d
	@echo "✅ Production environment ready"

# Deployment commands
.PHONY: deploy-dev deploy-stage deploy-prod

deploy-dev: dev
	@echo "🔄 Running smoke tests..."
	$(MAKE) smoke-all

deploy-stage: stage
	@echo "🔄 Running staging verification..."
	$(MAKE) health-check
	$(MAKE) smoke-all

deploy-prod: prod
	@echo "🔄 Running production verification..."
	$(MAKE) health-check
	$(MAKE) smoke-all
	@echo "🎉 Production deployment complete!"

# Health checks
.PHONY: health-check

health-check:
	@echo "🏥 Checking service health..."
	curl -f http://localhost:8080/health || (echo "❌ Gateway down" && exit 1)
	curl -f http://localhost:7001/health || (echo "❌ Calc service down" && exit 1)
	curl -f http://localhost:7002/health || (echo "❌ Risk engine down" && exit 1)
	curl -f http://localhost:7003/health || (echo "❌ Doc service down" && exit 1)
	curl -f http://localhost:7004/health || (echo "❌ Billing service down" && exit 1)
	@echo "✅ All services healthy"

# Database operations
.PHONY: db-migrate db-seed db-backup

db-migrate:
	@echo "🗄️  Running database migrations..."
	docker-compose exec db psql -U zakupai -d zakupai -f /docker-entrypoint-initdb.d/001_schema.sql
	docker-compose exec db psql -U zakupai -d zakupai -f /docker-entrypoint-initdb.d/002_schema_v2.sql
	docker-compose exec db psql -U zakupai -d zakupai -f /docker-entrypoint-initdb.d/003_indexes.sql

db-seed:
	@echo "🌱 Seeding database..."
	docker-compose exec db psql -U zakupai -d zakupai -f /docker-entrypoint-initdb.d/seed.sql

db-backup:
	@echo "💾 Creating database backup..."
	docker-compose exec db pg_dump -U zakupai -d zakupai > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup created"
```

## Бэкапы

### Автоматические бэкапы PostgreSQL

**Скрипт (`scripts/db/backup.sh`):**

```bash
#!/bin/bash

# Configuration
BACKUP_DIR="/backups"
POSTGRES_HOST="${POSTGRES_HOST:-db}"
POSTGRES_USER="${POSTGRES_USER:-zakupai}"
POSTGRES_DB="${POSTGRES_DB:-zakupai}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="zakupai_backup_${DATE}.sql"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

# Create backup directory
mkdir -p $BACKUP_DIR

# Database backup
echo "🗄️ Creating database backup..."
pg_dump -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB > $BACKUP_DIR/$BACKUP_FILE

# Compress backup
echo "🗜️ Compressing backup..."
gzip $BACKUP_DIR/$BACKUP_FILE

# Upload to cloud storage
if [ "$RCLONE_CONFIG" ]; then
    echo "☁️ Uploading to cloud storage..."
    rclone copy $BACKUP_DIR/${BACKUP_FILE}.gz $RCLONE_CONFIG:zakupai-backups/$(date +%Y/%m)/
    echo "✅ Backup uploaded to cloud"
fi

# Clean old backups
echo "🧹 Cleaning old backups..."
find $BACKUP_DIR -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete

# Log backup completion
echo "✅ Backup completed: ${BACKUP_FILE}.gz"
echo "📊 Backup size: $(ls -lh $BACKUP_DIR/${BACKUP_FILE}.gz | awk '{print $5}')"

# Send notification (if configured)
if [ "$BACKUP_WEBHOOK_URL" ]; then
    curl -X POST "$BACKUP_WEBHOOK_URL" \
         -H "Content-Type: application/json" \
         -d "{\"text\": \"✅ ZakupAI backup completed: ${BACKUP_FILE}.gz\"}"
fi
```

**Docker service для бэкапов:**

```dockerfile
# backup/Dockerfile
FROM postgres:16-alpine

RUN apk add --no-cache rclone curl

COPY backup.sh /usr/local/bin/backup.sh
COPY crontab /etc/cron.d/backup-cron

RUN chmod +x /usr/local/bin/backup.sh
RUN crontab /etc/cron.d/backup-cron

CMD ["crond", "-f"]
```

### Восстановление из бэкапов

**Скрипт восстановления (`backup/restore.sh`):**

```bash
#!/bin/bash

BACKUP_FILE=$1
POSTGRES_HOST="${POSTGRES_HOST:-db}"
POSTGRES_USER="${POSTGRES_USER:-zakupai}"
POSTGRES_DB="${POSTGRES_DB:-zakupai}"

if [ -z "$BACKUP_FILE" ]; then
    echo "❌ Usage: ./restore.sh <backup_file.sql.gz>"
    exit 1
fi

echo "🔄 Restoring from backup: $BACKUP_FILE"

# Download from cloud if needed
if [[ $BACKUP_FILE == *"://"* ]]; then
    echo "☁️ Downloading backup from cloud..."
    rclone copy "$BACKUP_FILE" ./
    BACKUP_FILE=$(basename "$BACKUP_FILE")
fi

# Decompress
if [[ $BACKUP_FILE == *.gz ]]; then
    echo "🗜️ Decompressing backup..."
    gunzip "$BACKUP_FILE"
    BACKUP_FILE="${BACKUP_FILE%.gz}"
fi

# Stop services
echo "⏸️ Stopping services..."
docker-compose down

# Restore database
echo "🗄️ Restoring database..."
docker-compose up -d db
sleep 10

# Drop and recreate database
docker-compose exec db dropdb -U $POSTGRES_USER $POSTGRES_DB
docker-compose exec db createdb -U $POSTGRES_USER $POSTGRES_DB

# Restore data
docker-compose exec -T db psql -U $POSTGRES_USER -d $POSTGRES_DB < "$BACKUP_FILE"

# Start services
echo "▶️ Starting services..."
docker-compose up -d

echo "✅ Restore completed!"
```

## Мониторинг деплоймента

### Health Check Scripts

**scripts/health-check.sh:**

```bash
#!/bin/bash

TIMEOUT=30
RETRY_INTERVAL=5

check_service() {
    local name=$1
    local url=$2
    local retries=$((TIMEOUT / RETRY_INTERVAL))

    echo "🏥 Checking $name..."

    for i in $(seq 1 $retries); do
        if curl -sf "$url" > /dev/null; then
            echo "✅ $name is healthy"
            return 0
        fi

        if [ $i -lt $retries ]; then
            echo "⏳ $name not ready, retrying in ${RETRY_INTERVAL}s..."
            sleep $RETRY_INTERVAL
        fi
    done

    echo "❌ $name health check failed"
    return 1
}

# Check all services
check_service "Gateway" "http://localhost:8080/health"
check_service "Calc Service" "http://localhost:7001/health"
check_service "Risk Engine" "http://localhost:7002/health"
check_service "Doc Service" "http://localhost:7003/health"
check_service "Billing Service" "http://localhost:7004/health"

echo "🎉 All services are healthy!"
```

### Deployment Rollback

**scripts/rollback.sh:**

```bash
#!/bin/bash

ROLLBACK_TAG=$1

if [ -z "$ROLLBACK_TAG" ]; then
    echo "❌ Usage: ./rollback.sh <git-tag-or-commit>"
    exit 1
fi

echo "🔄 Rolling back to: $ROLLBACK_TAG"

# Stop current services
docker-compose down

# Checkout previous version
git checkout $ROLLBACK_TAG

# Rebuild and restart
docker-compose build
docker-compose up -d

# Health check
sleep 30
./scripts/health-check.sh

if [ $? -eq 0 ]; then
    echo "✅ Rollback successful"
else
    echo "❌ Rollback failed, manual intervention required"
    exit 1
fi
```

## Security в Production

### SSL/TLS настройка

**Nginx reverse proxy (`nginx/prod.conf`):**

```nginx
server {
    listen 80;
    server_name zakupai.site api.zakupai.site;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name zakupai.site;

    ssl_certificate /etc/ssl/certs/zakupai.crt;
    ssl_certificate_key /etc/ssl/private/zakupai.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    location / {
        proxy_pass http://localhost:8082;  # Web UI
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 443 ssl http2;
    server_name api.zakupai.site;

    ssl_certificate /etc/ssl/certs/zakupai.crt;
    ssl_certificate_key /etc/ssl/private/zakupai.key;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=60r/m;
    limit_req zone=api burst=10 nodelay;

    location / {
        proxy_pass http://localhost:8080;  # API Gateway
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Firewall правила

**scripts/setup-firewall.sh:**

```bash
#!/bin/bash

# Basic firewall setup for production
ufw --force reset
ufw default deny incoming
ufw default allow outgoing

# SSH
ufw allow 22/tcp

# HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Monitoring (restrict to admin IPs)
ufw allow from 203.0.113.0/24 to any port 9090  # Prometheus
ufw allow from 203.0.113.0/24 to any port 3001  # Grafana

# Enable firewall
ufw --force enable

echo "🔥 Firewall configured for production"
```

## Заключение

Система развертывания ZakupAI обеспечивает:

- ✅ **Три окружения** - dev/stage/prod с изоляцией конфигураций
- ✅ **CI/CD автоматизация** - тестирование, сборка, развертывание
- ✅ **Автоматические бэкапы** - PostgreSQL с загрузкой в облако
- ✅ **Health checks** - проверка работоспособности после развертывания
- ✅ **Rollback механизм** - быстрый откат при проблемах
- ✅ **Security** - SSL, firewall, secrets management
- ✅ **Мониторинг деплоймента** - отслеживание процесса развертывания
