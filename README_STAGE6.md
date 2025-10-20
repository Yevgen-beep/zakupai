# Stage6 Observability & Security Runbook

ZakupAI Stage6 bundles application services with a full monitoring/security toolchain:

- **Prometheus** (v2.54.1) with unified config, SLO recording rules, Vault & nginx scrape jobs.
- **Grafana** (v11) provisioned from `monitoring/grafana/provisioning` into folders `overview`, `apis`, `security`.
- **Vault** (v1.15.4) running with TLS (`monitoring/vault/tls`), Shamir unseal (5/3), KV v2 secrets and telemetry.
- **Loki + Promtail**, **nginx-prometheus-exporter**, **node-exporter**, **cAdvisor**, **Alertmanager bot**.

All services communicate inside the Docker network `zakupai_zakupai-network` (`172.18.0.0/16`). Host port bindings are resolved dynamically by Compose commands below; avoid hard-coding port numbers.

______________________________________________________________________

## 1. Bring-up Checklist

Run all commands from the repository root (`/home/mint/projects/claude_sandbox/zakupai`).

1. **Render effective Compose**

   ```bash
   docker compose --profile stage6 \
     -f docker-compose.yml \
     -f docker-compose.override.stage6.yml \
     -f docker-compose.override.stage6.monitoring.yml \
     -f monitoring/vault/docker-compose.override.stage6.vault.yml \
     config >/tmp/stage6-config.yaml
   ```

1. **Lint Prometheus configuration**

   ```bash
   docker run --rm \
     -v $(pwd)/monitoring/prometheus:/etc/prometheus \
     --entrypoint promtool prom/prometheus:v2.54.1 \
     check config /etc/prometheus/prometheus.yml

   docker run --rm \
     -v $(pwd)/monitoring/prometheus:/etc/prometheus \
     --entrypoint promtool prom/prometheus:v2.54.1 \
     check rules /etc/prometheus/rules.yml
   ```

1. **Build & start monitoring core**

   ```bash
   docker compose --profile stage6 \
     -f docker-compose.yml \
     -f docker-compose.override.stage6.yml \
     -f docker-compose.override.stage6.monitoring.yml \
     -f monitoring/vault/docker-compose.override.stage6.vault.yml \
     up -d --build grafana prometheus vault loki promtail nginx-exporter
   ```

1. **Initialise and unseal Vault**

   ```bash
   ./scripts/vault-init.sh        # writes .secrets/vault-keys.txt
   ./scripts/vault-unseal.sh      # uses first 3 keys to unseal
   ```

   **Note:** The Vault container uses hostname `vault` for DNS resolution within the Docker network. After restart, Vault will be sealed; run `./scripts/vault-unseal.sh` again.

1. **Generate Prometheus metrics token**

   ```bash
   ./scripts/vault-rotate-token.sh
   ```

   This script:

   - Creates a `zakupai-metrics` policy with read access to `sys/metrics`
   - Generates a token with 720h TTL
   - Saves the token to `.secrets/vault-metrics-token.txt` and `monitoring/prometheus/vault-metrics.token`
   - Restarts Prometheus to pick up the new token

   **Token rotation:** Run this script periodically (e.g., every 30 days) to rotate the Prometheus metrics token before expiration.

1. **Seed application secrets into KV v2 (optional)**

   ```bash
   source .env
   ROOT_TOKEN=$(grep "Initial Root Token" .secrets/vault-keys.txt | awk '{print $4}')
   COMPOSE_CMD=(docker compose --profile stage6 \
     -f docker-compose.yml \
     -f docker-compose.override.stage6.yml \
     -f docker-compose.override.stage6.monitoring.yml \
     -f monitoring/vault/docker-compose.override.stage6.vault.yml)
   VAULT_ENV="env VAULT_ADDR=https://127.0.0.1:8200 VAULT_CACERT=/vault/tls/ca.pem VAULT_TOKEN=$ROOT_TOKEN"

   "${COMPOSE_CMD[@]}" exec -T vault \
     sh -c "$VAULT_ENV vault kv put secret/zakupai/db url=$DATABASE_URL user=$POSTGRES_USER pass=$POSTGRES_PASSWORD db=$POSTGRES_DB"

   "${COMPOSE_CMD[@]}" exec -T vault \
     sh -c "$VAULT_ENV vault kv put secret/zakupai/api goszakup_token=$GOSZAKUP_TOKEN"

   "${COMPOSE_CMD[@]}" exec -T vault \
     sh -c "$VAULT_ENV vault kv put secret/zakupai/telegram token=$TELEGRAM_BOT_TOKEN admin_id=$TELEGRAM_ADMIN_ID"
   ```

