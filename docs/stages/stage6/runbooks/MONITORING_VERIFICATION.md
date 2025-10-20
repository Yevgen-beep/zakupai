# Stage6 Monitoring Stack - Verification Guide

## Quick Start

```bash
# 1. Start the stack
docker compose --profile stage6 \
  -f docker-compose.yml \
  -f docker-compose.override.stage6.yml \
  -f docker-compose.override.stage6.monitoring.yml \
  up -d

# 2. Wait for initialization (30-45s)
sleep 45

# 3. Run diagnostics
./stage6-network-diagnostics.sh

# 4. Generate synthetic traffic (required for metrics!)
./stage6-traffic-warmup.sh

# 5. Verify Grafana dashboards
open http://localhost:3030/d/zakupai-overview
```

---

## Manual Verification Commands

### 1. Check Prometheus Targets

```bash
curl -s http://localhost:9095/api/v1/targets | \
  jq -r '.data.activeTargets[] | "\(.labels.job) | \(.labels.instance) | \(.health)"'
```

**Expected output:**
```
prometheus | prometheus:9090 | up
node-exporter | node-exporter-stage6:9100 | up
cadvisor | cadvisor:8080 | up
calc-service | calc-service:8000 | up
risk-engine | risk-engine:8000 | up
doc-service | doc-service:8000 | up
...
```

### 2. Verify Metrics Are Being Scraped

```bash
# Check for http_requests_total (should be EMPTY until traffic is generated!)
curl -s 'http://localhost:9095/api/v1/query?query=http_requests_total' | \
  jq -r '.data.result | length'

# After running ./stage6-traffic-warmup.sh:
curl -s 'http://localhost:9095/api/v1/query?query=rate(http_requests_total[1m])' | \
  jq -r '.data.result[] | "\(.metric.job) | \(.metric.handler // "N/A") | \(.value[1])"'
```

### 3. Check Recording Rules

```bash
# api_error_ratio (should be 0 if no errors)
curl -s 'http://localhost:9095/api/v1/query?query=api_error_ratio' | \
  jq -r '.data.result[0].value[1]'

# api_p95_latency (may be 0 or N/A until histogram metrics exist)
curl -s 'http://localhost:9095/api/v1/query?query=api_p95_latency' | jq
```

### 4. Verify Grafana Datasource

```bash
curl -s -u admin:admin http://localhost:3030/api/datasources | \
  jq '.[] | select(.name=="Prometheus") | {name, url, uid}'
```

**Expected:**
```json
{
  "name": "Prometheus",
  "url": "http://prometheus:9095",
  "uid": "zakupai-prom"
}
```

### 5. Test Individual Service Metrics

```bash
# calc-service
curl -s http://localhost:8100/health
curl -s http://localhost:8100/metrics | grep '^http_requests_total'

# risk-engine
curl -s http://localhost:8200/health
curl -s http://localhost:8200/metrics | grep '^http_requests_total'
```

---

## Troubleshooting

### ❌ Grafana shows "No data"

**Cause:** No traffic has hit the services yet.

**Solution:**
```bash
./stage6-traffic-warmup.sh
# Wait 15-30 seconds for Prometheus scrape + recording rule evaluation
# Then refresh Grafana
```

### ❌ Prometheus targets show "down"

**Check logs:**
```bash
docker compose --profile stage6 \
  -f docker-compose.yml \
  -f docker-compose.override.stage6.yml \
  -f docker-compose.override.stage6.monitoring.yml \
  logs <service-name> --tail 100
```

**Restart service:**
```bash
docker compose --profile stage6 \
  -f docker-compose.yml \
  -f docker-compose.override.stage6.yml \
  -f docker-compose.override.stage6.monitoring.yml \
  restart <service-name>
```

### ❌ "DATABASE_URL variable is not set" warnings

These are **benign** and filtered by the diagnostic script. If they appear, they don't affect functionality.

### ❌ Vault target shows "down"

