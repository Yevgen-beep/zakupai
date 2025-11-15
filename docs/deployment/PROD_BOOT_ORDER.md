# ZakupAI Production Boot Order

## Overview
- Vault 1.17 with B2 storage, TLS, and manual unseal
- Hybrid gateway: Nginx front end + FastAPI backend bridge
- Segmented networks: `zakupai-network`, `monitoring-net`, `ai-network`

## Prerequisites
1. Docker Engine + Docker Compose v2 installed on the host.
2. External Docker networks must exist:

```bash
docker network create zakupai_zakupai-network || true
docker network create zakupai_monitoring-net || true
docker network create zakupai_ai-network || true
```

## Boot Sequence
1. **Core dependencies** – bring up DB and Vault only using `docker-compose.yml`, `compose/networks.yml`, and `compose/vault.prod.yml` to verify storage + TLS volume mounts.
2. **Manual unseal** – run `./scripts/prod/unseal-vault.sh` (or execute `vault operator unseal` manually inside the `zakupai-vault` container).
3. **Initial Vault setup** – first deploy only: execute the existing `./scripts/stage9-phase1.sh` to configure auth methods, policies, and secrets.
4. **Core services** – deploy calc, risk, etl, billing, doc, embedding, web-ui, and bot services via the standard stage9 compose stack.
5. **Gateway** – attach the hybrid gateway using `compose/gateway.prod.yml` so all north-south traffic flows through Nginx.
6. **Monitoring (optional)** – launch Prometheus/Grafana/Alertmanager with `compose/monitoring.prod.yml` when observability is required.
7. **Workflows (optional)** – launch n8n/Flowise/Scheduler using `compose/workflows.prod.yml`.
8. **Full stack** – run `./scripts/prod/deploy.sh` whenever you need to roll out or restart everything at once (creates a compose backup before applying changes).

## Testing After Deployment
```bash
# Database
docker exec zakupai-db pg_isready -U zakupai

# Vault
docker exec -e VAULT_SKIP_VERIFY=true zakupai-vault vault status

# Gateway
curl http://localhost:8080/health
curl -k http://localhost:8080/vault/health

# Backend services (via gateway)
curl http://localhost:8080/calc/health
curl http://localhost:8080/risk/health

# Monitoring (Grafana)
curl http://localhost:3000/api/health  # if applicable

# Workflows
curl http://localhost:5678/healthz     # n8n
curl http://localhost:3000/api/v1/ping # Flowise (if mapped)
```

## Troubleshooting

### Vault won't unseal
```bash
docker logs zakupai-vault --tail=50
ls -la monitoring/vault/creds/unseal_key_*.txt
./scripts/prod/unseal-vault.sh
```

### Gateway not responding
```bash
docker logs zakupai-gateway
docker logs zakupai-gateway-backend
docker exec zakupai-gateway-backend curl http://localhost:8000/health || true
```

### Services can't reach Vault
```bash
docker exec calc-service curl -k https://vault:8200/v1/sys/health || true
```

### Network issues
```bash
docker network ls | grep zakupai
docker ps --format '{{.Names}} {{.Networks}}' | grep zakupai
```

## Simple restart after server reboot
```bash
./scripts/prod/deploy.sh
docker exec -e VAULT_SKIP_VERIFY=true zakupai-vault vault status
./scripts/prod/unseal-vault.sh   # if sealed
```

## Rollback
```bash
./scripts/prod/rollback.sh
```
