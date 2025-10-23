# Stage6 Blackbox Monitoring Restoration Report

**Date:** 2025-10-23
**Status:** ✅ COMPLETED
**Objective:** Restore data sources for existing Grafana panels using Prometheus Blackbox Exporter

---

## Executive Summary

Successfully configured Prometheus Blackbox Exporter to monitor:
1. **ZakupAI Bot Health** → `probe_success{job="zakupai-bot-health"}` = **1** (UP)
2. **External API: goszakup.gov.kz** → `probe_success{job="external-api-goszakup"}` = **1** (UP)

Both monitoring targets are operational and feeding live data to existing Grafana dashboards.

---

## Implementation Details

### 1. Blackbox Exporter Configuration

**File:** `monitoring/blackbox/config.tpl`

Created template-based configuration with environment variable substitution for secure token management:

```yaml
modules:
  http_2xx:
    prober: http
    timeout: 10s
    http:
      method: GET
      valid_status_codes: []
      valid_http_versions: ["HTTP/1.0", "HTTP/1.1", "HTTP/2.0"]
      preferred_ip_protocol: "ip4"

  http_2xx_auth:
    prober: http
    timeout: 10s
    http:
      method: POST
      headers:
        Authorization: "Bearer ${GOSZAKUP_TOKEN}"
        Content-Type: "application/json"
      body: '{"query":"{ __typename }"}'
      valid_status_codes: []
      valid_http_versions: ["HTTP/1.0", "HTTP/1.1", "HTTP/2.0"]
      preferred_ip_protocol: "ip4"
```

**Key Features:**
- `http_2xx`: Simple HTTP GET probe for internal services
- `http_2xx_auth`: GraphQL POST probe with Bearer authentication
- Token injection via `sed` substitution at container startup
- Supports HTTP/1.0, HTTP/1.1, HTTP/2.0

---

### 2. Docker Compose Integration

**File:** `docker-compose.override.stage6.monitoring.yml`

Added blackbox-exporter service:

```yaml
blackbox-exporter:
  image: prom/blackbox-exporter:latest
  container_name: zakupai-blackbox-exporter
  networks:
    - zakupai-network
  ports:
    - "9115:9115"
  environment:
    - GOSZAKUP_TOKEN=${GOSZAKUP_TOKEN}
  volumes:
    - ./monitoring/blackbox/config.tpl:/etc/blackbox_exporter/config.tpl:ro
  entrypoint: ["/bin/sh","-c"]
  command:
    - |
      sed "s|\$${GOSZAKUP_TOKEN}|$${GOSZAKUP_TOKEN}|g" /etc/blackbox_exporter/config.tpl > /tmp/config.yml
      exec /bin/blackbox_exporter --config.file=/tmp/config.yml
  restart: unless-stopped
```

**Network Configuration Fix:**
```yaml
networks:
  zakupai-network:
    external: true
    name: zakupai_zakupai-network
```

This ensures blackbox-exporter joins the same Docker network as zakupai-bot and other services.

---

### 3. Prometheus Scrape Jobs

**File:** `monitoring/prometheus/prometheus.yml`

Added two scrape configurations:

#### Job 1: ZakupAI Bot Health Monitor
```yaml
- job_name: 'zakupai-bot-health'
  metrics_path: /probe
  static_configs:
    - targets:
        - http://zakupai-bot:8081/health
  params:
    module: ['http_2xx']
  relabel_configs:
    - source_labels: [__address__]
      target_label: __param_target
    - source_labels: [__param_target]
      target_label: target
    - replacement: blackbox-exporter:9115
      target_label: __address__
    - target_label: env
      replacement: stage6
    - target_label: type
      replacement: external
```

#### Job 2: External API (Goszakup) Monitor
```yaml
- job_name: 'external-api-goszakup'
  metrics_path: /probe
  static_configs:
    - targets:
        - https://ows.goszakup.gov.kz/v3/graphql
  params:
    module: ['http_2xx_auth']
  relabel_configs:
    - source_labels: [__address__]
      target_label: __param_target
    - source_labels: [__param_target]
      target_label: target
    - replacement: blackbox-exporter:9115
      target_label: __address__
    - target_label: env
      replacement: stage6
    - target_label: type
      replacement: external
```

---

## Deployment & Verification

### Services Restarted
```bash
docker compose --profile stage6 \
  -f docker-compose.yml \
  -f docker-compose.override.stage6.yml \
  -f docker-compose.override.stage6.monitoring.yml \
  up -d blackbox-exporter prometheus
```

### Prometheus Targets Verification
```bash
docker exec zakupai-prometheus wget -qO- http://localhost:9090/api/v1/targets | \
  jq '.data.activeTargets | map(.labels.job)'
```

**Result:**
```json
[
  "external-api-goszakup",
  "zakupai-bot-health",
  ...
]
```

### Metrics Verification

#### Bot Health Check
```bash
curl -s 'http://localhost:9090/api/v1/query?query=probe_success{job="zakupai-bot-health"}'
```

