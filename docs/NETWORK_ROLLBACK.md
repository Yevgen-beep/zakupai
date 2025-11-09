# ZakupAI Vault Network Migration - Rollback Guide

## Quick Rollback (if migration failed)

### Step 1: Stop current stack
```bash
docker compose down
```

### Step 2: Restore old volumes
```bash
# Find your backup
ls -la backups/vault-migration-*

# Restore (replace TIMESTAMP with your backup)
BACKUP=backups/vault-migration-YYYYMMDD-HHMMSS

docker volume create zakupai_vault_data
docker volume create zakupai_vault_logs

docker run --rm \
  -v "$(pwd)/$BACKUP":/backup:ro \
  -v zakupai_vault_data:/data \
  alpine tar xzf /backup/vault_data.tar.gz -C /data

docker run --rm \
  -v "$(pwd)/$BACKUP":/backup:ro \
  -v zakupai_vault_logs:/logs \
  alpine tar xzf /backup/vault_logs.tar.gz -C /logs
```

### Step 3: Revert compose files
```bash
# Restore from git
git checkout HEAD -- docker-compose*.yml

# Or restore from backup
cp backups/docker-compose.yml.bak docker-compose.yml
```

### Step 4: Restart with old configuration
```bash
docker compose -f docker-compose.yml \
  -f docker-compose.override.stage8.vault-secure.yml \
  up -d
```

### Step 5: Verify
```bash
docker exec zakupai-vault vault status
docker exec zakupai-calc-service getent hosts vault
```

## Partial Rollback Scenarios

### Rollback networks only (keep new volumes)
```yaml
# In docker-compose.override.stage9.vault-prod.yml
services:
  vault:
    networks:
      - backend  # restore old name
      - monitoring

networks:
  backend:
    external: true
  monitoring:
    external: true
```

Then:
```bash
docker network create backend
docker network create monitoring
docker compose up -d vault
```

### Rollback volumes only (keep new networks)
```bash
# Update compose to use old volume names
sed -i 's/vault-data/vault_data/g' docker-compose*.yml
sed -i 's/vault-logs/vault_logs/g' docker-compose*.yml

docker compose up -d vault
```

## Prevention for Next Time

1. **Always test in staging first**
2. **Keep backups for at least 7 days**
3. **Document current state before changes**
4. **Use git branches for infrastructure changes**

## Emergency Contacts

- DevOps Lead: [contact]
- Vault Admin: [contact]
- On-call: [contact]
