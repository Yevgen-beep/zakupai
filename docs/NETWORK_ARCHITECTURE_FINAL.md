# ZakupAI — Final Docker Network Architecture

**Version:** 2.0 (Post-Consolidation)
**Date:** 2025-11-09
**Status:** Production Ready

---

## Executive Summary

ZakupAI now operates on a **two-network architecture**:
1. **zakupai-network** — Main application network (bridge)
2. **monitoring-net** — Internal monitoring network (bridge, isolated)

This consolidation eliminates legacy networks (`ai-network`, `vault-net`) and simplifies the infrastructure while maintaining security isolation for the monitoring stack.

---

## Network Overview

| Network                      | Driver            | Scope      | Internet Access | Containers Attached |
|------------------------------|-------------------|------------|-----------------|---------------------|
| `zakupai_zakupai-network`    | bridge            | main       | ✅ Yes          | 21 services         |
| `zakupai_monitoring-net`     | bridge (internal) | monitoring | ❌ No           | 4 services          |

### Network Definitions

```yaml
networks:
  zakupai-network:
    driver: bridge
    name: zakupai_zakupai-network
    # All application services + monitoring bridge

  monitoring-net:
    driver: bridge
    internal: true  # No external internet access
    name: zakupai_monitoring-net
    # Vault, Prometheus, Grafana, Alertmanager
```

---

## Service Inventory

### Core Infrastructure

| Service       | Container Name         | Networks           | Exposed Ports       | Purpose                |
|---------------|------------------------|--------------------|---------------------|------------------------|
| db            | zakupai-db             | zakupai-network    | 127.0.0.1:5432      | PostgreSQL 16          |
| redis         | zakupai-redis          | zakupai-network    | 127.0.0.1:6379      | Redis cache            |
| chromadb      | zakupai-chromadb       | zakupai-network    | 8010                | Vector database        |

### Application Microservices

| Service         | Container Name           | Networks           | Exposed Ports       | Purpose                     |
|-----------------|--------------------------|--------------------|---------------------|-----------------------------|
| calc-service    | zakupai-calc-service     | zakupai-network    | 7001                | Calculation engine          |
| risk-engine     | zakupai-risk-engine      | zakupai-network    | 7002                | ML-based risk scoring       |
| doc-service     | zakupai-doc-service      | zakupai-network    | 7003                | Document processing         |
| billing-service | zakupai-billing-service  | zakupai-network    | 7004                | Billing & payments          |
| goszakup-api    | zakupai-goszakup-api     | zakupai-network    | 7005                | Government procurement API  |
| embedding-api   | zakupai-embedding-api    | zakupai-network    | 7010                | AI embeddings service       |
| etl-service     | zakupai-etl-service      | zakupai-network    | 7011                | ETL pipeline                |
| gateway         | zakupai-gateway          | zakupai-network    | 8080                | API gateway (nginx)         |
| web-ui          | zakupai-web-ui           | zakupai-network    | 8082                | Web frontend                |
| zakupai-bot     | zakupai-bot              | zakupai-network    | (internal)          | Telegram bot                |

### Workflow & Automation

| Service  | Container Name   | Networks           | Exposed Ports | Purpose                |
|----------|------------------|--------------------|---------------|------------------------|
| flowise  | zakupai-flowise  | zakupai-network    | 3000          | AI workflow builder    |
| n8n      | zakupai-n8n      | zakupai-network    | 5678          | Workflow automation    |

### Monitoring & Observability

| Service        | Container Name          | Networks                              | Exposed Ports   | Purpose                    |
|----------------|-------------------------|---------------------------------------|-----------------|----------------------------|
| vault          | zakupai-vault           | zakupai-network, monitoring-net       | (internal only) | Secrets management (Vault) |
| prometheus     | zakupai-prometheus      | zakupai-network, monitoring-net       | 9095            | Metrics collection         |
| grafana        | zakupai-grafana         | zakupai-network, monitoring-net       | 3030            | Visualization & dashboards |
| alertmanager   | zakupai-alertmanager    | zakupai-network, monitoring-net       | 9093            | Alert routing              |
| cadvisor       | zakupai-cadvisor        | zakupai-network                       | 8081            | Container metrics          |
| blackbox       | zakupai-blackbox        | zakupai-network                       | 9115            | Blackbox probing           |

### Support Services

| Service     | Container Name     | Networks           | Exposed Ports | Purpose              |
|-------------|--------------------|--------------------|---------------|----------------------|
| db-backup   | zakupai-db-backup  | zakupai-network    | (internal)    | Automated DB backups |
| libs        | (build only)       | (none)             | (none)        | Shared library layer |

---