Expected. Vault metrics scraping is disabled (commented out in [prometheus.yml](monitoring/prometheus/prometheus.yml:114)) until token provisioning is implemented.

---

## CI/CD Integration

The GitHub Actions workflow [`.github/workflows/stage6-monitoring-test.yml`](.github/workflows/stage6-monitoring-test.yml) runs automatically on:

- Push to `main` or `stage6-monitoring` branches
- Pull requests affecting monitoring config
- Manual workflow dispatch

**Local simulation:**
```bash
# Mimic CI steps
docker compose --profile stage6 -f docker-compose.yml -f docker-compose.override.stage6.yml -f docker-compose.override.stage6.monitoring.yml build
docker compose --profile stage6 -f docker-compose.yml -f docker-compose.override.stage6.yml -f docker-compose.override.stage6.monitoring.yml up -d
sleep 45
./stage6-network-diagnostics.sh
./stage6-traffic-warmup.sh
curl -s http://localhost:9095/api/v1/query?query=http_requests_total | jq
```

---

## Expected Grafana Dashboard Behavior

After applying all fixes and running warmup:

### ZakupAI - Platform Overview ([zakupai-overview](http://localhost:3030/d/zakupai-overview))

| Panel | Metric | Expected Value |
|-------|--------|----------------|
| **Availability (last 5m)** | `(1 - avg(api_error_ratio)) * 100` | ~100% (green) |
| **Error Ratio (last 5m)** | `avg(api_error_ratio) * 100` | ~0% (green) |
| **API P95 Latency** | `max(api_p95_latency)` | < 0.5s (green/yellow) |
| **Request Rate by Service** | `sum by (service) (rate(http_requests_total[5m]))` | Lines for calc, risk, doc, etc. |
| **Error Ratio by Service** | `sum by (service) (rate(http_requests_total{status_code=~"5.."}) / rate(http_requests_total))` | Flat at 0 |

---

## Performance Tuning (Optional)

### Persist Prometheus Data

Add to `docker-compose.override.stage6.monitoring.yml`:

```yaml
services:
  prometheus:
    volumes:
      - prometheus-data:/prometheus
volumes:
  prometheus-data:
```

### Enable Vault Metrics

1. Generate Vault token with `metrics` policy
2. Write token to `monitoring/prometheus/vault-metrics.token`
3. Uncomment vault scrape config in [prometheus.yml](monitoring/prometheus/prometheus.yml:114)
4. Restart Prometheus

### Add More Recording Rules

Replace `monitoring/prometheus/rules.yml` with `monitoring/prometheus/rules-enhanced.yml`:

```bash
cp monitoring/prometheus/rules-enhanced.yml monitoring/prometheus/rules.yml
docker compose --profile stage6 \
  -f docker-compose.yml \
  -f docker-compose.override.stage6.yml \
  -f docker-compose.override.stage6.monitoring.yml \
  restart prometheus
```

---

## Summary of Files Changed

| File | Change |
|------|--------|
| [monitoring/grafana/provisioning/datasources/datasources.yml](monitoring/grafana/provisioning/datasources/datasources.yml:6) | Fixed URL: `prometheus:9095` |
| [monitoring/prometheus/prometheus.yml](monitoring/prometheus/prometheus.yml:114) | Commented out Vault target |
| [stage6-network-diagnostics.sh](stage6-network-diagnostics.sh:84) | Filter warnings, exit code on failure |
| [stage6-traffic-warmup.sh](stage6-traffic-warmup.sh) | **NEW**: Generate synthetic traffic |
| [.github/workflows/stage6-monitoring-test.yml](.github/workflows/stage6-monitoring-test.yml) | **NEW**: CI workflow |
| [monitoring/prometheus/rules-enhanced.yml](monitoring/prometheus/rules-enhanced.yml) | **NEW**: Optional advanced rules |

---

## Support

If diagnostics fail, attach output to your issue:

```bash
./stage6-network-diagnostics.sh > diagnostics.log 2>&1
```