1. **Recycle services that consume Vault**

   ```bash
   docker compose --profile stage6 \
     -f docker-compose.yml \
     -f docker-compose.override.stage6.yml \
     up -d --build calc-service etl-service risk-engine embedding-api doc-service goszakup-api
   ```

1. **Run the consolidated smoke test**

   ```bash
   ./stage6-monitoring-test.sh
   ```

   The script performs comprehensive validation:

   - Generates synthetic traffic to warm up SLO metrics
   - Verifies Prometheus targets (all services, Vault, nginx-exporter)
   - Checks SLO recording rules: `api_error_ratio`, `api_error_ratio_by_service`, `api_p95_latency`
   - Tests Grafana datasources (Prometheus + Loki) and dashboards
   - Validates Vault health (auto-unseal if sealed) and metrics endpoint
   - Confirms Loki API, log ingestion, and logcli queries
   - Prints ✅ success message with UI endpoints

   **Note:** If Vault is sealed when the test runs, it will automatically call `./scripts/vault-unseal.sh` and retry.

1. **Create a Raft snapshot**

   ```bash
   ./scripts/vault-snapshot.sh
   ```

   The snapshot is stored inside the container at `/vault/data/snapshot-YYYY-MM-DD.snap` (visible via `docker compose ... exec vault ls /vault/data`).

______________________________________________________________________

## 2. Quick Verification Commands

| Component            | Command                                                                                                                                |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Prometheus SLO rules | \`curl -s http://localhost:$(docker compose ... port prometheus 9090                                                                   |
| Grafana datasources  | \`curl -s -u admin:admin http://localhost:$(docker compose ... port grafana 3000                                                       |
| Grafana dashboards   | \`curl -s -u admin:admin http://localhost:$(docker compose ... port grafana 3000                                                       |
| Vault health         | \`curl -sk https://localhost:$(docker compose ... port vault 8200                                                                      |
| Vault metrics        | \`curl -sk -H "X-Vault-Token: $(cat monitoring/prometheus/vault-metrics.token)" https://localhost:$(docker compose ... port vault 8200 |
| Loki labels          | \`curl -s http://localhost:$(docker compose ... port loki 3100                                                                         |
| Loki calc logs       | \`curl -sG http://localhost:$(docker compose ... port loki 3100                                                                        |

Replace `docker compose ...` with the full profile/overrides snippet used earlier, or export helpers in your shell profile.

______________________________________________________________________

## 3. Grafana Provisioning Layout

```
monitoring/grafana/provisioning
├── datasources
│   └── datasources.yml        # Prometheus (default), Loki
└── dashboards
    ├── dashboards.yml         # Providers per folder (overview/apis/security)
    ├── overview/zakupai-overview.json
    ├── apis/{latency,http_5xx,compliance,nginx}.json
    └── security/{vault,mtls,audit}.json
```

Dashboards reference the SLO recording rules and key exporter metrics. Grafana is started with a bind mount (`./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro`).

______________________________________________________________________

## 4. Prometheus Details

- Single configuration file: `monitoring/prometheus/prometheus.yml` (the legacy `monitoring/prometheus.yml` has been removed).
- Rule group `slo` in `monitoring/prometheus/rules.yml` exposes:
  - `api_error_ratio` — global 5xx ratio (fallbacks to 0 when idle).
  - `api_error_ratio_by_service` — per service ratio, aligned via `up` targets.
  - `api_p95_latency` — per service P95 latency using `http_request_duration_seconds_bucket`.
- Additional scrape jobs:
  - `nginx` → `nginx-exporter:9113` with `service=gateway` relabel.
  - `vault` → `https://vault:8200/v1/sys/metrics?format=prometheus` using `/etc/prometheus/vault-metrics.token` and `insecure_skip_verify`. Telemetry retention = 24h.

______________________________________________________________________

## 5. Vault Operations

- TLS assets live in `monitoring/vault/tls` (ignored by git). Self-signed certs were generated via the `openssl` command in the Stage6 requirements.
- Config `monitoring/vault/config/vault.json` (single-node Raft storage):
  ```json
  {
    "listener": {"tcp": {"address": "0.0.0.0:8200", "tls_cert_file": "/vault/tls/server.crt", "tls_key_file": "/vault/tls/server.key"}},
    "storage": {"raft": {"path": "/vault/data", "node_id": "zakupai-vault"}},
    "telemetry": {"prometheus_retention_time": "24h", "disable_hostname": true, "unauthenticated_metrics_access": true}
  }
  ```
- Scripts in `scripts/`:
  - `vault-init.sh` → creates `.secrets/vault-keys.txt` (5 shares, threshold 3).
  - `vault-unseal.sh` → replays the first three keys.
  - `vault-snapshot.sh` → saves `/vault/data/snapshot-YYYY-MM-DD.snap` inside the container (Raft snapshot).
