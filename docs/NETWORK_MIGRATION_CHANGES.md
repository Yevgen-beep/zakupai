# Network Migration Change Summary

## Modified Files

### docker-compose.yml
**Changes:**
- Postgres port: `"5432:5432"` → `"127.0.0.1:5432:5432"` (localhost only)
- Volume names: `vault_data` → `vault-data`, `vault_logs` → `vault-logs`
- Network definitions:
  - Removed `vault-net` (redundant)
  - Added canonical name to `zakupai-network`: `name: zakupai_zakupai-network`
  - Added canonical name to `monitoring-net`: `name: zakupai_monitoring-net`
  - Set `monitoring-net` to `internal: true`
- Vault service networks: removed `vault-net`, kept `zakupai-network` + `monitoring-net`

### docker-compose.override.stage8.vault-secure.yml
**Changes:**
- Networks: `backend` → `zakupai-network`
- Networks: `monitoring` (external) → `monitoring-net` (external, references internal network)
- Vault volumes: `vault_data` → `vault-data`
- Removed public ports: `"8200:8200"` → `ports: []`
- Retained `/vault/data` mount (file backend)
- Network definitions updated with canonical names

### docker-compose.override.stage9.vault-prod.yml
**Changes:**
- Networks: `backend` → `zakupai-network`
- Networks: `monitoring` (external) → `monitoring-net` (external, references internal network)
- Removed public ports: `"8200:8200"` and `"8201:8201"` → `ports: []`
- No `/vault/data` mount (S3 backend only)
- Network definitions updated with canonical names

### docker-compose.override.yml
**Changes:**
- Networks: `backend` → `zakupai-network`
- Networks: `monitoring` (external) → `monitoring-net` (external, references internal network)
- Vault volumes: `vault_data` → `vault-data`
- Removed public ports: `"8200:8200"` → `ports: []`
- Network definitions updated with canonical names

### docker-compose.override.monitoring.yml
**Changes:**
- Vault volumes: `vault_data` → `vault-data`, `vault_logs` → `vault-logs`
- Removed public ports: `"8200:8200"` → `ports: []`
- Vault service networks: removed `vault-net`, kept `zakupai-network` + `monitoring-net`
- Network definitions: removed `vault-net`, updated `monitoring-net` to `internal: true`
- Added canonical name to `monitoring-net`

## Removed Components
- ❌ `backend` network (replaced with `zakupai-network`)
- ❌ `vault-net` (consolidated to `monitoring-net`)
- ❌ `monitoring` as external network (now uses `monitoring-net` which is internal)

## Retained Components
- ✅ `ai-network` (actively used by embedding-api, risk-engine, doc-service, flowise, n8n)
- ✅ `zakupai-network` (main application network)
- ✅ `monitoring-net` (internal monitoring network)

## Security Improvements
- ✅ Postgres/Redis bound to localhost only (`127.0.0.1`)
- ✅ Vault has no public ports (accessible only via Docker networks)
- ✅ Monitoring network is internal (no internet egress)
- ✅ Reduced attack surface for lateral movement
- ✅ Database not accessible from external networks

## Breaking Changes
⚠️ **Services must be restarted after migration**
⚠️ **External DB clients must connect via gateway/proxy or SSH tunnel**
⚠️ **Monitoring dashboards may temporarily lose data during migration**
⚠️ **Direct Vault API access from host requires `docker exec` or port forwarding**

## Network Topology Changes

### Before Migration
```
Services → backend (external, undefined)
Services → monitoring (external, undefined)
Services → vault-net (redundant)
Services → ai-network
Vault → vault-net, monitoring, backend
Postgres → 0.0.0.0:5432 (public)
```

### After Migration
```
Services → zakupai-network (main)
Monitoring → zakupai-network + monitoring-net (dual-homed)
Vault → zakupai-network + monitoring-net (dual-homed)
AI Services → zakupai-network + ai-network (dual-homed)
Postgres → 127.0.0.1:5432 (localhost only)
monitoring-net → internal: true (no internet access)
```

## Validation Commands
```bash
# Network topology
docker network inspect zakupai_zakupai-network | \
  jq '.[0].Containers | keys'

docker network inspect zakupai_monitoring-net | \
  jq '.[0].Containers | keys'

# Port bindings
docker ps --format 'table {{.Names}}\t{{.Ports}}' | \
  grep -E 'postgres|redis|vault'

# Vault connectivity
docker exec zakupai-calc-service curl -sf http://vault:8200/v1/sys/health

# Prometheus targets
docker exec zakupai-prometheus wget -qO- \
  http://localhost:9090/api/v1/targets | \
  jq '.data.activeTargets[] | select(.labels.job=="vault")'

# Verify monitoring-net is internal
docker network inspect zakupai_monitoring-net | \
  jq '.[0].Internal'
# Expected: true

# Verify volume names
docker volume ls | grep vault
# Expected: zakupai_vault-data, zakupai_vault-logs (dash-separated)
```

## Migration Timeline

1. **Phase 1**: Pre-migration analysis (completed)
2. **Phase 2**: Fixed Stage 8/9 network references (completed)
3. **Phase 3**: Standardized volume names (completed)
4. **Phase 4**: Secured port bindings (completed)
5. **Phase 5**: Updated monitoring network integration (completed)
6. **Phase 6**: Cleanup and final validation (completed)

## Post-Migration Checklist

- [ ] Run migration script: `./scripts/migrate_vault_networks.sh`
- [ ] Verify networks exist: `docker network ls | grep zakupai`
- [ ] Check Vault status: `docker exec zakupai-vault vault status`
- [ ] Unseal Vault (if sealed): `docker exec zakupai-vault vault operator unseal`
- [ ] Run verification script: `./scripts/verify_vault_networks.sh`
- [ ] Test service connectivity
- [ ] Verify Prometheus can scrape Vault metrics
- [ ] Check Grafana dashboards
- [ ] Test application endpoints
- [ ] Monitor logs for errors

## Rollback Procedure

See [NETWORK_ROLLBACK.md](NETWORK_ROLLBACK.md) for detailed rollback instructions.

## Support

For issues or questions:
- Check logs: `docker compose logs vault`
- Review configuration: `docker compose config`
- Consult documentation: `docs/VAULT_*.md`