## Network Topology Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            HOST (Linux)                                     │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                   zakupai_zakupai-network (bridge)                    │ │
│  │                                                                       │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │ │
│  │  │   Database   │  │    Redis     │  │   ChromaDB   │               │ │
│  │  │ PostgreSQL16 │  │              │  │              │               │ │
│  │  │ :5432 (127)  │  │ :6379 (127)  │  │    :8010     │               │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │ │
│  │                                                                       │ │
│  │  ┌──────────────────────────────────────────────────────────────┐   │ │
│  │  │              Application Microservices Layer                 │   │ │
│  │  │                                                              │   │ │
│  │  │  calc-service  risk-engine  doc-service  billing-service    │   │ │
│  │  │      :7001         :7002        :7003         :7004         │   │ │
│  │  │                                                              │   │ │
│  │  │  goszakup-api  embedding-api  etl-service  gateway          │   │ │
│  │  │      :7005         :7010         :7011       :8080          │   │ │
│  │  │                                                              │   │ │
│  │  │  web-ui        zakupai-bot                                  │   │ │
│  │  │    :8082         (internal)                                 │   │ │
│  │  └──────────────────────────────────────────────────────────────┘   │ │
│  │                                                                       │ │
│  │  ┌──────────────────────────────────────────────────────────────┐   │ │
│  │  │              Workflow & AI Automation Layer                  │   │ │
│  │  │                                                              │   │ │
│  │  │  flowise :3000         n8n :5678                            │   │ │
│  │  └──────────────────────────────────────────────────────────────┘   │ │
│  │                                                                       │ │
│  │  ┌──────────────────────────────────────────────────────────────┐   │ │
│  │  │              Monitoring & Observability (Bridge)             │   │ │
│  │  │                                                              │   │ │
│  │  │  cadvisor :8081   blackbox :9115                            │   │ │
│  │  └──────────────────────────────────────────────────────────────┘   │ │
│  │                                                                       │ │
│  │  ┌──────────────────────────────────────────────────────────────┐   │ │
│  │  │     Dual-Homed Monitoring Services (+ monitoring-net)        │   │ │
│  │  │                                                              │   │ │
│  │  │  vault (internal)  prometheus :9095  grafana :3030          │   │ │
│  │  │  alertmanager :9093                                          │   │ │
│  │  │                                                              │   │ │
│  │  │  ┌────────────────────────────────────────────────────────┐ │   │ │
│  │  │  │      ↓ Connected to monitoring-net (internal)          │ │   │ │
│  │  │  └────────────────────────────────────────────────────────┘ │   │ │
│  │  └──────────────────────────────────────────────────────────────┘   │ │
│  │                                                                       │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │              zakupai_monitoring-net (bridge, internal)                │ │
│  │                      ❌ No Internet Access                            │ │
│  │                                                                       │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │ │
│  │  │    Vault     │  │  Prometheus  │  │   Grafana    │               │ │
│  │  │   (sealed)   │  │   scraper    │  │  dashboard   │               │ │
│  │  │  (internal)  │  │              │  │              │               │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │ │
│  │                                                                       │ │
│  │  ┌──────────────┐                                                    │ │
│  │  │ Alertmanager │                                                    │ │
│  │  │  (internal)  │                                                    │ │
│  │  └──────────────┘                                                    │ │
│  │                                                                       │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Port Mapping Reference

### Public Ports (Accessible from Host)

| Port  | Service          | Protocol | Purpose                    | Access                |
|-------|------------------|----------|----------------------------|-----------------------|
| 3000  | flowise          | HTTP     | AI workflow UI             | localhost:3000        |
| 3030  | grafana          | HTTP     | Monitoring dashboards      | localhost:3030        |
| 5678  | n8n              | HTTP     | Workflow automation UI     | localhost:5678        |
| 7001  | calc-service     | HTTP     | Calculation API            | localhost:7001        |
| 7002  | risk-engine      | HTTP     | Risk scoring API           | localhost:7002        |
| 7003  | doc-service      | HTTP     | Document API               | localhost:7003        |
| 7004  | billing-service  | HTTP     | Billing API                | localhost:7004        |
| 7005  | goszakup-api     | HTTP     | Gov procurement API        | localhost:7005        |
| 7010  | embedding-api    | HTTP     | AI embeddings API          | localhost:7010        |
| 7011  | etl-service      | HTTP     | ETL pipeline API           | localhost:7011        |
| 8010  | chromadb         | HTTP     | Vector database API        | localhost:8010        |
| 8080  | gateway          | HTTP     | API gateway (main entry)   | localhost:8080        |
| 8081  | cadvisor         | HTTP     | Container metrics          | localhost:8081        |
| 8082  | web-ui           | HTTP     | Web frontend               | localhost:8082        |
| 9093  | alertmanager     | HTTP     | Alert routing UI           | localhost:9093        |
| 9095  | prometheus       | HTTP     | Metrics UI                 | localhost:9095        |
| 9115  | blackbox         | HTTP     | Blackbox exporter          | localhost:9115        |

