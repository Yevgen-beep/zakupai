# Stage6 Monitoring Stack - Recovery Summary

**Recovery Date**: 2025-10-16  
**Status**: ✅ **COMPLETE AND VERIFIED**  
**Downtime**: < 2 minutes

---

## Quick Status

```bash
# Run health check anytime
bash stage6_quick_check.sh
```

### Current State (All Green ✅)
- ✅ Prometheus: http://localhost:9090 (v2.54.1)
- ✅ Grafana: http://localhost:3030 (v10.4.3)
- ✅ Alertmanager: http://localhost:9093
- ✅ 16/16 Prometheus targets UP
- ✅ zakupai-bot: Telegram polling active
- ✅ All FastAPI services running

---

## What Was Fixed

### 1. Port Standardization
| Service | Before | After | Status |
|---------|--------|-------|--------|
| Prometheus | 9095 | **9090** | ✅ Fixed |
| Grafana | 3001 + 3030 | **3030** | ✅ Fixed |
| Alertmanager | 9093 | 9093 | ✅ No change |

### 2. Configuration Files Updated
All files backed up with `.bak` extension:
- [docker-compose.yml](docker-compose.yml)
- [docker-compose.override.stage6.yml](docker-compose.override.stage6.yml)
- [docker-compose.override.stage6.monitoring.yml](docker-compose.override.stage6.monitoring.yml)
- [monitoring/prometheus/prometheus.yml](monitoring/prometheus/prometheus.yml)
- [monitoring/grafana/provisioning/datasources/datasources.yml](monitoring/grafana/provisioning/datasources/datasources.yml)

### 3. Conflicts Resolved
- ✅ Stopped system-level Prometheus service (was using port 9090)
- ✅ Stopped duplicate Telegram bot (zakupai-alertmanager-bot-stage6)
- ✅ Cleared Telegram webhooks
- ✅ Fixed Grafana datasource URL: `http://prometheus:9090`

---

## Files Generated

1. **[stage6_auto_recovery_report.md](../incidents/stage6_auto_recovery_report.md)** - Full recovery report with all details
2. **[stage6_quick_check.sh](stage6_quick_check.sh)** - Health check script (run anytime)
3. **RECOVERY_SUMMARY.md** - This file

---

## Verification Commands

```bash
# Check containers
docker ps | grep -E "(prometheus|grafana|bot)"

# Check Prometheus
curl -s http://localhost:9090/-/ready

# Check Grafana
curl -s http://localhost:3030/api/health | jq

# Check targets
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets | length'

# Check bot metric
curl -s 'http://localhost:9090/api/v1/query?query=zakupai_bot_up' | jq
```

---

## Rollback (If Needed)

```bash
# Restore backups
cp docker-compose.yml.bak docker-compose.yml
cp docker-compose.override.stage6.yml.bak docker-compose.override.stage6.yml
cp docker-compose.override.stage6.monitoring.yml.bak docker-compose.override.stage6.monitoring.yml
cp monitoring/prometheus/prometheus.yml.bak monitoring/prometheus/prometheus.yml
cp monitoring/grafana/provisioning/datasources/datasources.yml.bak monitoring/grafana/provisioning/datasources/datasources.yml

# Restart
docker compose --profile stage6 down prometheus grafana
docker compose --profile stage6 up -d prometheus grafana
```

⚠️ **Warning**: Rollback returns to broken state with port 9095.

---

## Known Issues

### 1. System Prometheus Service
- **Status**: Stopped and disabled
- **Risk**: May restart after system reboot
- **Check**: `systemctl status prometheus`
- **Fix**: `systemctl stop prometheus && systemctl disable prometheus`

### 2. Duplicate Telegram Token
- **Status**: alertmanager-bot stopped
- **Recommendation**: Configure separate tokens for each bot
- **Current**: Both containers shared token `7922186015:...`

---

## Next Steps

### Immediate (Done ✅)
- [x] All services running
- [x] All health checks passing
- [x] Metrics flowing to Prometheus
- [x] Grafana dashboards accessible

### Monitoring (Next 24h)
- [ ] Verify Grafana dashboards render correctly
- [ ] Check alert rules trigger properly
- [ ] Monitor bot Telegram polling stability
- [ ] Verify no system Prometheus auto-restart

### Documentation
- [ ] Update TODO.md Stage6 checklist
- [ ] Document standard port assignments
- [ ] Add troubleshooting guide

---

## Support

If issues arise:

1. Run health check: `bash stage6_quick_check.sh`
2. Check logs: `docker logs zakupai-prometheus`
3. Review report: [stage6_auto_recovery_report.md](../incidents/stage6_auto_recovery_report.md)
4. Restart services:
   ```bash
   docker compose --profile stage6 restart prometheus grafana
   ```

---

**Recovery completed successfully. System is stable and operational.**

*Last updated: 2025-10-16*