**Result:**
```json
{
  "job": "zakupai-bot-health",
  "value": "1",
  "target": "http://zakupai-bot:8081/health"
}
```

#### External API Check
```bash
curl -s 'http://localhost:9090/api/v1/query?query=probe_success{job="external-api-goszakup"}'
```

**Result:**
```json
{
  "job": "external-api-goszakup",
  "value": "1",
  "target": "https://ows.goszakup.gov.kz/v3/graphql"
}
```

---

## Grafana Dashboard Status

### Expected Panels (No Changes Required)

The existing Grafana dashboards automatically started displaying data:

1. **ZakupAI Bot Health Panel**
   - Query: `probe_success{job="zakupai-bot-health"}`
   - Status: 🟢 **1** (UP)
   - Endpoint: `http://zakupai-bot:8081/health`

2. **External API: goszakup.gov.kz Panel**
   - Query: `probe_success{job="external-api-goszakup"}`
   - Status: 🟢 **1** (UP)
   - Endpoint: `https://ows.goszakup.gov.kz/v3/graphql`

**Dashboard Locations:**
- Platform Ops Dashboard: `/dashboards/ops/`
- Overview Dashboard: `/dashboards/overview/`

---

## Security & Configuration

### Token Management

✅ **GOSZAKUP_TOKEN** is:
- Stored in `.env` (excluded from git via `.gitignore`)
- Injected at runtime via Docker environment variables
- Substituted into config using `sed` at container startup
- Never committed to repository

### Files Modified

| File | Purpose |
|------|---------|
| `monitoring/blackbox/config.tpl` | Blackbox exporter module configuration |
| `docker-compose.override.stage6.monitoring.yml` | Service definition & network config |
| `monitoring/prometheus/prometheus.yml` | Scrape job definitions |
| `stage6_blackbox_enable.diff` | Complete changeset patch |

### Files Created

| File | Purpose |
|------|---------|
| `monitoring/blackbox/config.tpl` | New blackbox config template |
| `STAGE6_BLACKBOX_MONITORING_RESTORE.md` | This report |

---

## Troubleshooting Notes

### Issues Resolved During Implementation

1. **DNS Resolution Issue**
   - Problem: `zakupai-blackbox-exporter` couldn't resolve `zakupai-bot`
   - Root Cause: Network was set to `external: false`, creating isolated network
   - Solution: Changed to `external: true` with explicit network name

2. **HTTP Version Mismatch**
   - Problem: `probe_success` returning 0 despite HTTP 200 response
   - Root Cause: Bot returns HTTP/1.0, config only allowed HTTP/1.1 and HTTP/2
   - Solution: Added HTTP/1.0 to `valid_http_versions`

3. **Goszakup API 404 Error**
   - Problem: GraphQL endpoint returns 404 on GET requests
   - Root Cause: GraphQL requires POST with query body
   - Solution: Changed module to use POST with introspection query

4. **Envsubst Not Found**
   - Problem: Alpine image doesn't include `envsubst` utility
   - Root Cause: Lightweight base image
   - Solution: Used `sed` for simple variable substitution

---

## Verification Commands

### Check Container Status
```bash
docker ps | grep -E "blackbox|prometheus"
```

### Check Prometheus Targets
```bash
docker exec zakupai-prometheus wget -qO- http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job | test("zakupai-bot-health|external-api-goszakup"))'
```

### Query Metrics Directly
```bash
# Bot health
curl -s 'http://localhost:9090/api/v1/query?query=probe_success{job="zakupai-bot-health"}' | jq

# Goszakup API
curl -s 'http://localhost:9090/api/v1/query?query=probe_success{job="external-api-goszakup"}' | jq
```

### Test Blackbox Probes Directly
```bash
# Bot health probe
curl -s 'http://localhost:9115/probe?target=http://zakupai-bot:8081/health&module=http_2xx' | grep probe_success

# Goszakup API probe
curl -s 'http://localhost:9115/probe?target=https://ows.goszakup.gov.kz/v3/graphql&module=http_2xx_auth' | grep probe_success
```

---

## Success Criteria ✅

- [x] Blackbox exporter deployed and running
- [x] Prometheus targets showing both jobs as UP
- [x] `probe_success{job="zakupai-bot-health"}` returns 1
- [x] `probe_success{job="external-api-goszakup"}` returns 1
- [x] No tokens committed to git
- [x] Existing Grafana panels display live data
- [x] Network connectivity resolved
- [x] Complete documentation provided

---

## Next Steps

1. **Monitor Stability:** Observe metrics over 24-48 hours to ensure consistent uptime
2. **Alert Configuration:** Configure Prometheus alerts for `probe_success == 0`
3. **Dashboard Enhancement:** Add response time graphs using `probe_duration_seconds`
4. **Token Rotation:** Implement periodic GOSZAKUP_TOKEN rotation procedure

---

**Deployment Date:** 2025-10-23
**Deployed By:** Claude (ZakupAI DevOps Agent)
**Verification Status:** ✅ All checks passed