### Localhost-Only Ports (127.0.0.1 binding)

| Port | Service  | Protocol | Purpose          | Security Note                 |
|------|----------|----------|------------------|-------------------------------|
| 5432 | db       | TCP      | PostgreSQL       | Not exposed to Docker network |
| 6379 | redis    | TCP      | Redis cache      | Not exposed to Docker network |

### Internal-Only Services (No Public Ports)

| Service       | Access Method                   | Purpose                     |
|---------------|---------------------------------|-----------------------------|
| vault         | zakupai-network (http://vault)  | Secrets backend             |
| zakupai-bot   | Internal polling                | Telegram bot                |
| db-backup     | Cron job                        | Automated backups           |

---

## Network Security Summary

### Security Posture

| Feature                           | Status | Notes                                       |
|-----------------------------------|--------|---------------------------------------------|
| PostgreSQL public binding         | ✅ Secure | Bound to 127.0.0.1 only                   |
| Redis public binding              | ✅ Secure | Bound to 127.0.0.1 only                   |
| Vault public ports                | ✅ Secure | No public ports, network-only access      |
| Monitoring network isolation      | ✅ Secure | `internal: true` (no internet egress)     |
| Removed unused networks           | ✅ Secure | ai-network, vault-net eliminated          |
| Dual-homed monitoring services    | ✅ Secure | Limited blast radius                      |

### Firewall Rules (Host-Level)

The following host-level firewall rules should be applied:

```bash
# Allow localhost access to Postgres/Redis
iptables -A INPUT -i lo -p tcp --dport 5432 -j ACCEPT
iptables -A INPUT -i lo -p tcp --dport 6379 -j ACCEPT

# Block external access to Postgres/Redis
iptables -A INPUT -p tcp --dport 5432 -j DROP
iptables -A INPUT -p tcp --dport 6379 -j DROP

# Allow Docker bridge network
iptables -A FORWARD -i br+ -j ACCEPT
iptables -A FORWARD -o br+ -j ACCEPT
```

---

## Network Communication Patterns

### Application Data Flow

```
User → gateway:8080 → microservices (calc/risk/doc/billing/etl)
                    ↓
                    db:5432 (internal), redis:6379 (internal)
                    ↓
                    vault (secrets) → monitoring-net
```

### Monitoring Data Flow

```
Prometheus (zakupai-network) → scrape metrics from all services
                             ↓
                    monitoring-net (isolated)
                             ↓
                    Grafana ← queries Prometheus
                             ↓
                    Alertmanager ← receives alerts
```

### AI/Workflow Data Flow

```
flowise/n8n → embedding-api → ChromaDB → risk-engine/doc-service
            ↓
            External Ollama (host.docker.internal:11434)
```

---

## Deployment Instructions

### Initial Deployment

```bash
# Stop any running containers
docker compose down

# Remove old networks
docker network rm zakupai_ai-network zakupai_vault-net 2>/dev/null || true

# Start with new topology
docker compose up -d

# Verify network creation
docker network ls | grep zakupai
docker network inspect zakupai_zakupai-network
docker network inspect zakupai_monitoring-net
```

### With Monitoring Stack

```bash
# Start with monitoring overlay
docker compose -f docker-compose.yml \
               -f docker-compose.override.monitoring.yml \
               up -d
```

### With Stage 9 (Production Vault)

```bash
# Start with production Vault configuration
docker compose -f docker-compose.yml \
               -f docker-compose.override.stage9.vault-prod.yml \
               up -d
```

---

## Verification Checklist

After deployment, verify the following:

- [ ] Two networks exist: `zakupai_zakupai-network` and `zakupai_monitoring-net`
- [ ] No `ai-network` or `vault-net` networks exist
- [ ] All application services are on `zakupai-network`
- [ ] Vault, Prometheus, Grafana, Alertmanager are dual-homed
- [ ] PostgreSQL accessible on `127.0.0.1:5432` only
- [ ] Redis accessible on `127.0.0.1:6379` only
- [ ] Vault has no public ports
- [ ] Grafana accessible on `http://localhost:3030`
- [ ] API gateway accessible on `http://localhost:8080`
- [ ] All services can resolve each other by container name

### Verification Commands

```bash
# Check network membership
docker ps --format "table {{.Names}}\t{{.Networks}}"

# Verify network isolation
docker network inspect zakupai_monitoring-net | jq '.[0].Internal'
# Should return: true

# Test service connectivity
docker exec zakupai-calc-service curl -s http://db:5432 -o /dev/null && echo "DB reachable"
docker exec zakupai-prometheus curl -s http://vault:8200/v1/sys/health -o /dev/null && echo "Vault reachable"

# Verify Vault is not publicly accessible
curl -s http://localhost:8200 -o /dev/null && echo "❌ Vault exposed!" || echo "✅ Vault secured"
```

---

## Troubleshooting

### Issue: Services can't reach each other

**Cause:** Old networks still attached to containers

**Solution:**
```bash
docker compose down
docker network prune -f
docker compose up -d
```

### Issue: Vault not reachable from Prometheus

**Cause:** Vault not connected to monitoring-net

**Solution:**
```bash
docker inspect zakupai-vault | jq '.[0].NetworkSettings.Networks'
# Should show both zakupai-network and monitoring-net

# If missing, recreate:
docker compose -f docker-compose.yml -f docker-compose.override.monitoring.yml up -d vault
```

### Issue: PostgreSQL connection refused from services

**Cause:** Services trying to use old network names or wrong host binding

**Solution:**
```bash
# Ensure services use "db" as hostname, not "localhost" or IP
# Check DATABASE_URL in service env:
docker exec zakupai-calc-service env | grep DATABASE_URL
# Should be: postgresql://user:pass@db:5432/zakupai
```

---

## Migration from Legacy Networks

### Pre-Migration Checklist

- [ ] Backup all data volumes
- [ ] Export Grafana dashboards
- [ ] Document current service URLs
- [ ] Notify users of maintenance window

### Migration Steps

1. **Stop all services**
   ```bash
   docker compose down
   ```

2. **Apply network cleanup changes**
   ```bash
   git pull origin feature/stage7-phase3-vault-hvac
   ```

3. **Remove old networks**
   ```bash
   docker network rm zakupai_ai-network zakupai_vault-net 2>/dev/null || true
   ```

4. **Start with new topology**
   ```bash
   docker compose up -d
   ```

5. **Verify connectivity**
   ```bash
   docker ps --format "table {{.Names}}\t{{.Networks}}"
   docker exec zakupai-gateway curl -s http://calc-service:8000/health
   ```

6. **Check monitoring stack**
   ```bash
   curl -s http://localhost:9095/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
   ```

### Rollback Procedure

If issues occur:

```bash
# Stop services
docker compose down

# Revert code changes
git apply -R network_cleanup.patch

# Restart with old topology
docker compose up -d
```

---

## Performance Considerations

### Network Throughput

- **zakupai-network:** Standard Docker bridge (≈10 Gbps on modern hardware)
- **monitoring-net:** Internal-only, same performance as bridge
- **Host network mode:** Not used (reduces security)

### Latency

- Inter-container communication: <1ms (same host)
- External API calls: Depends on internet connection
- Database queries: <5ms (PostgreSQL on same network)

### Scaling

To scale horizontally:

```bash
# Scale microservices
docker compose up -d --scale calc-service=3 --scale risk-engine=2

# Load balance with nginx (gateway)
# Edit gateway/nginx.conf to add upstream backends
```

---

## Related Documentation

- [Network Cleanup Summary](./NETWORK_CLEANUP_SUMMARY.md) — Changes made during consolidation
- [Vault Operations Guide](./VAULT_OPERATIONS.md) — Vault setup and network access
- [Vault Admin Guide](./VAULT_ADMIN_GUIDE.md) — Administrative tasks
- [Vault Migration Guide](./VAULT_MIGRATION_STAGE7_TO_STAGE9.md) — Upgrading Vault storage

---

## Appendix: Docker Network Commands

### Inspect Network

```bash
docker network inspect zakupai_zakupai-network
docker network inspect zakupai_monitoring-net
```

### List Containers on Network

```bash
docker network inspect zakupai_zakupai-network | jq '.[0].Containers | keys'
```

### Connect Container to Network (Manual)

```bash
docker network connect zakupai_monitoring-net zakupai-vault
```

### Disconnect Container from Network

```bash
docker network disconnect zakupai_ai-network zakupai-risk-engine
```

### Clean Up Unused Networks

```bash
docker network prune -f
```

---

## Changelog

### v2.0 (2025-11-09) — Network Consolidation
- ✅ Removed `ai-network` (consolidated into `zakupai-network`)
- ✅ Removed `vault-net` (Vault now dual-homed)
- ✅ Standardized on 2 networks: `zakupai-network` + `monitoring-net`
- ✅ Eliminated deprecated `version:` fields from compose files
- ✅ Migrated 6 services from `ai-network` to `zakupai-network`

### v1.0 (2025-10-15) — Initial Architecture
- Created `zakupai-network` for main services
- Created `ai-network` for AI/ML services
- Created `vault-net` for Vault isolation

---

**Generated:** 2025-11-09
**Status:** ✅ Production Ready
**Commit:** feature/stage7-phase3-vault-hvac
