# ZakupAI Stage6 Monitoring Diagnostics (2025-10-15)

All checks were run with read-only Docker `exec`/`logs` commands; no containers were restarted.

## 🕸 Network Map

| Container | IPv4 | Aliases |
| --- | --- | --- |
| zakupai-alertmanager | 172.19.0.7 | – |
| zakupai-grafana | 172.19.0.19 | – |
| zakupai-blackbox | 172.19.0.5 | – |
| zakupai-doc-service | 172.19.0.16 | – |
| zakupai-n8n | 172.19.0.9 | – |
| zakupai-flowise | 172.19.0.22 | – |
| zakupai-web-ui | 172.19.0.11 | – |
| zakupai-calc-service | 172.19.0.13 | – |
| zakupai-billing-service | 172.19.0.15 | – |
| zakupai-promtail-stage6 | 172.19.0.6 | – |
| zakupai-goszakup-api | 172.19.0.17 | – |
| zakupai-risk-engine | 172.19.0.23 | – |
| zakupai-chromadb | 172.19.0.4 | – |
| zakupai-cadvisor | 172.19.0.8 | – |
| zakupai-gateway | 172.19.0.12 | – |
| zakupai-etl-service | 172.19.0.10 | – |
| zakupai-db | 172.19.0.21 | – |
| zakupai-node-exporter-stage6 | 172.19.0.2 | – |
| zakupai-alertmanager-bot-stage6 | 172.19.0.14 | – |
| zakupai-prometheus | 172.19.0.18 | – |
| zakupai-embedding-api | 172.19.0.24 | – |
| zakupai-nginx-exporter-stage6 | 172.19.0.3 | – |

> `zakupai-loki` is not listed because the container is stopped (`Exited (0) 8 days ago)` and is no longer attached to the bridge network.

## 📊 Service Health Summary

| Service | Status | Endpoint(s) | Response | Notes |
| --- | --- | --- | --- | --- |
| Prometheus (`zakupai-prometheus`) | 🟢 Healthy | `http://localhost:9090/-/healthy` (in-container) | `200` – `Prometheus Server is Healthy.` | `docker exec zakupai-prometheus wget -qO- localhost:9090/-/healthy` succeeded. Grafana can reach it via DNS. |
| Loki (`zakupai-loki`) | 🔴 Unreachable | `http://localhost:3100/ready` | N/A – container not running | `docker ps -a` shows `zakupai-loki  Exited (0) 8 days ago`; readiness probe cannot be executed. |
| Promtail (`zakupai-promtail-stage6`) | 🔴 Failing to ship logs | `http://loki:3100/loki/api/v1/push` | DNS lookup failure | `getent hosts {loki, zakupai-loki}` returned nothing; logs show repeated `dial tcp: lookup loki on 127.0.0.11:53: server misbehaving`. |
| Grafana (`zakupai-grafana`) | 🟢 Healthy | `http://localhost:3000/api/health` | `200` – `{"database":"ok"}` | `curl` succeeded; `docker exec zakupai-grafana curl -s http://zakupai-prometheus:9090/-/healthy` returned `200`, confirming Prometheus DNS connectivity. |
| Alertmanager (`zakupai-alertmanager`) | 🟡 Degraded | `http://localhost:9093/-/healthy` | `200` – `OK` | Local health is fine, but `wget http://zakupai-prometheus:9090/-/ready` → `bad address`; direct IP (`http://172.19.0.18:9090/-/ready`) returns `Prometheus Server is Ready.` Old logs show webhook retries to `http://localhost:5001/webhook`. |

- Promtail logs (`docker logs --tail=50 zakupai-promtail-stage6`) contain persistent DNS errors targeting `loki:3100`.
- Loki logs (`docker logs --tail=50 zakupai-loki`) end with a graceful shutdown on 2025-10-07, explaining the missing container.
- Grafana logs are routine (cleanup + update checks), no errors in last 50 lines.
- Prometheus logs show normal TSDB rotation; no scrape or alert errors observed.
- Alertmanager logs show repeated webhook failures to `localhost:5001`; verify the bot endpoint if alerts need to be delivered.

## promtail-config.yaml

```yaml
clients:
  - url: http://loki:3100/loki/api/v1/push
```

Promtail currently targets the hostname `loki`, but neither `loki` nor `zakupai-loki` resolve inside the container, causing ingestion failures.

## docker-compose.override.stage6.monitoring.yml

```yaml
services:
  zakupai-promtail:
    networks:
      zakupai_zakupai-network:
        aliases:
          - loki
```

👉 Minimal fix: either restore the `zakupai-loki` container (preferred) or add an alias (`loki`) for the Loki service so Promtail’s client URL resolves. Ensure Alertmanager also has a resolvable DNS name (or service alias) for Prometheus to avoid the current `bad address` errors.