- **Token rotation example** — add cron entry (runs daily at 01:00) to mint a fresh metrics token and restart Prometheus:
  ```cron
  0 1 * * * cd /home/mint/projects/claude_sandbox/zakupai && \
    ./scripts/vault-unseal.sh && \
    ROOT_TOKEN=$(awk '{print $4}' .secrets/vault-keys.txt | head -n1) && \
    docker compose --profile stage6 -f docker-compose.yml \
      -f docker-compose.override.stage6.yml \
      -f docker-compose.override.stage6.monitoring.yml \
      -f monitoring/vault/docker-compose.override.stage6.vault.yml \
      exec -T vault env VAULT_ADDR=https://127.0.0.1:8200 VAULT_CACERT=/vault/tls/ca.pem VAULT_TOKEN=$ROOT_TOKEN \
      vault token create -policy=zakupai-metrics -ttl=720h -format=json \
      | jq -r '.auth.client_token' \
      | tee monitoring/prometheus/vault-metrics.token \
      | tee .secrets/vault-metrics-token.txt >/dev/null && \
    chmod 600 monitoring/prometheus/vault-metrics.token .secrets/vault-metrics-token.txt && \
    docker compose --profile stage6 -f docker-compose.yml \
      -f docker-compose.override.stage6.yml \
      -f docker-compose.override.stage6.monitoring.yml \
      -f monitoring/vault/docker-compose.override.stage6.vault.yml restart prometheus
  ```

______________________________________________________________________

## 6. Troubleshooting Cheat-sheet

| Symptom                                      | Checks & Fixes                                                                                                                                                                                                                         |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Grafana loads with default UI, no dashboards | Ensure `docker-compose.override.stage6.monitoring.yml` mounts `./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro`. Restart Grafana (`docker compose ... restart grafana`). Review logs with \`docker logs zakupai-grafana |
| `slo` group missing in Prometheus            | Verify `monitoring/prometheus/rules.yml` and rerun `promtool check rules`. Restart Prometheus (`docker compose ... restart prometheus`).                                                                                               |
| Vault scrape `403 Forbidden`                 | Confirm `monitoring/prometheus/vault-metrics.token` exists and token policy `zakupai-metrics` grants `sys/metrics` read. Restart Prometheus after updating the token.                                                                  |
| `vault` target `down` in Prometheus          | Check container health: \`docker logs zakupai-vault                                                                                                                                                                                    |
| Grafana API `401`/`connection refused`       | Re-evaluate host port via `docker compose ... port grafana 3000`. Credentials default to `admin:admin`.                                                                                                                                |
| Loki queries empty                           | Confirm promtail is running (\`docker ps                                                                                                                                                                                               |
| nginx stub status `403`                      | The gateway config allows `127.0.0.1` and `172.18.0.0/16`. Validate the exporter is hitting `http://gateway:80/stub_status` and that your curl originates from permitted subnet.                                                       |
| Vault TLS errors in services                 | Service containers mount `monitoring/vault/tls/ca.pem` and `monitoring/vault/creds/service.token`. Ensure the files exist and have `0644/0600` permissions respectively, then rebuild affected services.                               |

______________________________________________________________________

## 7. Next Steps

- Hook Alertmanager bot by filling `TELEGRAM_BOT_TOKEN`/`TELEGRAM_ADMIN_ID` in `.env` and restarting `alertmanager-bot`.
- Add synthetic traffic or load tests to produce non-zero SLO metrics.
- Automate snapshots using `scripts/vault-snapshot.sh` (cron/CI).

Stage6 monitoring & security are now reproducible end-to-end with a single smoke test gate.

______________________________________________________________________

## 8. UI Endpoints

After successful deployment, the following UIs are available:

| Service        | URL                              | Credentials                               | Description                                                 |
| -------------- | -------------------------------- | ----------------------------------------- | ----------------------------------------------------------- |
| **Grafana**    | http://localhost:3030            | admin / admin                             | Dashboards for monitoring (overview, APIs, security)        |
| **Prometheus** | http://localhost:9095            | -                                         | Metrics, targets, alerts, rules                             |
| **Vault**      | https://localhost:8200/ui/vault/ | Root token from `.secrets/vault-keys.txt` | Secrets management, policies, audit                         |
| **Loki**       | http://localhost:3100            | -                                         | Log aggregation API (use `/loki/api/v1/labels`, `/metrics`) |

**Quick links:**

- Grafana Platform Overview: http://localhost:3030/d/zakupai-overview
- Prometheus Targets: http://localhost:9095/targets
- Vault Status: https://localhost:8200/v1/sys/health

**Note:** Port numbers above are defaults. If you encounter conflicts, Docker Compose will assign different ports. Use `docker compose port <service> <internal-port>` to discover the actual host port.
